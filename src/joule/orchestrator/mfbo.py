from __future__ import annotations

from datetime import UTC, datetime
import uuid

from joule.config import JouleSettings
from joule.evaluators.correctness import CorrectnessEngine
from joule.evaluators.oracle import PerformanceOracle
from joule.models import CandidateEvaluation, Fidelity, TargetSpec, WorkloadBundle
from joule.orchestrator.explainer import synthesize_explanation
from joule.orchestrator.pareto import ParetoFront, ParetoPoint
from joule.surrogate.gp import GaussianProcessSurrogate
from joule.transformers.registry import OperatorRegistry
from joule.utils.db import JouleDB
from joule.utils.metrics import improvement_ratio, scalar_score
from joule.utils.reporting import improvement_summary


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
    ) -> tuple:
        baseline = self.baseline(run_id, target, bundle)
        baseline_score = scalar_score(baseline.aggregate)
        self.surrogate.record(target.source, baseline_score)
        pareto = ParetoFront()
        pareto.add(ParetoPoint(candidate_id="baseline", metrics=baseline.aggregate))
        best_candidate: CandidateEvaluation | None = None

        remaining = budget or self.settings.optimization_budget
        for operator in self.registry.ranked():
            if remaining <= 0:
                break
            if self.reporter:
                self.reporter.verbose("operator", f"Trying {operator.name}")
            for result in operator.generate(target):
                if result.candidate_source.strip() == target.source.strip():
                    continue
                remaining -= 1
                candidate_id = uuid.uuid4().hex[:8]
                if self.reporter:
                    self.reporter.verbose("candidate", f"{candidate_id} proposed by {result.operator_name}")
                valid, reasons = self.correctness.verify(
                    target,
                    bundle,
                    candidate_source=result.candidate_source,
                    timeout_s=self.settings.workload_timeout_s,
                )
                if not valid:
                    evaluation = CandidateEvaluation(
                        candidate_id=candidate_id,
                        operator_name=result.operator_name,
                        reasoning="; ".join(reasons) or result.reasoning,
                        source=result.candidate_source,
                        dependencies=result.dependencies,
                        accepted=False,
                        score=float("inf"),
                        metadata={
                            "rejected": "correctness",
                            "reason": reasons,
                            "dependency_policy_state": "review_required" if result.dependencies else "no_dependencies",
                            "dependency_policy_reason": (
                                "candidate proposes additional dependencies and remains review-only"
                                if result.dependencies
                                else "candidate uses existing dependencies only"
                            ),
                        },
                    )
                    self._record_candidate(run_id, evaluation, status="rejected")
                    self._update_operator(result, success=False, reward=0.0)
                    if self.reporter:
                        self.reporter.verbose("correctness", f"{candidate_id} rejected: {evaluation.reasoning}")
                    continue

                if not self.surrogate.is_promising(result.candidate_source, baseline_score):
                    evaluation = CandidateEvaluation(
                        candidate_id=candidate_id,
                        operator_name=result.operator_name,
                        reasoning=result.reasoning,
                        source=result.candidate_source,
                        dependencies=result.dependencies,
                        accepted=False,
                        score=float("inf"),
                        metadata={
                            "rejected": "surrogate",
                            "dependency_policy_state": "review_required" if result.dependencies else "no_dependencies",
                            "dependency_policy_reason": (
                                "candidate proposes additional dependencies and remains review-only"
                                if result.dependencies
                                else "candidate uses existing dependencies only"
                            ),
                        },
                    )
                    self._record_candidate(run_id, evaluation, status="rejected")
                    self._update_operator(result, success=False, reward=0.0)
                    if self.reporter:
                        self.reporter.verbose("surrogate", f"{candidate_id} rejected before measurement")
                    continue

                accepted = False
                candidate_report = None
                candidate_score = float("inf")
                last_stage = "F0"
                rejection_reason = ""
                for fidelity in (Fidelity.F1, Fidelity.F2, Fidelity.F3):
                    report = self.oracle.measure_bundle(
                        run_id=run_id,
                        target=target,
                        bundle=bundle,
                        fidelity=fidelity,
                        candidate_id=candidate_id,
                        candidate_source=result.candidate_source,
                    )
                    self.db.record_measurement(report, created_at=datetime.now(UTC).isoformat())
                    candidate_report = report
                    last_stage = fidelity.value
                    candidate_score = scalar_score(report.aggregate)
                    self.surrogate.record(result.candidate_source, candidate_score)
                    if fidelity is not Fidelity.F3:
                        can_promote, rejection_reason = self._should_promote(baseline.aggregate, report.aggregate)
                        if self.reporter:
                            self.reporter.verbose(
                                "promotion",
                                f"{candidate_id} {fidelity.value} {'promoted' if can_promote else 'rejected'}",
                            )
                        if not can_promote:
                            break
                        continue
                    accepted, rejection_reason = self._should_accept_final(baseline.aggregate, report.aggregate)
                    if self.reporter:
                        self.reporter.verbose(
                            "promotion",
                            f"{candidate_id} F3 {'accepted' if accepted else 'rejected'}",
                        )
                    break

                evaluation = CandidateEvaluation(
                    candidate_id=candidate_id,
                    operator_name=result.operator_name,
                    reasoning=result.reasoning,
                    source=result.candidate_source,
                    dependencies=result.dependencies,
                    accepted=accepted,
                    score=candidate_score,
                    report=candidate_report,
                    metadata={
                        "improvement": improvement_ratio(baseline.aggregate, candidate_report.aggregate) if candidate_report else {},
                        "improvement_summary": (
                            improvement_summary(baseline.aggregate, candidate_report.aggregate)
                            if candidate_report
                            else {}
                        ),
                        "explanation_summary": "",
                        "stage": last_stage,
                        "rejected": None if accepted else rejection_reason or "threshold",
                        "dependency_policy_state": "review_required" if result.dependencies else "no_dependencies",
                        "dependency_policy_reason": (
                            "candidate proposes additional dependencies and remains review-only"
                            if result.dependencies
                            else "candidate uses existing dependencies only"
                        ),
                    },
                )
                if candidate_report:
                    evaluation.metadata["explanation_summary"] = synthesize_explanation(baseline, evaluation)
                self._record_candidate(run_id, evaluation, status="accepted" if accepted else "rejected")
                self._update_operator(result, success=accepted, reward=max(0.0, baseline_score - candidate_score))
                if accepted:
                    assert candidate_report is not None
                    pareto.add(ParetoPoint(candidate_id=candidate_id, metrics=candidate_report.aggregate))
                    if best_candidate is None or candidate_score < best_candidate.score:
                        best_candidate = evaluation
        return baseline, pareto, best_candidate

    def _record_candidate(self, run_id: str, evaluation: CandidateEvaluation, *, status: str) -> None:
        self.db.record_candidate(
            candidate_id=evaluation.candidate_id,
            run_id=run_id,
            parent_id="baseline",
            operator_name=evaluation.operator_name,
            reasoning=evaluation.reasoning,
            dependencies=evaluation.dependencies,
            source_code=evaluation.source,
            status=status,
            score=evaluation.score,
            metadata=evaluation.metadata,
        )

    def _update_operator(self, result, *, success: bool, reward: float) -> None:
        self.registry.update(result, success=success, reward=reward)
        self.db.bump_operator(result.operator_name, success=success, reward=reward)

    def _should_promote(self, baseline, candidate) -> tuple[bool, str]:
        if candidate.success_rate < 1.0:
            return False, "success_rate"
        score_delta = (scalar_score(baseline) - scalar_score(candidate)) / max(scalar_score(baseline), 1e-9)
        if score_delta < self.settings.promotion_scalar_min:
            return False, "promotion_scalar_min"
        memory_delta = improvement_ratio(baseline, candidate)["memory"]
        if memory_delta < -self.settings.candidate_memory_regression_limit:
            return False, "memory_regression"
        return True, ""

    def _should_accept_final(self, baseline, candidate) -> tuple[bool, str]:
        if candidate.success_rate < 1.0:
            return False, "success_rate"
        improvements = improvement_ratio(baseline, candidate)
        memory_delta = improvements["memory"]
        if memory_delta < -self.settings.candidate_memory_regression_limit:
            return False, "memory_regression"
        if max(improvements["energy"], improvements["latency"]) < self.settings.final_improvement_min:
            return False, "final_improvement_min"
        return True, ""
