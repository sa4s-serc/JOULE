from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from joule.models import SearchContext, TargetSpec, Tier, TransformationResult, tier_descriptor


class BaseOperator(ABC):
    name: ClassVar[str]
    family: ClassVar[str] = "deterministic"
    tier: ClassVar[Tier] = Tier.L
    escape_only: ClassVar[bool] = False
    precheck_node_types: ClassVar[tuple[type[ast.AST], ...]] = ()
    # Energy-Smells taxonomy categories this operator primarily targets.
    # Used by OperatorRegistry for smell-overlap scoring (Phase 2).
    targets_smells: ClassVar[frozenset[str]] = frozenset()

    def tier_name(self) -> str:
        return self.tier.value

    def tier_description(self) -> str:
        return tier_descriptor(self.tier)

    def build_result(
        self,
        *,
        candidate_source: str,
        reasoning: str,
        dependencies: list[str] | None = None,
        proposal_rank: int = 0,
        feature_hints: dict[str, float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TransformationResult:
        combined_metadata: dict[str, Any] = {
            "operator_tier": self.tier_name(),
            "operator_tier_descriptor": self.tier_description(),
        }
        if metadata:
            combined_metadata.update(metadata)
        return TransformationResult(
            operator_name=self.name,
            candidate_source=candidate_source,
            reasoning=reasoning,
            dependencies=list(dependencies or []),
            operator_family=self.family,
            operator_tier=self.tier,
            proposal_rank=proposal_rank,
            feature_hints=dict(feature_hints or {}),
            metadata=combined_metadata,
        )

    def precheck(self, target: TargetSpec, context: SearchContext | None = None) -> bool:
        try:
            tree = ast.parse(target.source)
        except SyntaxError:
            return False
        return self._precheck_tree(tree, target, context)

    def _precheck_tree(self, tree: ast.AST, target: TargetSpec, context: SearchContext | None = None) -> bool:
        del target, context
        if not self.precheck_node_types:
            return False
        for node in ast.walk(tree):
            if isinstance(node, self.precheck_node_types) and self._precheck_node(node):
                return True
        return False

    def _precheck_node(self, node: ast.AST) -> bool:
        del node
        return True

    @abstractmethod
    def generate(self, target: TargetSpec, context: SearchContext | None = None) -> list[TransformationResult]:
        raise NotImplementedError
