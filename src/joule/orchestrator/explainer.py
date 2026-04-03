from __future__ import annotations

from joule.models import CandidateEvaluation
from joule.utils.reporting import improvement_summary


def synthesize_explanation(baseline, candidate: CandidateEvaluation) -> str:
    if not candidate.report:
        return candidate.reasoning
    improvement = improvement_summary(baseline.aggregate, candidate.report.aggregate)
    return (
        f"{candidate.reasoning}\n\n"
        f"Energy delta: {improvement['energy']:.1%}\n"
        f"Latency delta: {improvement['latency']:.1%}\n"
        f"Memory delta: {improvement['memory']:.1%}"
    )
