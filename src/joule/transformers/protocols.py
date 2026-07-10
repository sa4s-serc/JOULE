"""Formal Protocol for operator selector implementations.

Replaces the fragile ``getattr``-based duck typing in
``orchestrator/mfbo.py`` with an explicit, type-safe interface.

All methods that ``OptimizationOrchestrator`` calls on an
``OperatorRegistry`` are collected here so that:
1. Static type checkers can verify correctness.
2. Plug-in registry implementations have a clear contract.
3. Test doubles can subclass or implement this Protocol directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from joule.models import SearchContext, SearchPhase, TargetSpec, TransformationResult
    from joule.transformers.base import BaseOperator


@runtime_checkable
class OperatorSelectorProtocol(Protocol):
    """Protocol satisfied by ``OperatorRegistry`` and any compatible replacement."""

    # ------------------------------------------------------------------ #
    # Introspection                                                         #
    # ------------------------------------------------------------------ #

    @property
    def operators(self) -> list[BaseOperator]:
        """All non-escape operators currently registered."""
        ...

    # ------------------------------------------------------------------ #
    # Candidate-level selection (preferred API)                             #
    # ------------------------------------------------------------------ #

    def select_operators_for_candidate(
        self,
        *,
        target: TargetSpec,
        context: SearchContext | None,
        phase: SearchPhase,
        parent_generation: int,
        top_k: int = 1,
    ) -> list[BaseOperator]:
        """Return up to *top_k* operators suitable for *target* and *context*."""
        ...

    def select_escape_operator_for_candidate(
        self,
        *,
        target: TargetSpec,
        context: SearchContext | None,
        phase: SearchPhase,
        parent_generation: int,
    ) -> BaseOperator | None:
        """Return the best escape operator for *target*, or ``None``."""
        ...

    # ------------------------------------------------------------------ #
    # Feedback                                                              #
    # ------------------------------------------------------------------ #

    def update(
        self,
        result: TransformationResult,
        success: bool,
        reward: float,
        *,
        phase: SearchPhase,
        parent_generation: int,
        duplicate: bool = False,
        correctness_failure: bool = False,
        frontier_contribution: bool = False,
    ) -> None:
        """Record the outcome of applying *result*."""
        ...

    def record_empty_attempt(
        self,
        operator_name: str,
        *,
        phase: SearchPhase,
        parent_generation: int,
    ) -> None:
        """Record that an operator produced zero proposals."""
        ...

    def load_stats(self, persisted: dict[str, dict[str, Any]]) -> None:
        """Hydrate persisted per-operator statistics."""
        ...
