from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
import uuid

from joule.config import JouleSettings
from joule.evaluators.correctness import CorrectnessEngine
from joule.evaluators.oracle import PerformanceOracle
from joule.models import (
    CandidateEvaluation,
    Fidelity,
    FrontierState,
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


@dataclass(slots=True)
class _ParentSnapshot:
    candidate_id: str
    source: str
    operator_name: str
    generation_depth: int
    rejection_history: list[str] = field(default_factory=list)


class OptimizationOrchestrator:
    def __init__(self, settings: JouleSettings, db: JouleDB, oracle: PerformanceOracle, reporter=None) -> None:
        self.settings = settings
        self.db = db
        self.oracle = oracle
        self.reporter = reporter
        self.correctness = CorrectnessEngine()
        self.registry = OperatorRegistry(llm_model=settings.llm_model, include_llm=True)
        self.registry.load_stats(self.db.get_operator_stats())
        self.surrogate = GaussianProcessSurrogate()
        self._warm_start_surrogate()

    def baseline(self, run_id: str, target: TargetSpec, bundle: WorkloadBundle, repetitions: int | None = None):
        if self.reporter:
            self.reporter.info("baseline", f"Measuring {target.qualname} with {len(bundle.workloads)} workload(s)")
        report = self.oracle.measure_bundle(
            run_id=run_id,
            target=target,
            bundle=bundle,
            fidelity=Fidelity.F3,
            repetitions=repetitions,
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
    ) -> tuple:
        baseline = self.baseline(run_id, target, bundle)
        baseline_score = scalar_score(baseline.aggregate)
        self.surrogate.record(target.source, baseline_score)
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
        accepted_evaluations: dict[str, CandidateEvaluation] = {}
        parent_snapshots: dict[str, _ParentSnapshot] = {
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
            max_parent_expansions=max(1, self.settings.search_branching_factor) * max(1, len(self.registry.operators)),
        )
        escape_used = False
        if self.reporter:
            self.reporter.info("progress", f"Optimization budget: {state.total_budget} measured candidate(s)")
        while state.measured < state.total_budget:
            phase = self._phase_for_index(state.measured, state.total_budget)
            parent_id = pareto.sample_active_parent(max_generation=self.settings.search_max_generations)
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
            ranked_proposals = sorted(proposals, key=lambda item: item.proposal_rank)[: self.settings.search_branching_factor]
            for proposal in ranked_proposals:
                if state.measured >= state.total_budget:
                    break
                candidate_id = uuid.uuid4().hex[:8]
                source_hash = candidate_source_hash(proposal.candidate_source)
                next_depth = parent.generation_depth + 1
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
                    self.surrogate.record(
                        proposal.candidate_source,
                        candidate_score,
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
                **dependency_policy_metadata(proposal.dependencies),
            },
        )
        self._record_candidate(run_id, evaluation, status=status)

    def _warm_start_surrogate(self) -> None:
        limit = max(0, self.settings.surrogate_warm_start_limit)
        if limit == 0:
            return
        observations = self.db.get_recent_candidate_observations(limit=limit)
        for source, score in reversed(observations):
            self.surrogate.record(source, score)

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
