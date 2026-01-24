"""
Mutation Orchestrator - Intelligent Hierarchical Coordination

This is the main orchestrator for HEDGE's mutation system, providing:
- Early pruning to prevent exponential growth
- Adaptive layer selection based on performance
- Parallel mutation generation
- Smart conflict resolution
- Registry-based mutator management
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from src.application.mutators.base import (LayeredMutator, MutationLayer,
                                           MutationResult)
from src.application.mutators.registry import get_registry
from src.domain.ir import schema
from src.domain.ir.validators import IRValidator

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationConfig:
    """Configuration for mutation orchestration."""

    max_variants_per_layer: int = 5
    max_total_variants: int = 20
    enable_parallel_mutations: bool = False
    max_workers: int = 4
    early_pruning_threshold: float = 0.3
    adaptive_selection: bool = True
    layer_timeout_seconds: float = 30.0


@dataclass
class LayerResult:
    """Results from a single layer of mutations."""

    layer: MutationLayer
    variants: List[MutationResult]
    execution_time: float
    success_rate: float
    pruned_count: int = 0


class MutationOrchestrator:
    """
    Main orchestrator with intelligent coordination and pruning.

    Features:
    - Early pruning to prevent exponential variant growth
    - Adaptive mutator selection based on historical performance
    - Parallel mutation generation for better performance
    - Smart conflict resolution between mutators
    - Registry-based mutator management
    """

    def __init__(self, config: Optional[OrchestrationConfig] = None):
        self.config = config or OrchestrationConfig()
        self.registry = get_registry()
        self.validator = IRValidator(strict=False)
        self.layer_history: Dict[MutationLayer, List[float]] = {
            layer: [] for layer in MutationLayer
        }

    def orchestrate_mutations(
        self,
        ir: schema.Module,
        enabled_layers: Optional[Set[MutationLayer]] = None,
        llm_client=None,
    ) -> List[MutationResult]:
        """
        Orchestrate hierarchical mutations with intelligent coordination.

        Args:
            ir: Input IR module
            enabled_layers: Set of enabled layers (None = all)
            llm_client: LLM client for semantic mutations

        Returns:
            List of mutation results, pruned and optimized
        """
        if enabled_layers is None:
            enabled_layers = set(MutationLayer)

        logger.info(f"Starting orchestration with {len(enabled_layers)} layers")

        # Start with the original IR
        current_variants = [
            MutationResult(
                ir=ir,
                strategy_name="original",
                layer=MutationLayer.SEMANTIC,  # Placeholder
                confidence=1.0,
                description="Original code",
            )
        ]

        all_results = []
        layer_order = self._get_layer_order(enabled_layers)

        for layer in layer_order:
            logger.info(f"Processing layer: {layer.value}")

            layer_start_time = time.time()
            layer_variants = []

            # Get mutators for this layer
            mutators = self._get_layer_mutators(layer, llm_client)

            if not mutators:
                logger.warning(f"No mutators available for layer {layer.value}")
                continue

            # Apply mutations to current variants
            if self.config.enable_parallel_mutations:
                layer_variants = self.mutate_parallel(current_variants, mutators, layer)
            else:
                layer_variants = self.mutate_sequential(current_variants, mutators, layer)

            # Early pruning
            pruned_variants, pruned_count = self._prune_variants(
                layer_variants, self.config.max_variants_per_layer
            )

            layer_time = time.time() - layer_start_time
            success_rate = len(pruned_variants) / max(1, len(layer_variants))

            # Record layer performance
            self.layer_history[layer].append(success_rate)

            # Create layer result
            layer_result = LayerResult(
                layer=layer,
                variants=pruned_variants,
                execution_time=layer_time,
                success_rate=success_rate,
                pruned_count=pruned_count,
            )

            logger.info(
                f"Layer {layer.value} completed: "
                f"{len(pruned_variants)} variants, "
                f"{success_rate:.2%} success rate, "
                f"{layer_time:.2f}s"
            )

            # Update current variants for next layer
            current_variants.extend(pruned_variants)
            all_results.extend(pruned_variants)

            # Global pruning if too many variants
            if len(current_variants) > self.config.max_total_variants:
                current_variants, _ = self._prune_variants(
                    current_variants, self.config.max_total_variants
                )

        # Final pruning and ranking
        final_results, _ = self._prune_variants(all_results, self.config.max_total_variants)

        logger.info(f"Orchestration completed: {len(final_results)} final variants")
        return final_results

    def _get_layer_order(self, enabled_layers: Set[MutationLayer]) -> List[MutationLayer]:
        """Get the order in which to apply layers."""
        # Standard hierarchical order: Semantic -> Algorithmic -> Syntactic -> Micro
        standard_order = [
            MutationLayer.SEMANTIC,
            MutationLayer.ALGORITHMIC,
            MutationLayer.SYNTACTIC,
            MutationLayer.MICRO,
        ]

        return [layer for layer in standard_order if layer in enabled_layers]

    def _get_layer_mutators(self, layer: MutationLayer, llm_client=None) -> List[LayeredMutator]:
        """Get mutators for a specific layer with adaptive selection."""
        if self.config.adaptive_selection:
            mutator_names = self.registry.get_adaptive_selection(layer, max_mutators=3)
        else:
            mutator_names = self.registry.get_layer_mutators(layer)

        mutators = []
        for name in mutator_names:
            mutator = self.registry.get_mutator(name)
            if mutator:
                # Inject LLM client for semantic mutators
                if hasattr(mutator, "llm_client") and llm_client:
                    mutator.llm_client = llm_client
                mutators.append(mutator)

        return mutators

    def mutate_sequential(
        self, variants: List[MutationResult], mutators: List[LayeredMutator], layer: MutationLayer
    ) -> List[MutationResult]:
        """Apply mutations sequentially."""
        layer_variants = []

        for variant in variants:
            for mutator in mutators:
                try:
                    start_time = time.time()
                    results = mutator.mutate(variant.ir)
                    execution_time = time.time() - start_time

                    # Update mutator metrics
                    for result in results:
                        self.registry.update_metrics(
                            mutator.__class__.__name__, result, execution_time
                        )

                    layer_variants.extend(results)

                except Exception as e:
                    logger.error(f"Mutation failed in {mutator.__class__.__name__}: {e}")

        return layer_variants

    def mutate_parallel(
        self, variants: List[MutationResult], mutators: List[LayeredMutator], layer: MutationLayer
    ) -> List[MutationResult]:
        """Apply mutations in parallel."""
        layer_variants = []

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all mutation tasks
            futures = []

            for variant in variants:
                for mutator in mutators:
                    future = executor.submit(
                        self._apply_single_mutation, variant.ir, mutator, mutator.__class__.__name__
                    )
                    futures.append(future)

            # Collect results
            for future in as_completed(futures, timeout=self.config.layer_timeout_seconds):
                try:
                    results = future.result()
                    if results:
                        layer_variants.extend(results)
                except Exception as e:
                    logger.error(f"Parallel mutation failed: {e}")

        return layer_variants

    def _apply_single_mutation(
        self, ir: schema.Module, mutator: LayeredMutator, mutator_name: str
    ) -> List[MutationResult]:
        """Apply a single mutation (for parallel execution)."""
        try:
            start_time = time.time()
            results = mutator.mutate(ir)
            execution_time = time.time() - start_time

            # Update metrics
            for result in results:
                self.registry.update_metrics(mutator_name, result, execution_time)

            return results

        except Exception as e:
            logger.error(f"Single mutation failed in {mutator_name}: {e}")
            return []

    def _prune_variants(
        self, variants: List[MutationResult], max_variants: int
    ) -> Tuple[List[MutationResult], int]:
        """
        Prune variants using intelligent selection criteria.

        Args:
            variants: List of variants to prune
            max_variants: Maximum number to keep

        Returns:
            Tuple of (pruned_variants, pruned_count)
        """
        if len(variants) <= max_variants:
            return variants, 0

        # Score variants based on multiple criteria
        scored_variants = []

        for variant in variants:
            score = self._calculate_variant_score(variant)
            scored_variants.append((score, variant))

        # Sort by score (descending) and take top variants
        scored_variants.sort(key=lambda x: x[0], reverse=True)

        pruned = [variant for _, variant in scored_variants[:max_variants]]
        pruned_count = len(variants) - len(pruned)

        return pruned, pruned_count

    def _calculate_variant_score(self, variant: MutationResult) -> float:
        """
        Calculate a score for variant selection.

        Args:
            variant: The variant to score

        Returns:
            Score (higher is better)
        """
        # Base score from confidence
        score = variant.confidence

        # Bonus for certain strategy types
        if "Complexity" in variant.strategy_name:
            score += 0.2  # Complexity improvements are valuable

        if "Constant" in variant.strategy_name:
            score += 0.1  # Constant optimizations are safe

        # Penalty for very low confidence
        if variant.confidence < self.config.early_pruning_threshold:
            score *= 0.5

        return score

    def get_orchestration_statistics(self) -> Dict[str, Any]:
        """Get statistics about orchestration performance."""
        stats = {
            "layer_history": {
                layer.value: {
                    "avg_success_rate": sum(history) / len(history) if history else 0.0,
                    "total_runs": len(history),
                }
                for layer, history in self.layer_history.items()
            },
            "mutator_stats": self.registry.get_statistics(),
            "config": {
                "max_variants_per_layer": self.config.max_variants_per_layer,
                "max_total_variants": self.config.max_total_variants,
                "parallel_enabled": self.config.enable_parallel_mutations,
                "adaptive_selection": self.config.adaptive_selection,
            },
        }

        return stats
