from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from time import perf_counter
from typing import Any
import uuid

from joule.config import JouleSettings
from joule.evaluators.correctness import CorrectnessEngine
from joule.evaluators.oracle import PerformanceOracle
from joule.models import (
    AggregateMetrics,
    CandidateEvaluation,
    Fidelity,
    FrontierState,
    MeasurementReport,
    MetricSample,
    SearchContext,
    SearchPhase,
    TargetSpec,
    TransformationResult,
    WorkloadBundle,
)
from joule.orchestrator.explainer import synthesize_explanation
from joule.orchestrator.internal.mfbo_flow import (
    OptimizationState,
    build_candidate_metadata,
    build_correctness_rejection_evaluation,
    build_parent_context,
    dependency_policy_metadata,
    generated_candidate_detail,
)
from joule.orchestrator.pareto import ParetoFront, ParetoPoint
from joule.surrogate.gp import GaussianProcessSurrogate
from joule.transformers.registry import OperatorRegistry
from joule.utils.analysis import candidate_source_hash
from joule.utils.db import JouleDB
from joule.utils.metrics import improvement_ratio, scalar_score
from joule.utils.terminal import TerminalReporter


@dataclass(slots=True)
class _ParentSnapshot:
    candidate_id: str
    source: str
    operator_name: str
    generation_depth: int
    rejection_history: list[str] = field(default_factory=list)


