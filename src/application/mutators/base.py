"""
Base Mutation System - Hierarchical Abstraction Layer

This module defines the core abstraction for HEDGE's hierarchical mutation system.
Mutations are organized in layers from high-level semantic changes down to 
low-level syntactic optimizations.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass
import copy
import logging

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
    SEMANTIC = "semantic"        # Algorithm intent and high-level logic
    ALGORITHMIC = "algorithmic"  # Data structures and complexity
    SYNTACTIC = "syntactic"      # Code patterns and idioms
    MICRO = "micro"             # Low-level optimizations


@dataclass
class MutationResult:
    """Result of a mutation operation with metadata."""
    ir: schema.Module
    strategy_name: str
    layer: MutationLayer
    confidence: float = 1.0  # Confidence in the mutation (0.0 to 1.0)
    description: str = ""    # Human-readable description of the change


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
    
    @abstractmethod
    def get_available_strategies(self) -> List[str]:
        """Return list of available mutation strategies for this mutator."""
        pass
    
    @abstractmethod
    def _apply_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply layer-specific mutations and return results with metadata."""
        pass
    
    def mutate(self, ir: schema.Module) -> List[Tuple[schema.Module, str]]:
        """
        Main mutation interface - applies mutations and returns IR variants.
        
        This method wraps _apply_mutations to maintain compatibility with
        the existing Mutator interface while providing enhanced metadata.
        """
        try:
            results = self._apply_mutations(ir)
            self.mutation_count += len(results)
            
            # Convert to legacy format for compatibility
            variants = []
            for result in results:
                if self._is_strategy_enabled(result.strategy_name):
                    variants.append((result.ir, result.strategy_name))
                    self.success_count += 1
            
            return variants
            
        except Exception as e:
            logger.error(f"Mutation failed in {self.__class__.__name__}: {e}")
            return []
    
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


# Legacy orchestrator - replaced by orchestrator_v2.py
# Kept for backward compatibility
class MutationOrchestrator:
    """
    DEPRECATED: Use EnhancedMutationOrchestrator from orchestrator_v2.py instead.
    
    Legacy orchestrator for mutations across different layers.
    """
    
    def __init__(self):
        logger.warning("MutationOrchestrator is deprecated. Use EnhancedMutationOrchestrator instead.")
        self.mutators_by_layer = {layer: [] for layer in MutationLayer}
        self.layer_order = [
            MutationLayer.SEMANTIC,
            MutationLayer.ALGORITHMIC, 
            MutationLayer.SYNTACTIC,
            MutationLayer.MICRO
        ]
    
    def register_mutator(self, mutator: LayeredMutator):
        """Register a mutator for its specific layer."""
        self.mutators_by_layer[mutator.layer].append(mutator)
        logger.debug(f"Registered {mutator.__class__.__name__} for {mutator.layer.value} layer")
    
    def apply_layered_mutations(self, ir: schema.Module, 
                              enabled_layers: Optional[Set[MutationLayer]] = None) -> List[Tuple[schema.Module, str]]:
        """Apply mutations in hierarchical order across enabled layers."""
        if enabled_layers is None:
            enabled_layers = set(MutationLayer)
        
        all_variants = []
        
        for layer in self.layer_order:
            if layer not in enabled_layers:
                continue
                
            layer_variants = []
            mutators = self.mutators_by_layer[layer]
            
            logger.debug(f"Applying {len(mutators)} mutators for {layer.value} layer")
            
            for mutator in mutators:
                try:
                    variants = mutator.mutate(ir)
                    layer_variants.extend(variants)
                    logger.debug(f"{mutator.__class__.__name__} produced {len(variants)} variants")
                except Exception as e:
                    logger.error(f"Mutator {mutator.__class__.__name__} failed: {e}")
            
            all_variants.extend(layer_variants)
        
        return all_variants
    
    def get_layer_statistics(self) -> dict:
        """Get statistics for each layer."""
        stats = {}
        for layer, mutators in self.mutators_by_layer.items():
            layer_stats = {
                'mutator_count': len(mutators),
                'total_mutations': sum(m.mutation_count for m in mutators),
                'total_successes': sum(m.success_count for m in mutators),
                'average_success_rate': sum(m.get_success_rate() for m in mutators) / len(mutators) if mutators else 0.0
            }
            stats[layer.value] = layer_stats
        return stats


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
    
    __slots__ = ('_original', '_copied', '_was_accessed')
    
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


def create_mutation_result(ir: schema.Module, strategy_name: str, layer: MutationLayer,
                         confidence: float = 1.0, description: str = "") -> MutationResult:
    """Helper to create a MutationResult with proper metadata."""
    return MutationResult(
        ir=ir,
        strategy_name=strategy_name,
        layer=layer,
        confidence=confidence,
        description=description
    )