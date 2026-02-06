"""
Base Mutation System - Hierarchical Abstraction Layer

This module defines the core abstraction for HEDGE's hierarchical mutation system.
Mutations are organized in layers from high-level semantic changes down to
low-level syntactic optimizations.
"""

import copy
import logging
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set

from src.domain.interfaces import Mutator
from src.domain.ir import schema

logger = logging.getLogger(__name__)


class MutationLayer(Enum):
    """
    Hierarchical mutation layers from high-level to low-level transformations.

    SEMANTIC: Algorithm and intent optimization (highest level)
    ALGORITHMIC: Data structure and complexity improvements
    SYNTACTIC: Code structure and idiom improvements
    MICRO: Low-level optimizations (loop unrolling, constant folding)
    """

    SEMANTIC = "semantic"  # Algorithm intent and high-level logic
    ALGORITHMIC = "algorithmic"  # Data structures and complexity
    SYNTACTIC = "syntactic"  # Code patterns and idioms
    MICRO = "micro"  # Low-level optimizations


@dataclass
class MutationResult:
    """Result of a mutation operation with metadata."""

    ir: schema.Module
    strategy_name: str
    layer: MutationLayer
    mutator_name: str = ""
    confidence: float = 1.0  # Confidence in the mutation (0.0 to 1.0)
    description: str = ""  # Human-readable description of the change


class LayeredMutator(Mutator):
    """
    Base class for all layered mutators in HEDGE.

    Each mutator operates at a specific abstraction layer and provides
    metadata about its transformations.
    """

    def __init__(self, layer: MutationLayer, enabled_strategies: Optional[Set[str]] = None):
        self.layer = layer
        self.enabled_strategies = enabled_strategies or set()
        self.mutation_count = 0
        self.success_count = 0

    def _create_result(
        self, ir: schema.Module, strategy_name: str, confidence: float = 1.0, description: str = ""
    ) -> MutationResult:
        """Helper to create a MutationResult with this mutator's metadata."""
        from src.utils.mutation_factory import create_mutation_result

        return create_mutation_result(
            ir=ir,
            strategy_name=strategy_name,
            layer=self.layer,
            mutator_name=self.__class__.__name__,
            confidence=confidence,
            description=description,
        )

    @abstractmethod
    def get_available_strategies(self) -> List[str]:
        """Return list of available mutation strategies for this mutator."""

    @abstractmethod
    def mutate(self, ir: schema.Module) -> List[MutationResult]:
        """Apply layer-specific mutations and return results with metadata."""

    def _is_strategy_enabled(self, strategy_name: str) -> bool:
        """Check if a specific strategy is enabled."""
        if not self.enabled_strategies:
            return True  # All strategies enabled by default
        return strategy_name in self.enabled_strategies

    def get_success_rate(self) -> float:
        """Get the success rate of this mutator."""
        if self.mutation_count == 0:
            return 0.0
        return self.success_count / self.mutation_count

    def get_layer_name(self) -> str:
        """Get the human-readable layer name."""
        return self.layer.value.title()


# Utility functions for common mutation patterns


class LazyIRWrapper:
    """
    Wraps IR with copy-on-write semantics.

    Delays the deep copy until the IR is actually accessed for modification,
    reducing unnecessary copying overhead when mutations don't produce changes.

    Usage:
        wrapper = LazyIRWrapper(original_ir)
        ir = wrapper.get_mutable()  # Deep copy happens here
        # ... mutate ir ...
        if wrapper.was_modified:
            return ir
    """

    __slots__ = ("_original", "_copied", "_was_accessed")

    def __init__(self, original: schema.Module):
        self._original = original
        self._copied = None
        self._was_accessed = False

    def get_mutable(self) -> schema.Module:
        """Get a mutable copy of the IR (performs deep copy on first call)."""
        if self._copied is None:
            self._copied = copy.deepcopy(self._original)
        self._was_accessed = True
        return self._copied

    def get_readonly(self) -> schema.Module:
        """Get readonly access to the original IR (no copy)."""
        return self._original

    @property
    def was_modified(self) -> bool:
        """Check if the mutable IR was accessed."""
        return self._was_accessed

    @property
    def ir(self) -> schema.Module:
        """Alias for get_mutable() for convenience."""
        return self.get_mutable()


def safe_deepcopy_ir(ir: schema.Module) -> schema.Module:
    """Safely create a deep copy of IR for mutation."""
    return copy.deepcopy(ir)


def mutate_ir(ir: schema.Module) -> LazyIRWrapper:
    """
    Create a lazy copy wrapper for mutation.

    This is the preferred way to start a mutation as it delays
    deep copying until absolutely necessary.

    Usage:
        wrapper = mutate_ir(original_ir)
        mutated = wrapper.ir  # Copy happens here
        transformer.visit(mutated)
        if transformer.changed:
            return mutated
    """
    return LazyIRWrapper(ir)
