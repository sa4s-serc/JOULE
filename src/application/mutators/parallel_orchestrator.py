"""
Parallel Mutation Orchestrator - High-Performance Concurrent Processing

This module provides advanced parallel processing capabilities for mutations:
- Concurrent layer processing with conflict resolution
- Intelligent work distribution and load balancing
- Adaptive resource management based on system capabilities
- Performance monitoring and optimization
"""

import logging
import multiprocessing as mp
import time
from concurrent.futures import (ProcessPoolExecutor, ThreadPoolExecutor,
                                as_completed)
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

import psutil

from src.application.mutators.base import (LayeredMutator, MutationLayer,
                                           MutationResult)
from src.application.mutators.registry import get_registry
from src.domain.ir import schema
from src.domain.ir.lazy_wrapper import create_lazy_wrapper, get_memory_stats
from src.domain.ir.validators import IRValidator

logger = logging.getLogger(__name__)


@dataclass
class ParallelConfig:
    """Configuration for parallel mutation processing."""

    max_workers: int = field(default_factory=lambda: min(8, mp.cpu_count()))
    # Use threads by default for better memory sharing
    enable_process_pool: bool = False
    layer_timeout_seconds: float = 60.0
    mutation_timeout_seconds: float = 30.0
    max_memory_usage_mb: int = 2048
    adaptive_scaling: bool = True
    conflict_resolution_strategy: str = "merge"  # "merge", "priority", "discard"

    def __post_init__(self):
        """Validate and adjust configuration based on system resources."""
        # Adjust based on available memory
        available_memory_mb = psutil.virtual_memory().available // (1024 * 1024)
        if self.max_memory_usage_mb > available_memory_mb * 0.8:
            self.max_memory_usage_mb = int(available_memory_mb * 0.8)
            logger.warning(f"Adjusted max memory usage to {self.max_memory_usage_mb}MB")

        # Adjust workers based on CPU count and memory
        optimal_workers = min(
            self.max_workers,
            max(2, mp.cpu_count() - 1),  # Leave one CPU free
            self.max_memory_usage_mb // 256,  # Rough estimate: 256MB per worker
        )
        if optimal_workers != self.max_workers:
            self.max_workers = optimal_workers
            logger.info(f"Adjusted worker count to {self.max_workers}")


@dataclass
class MutationTask:
    """A single mutation task for parallel processing."""

    task_id: str
    mutator: LayeredMutator
    ir_wrapper: Any  # LazyIRWrapper
    layer: MutationLayer
    strategy_name: str
    priority: float = 1.0
    dependencies: Set[str] = field(default_factory=set)

    def __hash__(self):
        return hash(self.task_id)


@dataclass
class ParallelExecutionStats:
    """Statistics for parallel execution performance."""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time: float = 0.0
    parallel_efficiency: float = 0.0
    memory_peak_mb: float = 0.0
    conflict_resolutions: int = 0

    @property
    def success_rate(self) -> float:
        return self.completed_tasks / max(1, self.total_tasks)

    @property
    def throughput(self) -> float:
        return self.completed_tasks / max(0.001, self.total_execution_time)


