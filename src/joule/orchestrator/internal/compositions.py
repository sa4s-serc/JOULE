"""Operator composition logic for MFBO search space augmentation."""

from __future__ import annotations

from typing import Any

from joule.models import SearchContext, SearchPhase, TargetSpec, TransformationResult


def proposal_generation_delta(proposal: TransformationResult) -> int:
    raw = proposal.metadata.get("generation_delta", 1)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def merge_feature_hints(
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


def augment_with_compositions(
    *,
    proposals: list[TransformationResult],
    target: TargetSpec,
    parent_id: str,
    parent: Any,
    parent_context: SearchContext,
    phase: SearchPhase,
    settings: Any,
    registry: Any,
    target_with_source_fn: Any,
) -> list[TransformationResult]:
    if not settings.search_composition_enabled:
        return proposals

    width = max(1, int(settings.search_composition_width))
    max_hops = max(1, int(settings.search_composition_max_hops))
    ranked = sorted(proposals, key=lambda item: item.proposal_rank)[:width]
    composed: list[TransformationResult] = []

    for base_proposal in ranked:
        current_proposal = base_proposal
        current_depth = parent.generation_depth + proposal_generation_delta(current_proposal)
        chained_names = [current_proposal.operator_name]
        chained_reasoning = [current_proposal.reasoning]
        chained_delta = proposal_generation_delta(current_proposal)

        for hop in range(1, max_hops + 1):
            if current_depth >= settings.search_max_generations:
                break

            intermediate_target = target_with_source_fn(target, current_proposal.candidate_source, parent_id=parent_id)
            intermediate_context = SearchContext(
                parent_id=parent_id,
                parent_source=current_proposal.candidate_source,
                parent_operator_name=current_proposal.operator_name,
                generation_depth=current_depth,
                phase=phase,
                rejection_history=parent_context.rejection_history[-5:],
                search_metadata={
                    **dict(parent_context.search_metadata),
                    "composition_hops": hop,
                    "composed_from_operator": current_proposal.operator_name,
                },
            )
            ops = registry.select_operators_for_candidate(
                target=intermediate_target,
                context=intermediate_context,
                phase=phase,
                parent_generation=current_depth,
                top_k=1,
            )
            next_operator = ops[0] if ops else None
            if next_operator is None:
                break
            next_proposals = next_operator.generate(intermediate_target, intermediate_context)
            if not next_proposals:
                break
            next_proposal = sorted(next_proposals, key=lambda item: item.proposal_rank)[0]
            
            if next_proposal.candidate_source == current_proposal.candidate_source:
                break
            
            next_delta = proposal_generation_delta(next_proposal)
            current_depth += next_delta
            chained_names.append(next_proposal.operator_name)
            chained_reasoning.append(next_proposal.reasoning)
            chained_delta += next_delta
            
            merged_hints = merge_feature_hints(current_proposal.feature_hints, next_proposal.feature_hints)
            
            new_proposal = TransformationResult(
                operator_name=next_proposal.operator_name,
                candidate_source=next_proposal.candidate_source,
                reasoning=" -> ".join(chained_reasoning).strip(),
                dependencies=sorted(set([*current_proposal.dependencies, *next_proposal.dependencies])),
                operator_family=next_proposal.operator_family,
                operator_tier=next_proposal.operator_tier,
                # Composed proposals are intentionally ranked after base proposals
                # (multiplied by 1000) so they are only evaluated when the base
                # proposals have been exhausted within the branching factor budget.
                proposal_rank=(base_proposal.proposal_rank * 1000) + next_proposal.proposal_rank + (hop * 500),
                feature_hints=merged_hints,
                metadata={
                    **dict(next_proposal.metadata),
                    "composed_operator_chain": list(chained_names),
                    "composition_hops": hop,
                    "generation_delta": chained_delta,
                    "composed_from_operator": base_proposal.operator_name,
                    "composed_from_reasoning": base_proposal.reasoning,
                },
            )
            composed.append(new_proposal)
            current_proposal = new_proposal

    if not composed:
        return proposals
    merged: dict[str, TransformationResult] = {}
    for proposal in [*proposals, *composed]:
        merged.setdefault(proposal.candidate_source, proposal)
    return list(merged.values())
