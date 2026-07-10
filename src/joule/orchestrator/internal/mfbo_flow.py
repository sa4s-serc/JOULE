from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Any

from joule.metadata import CandidateMetadata, ImprovementSummary, SurrogateDecision
from joule.models import CandidateEvaluation, FrontierState, SearchContext, SearchPhase, TransformationResult
from joule.utils.metrics import improvement_ratio
from joule.utils.reporting import improvement_summary
from joule.transformers.smell_tagger import tag_source_with_evidence



@dataclass(slots=True)
class OptimizationState:
    total_budget: int
    max_parent_expansions: int
    measured: int = 0
    no_frontier_gain: int = 0


def build_parent_context(parent: Any, *, phase: SearchPhase, analysis: bool) -> SearchContext:
    return SearchContext(
        parent_id=parent.candidate_id,
        parent_source=parent.source,
        parent_operator_name=parent.operator_name,
        generation_depth=parent.generation_depth,
        phase=phase,
        rejection_history=parent.rejection_history[-5:],
        search_metadata={"analysis_enabled": analysis},
    )


def generated_candidate_detail(
    *,
    proposal: TransformationResult,
    source_hash: str,
    analysis: bool,
    parent_id: str,
    phase: SearchPhase,
    generation_depth: int,
) -> dict[str, Any]:
    return {
        "reasoning": proposal.reasoning,
        "source_hash": source_hash,
        "analysis_enabled": analysis,
        "parent_id": parent_id,
        "phase": phase.value,
        "generation_depth": generation_depth,
        "proposal_rank": proposal.proposal_rank,
        "operator_family": proposal.operator_family,
        "operator_tier": proposal.operator_tier.value,
        "operator_tier_descriptor": proposal.metadata.get("operator_tier_descriptor", ""),
        "generation_delta": int(proposal.metadata.get("generation_delta", 1) or 1),
        "composed_operator_chain": list(proposal.metadata.get("composed_operator_chain", [])),
        "composition_hops": int(proposal.metadata.get("composition_hops", 0) or 0),
    }


def dependency_policy_metadata(dependencies: list[str]) -> dict[str, str]:
    if dependencies:
        external_deps = [dependency for dependency in dependencies if not _is_stdlib_dependency(dependency)]
        if external_deps:
            return {
                "dependency_policy_state": "review_required",
                "dependency_policy_reason": "candidate proposes external dependencies and remains review-only",
            }
        return {
            "dependency_policy_state": "stdlib_only",
            "dependency_policy_reason": "candidate uses stdlib dependencies only",
        }
    return {
        "dependency_policy_state": "no_dependencies",
        "dependency_policy_reason": "candidate uses existing dependencies only",
    }


def _is_stdlib_dependency(dependency: str) -> bool:
    root = dependency.split(".", 1)[0].strip()
    return bool(root) and root in sys.stdlib_module_names


def build_correctness_rejection_evaluation(
    *,
    candidate_id: str,
    proposal: TransformationResult,
    parent_id: str,
    generation_depth: int,
    reasons: list[str],
    phase: SearchPhase,
    source_hash: str,
    screening: dict[str, Any],
) -> CandidateEvaluation:
    dependency_policy = dependency_policy_metadata(proposal.dependencies)
    metadata = CandidateMetadata(
        rejected="correctness",
        reason=[str(item) for item in reasons],
        stage="correctness",
        phase=phase.value,
        source_hash=source_hash,
        parent_id=parent_id,
        generation_depth=generation_depth,
        frontier_state=FrontierState.SCREENED_OUT.value,
        surrogate=SurrogateDecision.from_record(screening),
        operator_family=proposal.operator_family,
        operator_tier=proposal.operator_tier.value,
        operator_tier_descriptor=proposal.metadata.get("operator_tier_descriptor", ""),
        proposal_rank=proposal.proposal_rank,
        generation_delta=int(proposal.metadata.get("generation_delta", 1) or 1),
        composed_operator_chain=list(proposal.metadata.get("composed_operator_chain", [])),
        composition_hops=int(proposal.metadata.get("composition_hops", 0) or 0),
        dependency_policy_state=dependency_policy["dependency_policy_state"],
        dependency_policy_reason=dependency_policy["dependency_policy_reason"],
        extra={
            "smell_evidence": {
                k: v.to_record()
                for k, v in tag_source_with_evidence(proposal.candidate_source).items()
            }
        },
    ).to_record()
    return CandidateEvaluation(
        candidate_id=candidate_id,
        operator_name=proposal.operator_name,
        reasoning="; ".join(reasons) or proposal.reasoning,
        source=proposal.candidate_source,
        dependencies=proposal.dependencies,
        parent_id=parent_id,
        generation_depth=generation_depth,
        frontier_state=FrontierState.SCREENED_OUT,
        accepted=False,
        score=0.0,
        acquisition_score=float(screening["acquisition_score"]),
        dominance_summary={},
        metadata=metadata,
    )


def build_candidate_metadata(
    *,
    baseline_aggregate,
    candidate_report,
    stage: str,
    phase: SearchPhase,
    screening: dict[str, Any],
    measurement_cost_s: float,
    accepted: bool,
    rejection_reason: str,
    source_hash: str,
    parent_id: str,
    generation_depth: int,
    frontier_state: FrontierState,
    proposal: TransformationResult,
) -> dict[str, Any]:
    improvement = improvement_ratio(baseline_aggregate, candidate_report.aggregate) if candidate_report else {}
    improvement_notes = improvement_summary(baseline_aggregate, candidate_report.aggregate) if candidate_report else {}
    dependency_policy = dependency_policy_metadata(proposal.dependencies)
    metadata = CandidateMetadata(
        improvement={str(key): float(value) for key, value in improvement.items()},
        improvement_summary=ImprovementSummary.from_record(improvement_notes),
        explanation_summary="",
        stage=stage,
        phase=phase.value,
        measurement_decision=str(screening.get("decision", "")),
        measurement_cost_s=measurement_cost_s,
        rejected=None if accepted else (rejection_reason or "threshold"),
        source_hash=source_hash,
        parent_id=parent_id,
        generation_depth=generation_depth,
        frontier_state=frontier_state.value,
        surrogate=SurrogateDecision.from_record(screening),
        operator_family=proposal.operator_family,
        operator_tier=proposal.operator_tier.value,
        operator_tier_descriptor=proposal.metadata.get("operator_tier_descriptor", ""),
        proposal_rank=proposal.proposal_rank,
        generation_delta=int(proposal.metadata.get("generation_delta", 1) or 1),
        composed_operator_chain=list(proposal.metadata.get("composed_operator_chain", [])),
        composition_hops=int(proposal.metadata.get("composition_hops", 0) or 0),
        dependency_policy_state=dependency_policy["dependency_policy_state"],
        dependency_policy_reason=dependency_policy["dependency_policy_reason"],
        extra={
            "smell_evidence": {
                k: v.to_record()
                for k, v in tag_source_with_evidence(proposal.candidate_source).items()
            }
        },
    )
    return metadata.to_record()