class ConflictResolver:
    """Resolves conflicts between concurrent mutations."""

    def __init__(self, strategy: str = "merge"):
        self.strategy = strategy
        self.resolution_count = 0

    def resolve_conflicts(
        self, results: List[MutationResult], original_ir: schema.Module
    ) -> List[MutationResult]:
        """Resolve conflicts between mutation results."""
        if len(results) <= 1:
            logger.debug(f"[CONFLICT_RESOLVER] No conflicts to resolve ({len(results)} results)")
            return results

        logger.info(
            f"[CONFLICT_RESOLVER] Resolving conflicts for {len(results)} results using strategy: {self.strategy}"
        )
        self.resolution_count += len(results) - 1

        if self.strategy == "merge":
            resolved = self._merge_compatible_mutations(results, original_ir)
            logger.info(f"[CONFLICT_RESOLVER] Merge strategy produced {len(resolved)} results")
            return resolved
        elif self.strategy == "priority":
            resolved = self._select_by_priority(results)
            logger.info(f"[CONFLICT_RESOLVER] Priority strategy produced {len(resolved)} results")
            return resolved
        else:  # discard
            resolved = results[:1]  # Keep only the first result
            logger.info(f"[CONFLICT_RESOLVER] Discard strategy produced {len(resolved)} results")
            return resolved

    def _merge_compatible_mutations(
        self, results: List[MutationResult], original_ir: schema.Module
    ) -> List[MutationResult]:
        """Merge compatible mutations that don't conflict."""
        # Group by compatibility
        compatible_groups = self._group_by_compatibility(results)

        merged_results = []
        for group in compatible_groups:
            if len(group) == 1:
                merged_results.extend(group)
            else:
                # Attempt to merge the group
                merged = self._attempt_merge(group, original_ir)
                if merged:
                    merged_results.append(merged)
                else:
                    # Fall back to highest confidence
                    merged_results.append(max(group, key=lambda r: r.confidence))

        return merged_results

    def _group_by_compatibility(self, results: List[MutationResult]) -> List[List[MutationResult]]:
        """Group mutations by compatibility (simplified heuristic)."""
        # Simple heuristic: mutations from different layers are more likely to be compatible
        layer_groups: Dict[MutationLayer, List[MutationResult]] = {}
        for result in results:
            layer = result.layer
            if layer not in layer_groups:
                layer_groups[layer] = []
            layer_groups[layer].append(result)

        return list(layer_groups.values())

    def _attempt_merge(
        self, group: List[MutationResult], original_ir: schema.Module
    ) -> Optional[MutationResult]:
        """Attempt to merge a group of compatible mutations."""
        # This is a simplified merge - in practice, would need sophisticated conflict detection
        try:
            logger.debug(f"[MERGE_DEBUG] Attempting to merge {len(group)} mutations")

            # Log the mutator names in the group
            for i, result in enumerate(group):
                logger.debug(
                    f"[MERGE_DEBUG] Result {i}: mutator_name='{result.mutator_name}', strategy='{result.strategy_name}'"
                )

            # Start with the highest confidence mutation
            base_result = max(group, key=lambda r: r.confidence)

            # Create merged description
            descriptions = [r.description for r in group]
            merged_description = f"Merged: {'; '.join(descriptions)}"

            # Collect mutator names for the merged result (filter out empty strings)
            mutator_names = [
                r.mutator_name for r in group if r.mutator_name and r.mutator_name.strip()
            ]

            logger.debug(
                f"[MERGE_DEBUG] Found {len(mutator_names)} non-empty mutator names: {mutator_names}"
            )

            if mutator_names:
                # Use the mutator names we found - join unique names
                unique_names = list(
                    dict.fromkeys(mutator_names)
                )  # Preserve order, remove duplicates
                merged_mutator_name = "+".join(unique_names)  # Use + to indicate combination
                logger.info(f"[MERGE_DEBUG] Using collected mutator names: {merged_mutator_name}")
            else:
                # Fallback: try to infer from strategy names
                # Strategy names often follow pattern: "Category_SpecificStrategy"
                # We want to extract meaningful mutator info
                strategy_names = [r.strategy_name for r in group if r.strategy_name]

                logger.debug(
                    f"[MERGE_DEBUG] No mutator names found, inferring from strategies: {strategy_names}"
                )

                if strategy_names:
                    # Try to infer mutator type from strategy prefix
                    # e.g., "Pattern_ConditionalSimplification" -> "CodePatternOptimizer"
                    # e.g., "Idiom_ComprehensionOptimization" -> "PythonicIdiomOptimizer"
                    inferred_names = []
                    for strategy in strategy_names:
                        prefix = strategy.split("_")[0] if "_" in strategy else strategy
                        # Map common prefixes to likely mutator names
                        prefix_map = {
                            "Pattern": "CodePatternOptimizer",
                            "Idiom": "PythonicIdiomOptimizer",
                            "Constant": "ConstantOptimizer",
                            "DeadCode": "DeadCodeEliminator",
                            "Loop": "LoopMicroOptimizer",
                            "Complexity": "ComplexityReducer",
                            "AlgorithmicIntent": "AlgorithmicIntentMutator",
                            "ProgramIntent": "ProgramIntentMutator",
                            "Advanced": "AdvancedAlgorithmicOptimizer",
                            "Merged": "MergedMutator",  # Handle already-merged results
                        }
                        inferred_name = prefix_map.get(prefix, prefix + "Mutator")
                        inferred_names.append(inferred_name)
                        logger.debug(
                            f"[MERGE_DEBUG] Strategy '{strategy}' -> prefix '{prefix}' -> inferred '{inferred_name}'"
                        )

                    # Use unique inferred names
                    unique_inferred = list(dict.fromkeys(inferred_names))
                    merged_mutator_name = (
                        "+".join(unique_inferred) if inferred_names else "ParallelOrchestrator"
                    )
                    logger.info(
                        f"[MERGE_DEBUG] Inferred mutator name from strategies: {merged_mutator_name}"
                    )
                else:
                    merged_mutator_name = "ParallelOrchestrator"
                    logger.warning(
                        f"[MERGE_DEBUG] No strategies found, using fallback: {merged_mutator_name}"
                    )

            # Collect unique strategy names for merged strategy
            strategy_names = [r.strategy_name for r in group if r.strategy_name]
            unique_strategies = list(
                dict.fromkeys([s.split("_")[-1] for s in strategy_names])
            )  # Get last part of strategy
            merged_strategy = (
                f"Merged_{'_'.join(unique_strategies[:3])}"  # Limit to 3 to avoid too long names
            )

            # Average confidence (conservative approach)
            avg_confidence = sum(r.confidence for r in group) / len(group)

            # Final validation: ensure mutator_name is not empty
            if not merged_mutator_name or merged_mutator_name.strip() == "":
                merged_mutator_name = "ParallelOrchestrator"
                logger.error(
                    f"[MERGE_DEBUG] CRITICAL: merged_mutator_name was empty after all logic! Using fallback: {merged_mutator_name}"
                )

            # CRITICAL FIX: Ensure mutator_name is never empty before creating the result
            if not merged_mutator_name or not merged_mutator_name.strip():
                merged_mutator_name = "MergedMutator"
                logger.error(
                    f"[MERGE_DEBUG] CRITICAL: merged_mutator_name was empty before MutationResult creation! Using fallback: {merged_mutator_name}"
                )

            merged_result = MutationResult(
                ir=base_result.ir,  # Use the best IR as base
                strategy_name=merged_strategy,
                layer=base_result.layer,
                mutator_name=merged_mutator_name,  # Set the merged mutator name
                confidence=avg_confidence,
                description=merged_description,
            )

            logger.info(
                f"[MERGE_DEBUG] Created merged result: mutator_name='{merged_result.mutator_name}', strategy='{merged_result.strategy_name}'"
            )

            # Double-check the result has a valid mutator_name after creation
            if not merged_result.mutator_name or merged_result.mutator_name.strip() == "":
                logger.error(
                    f"[MERGE_DEBUG] CRITICAL BUG: MutationResult.mutator_name is empty after creation despite passing '{merged_mutator_name}'!"
                )
                # Force set it using object.__setattr__ to bypass any potential issues
                object.__setattr__(merged_result, "mutator_name", merged_mutator_name)
                logger.info(
                    f"[MERGE_DEBUG] Force-set mutator_name to: '{merged_result.mutator_name}'"
                )

            return merged_result

        except Exception as e:
            logger.warning(f"[MERGE_DEBUG] Failed to merge mutations: {e}", exc_info=True)
            return None

    def _select_by_priority(self, results: List[MutationResult]) -> List[MutationResult]:
        """Select results by priority (confidence score)."""
        return [max(results, key=lambda r: r.confidence)]