class OptimizationOrchestrator:
    def __init__(
        self,
        settings: JouleSettings,
        db: JouleDB,
        oracle: PerformanceOracle,
        correctness: CorrectnessEngine,
        registry: OperatorRegistry,
        surrogate: GaussianProcessSurrogate,
        reporter: TerminalReporter | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.oracle = oracle
        self.correctness = correctness
        self.registry = registry
        self.surrogate = surrogate
        self.reporter = reporter

    @classmethod
    def create(
        cls,
        settings: JouleSettings,
        db: JouleDB,
        oracle: PerformanceOracle,
        reporter: TerminalReporter | None = None,
    ) -> "OptimizationOrchestrator":
        correctness = CorrectnessEngine()
        registry = OperatorRegistry(llm_model=settings.llm_model, include_llm=True)
        registry.load_stats(db.get_operator_stats())
        surrogate = GaussianProcessSurrogate(
            acquisition=settings.surrogate_acquisition,
            gp_noise=settings.surrogate_gp_noise,
            gp_length_scale=settings.surrogate_gp_length_scale,
            gp_nu=settings.surrogate_gp_nu,
            gp_ucb_beta=settings.surrogate_gp_ucb_beta,
        )
        return cls(
            settings=settings,
            db=db,
            oracle=oracle,
            correctness=correctness,
            registry=registry,
            surrogate=surrogate,
            reporter=reporter,
        )

    def baseline(
        self, run_id: str, target: TargetSpec, bundle: WorkloadBundle, repetitions: int | None = None, use_cache: bool = True
    ) -> MeasurementReport:
        if self.reporter:
            self.reporter.info("baseline", f"Measuring {target.qualname} with {len(bundle.workloads)} workload(s)")
        report = self.oracle.measure_bundle(
            run_id=run_id,
            target=target,
            bundle=bundle,
            fidelity=Fidelity.F3,
            repetitions=repetitions,
            use_cache=use_cache,
        )
        self.db.record_measurement(report, created_at=datetime.now(UTC).isoformat())
        return report

    def optimize(
        self,
        run_id: str,
        target: TargetSpec,
        bundle: WorkloadBundle,
        *,
        budget: int | None = None,
        analysis: bool = False,
        resume: str | None = None,
        use_cache: bool = True,
        checkpoint_path: Path | None = None,
        fresh_surrogate: bool = False,
    ) -> tuple:
        if resume and resume != run_id:
            raise ValueError("Run IDs must match when resuming. Use `joule resume --run-id <id>` to continue an existing run.")

        target_key = self._target_key(target)
        self._warm_start_surrogate(target_key=target_key, fresh_start=fresh_surrogate)

        restored = self._restore_checkpoint(run_id=resume or run_id)
        if restored:
            baseline = restored["baseline"]
            pareto = restored["pareto"]
            parent_snapshots = restored["parent_snapshots"]
            seen_sources = restored["seen_sources"]
            state = restored["state"]
            escape_used = restored["escape_used"]
            if budget is not None:
                state.total_budget = max(state.measured, budget)
            accepted_evaluations = self._load_accepted_evaluations(run_id)
            if self.reporter:
                self.reporter.info(
                    "resume",
                    f"Resumed run at candidate {state.measured}/{state.total_budget}",
                )
        else:
            baseline = self.baseline(run_id, target, bundle, use_cache=use_cache)
            pareto = ParetoFront(
                weights=(
                    self.settings.pareto_weights.energy,
                    self.settings.pareto_weights.latency,
                    self.settings.pareto_weights.memory,
                )
            )
            pareto.add(
                ParetoPoint(
                    candidate_id="baseline",
                    metrics=baseline.aggregate,
                    parent_id=None,
                    generation_depth=0,
                    operator_name="baseline",
                    active=True,
                )
            )
            accepted_evaluations = {}
            parent_snapshots = {
                "baseline": _ParentSnapshot(
                    candidate_id="baseline",
                    source=target.source,
                    operator_name="baseline",
                    generation_depth=0,
                )
            }
            seen_sources = {candidate_source_hash(target.source): "baseline"}
            state = OptimizationState(
                total_budget=budget or self.settings.optimization_budget,
                max_parent_expansions=max(1, self.settings.search_branching_factor)
                * max(1, len(self.registry.operators)),
            )
            escape_used = False

        baseline_score = scalar_score(baseline.aggregate)
        self._record_surrogate_observation(
            run_id=run_id,
            target_key=target_key,
            source=target.source,
            score=baseline_score,
        )
        accepted_candidate_ids = {candidate_id for candidate_id in accepted_evaluations}
        if self.reporter:
            self.reporter.info("progress", f"Optimization budget: {state.total_budget} measured candidate(s)")
        while state.measured < state.total_budget:
            phase = self._phase_for_index(state.measured, state.total_budget)
            prefer_deeper_parent = phase is not SearchPhase.EXPLORATION or state.no_frontier_gain > 0
            parent_id = pareto.sample_active_parent(
                max_generation=self.settings.search_max_generations,
                prefer_deeper=prefer_deeper_parent,
            )
            if parent_id is None:
                if self.reporter:
                    self.reporter.info("progress", "Stopping early: no active frontier candidates left")
                self._record_event(
                    run_id,
                    event_type="converged",
                    stage="search",
                    detail={"reason": "no_active_frontier"},
                )
                break
            parent = parent_snapshots[parent_id]
            parent_context = build_parent_context(parent, phase=phase, analysis=analysis)
            candidate_target = self._target_with_source(target, parent.source, parent_id=parent_id)
            operator = None
            if state.no_frontier_gain >= self.settings.search_convergence_patience:
                select_escape = getattr(self.registry, "select_escape_operator_for_candidate", None)
                escape_operator = (
                    select_escape(
                        target=candidate_target,
                        context=parent_context,
                        phase=phase,
                        parent_generation=parent.generation_depth,
                    )
                    if callable(select_escape)
                    else None
                )
                if escape_operator is not None and not escape_used:
                    operator = escape_operator
                    escape_used = True
                    self._record_event(
                        run_id,
                        event_type="escape_invoked",
                        stage="search",
                        candidate_id=parent_id,
                        operator_name=escape_operator.name,
                        detail={
                            "reason": "frontier_stagnation",
                            "patience": self.settings.search_convergence_patience,
                        },
                    )
                    if self.reporter:
                        self.reporter.info("progress", f"Stagnation detected: invoking escape operator {escape_operator.name}")
                else:
                    if self.reporter:
                        self.reporter.info(
                            "progress",
                            "Stopping early: frontier stagnation threshold reached",
                        )
                    self._record_event(
                        run_id,
                        event_type="converged",
                        stage="search",
                        detail={
                            "reason": "frontier_stagnation",
                            "patience": self.settings.search_convergence_patience,
                            "escape_used": escape_used,
                            "precheck_pruned": True,
                        },
                    )
                    break
            if operator is None:
                select_for_candidate = getattr(self.registry, "select_operator_for_candidate", None)
                if callable(select_for_candidate):
                    operator = select_for_candidate(
                        target=candidate_target,
                        context=parent_context,
                        phase=phase,
                        parent_generation=parent.generation_depth,
                    )
                else:
                    operator = self.registry.select_operator(phase=phase, parent_generation=parent.generation_depth)
                if operator is None:
                    self._record_event(
                        run_id,
                        event_type="operator_pruned",
                        stage="search",
                        candidate_id=parent_id,
                        detail={
                            "reason": "no_valid_operator",
                            "phase": phase.value,
                            "generation_depth": parent.generation_depth,
                        },
                    )
                    pareto.mark_exhausted(parent_id)
                    continue
            if self.reporter:
                self.reporter.verbose(
                    "scheduler",
                    f"phase={phase.value} parent={parent_id} depth={parent.generation_depth} operator={operator.name}",
                )
            proposals = operator.generate(candidate_target, parent_context)
            if not proposals:
                self._record_event(
                    run_id,
                    event_type="operator_empty",
                    stage="generation",
                    candidate_id=parent_id,
                    operator_name=operator.name,
                    detail={"reason": "no_proposals", "phase": phase.value},
                )
                self.registry.record_empty_attempt(
                    operator.name,
                    phase=phase,
                    parent_generation=parent.generation_depth,
                )
                self.db.bump_operator(operator.name, success=False, reward=0.0)
                if pareto.expansion_count(parent_id) >= state.max_parent_expansions:
                    pareto.mark_exhausted(parent_id)
                continue
            proposals = self._augment_with_compositions(
                proposals=proposals,
                target=target,
                parent_id=parent_id,
                parent=parent,
                parent_context=parent_context,
                phase=phase,
            )
            ranked_proposals = sorted(proposals, key=lambda item: item.proposal_rank)[: self.settings.search_branching_factor]
            for proposal in ranked_proposals:
                if state.measured >= state.total_budget:
                    break
                candidate_id = uuid.uuid4().hex[:8]
                source_hash = candidate_source_hash(proposal.candidate_source)
                generation_delta = self._proposal_generation_delta(proposal)
                next_depth = min(self.settings.search_max_generations, parent.generation_depth + generation_delta)
                self._record_event(
                    run_id,
                    event_type="generated",
                    stage="generation",
                    candidate_id=candidate_id,
                    operator_name=proposal.operator_name,
                    detail=generated_candidate_detail(
                        proposal=proposal,
                        source_hash=source_hash,
                        analysis=analysis,
                        parent_id=parent_id,
                        phase=phase,
                        generation_depth=next_depth,
                    ),
                )
                if proposal.candidate_source.strip() == parent.source.strip():
                    self._record_screened_candidate(
                        run_id,
                        candidate_id=candidate_id,
                        proposal=proposal,
                        parent_id=parent_id,
                        generation_depth=next_depth,
                        source_hash=source_hash,
                        reason="unchanged_source",
                        status="skipped",
                        stage="generation",
                        duplicate_of=parent_id,
                    )
                    self._record_event(
                        run_id,
                        event_type="unchanged",
                        stage="generation",
                        candidate_id=candidate_id,
                        operator_name=proposal.operator_name,
                        detail={"reason": "unchanged_source", "source_hash": source_hash, "duplicate_of": parent_id},
                    )
                    self._update_operator(
                        proposal,
                        success=False,
                        reward=0.0,
                        phase=phase,
                        parent_generation=parent.generation_depth,
                        duplicate=True,
                    )
                    parent.rejection_history.append("unchanged_source")
                    continue
                duplicate_of = seen_sources.get(source_hash)
                if duplicate_of:
                    self._record_screened_candidate(
                        run_id,
                        candidate_id=candidate_id,
                        proposal=proposal,
                        parent_id=parent_id,
                        generation_depth=next_depth,
                        source_hash=source_hash,
                        reason="duplicate_source",
                        status="skipped",
                        stage="generation",
                        duplicate_of=duplicate_of,
                    )
                    self._record_event(
                        run_id,
                        event_type="duplicate",
                        stage="generation",
                        candidate_id=candidate_id,
                        operator_name=proposal.operator_name,
                        detail={"reason": "duplicate_source", "source_hash": source_hash, "duplicate_of": duplicate_of},
                    )
                    self._update_operator(
                        proposal,
                        success=False,
                        reward=0.0,
                        phase=phase,
                        parent_generation=parent.generation_depth,
                        duplicate=True,
                    )
                    parent.rejection_history.append("duplicate_source")
                    continue
                state.measured += 1
                if self.reporter:
                    self.reporter.info(
                        "progress",
                        f"Evaluating candidate {state.measured}/{state.total_budget} ({candidate_id}) phase={phase.value}",
                    )
                seen_sources[source_hash] = candidate_id
                screening = self.surrogate.screen_candidate(
                    source=proposal.candidate_source,
                    best_score=baseline_score,
                    phase=phase,
                    min_novelty=self.settings.search_min_novelty,
                    min_training_points=self.settings.surrogate_min_training_points,
                    feature_hints=proposal.feature_hints,
                    context=parent_context,
                )
                if screening["decision"] == "reject":
                    if self.reporter:
                        self.reporter.verbose(
                            "progress",
                            f"Candidate {candidate_id} screened out ({screening['reason']})",
                        )
                    self._record_screened_candidate(
                        run_id,
                        candidate_id=candidate_id,
                        proposal=proposal,
                        parent_id=parent_id,
                        generation_depth=next_depth,
                        source_hash=source_hash,
                        reason=str(screening["reason"]),
                        status="rejected",
                        stage="surrogate",
                        screening=screening,
                    )
                    self._record_event(
                        run_id,
                        event_type="surrogate_rejected",
                        stage="surrogate",
                        candidate_id=candidate_id,
                        operator_name=proposal.operator_name,
                        detail={"reason": screening["reason"], "acquisition_score": screening["acquisition_score"]},
                    )
                    self._update_operator(
                        proposal,
                        success=False,
                        reward=0.0,
                        phase=phase,
                        parent_generation=parent.generation_depth,
                        duplicate=str(screening["reason"]) == "low_novelty",
                    )
                    parent.rejection_history.append(str(screening["reason"]))
                    state.no_frontier_gain += 1
                    self._save_checkpoint(
                        run_id=run_id,
                        candidate_id=candidate_id,
                        baseline=baseline,
                        pareto=pareto,
                        parent_snapshots=parent_snapshots,
                        seen_sources=seen_sources,
                        state=state,
                        escape_used=escape_used,
                        accepted_candidate_ids=accepted_candidate_ids,
                        checkpoint_path=checkpoint_path,
                    )
                    continue
                correctness_started = perf_counter()
                valid, reasons = self.correctness.verify(
                    target,
                    bundle,
                    candidate_source=proposal.candidate_source,
                    timeout_s=self.settings.workload_timeout_s,
                )
                correctness_duration = perf_counter() - correctness_started
                if not valid:
                    if self.reporter:
                        self.reporter.verbose("progress", f"Candidate {candidate_id} failed correctness checks")
                    evaluation = build_correctness_rejection_evaluation(
                        candidate_id=candidate_id,
                        proposal=proposal,
                        parent_id=parent_id,
                        generation_depth=next_depth,
                        reasons=reasons,
                        phase=phase,
                        source_hash=source_hash,
                        screening=screening,
                    )
                    self._record_candidate(run_id, evaluation, status="rejected")
                    self._record_event(
                        run_id,
                        event_type="correctness_rejected",
                        stage="correctness",
                        candidate_id=candidate_id,
                        operator_name=proposal.operator_name,
                        detail={"reason": "correctness", "details": reasons, "duration_s": correctness_duration},
                    )
                    self._update_operator(
                        proposal,
                        success=False,
                        reward=0.0,
                        phase=phase,
                        parent_generation=parent.generation_depth,
                        correctness_failure=True,
                    )
                    parent.rejection_history.append("correctness")
                    state.no_frontier_gain += 1
                    self._save_checkpoint(
                        run_id=run_id,
                        candidate_id=candidate_id,
                        baseline=baseline,
                        pareto=pareto,
                        parent_snapshots=parent_snapshots,
                        seen_sources=seen_sources,
                        state=state,
                        escape_used=escape_used,
                        accepted_candidate_ids=accepted_candidate_ids,
                        checkpoint_path=checkpoint_path,
                    )
                    continue
                fidelities = self._fidelities_for_decision(str(screening["decision"]), phase)
                accepted = False
                candidate_report = None
                candidate_score = float(screening["predicted_score"])
                dominance_summary: dict[str, Any] = {}
                measurement_cost_s = 0.0
                rejection_reason = ""
                frontier_state = FrontierState.MEASURED_PARTIAL
                last_stage = "surrogate"
                for fidelity in fidelities:
                    measure_started = perf_counter()
                    report = self.oracle.measure_bundle(
                        run_id=run_id,
                        target=target,
                        bundle=bundle,
                        fidelity=fidelity,
                        candidate_id=candidate_id,
                        candidate_source=proposal.candidate_source,
                    )
                    duration = perf_counter() - measure_started
                    measurement_cost_s += duration
                    self.db.record_measurement(report, created_at=datetime.now(UTC).isoformat())
                    candidate_report = report
                    last_stage = fidelity.value
                    candidate_score = scalar_score(report.aggregate)
                    self._record_surrogate_observation(
                        run_id=run_id,
                        target_key=target_key,
                        source=proposal.candidate_source,
                        score=candidate_score,
                        feature_hints=proposal.feature_hints,
                        context=parent_context,
                    )
                    dominance_summary = pareto.dominance_summary(report.aggregate)
                    self._record_event(
                        run_id,
                        event_type=f"measured_{fidelity.value.lower()}",
                        stage=fidelity.value,
                        candidate_id=candidate_id,
                        operator_name=proposal.operator_name,
                        detail={
                            "duration_s": duration,
                            "score": candidate_score,
                            "dominance": dominance_summary,
                            "acquisition_score": screening["acquisition_score"],
                        },
                    )
                    if fidelity is not Fidelity.F3:
                        can_promote, rejection_reason = self._should_promote(
                            baseline.aggregate,
                            report.aggregate,
                            dominance_summary=dominance_summary,
                            uncertainty=float(screening["uncertainty"]),
                            phase=phase,
                        )
                        if not can_promote:
                            self._record_event(
                                run_id,
                                event_type=f"rejected_{fidelity.value.lower()}",
                                stage=fidelity.value,
                                candidate_id=candidate_id,
                                operator_name=proposal.operator_name,
                                detail={"reason": rejection_reason},
                            )
                            frontier_state = FrontierState.MEASURED_PARTIAL
                            break
                        continue
                    accepted, rejection_reason = self._should_accept_final(
                        baseline.aggregate,
                        report.aggregate,
                        dominance_summary=dominance_summary,
                    )
                    if accepted:
                        added = pareto.add(
                            ParetoPoint(
                                candidate_id=candidate_id,
                                metrics=report.aggregate,
                                parent_id=parent_id,
                                generation_depth=next_depth,
                                operator_name=proposal.operator_name,
                                active=True,
                            )
                        )
                        dominance_summary = {**dominance_summary, **added}
                        if not added["accepted"]:
                            accepted = False
                            rejection_reason = "frontier_dominated"
                            frontier_state = FrontierState.FRONTIER_DOMINATED
                        else:
                            frontier_state = FrontierState.FRONTIER_ACTIVE
                            parent_snapshots[candidate_id] = _ParentSnapshot(
                                candidate_id=candidate_id,
                                source=proposal.candidate_source,
                                operator_name=proposal.operator_name,
                                generation_depth=next_depth,
                            )
                            for dominated_id in added["dominated_ids"]:
                                self._record_event(
                                    run_id,
                                    event_type="frontier_dominated",
                                    stage="frontier",
                                    candidate_id=dominated_id,
                                    operator_name=proposal.operator_name,
                                    detail={"by": candidate_id},
                                )
                    else:
                        frontier_state = (
                            FrontierState.FRONTIER_DOMINATED
                            if dominance_summary.get("dominated")
                            else FrontierState.MEASURED_PARTIAL
                        )
                    self._record_event(
                        run_id,
                        event_type="accepted" if accepted else "rejected_f3",
                        stage=fidelity.value,
                        candidate_id=candidate_id,
                        operator_name=proposal.operator_name,
                        detail={"reason": rejection_reason or ("accepted" if accepted else "threshold")},
                    )
                    break
                evaluation = CandidateEvaluation(
                    candidate_id=candidate_id,
                    operator_name=proposal.operator_name,
                    reasoning=proposal.reasoning,
                    source=proposal.candidate_source,
                    dependencies=proposal.dependencies,
                    parent_id=parent_id,
                    generation_depth=next_depth,
                    frontier_state=frontier_state,
                    accepted=accepted,
                    score=candidate_score,
                    acquisition_score=float(screening["acquisition_score"]),
                    dominance_summary=dominance_summary,
                    report=candidate_report,
                    metadata=build_candidate_metadata(
                        baseline_aggregate=baseline.aggregate,
                        candidate_report=candidate_report,
                        stage=last_stage,
                        phase=phase,
                        screening=screening,
                        measurement_cost_s=measurement_cost_s,
                        accepted=accepted,
                        rejection_reason=rejection_reason,
                        source_hash=source_hash,
                        parent_id=parent_id,
                        generation_depth=next_depth,
                        frontier_state=frontier_state,
                        proposal=proposal,
                    ),
                )
                if candidate_report:
                    evaluation.metadata["explanation_summary"] = synthesize_explanation(baseline, evaluation)
                self._record_candidate(run_id, evaluation, status="accepted" if accepted else "rejected")
                self._update_operator(
                    proposal,
                    success=accepted,
                    reward=max(0.0, baseline_score - candidate_score),
                    phase=phase,
                    parent_generation=parent.generation_depth,
                    frontier_contribution=accepted and frontier_state is FrontierState.FRONTIER_ACTIVE,
                )
                if accepted:
                    accepted_evaluations[candidate_id] = evaluation
                    accepted_candidate_ids.add(candidate_id)
                    state.no_frontier_gain = 0
                    escape_used = False
                    if self.reporter:
                        self.reporter.info("progress", f"Accepted candidate {candidate_id} into frontier")
                else:
                    parent.rejection_history.append(rejection_reason or "threshold")
                    state.no_frontier_gain += 1
                    if self.reporter:
                        self.reporter.verbose(
                            "progress",
                            f"Candidate {candidate_id} rejected ({rejection_reason or 'threshold'})",
                        )
                self._save_checkpoint(
                    run_id=run_id,
                    candidate_id=candidate_id,
                    baseline=baseline,
                    pareto=pareto,
                    parent_snapshots=parent_snapshots,
                    seen_sources=seen_sources,
                    state=state,
                    escape_used=escape_used,
                    accepted_candidate_ids=accepted_candidate_ids,
                    checkpoint_path=checkpoint_path,
                )
                if state.no_frontier_gain >= self.settings.search_convergence_patience:
                    # Break out early so the next outer-loop iteration can trigger the escape operator.
                    break
            if pareto.expansion_count(parent_id) >= state.max_parent_expansions:
                pareto.mark_exhausted(parent_id)
                self._record_event(
                    run_id,
                    event_type="frontier_exhausted",
                    stage="frontier",
                    candidate_id=parent_id,
                    detail={"expansions": pareto.expansion_count(parent_id)},
                )

        best_point = pareto.best(exclude_ids={"baseline"})
        best_candidate = accepted_evaluations.get(best_point.candidate_id) if best_point else None
        if self.reporter:
            self.reporter.info(
                "progress",
                f"Optimization complete: measured {state.measured}/{state.total_budget} candidate(s)",
            )
        return baseline, pareto, best_candidate

    def _save_checkpoint(
        self,
        *,
        run_id: str,
        candidate_id: str,
        baseline: MeasurementReport,
        pareto: ParetoFront,
        parent_snapshots: dict[str, _ParentSnapshot],
        seen_sources: dict[str, str],
        state: OptimizationState,
        escape_used: bool,
        accepted_candidate_ids: set[str],
        checkpoint_path: Path | None,
    ) -> None:
        pareto_payload = [
            {
                "candidate_id": point.candidate_id,
                "metrics": point.metrics.to_record(),
                "parent_id": point.parent_id,
                "generation_depth": point.generation_depth,
                "operator_name": point.operator_name,
                "active": point.active,
            }
            for point in pareto.points()
        ]
        metadata = {
            "baseline_report": baseline.to_record(),
            "state": {
                "measured": state.measured,
                "total_budget": state.total_budget,
                "no_frontier_gain": state.no_frontier_gain,
                "max_parent_expansions": state.max_parent_expansions,
            },
            "seen_sources": seen_sources,
            "parent_snapshots": {
                key: {
                    "candidate_id": item.candidate_id,
                    "source": item.source,
                    "operator_name": item.operator_name,
                    "generation_depth": item.generation_depth,
                    "rejection_history": item.rejection_history,
                }
                for key, item in parent_snapshots.items()
            },
            "accepted_candidate_ids": sorted(accepted_candidate_ids),
            "escape_used": escape_used,
            "expansion_counts": pareto.expansion_counts(),
        }
        self.db.save_checkpoint(
            run_id=run_id,
            generation=state.measured,
            candidate_id=candidate_id,
            pareto_front_json=json.dumps(pareto_payload),
            metadata_json=json.dumps(metadata),
        )
        if checkpoint_path is None:
            return
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "generation": state.measured,
                    "candidate_id": candidate_id,
                    "pareto": pareto_payload,
                    "metadata": metadata,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _restore_checkpoint(self, *, run_id: str) -> dict[str, Any] | None:
        checkpoint = self.db.get_latest_checkpoint(run_id)
        if checkpoint is None:
            return None
        metadata = checkpoint.get("metadata", {}) if isinstance(checkpoint, dict) else {}
        baseline_payload = metadata.get("baseline_report") if isinstance(metadata, dict) else None
        if not isinstance(baseline_payload, dict):
            return None
        baseline = self._measurement_report_from_record(baseline_payload)

        pareto = ParetoFront(
            weights=(
                self.settings.pareto_weights.energy,
                self.settings.pareto_weights.latency,
                self.settings.pareto_weights.memory,
            )
        )
        try:
            pareto_payload = json.loads(str(checkpoint.get("pareto_front_json", "[]")))
        except json.JSONDecodeError:
            pareto_payload = []
        for point in pareto_payload:
            if not isinstance(point, dict):
                continue
            metrics_payload = point.get("metrics")
            if not isinstance(metrics_payload, dict):
                continue
            pareto.add(
                ParetoPoint(
                    candidate_id=str(point.get("candidate_id", "")),
                    metrics=AggregateMetrics(**metrics_payload),
                    parent_id=point.get("parent_id"),
                    generation_depth=int(point.get("generation_depth", 0)),
                    operator_name=str(point.get("operator_name", "baseline")),
                    active=bool(point.get("active", True)),
                )
            )
        if not pareto.points():
            pareto.add(
                ParetoPoint(
                    candidate_id="baseline",
                    metrics=baseline.aggregate,
                    parent_id=None,
                    generation_depth=0,
                    operator_name="baseline",
                    active=True,
                )
            )

        expansion_counts = metadata.get("expansion_counts", {}) if isinstance(metadata, dict) else {}
        if isinstance(expansion_counts, dict):
            pareto.load_expansion_counts({str(key): int(value) for key, value in expansion_counts.items()})

        parent_payload = metadata.get("parent_snapshots", {}) if isinstance(metadata, dict) else {}
        parent_snapshots: dict[str, _ParentSnapshot] = {}
        if isinstance(parent_payload, dict):
            for key, payload in parent_payload.items():
                if not isinstance(payload, dict):
                    continue
                parent_snapshots[str(key)] = _ParentSnapshot(
                    candidate_id=str(payload.get("candidate_id", key)),
                    source=str(payload.get("source", "")),
                    operator_name=str(payload.get("operator_name", "baseline")),
                    generation_depth=int(payload.get("generation_depth", 0)),
                    rejection_history=[str(item) for item in payload.get("rejection_history", [])],
                )

        if "baseline" not in parent_snapshots:
            parent_snapshots["baseline"] = _ParentSnapshot(
                candidate_id="baseline",
                source="",
                operator_name="baseline",
                generation_depth=0,
            )

        seen_sources_payload = metadata.get("seen_sources", {}) if isinstance(metadata, dict) else {}
        if isinstance(seen_sources_payload, dict):
            seen_sources = {str(key): str(value) for key, value in seen_sources_payload.items()}
        else:
            seen_sources = {}
        baseline_source = parent_snapshots["baseline"].source
        if baseline_source:
            seen_sources.setdefault(candidate_source_hash(baseline_source), "baseline")

        state_payload = metadata.get("state", {}) if isinstance(metadata, dict) else {}
        if not isinstance(state_payload, dict):
            state_payload = {}
        state = OptimizationState(
            total_budget=max(1, int(state_payload.get("total_budget", self.settings.optimization_budget))),
            max_parent_expansions=max(
                1,
                int(
                    state_payload.get(
                        "max_parent_expansions",
                        max(1, self.settings.search_branching_factor) * max(1, len(self.registry.operators)),
                    )
                ),
            ),
            measured=max(0, int(state_payload.get("measured", checkpoint.get("generation", 0)))),
            no_frontier_gain=max(0, int(state_payload.get("no_frontier_gain", 0))),
        )
        return {
            "baseline": baseline,
            "pareto": pareto,
            "parent_snapshots": parent_snapshots,
            "seen_sources": seen_sources,
            "state": state,
            "escape_used": bool(metadata.get("escape_used", False)) if isinstance(metadata, dict) else False,
        }

    def _load_accepted_evaluations(self, run_id: str) -> dict[str, CandidateEvaluation]:
        candidates = [item for item in self.db.get_candidates(run_id) if item["status"] == "accepted"]
        if not candidates:
            return {}

        measurements = self.db.get_measurements(run_id)
        reports_by_candidate: dict[str, MeasurementReport] = {}
        fidelity_rank = {Fidelity.F1: 1, Fidelity.F2: 2, Fidelity.F3: 3}
        for payload in measurements:
            candidate_id = payload.get("candidate_id")
            if not candidate_id:
                continue
            report = self._measurement_report_from_record(payload)
            existing = reports_by_candidate.get(candidate_id)
            if existing is None or fidelity_rank[report.fidelity] >= fidelity_rank[existing.fidelity]:
                reports_by_candidate[candidate_id] = report

        evaluations: dict[str, CandidateEvaluation] = {}
        for item in candidates:
            metadata = dict(item.get("metadata", {}))
            frontier_raw = str(metadata.get("frontier_state", FrontierState.FRONTIER_ACTIVE.value))
            try:
                frontier_state = FrontierState(frontier_raw)
            except ValueError:
                frontier_state = FrontierState.FRONTIER_ACTIVE
            surrogate_payload = metadata.get("surrogate", {})
            acquisition_score = 0.0
            if isinstance(surrogate_payload, dict):
                acquisition_score = float(surrogate_payload.get("acquisition_score", 0.0))

            evaluations[item["candidate_id"]] = CandidateEvaluation(
                candidate_id=item["candidate_id"],
                operator_name=item["operator_name"],
                reasoning=item["reasoning"],
                source=item["source_code"],
                dependencies=item["dependencies"],
                parent_id=item["parent_id"] or "baseline",
                generation_depth=int(metadata.get("generation_depth", 0)),
                frontier_state=frontier_state,
                accepted=True,
                score=float(item["score"]),
                acquisition_score=acquisition_score,
                dominance_summary=dict(metadata.get("dominance_summary", {})),
                report=reports_by_candidate.get(item["candidate_id"]),
                metadata=metadata,
            )
        return evaluations

    def _measurement_report_from_record(self, payload: dict[str, Any]) -> MeasurementReport:
        return MeasurementReport(
            run_id=str(payload["run_id"]),
            candidate_id=payload.get("candidate_id"),
            fidelity=Fidelity(str(payload["fidelity"])),
            aggregate=AggregateMetrics(**payload["aggregate"]),
            per_workload=[AggregateMetrics(**item) for item in payload.get("per_workload", [])],
            samples=[
                MetricSample(
                    workload_id=str(item["workload_id"]),
                    fidelity=Fidelity(str(item["fidelity"])),
                    repetition=int(item["repetition"]),
                    success=bool(item["success"]),
                    wall_time_s=float(item["wall_time_s"]),
                    cpu_time_s=float(item["cpu_time_s"]),
                    peak_memory_bytes=int(item["peak_memory_bytes"]),
                    energy_j=float(item["energy_j"]),
                    return_code=int(item["return_code"]),
                    stdout=str(item.get("stdout", "")),
                    stderr=str(item.get("stderr", "")),
                    metadata=dict(item.get("metadata", {})),
                )
                for item in payload.get("samples", [])
            ],
            environment=dict(payload.get("environment", {})),
            metadata=dict(payload.get("metadata", {})),
        )

    def _record_candidate(self, run_id: str, evaluation: CandidateEvaluation, *, status: str) -> None:
        self.db.record_candidate(
            candidate_id=evaluation.candidate_id,
            run_id=run_id,
            parent_id=evaluation.parent_id,
            operator_name=evaluation.operator_name,
            reasoning=evaluation.reasoning,
            dependencies=evaluation.dependencies,
            source_code=evaluation.source,
            status=status,
            score=evaluation.score,
            metadata=evaluation.metadata,
        )

    def _record_event(
        self,
        run_id: str,
        *,
        event_type: str,
        stage: str,
        detail: dict,
        candidate_id: str | None = None,
        operator_name: str | None = None,
    ) -> None:
        self.db.record_search_event(
            run_id=run_id,
            event_type=event_type,
            stage=stage,
            detail=detail,
            candidate_id=candidate_id,
            operator_name=operator_name,
            created_at=datetime.now(UTC).isoformat(),
        )

    def _update_operator(
        self,
        result: TransformationResult,
        *,
        success: bool,
        reward: float,
        phase: SearchPhase,
        parent_generation: int,
        duplicate: bool = False,
        correctness_failure: bool = False,
        frontier_contribution: bool = False,
    ) -> None:
        self.registry.update(
            result,
            success=success,
            reward=reward,
            phase=phase,
            parent_generation=parent_generation,
            duplicate=duplicate,
            correctness_failure=correctness_failure,
            frontier_contribution=frontier_contribution,
        )
        self.db.bump_operator(result.operator_name, success=success, reward=reward)

    def _should_promote(
        self,
        baseline,
        candidate,
        *,
        dominance_summary: dict[str, Any],
        uncertainty: float,
        phase: SearchPhase,
    ) -> tuple[bool, str]:
        if candidate.success_rate < 1.0:
            return False, "success_rate"
        memory_delta = improvement_ratio(baseline, candidate)["memory"]
        if memory_delta < -self.settings.candidate_memory_regression_limit:
            return False, "memory_regression"
        if not dominance_summary.get("dominated"):
            return True, ""
        uncertainty_factor = {
            SearchPhase.EXPLORATION: 1.0,
            SearchPhase.EXPLOITATION: 0.7,
            SearchPhase.CONFIRMATION: 0.4,
        }[phase]
        optimistic_score = scalar_score(candidate) - (uncertainty * uncertainty_factor)
        if optimistic_score <= scalar_score(baseline):
            return True, ""
        return False, "dominated_low_uncertainty"

    def _should_accept_final(self, baseline, candidate, *, dominance_summary: dict[str, Any]) -> tuple[bool, str]:
        if candidate.success_rate < 1.0:
            return False, "success_rate"
        improvements = improvement_ratio(baseline, candidate)
        memory_delta = improvements["memory"]
        if memory_delta < -self.settings.candidate_memory_regression_limit:
            return False, "memory_regression"
        if dominance_summary.get("dominated"):
            return False, "frontier_dominated"
        return True, ""

    def _phase_for_index(self, index: int, total_budget: int) -> SearchPhase:
        explore = max(0.0, self.settings.search_exploration_fraction)
        exploit = max(0.0, self.settings.search_exploitation_fraction)
        confirm = max(0.0, self.settings.search_confirmation_fraction)
        total = max(explore + exploit + confirm, 1e-9)
        exploration_cutoff = int(total_budget * (explore / total))
        exploitation_cutoff = exploration_cutoff + int(total_budget * (exploit / total))
        if index < exploration_cutoff:
            return SearchPhase.EXPLORATION
        if index < exploitation_cutoff:
            return SearchPhase.EXPLOITATION
        return SearchPhase.CONFIRMATION

    def _fidelities_for_decision(self, decision: str, phase: SearchPhase) -> tuple[Fidelity, ...]:
        if decision == "measure_partial":
            if phase is SearchPhase.EXPLORATION:
                return (Fidelity.F1,)
            return (Fidelity.F1, Fidelity.F2)
        return (Fidelity.F1, Fidelity.F2, Fidelity.F3)

    def _record_screened_candidate(
        self,
        run_id: str,
        *,
        candidate_id: str,
        proposal: TransformationResult,
        parent_id: str,
        generation_depth: int,
        source_hash: str,
        reason: str,
        status: str,
        stage: str,
        duplicate_of: str | None = None,
        screening: dict[str, Any] | None = None,
    ) -> None:
        evaluation = CandidateEvaluation(
            candidate_id=candidate_id,
            operator_name=proposal.operator_name,
            reasoning=proposal.reasoning,
            source=proposal.candidate_source,
            dependencies=proposal.dependencies,
            parent_id=parent_id,
            generation_depth=generation_depth,
            frontier_state=FrontierState.SCREENED_OUT,
            accepted=False,
            score=float("inf"),
            acquisition_score=float(screening["acquisition_score"]) if screening else 0.0,
            dominance_summary={},
            metadata={
                "rejected": reason,
                "stage": stage,
                "source_hash": source_hash,
                "parent_id": parent_id,
                "generation_depth": generation_depth,
                "frontier_state": FrontierState.SCREENED_OUT.value,
                "duplicate_of": duplicate_of,
                "surrogate": screening or {},
                "operator_family": proposal.operator_family,
                "operator_tier": proposal.operator_tier.value,
                "operator_tier_descriptor": proposal.metadata.get("operator_tier_descriptor", ""),
                "proposal_rank": proposal.proposal_rank,
                "generation_delta": self._proposal_generation_delta(proposal),
                "composed_operator_chain": list(proposal.metadata.get("composed_operator_chain", [])),
                "composition_hops": int(proposal.metadata.get("composition_hops", 0) or 0),
                **dependency_policy_metadata(proposal.dependencies),
            },
        )
        self._record_candidate(run_id, evaluation, status=status)

    def _proposal_generation_delta(self, proposal: TransformationResult) -> int:
        raw = proposal.metadata.get("generation_delta", 1)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 1

    def _merge_feature_hints(
        self,
        first: dict[str, float],
        second: dict[str, float],
    ) -> dict[str, float]:
        merged: dict[str, float] = {}
        for payload in (first, second):
            for key, value in payload.items():
                try:
                    merged[key] = float(merged.get(key, 0.0)) + float(value)
                except (TypeError, ValueError):
                    continue
        return merged

    def _augment_with_compositions(
        self,
        *,
        proposals: list[TransformationResult],
        target: TargetSpec,
        parent_id: str,
        parent: _ParentSnapshot,
        parent_context: SearchContext,
        phase: SearchPhase,
    ) -> list[TransformationResult]:
        if not self.settings.search_composition_enabled:
            return proposals

        width = max(1, int(self.settings.search_composition_width))
        ranked = sorted(proposals, key=lambda item: item.proposal_rank)[:width]
        composed: list[TransformationResult] = []

        for primary in ranked:
            primary_delta = self._proposal_generation_delta(primary)
            intermediate_depth = parent.generation_depth + primary_delta
            if intermediate_depth >= self.settings.search_max_generations:
                continue
            intermediate_target = self._target_with_source(target, primary.candidate_source, parent_id=parent_id)
            intermediate_context = SearchContext(
                parent_id=parent_id,
                parent_source=primary.candidate_source,
                parent_operator_name=primary.operator_name,
                generation_depth=intermediate_depth,
                phase=phase,
                rejection_history=parent_context.rejection_history[-5:],
                search_metadata={
                    **dict(parent_context.search_metadata),
                    "composition_hops": 1,
                    "composed_from_operator": primary.operator_name,
                },
            )
            select_for_candidate = getattr(self.registry, "select_operator_for_candidate", None)
            if callable(select_for_candidate):
                secondary_operator = select_for_candidate(
                    target=intermediate_target,
                    context=intermediate_context,
                    phase=phase,
                    parent_generation=intermediate_depth,
                )
            else:
                secondary_operator = self.registry.select_operator(
                    phase=phase,
                    parent_generation=intermediate_depth,
                )
            if secondary_operator is None:
                continue
            secondary_proposals = secondary_operator.generate(intermediate_target, intermediate_context)
            if not secondary_proposals:
                continue
            secondary = sorted(secondary_proposals, key=lambda item: item.proposal_rank)[0]
            secondary_delta = self._proposal_generation_delta(secondary)
            merged_hints = self._merge_feature_hints(primary.feature_hints, secondary.feature_hints)
            composed_metadata = {
                **dict(secondary.metadata),
                "composed_operator_chain": [primary.operator_name, secondary.operator_name],
                "composition_hops": 1,
                "generation_delta": primary_delta + secondary_delta,
                "composed_from_operator": primary.operator_name,
                "composed_from_reasoning": primary.reasoning,
            }
            composed.append(
                TransformationResult(
                    operator_name=secondary.operator_name,
                    candidate_source=secondary.candidate_source,
                    reasoning=f"{primary.reasoning} -> {secondary.reasoning}".strip(),
                    dependencies=sorted(set([*primary.dependencies, *secondary.dependencies])),
                    operator_family=secondary.operator_family,
                    operator_tier=secondary.operator_tier,
                    proposal_rank=(primary.proposal_rank * 1000) + secondary.proposal_rank + 500,
                    feature_hints=merged_hints,
                    metadata=composed_metadata,
                )
            )

        if not composed:
            return proposals
        merged: dict[str, TransformationResult] = {}
        for proposal in [*proposals, *composed]:
            merged.setdefault(proposal.candidate_source, proposal)
        return list(merged.values())

    def _target_key(self, target: TargetSpec) -> str:
        return f"{target.module}:{target.qualname}"

    def _surrogate_hints(
        self,
        *,
        source: str,
        feature_hints: dict[str, float] | None,
        context: SearchContext | None,
    ) -> dict[str, float]:
        hints = dict(feature_hints or {})
        if context is not None:
            hints.setdefault("parent_len_delta", float(abs(len(source) - len(context.parent_source))))
            hints.setdefault("generation_depth", float(context.generation_depth))
        return hints

    def _record_surrogate_observation(
        self,
        *,
        run_id: str,
        target_key: str,
        source: str,
        score: float,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> None:
        hints = self._surrogate_hints(source=source, feature_hints=feature_hints, context=context)
        self.surrogate.record(source, score, feature_hints=hints, context=context)
        self.db.save_surrogate_observation(
            run_id=run_id,
            target_key=target_key,
            source_code=source,
            score=score,
            feature_hints=hints,
        )

    def _warm_start_surrogate(self, *, target_key: str, fresh_start: bool) -> None:
        limit = max(0, self.settings.surrogate_warm_start_limit)
        if limit == 0 or fresh_start or not self.settings.surrogate_reuse_observations:
            return
        observations = self.db.get_surrogate_observations(limit=limit, target_key=target_key)
        for item in reversed(observations):
            self.surrogate.record(
                str(item.get("source", "")),
                float(item.get("score", 0.0)),
                feature_hints=dict(item.get("feature_hints", {})),
            )

    def _target_with_source(self, target: TargetSpec, source: str, *, parent_id: str) -> TargetSpec:
        metadata = dict(target.metadata)
        metadata["candidate_parent_id"] = parent_id
        return TargetSpec(
            project_root=target.project_root,
            module=target.module,
            file_path=target.file_path,
            function_name=target.function_name,
            qualname=target.qualname,
            owner_path=list(target.owner_path),
            line_start=target.line_start,
            line_end=target.line_end,
            source=source,
            is_async=target.is_async,
            metadata=metadata,
        )