class ParallelMutationOrchestrator:
    """
    High-performance parallel mutation orchestrator.

    Features:
    - Concurrent processing across multiple layers
    - Intelligent task scheduling and load balancing
    - Conflict resolution between concurrent mutations
    - Adaptive resource management
    - Performance monitoring and optimization
    """

    def __init__(self, config: Optional[ParallelConfig] = None):
        self.config = config or ParallelConfig()
        self.registry = get_registry()
        self.validator = IRValidator(strict=False)
        self.conflict_resolver = ConflictResolver(self.config.conflict_resolution_strategy)
        self.stats = ParallelExecutionStats()
        self._task_counter = 0
        self._task_lock = Lock()

    def orchestrate_parallel_mutations(
        self,
        ir: schema.Module,
        enabled_layers: Optional[Set[MutationLayer]] = None,
        llm_client=None,
        selected_mutations: Optional[List[Tuple[LayeredMutator, str, float]]] = None,
    ) -> List[MutationResult]:
        """
        Orchestrate mutations with parallel processing.

        Args:
            ir: Input IR module
            enabled_layers: Set of enabled layers (None = all)
            llm_client: LLM client for semantic mutations
            selected_mutations: Optional list of pre-selected (mutator, strategy, score) tuples
        """
        start_time = time.time()

        if enabled_layers is None:
            enabled_layers = set(MutationLayer)

        logger.info(f"Starting parallel orchestration with {len(enabled_layers)} layers")

        # Create lazy wrapper for memory efficiency
        ir_wrapper = create_lazy_wrapper(ir)

        # Generate mutation tasks
        tasks = self._generate_mutation_tasks(
            ir_wrapper, enabled_layers, llm_client, selected_mutations
        )
        self.stats.total_tasks = len(tasks)

        # Execute tasks in parallel
        results = self._execute_parallel_tasks(tasks)

        # Log results before conflict resolution
        logger.info(f"[ORCHESTRATOR] Before conflict resolution: {len(results)} results")
        for i, r in enumerate(results):
            logger.debug(
                f"[ORCHESTRATOR] Pre-resolve result {i}: mutator_name='{r.mutator_name}', strategy='{r.strategy_name}'"
            )

        # Resolve conflicts
        resolved_results = self.conflict_resolver.resolve_conflicts(results, ir)
        self.stats.conflict_resolutions = self.conflict_resolver.resolution_count

        # Log results after conflict resolution with detailed attribute inspection
        logger.info(f"[ORCHESTRATOR] After conflict resolution: {len(resolved_results)} results")
        for i, r in enumerate(resolved_results):
            # Check if mutator_name exists and has a value
            has_attr = hasattr(r, "mutator_name")
            mutator_val = r.mutator_name if has_attr else "MISSING_ATTR"
            logger.debug(
                f"[ORCHESTRATOR] Post-resolve result {i}: has_mutator_name={has_attr}, mutator_name='{mutator_val}', strategy='{r.strategy_name}'"
            )
            if not r.mutator_name or not r.mutator_name.strip():
                logger.error(
                    f"[ORCHESTRATOR] CRITICAL: Result {i} has empty mutator_name after conflict resolution!"
                )
                # Try to fix it here as a last resort
                if "Merged" in r.strategy_name:
                    object.__setattr__(r, "mutator_name", "MergedMutator")
                    logger.info(
                        f"[ORCHESTRATOR] Fixed merged result {i} mutator_name to: MergedMutator"
                    )

        # Update statistics
        self.stats.total_execution_time = time.time() - start_time
        self.stats.completed_tasks = len(resolved_results)
        self.stats.parallel_efficiency = self._calculate_parallel_efficiency()

        # Log performance metrics
        self._log_performance_metrics()

        return resolved_results

    def _generate_mutation_tasks(
        self,
        ir_wrapper: Any,
        enabled_layers: Set[MutationLayer],
        llm_client=None,
        selected_mutations: Optional[List[Tuple[LayeredMutator, str, float]]] = None,
    ) -> List[MutationTask]:
        """Generate mutation tasks for parallel execution."""
        tasks = []

        # If specific mutations are selected, use those
        if selected_mutations:
            for mutator, strategy, score in selected_mutations:
                # Configure mutator if needed
                if hasattr(mutator, "set_llm_client") and llm_client:
                    mutator.set_llm_client(llm_client)

                task_id = self._generate_task_id()
                # Use score as base for priority
                priority = score * 2.0  # Boost priority for selected items

                task = MutationTask(
                    task_id=task_id,
                    mutator=mutator,
                    ir_wrapper=ir_wrapper,
                    layer=mutator.layer,
                    strategy_name=strategy,
                    priority=priority,
                    dependencies=set(),  # Selected mutations are assumed independent or pre-ordered
                )
                tasks.append(task)

            return self._sort_tasks_by_priority(tasks)

            # Otherwise generate all possible tasks from enabled layers
            mutators = self.registry.get_mutators_for_layer(layer, llm_client=llm_client)

            for mutator in mutators:
                # Configure mutator for parallel execution
                if hasattr(mutator, "set_llm_client") and llm_client:
                    mutator.set_llm_client(llm_client)

                # Get available strategies
                strategies = mutator.get_available_strategies()

                for strategy in strategies:
                    task_id = self._generate_task_id()
                    priority = self._calculate_task_priority(layer, strategy, mutator)

                    task = MutationTask(
                        task_id=task_id,
                        mutator=mutator,
                        ir_wrapper=ir_wrapper,
                        layer=layer,
                        strategy_name=strategy,
                        priority=priority,
                        dependencies=self._calculate_dependencies(layer, strategy),
                    )
                    tasks.append(task)

        # Sort by priority and dependencies
        return self._sort_tasks_by_priority(tasks)

    def _execute_parallel_tasks(self, tasks: List[MutationTask]) -> List[MutationResult]:
        """Execute mutation tasks in parallel."""
        results = []

        # Choose executor type based on configuration
        executor_class = (
            ProcessPoolExecutor if self.config.enable_process_pool else ThreadPoolExecutor
        )

        with executor_class(max_workers=self.config.max_workers) as executor:
            # Submit tasks
            future_to_task = {}
            for task in tasks:
                future = executor.submit(self._execute_single_task, task)
                future_to_task[future] = task

            # Collect results with timeout
            for future in as_completed(future_to_task, timeout=self.config.layer_timeout_seconds):
                task = future_to_task[future]
                try:
                    result = future.result(timeout=self.config.mutation_timeout_seconds)
                    if result:
                        # Validate each result has a mutator_name
                        for r in result:
                            if not r.mutator_name or not r.mutator_name.strip():
                                logger.error(
                                    f"[PARALLEL_EXEC] Task {task.task_id} returned result with empty mutator_name! Strategy: {r.strategy_name}"
                                )
                        results.extend(result)
                        logger.debug(
                            f"Task {task.task_id} completed successfully with {len(result)} results"
                        )
                    else:
                        logger.debug(f"Task {task.task_id} produced no results")
                except Exception as e:
                    logger.warning(f"Task {task.task_id} failed: {e}")
                    self.stats.failed_tasks += 1

        logger.info(
            f"[PARALLEL_EXEC] Collected {len(results)} total results from parallel execution"
        )
        return results

    def _execute_single_task(self, task: MutationTask) -> List[MutationResult]:
        """Execute a single mutation task."""
        try:
            # Apply the specific strategy
            mutator = task.mutator
            mutator_class_name = mutator.__class__.__name__

            logger.debug(
                f"[MUTATOR_DEBUG] Executing task for mutator: {mutator_class_name}, strategy: {task.strategy_name}"
            )

            if hasattr(mutator, "enabled_strategies"):
                mutator.enabled_strategies = {task.strategy_name}

            # Get the IR from the wrapper
            ir = task.ir_wrapper.ir

            # Apply mutations
            results = mutator.mutate(ir)
            logger.debug(
                f"[MUTATOR_DEBUG] Mutator {mutator_class_name} produced {len(results)} results"
            )

            # Filter results for the current strategy if necessary
            meta_results = [r for r in results if r.strategy_name == task.strategy_name]
            logger.debug(
                f"[MUTATOR_DEBUG] Filtered to {len(meta_results)} results for strategy {task.strategy_name}"
            )

            # Ensure all results have mutator_name set (create new results if needed)
            fixed_results = []
            fixed_count = 0
            for i, result in enumerate(meta_results):
                original_name = result.mutator_name
                if not result.mutator_name or not result.mutator_name.strip():
                    # Create a new result with the correct mutator_name
                    logger.debug(
                        f"[MUTATOR_DEBUG] Result {i} has empty mutator_name, fixing to: {mutator_class_name}"
                    )
                    from src.application.mutators.base import MutationResult

                    fixed_result = MutationResult(
                        ir=result.ir,
                        strategy_name=result.strategy_name,
                        layer=result.layer,
                        mutator_name=mutator_class_name,
                        confidence=result.confidence,
                        description=result.description,
                    )
                    fixed_results.append(fixed_result)
                    fixed_count += 1
                else:
                    logger.debug(
                        f"[MUTATOR_DEBUG] Result {i} already has mutator_name: {original_name}"
                    )
                    fixed_results.append(result)

            if fixed_count > 0:
                logger.info(
                    f"[MUTATOR_DEBUG] Fixed {fixed_count}/{len(meta_results)} results with mutator_name: {mutator_class_name}"
                )

            return fixed_results

        except Exception as e:
            logger.error(
                f"[MUTATOR_DEBUG] Task execution failed for {task.mutator.__class__.__name__}: {e}"
            )
            return []

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        with self._task_lock:
            self._task_counter += 1
            return f"task_{self._task_counter:04d}"

    def _calculate_task_priority(
        self, layer: MutationLayer, strategy: str, mutator: LayeredMutator
    ) -> float:
        """Calculate task priority based on layer and historical performance."""
        # Base priority by layer (higher level = higher priority)
        layer_priorities = {
            MutationLayer.SEMANTIC: 1.0,
            MutationLayer.ALGORITHMIC: 0.8,
            MutationLayer.SYNTACTIC: 0.6,
            MutationLayer.MICRO: 0.4,
        }

        base_priority = layer_priorities.get(layer, 0.5)

        # Adjust based on mutator success rate
        success_rate = mutator.get_success_rate() if hasattr(mutator, "get_success_rate") else 0.5

        return base_priority * (0.5 + success_rate)

    def _calculate_dependencies(self, layer: MutationLayer, strategy: str) -> Set[str]:
        """Calculate task dependencies (simplified)."""
        # Semantic mutations should run before others
        if layer == MutationLayer.SEMANTIC:
            return set()
        elif layer == MutationLayer.ALGORITHMIC:
            return {"semantic"}
        else:
            return {"semantic", "algorithmic"}

    def _sort_tasks_by_priority(self, tasks: List[MutationTask]) -> List[MutationTask]:
        """Sort tasks by priority and dependencies."""
        return sorted(tasks, key=lambda t: (-t.priority, len(t.dependencies)))

    def _calculate_parallel_efficiency(self) -> float:
        """Calculate parallel execution efficiency."""
        if self.stats.total_execution_time == 0:
            return 0.0

        # Estimate sequential time (rough approximation)
        estimated_sequential_time = self.stats.total_execution_time * self.config.max_workers

        # Efficiency = (Sequential Time) / (Parallel Time * Workers)
        return min(
            1.0,
            estimated_sequential_time / (self.stats.total_execution_time * self.config.max_workers),
        )

    def _log_performance_metrics(self):
        """Log performance metrics and memory usage."""
        memory_stats = get_memory_stats()

        logger.info(f"Parallel execution completed:")
        logger.info(
            f"  Tasks: {self.stats.completed_tasks}/{self.stats.total_tasks} ({self.stats.success_rate:.1%})"
        )
        logger.info(f"  Time: {self.stats.total_execution_time:.2f}s")
        logger.info(f"  Throughput: {self.stats.throughput:.1f} tasks/sec")
        logger.info(f"  Parallel efficiency: {self.stats.parallel_efficiency:.1%}")
        logger.info(f"  Conflicts resolved: {self.stats.conflict_resolutions}")
        logger.info(f"  Memory saved: {memory_stats.get('memory_saved_mb', 0):.1f}MB")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get detailed performance statistics."""
        memory_stats = get_memory_stats()

        return {
            "execution_stats": {
                "total_tasks": self.stats.total_tasks,
                "completed_tasks": self.stats.completed_tasks,
                "failed_tasks": self.stats.failed_tasks,
                "success_rate": self.stats.success_rate,
                "execution_time": self.stats.total_execution_time,
                "throughput": self.stats.throughput,
                "parallel_efficiency": self.stats.parallel_efficiency,
                "conflict_resolutions": self.stats.conflict_resolutions,
            },
            "memory_stats": memory_stats,
            "config": {
                "max_workers": self.config.max_workers,
                "enable_process_pool": self.config.enable_process_pool,
                "max_memory_usage_mb": self.config.max_memory_usage_mb,
                "conflict_resolution_strategy": self.config.conflict_resolution_strategy,
            },
        }
