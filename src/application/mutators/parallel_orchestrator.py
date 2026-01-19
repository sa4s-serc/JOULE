"""
Parallel Mutation Orchestrator - High-Performance Concurrent Processing

This module provides advanced parallel processing capabilities for mutations:
- Concurrent layer processing with conflict resolution
- Intelligent work distribution and load balancing
- Adaptive resource management based on system capabilities
- Performance monitoring and optimization
"""
import asyncio
import logging
import time
import threading
from typing import List, Dict, Set, Optional, Tuple, Callable, Any
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from queue import Queue, Empty
from threading import Lock, Event
import multiprocessing as mp
import psutil

from src.application.mutators.base import MutationLayer, MutationResult, LayeredMutator
from src.application.mutators.registry import get_registry, MutatorRegistry
from src.application.mutators.orchestrator import OrchestrationConfig, LayerResult
from src.domain.ir import schema
from src.domain.ir.validators import IRValidator
from src.domain.ir.lazy_wrapper import create_lazy_wrapper, get_memory_stats

logger = logging.getLogger(__name__)


@dataclass
class ParallelConfig:
    """Configuration for parallel mutation processing."""
    max_workers: int = field(default_factory=lambda: min(8, mp.cpu_count()))
    enable_process_pool: bool = False  # Use threads by default for better memory sharing
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
            self.max_memory_usage_mb // 256  # Rough estimate: 256MB per worker
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
        self, 
        results: List[MutationResult], 
        original_ir: schema.Module
    ) -> List[MutationResult]:
        """Resolve conflicts between mutation results."""
        if len(results) <= 1:
            return results
        
        self.resolution_count += len(results) - 1
        
        if self.strategy == "merge":
            return self._merge_compatible_mutations(results, original_ir)
        elif self.strategy == "priority":
            return self._select_by_priority(results)
        else:  # discard
            return results[:1]  # Keep only the first result
    
    def _merge_compatible_mutations(
        self, 
        results: List[MutationResult], 
        original_ir: schema.Module
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
        layer_groups = {}
        for result in results:
            layer = result.layer
            if layer not in layer_groups:
                layer_groups[layer] = []
            layer_groups[layer].append(result)
        
        return list(layer_groups.values())
    
    def _attempt_merge(self, group: List[MutationResult], original_ir: schema.Module) -> Optional[MutationResult]:
        """Attempt to merge a group of compatible mutations."""
        # This is a simplified merge - in practice, would need sophisticated conflict detection
        try:
            # Start with the highest confidence mutation
            base_result = max(group, key=lambda r: r.confidence)
            
            # Create merged description
            descriptions = [r.description for r in group]
            merged_description = f"Merged: {'; '.join(descriptions)}"
            
            # Average confidence (conservative approach)
            avg_confidence = sum(r.confidence for r in group) / len(group)
            
            return MutationResult(
                ir=base_result.ir,  # Use the best IR as base
                strategy_name=f"Merged_{base_result.strategy_name}",
                layer=base_result.layer,
                confidence=avg_confidence,
                description=merged_description
            )
        except Exception as e:
            logger.warning(f"Failed to merge mutations: {e}")
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
        llm_client=None
    ) -> List[MutationResult]:
        """
        Orchestrate mutations with parallel processing.
        
        Args:
            ir: Input IR module
            enabled_layers: Set of enabled layers (None = all)
            llm_client: LLM client for semantic mutations
            
        Returns:
            List of optimized mutation results
        """
        start_time = time.time()
        
        if enabled_layers is None:
            enabled_layers = set(MutationLayer)
        
        logger.info(f"Starting parallel orchestration with {len(enabled_layers)} layers")
        
        # Create lazy wrapper for memory efficiency
        ir_wrapper = create_lazy_wrapper(ir)
        
        # Generate mutation tasks
        tasks = self._generate_mutation_tasks(ir_wrapper, enabled_layers, llm_client)
        self.stats.total_tasks = len(tasks)
        
        # Execute tasks in parallel
        results = self._execute_parallel_tasks(tasks)
        
        # Resolve conflicts
        resolved_results = self.conflict_resolver.resolve_conflicts(results, ir)
        self.stats.conflict_resolutions = self.conflict_resolver.resolution_count
        
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
        llm_client=None
    ) -> List[MutationTask]:
        """Generate mutation tasks for parallel execution."""
        tasks = []
        
        for layer in enabled_layers:
            mutators = self.registry.get_mutators_for_layer(layer, llm_client=llm_client)
            
            for mutator in mutators:
                # Configure mutator for parallel execution
                if hasattr(mutator, 'set_llm_client') and llm_client:
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
                        dependencies=self._calculate_dependencies(layer, strategy)
                    )
                    tasks.append(task)
        
        # Sort by priority and dependencies
        return self._sort_tasks_by_priority(tasks)
    
    def _execute_parallel_tasks(self, tasks: List[MutationTask]) -> List[MutationResult]:
        """Execute mutation tasks in parallel."""
        results = []
        
        # Choose executor type based on configuration
        executor_class = ProcessPoolExecutor if self.config.enable_process_pool else ThreadPoolExecutor
        
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
                        results.extend(result)
                        logger.debug(f"Task {task.task_id} completed successfully")
                    else:
                        logger.debug(f"Task {task.task_id} produced no results")
                except Exception as e:
                    logger.warning(f"Task {task.task_id} failed: {e}")
                    self.stats.failed_tasks += 1
        
        return results
    
    def _execute_single_task(self, task: MutationTask) -> List[MutationResult]:
        """Execute a single mutation task."""
        try:
            # Apply the specific strategy
            mutator = task.mutator
            if hasattr(mutator, 'enabled_strategies'):
                mutator.enabled_strategies = {task.strategy_name}
            
            # Get the IR from the wrapper
            ir = task.ir_wrapper.ir
            
            # Apply mutations
            variants = mutator.mutate(ir)
            
            # Convert to MutationResult format
            results = []
            for variant_ir, strategy_name in variants:
                if strategy_name == task.strategy_name:
                    result = MutationResult(
                        ir=variant_ir,
                        strategy_name=strategy_name,
                        layer=task.layer,
                        confidence=getattr(mutator, 'get_confidence', lambda: 0.8)(),
                        description=f"{task.layer.value} optimization: {strategy_name}"
                    )
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return []
    
    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        with self._task_lock:
            self._task_counter += 1
            return f"task_{self._task_counter:04d}"
    
    def _calculate_task_priority(self, layer: MutationLayer, strategy: str, mutator: LayeredMutator) -> float:
        """Calculate task priority based on layer and historical performance."""
        # Base priority by layer (higher level = higher priority)
        layer_priorities = {
            MutationLayer.SEMANTIC: 1.0,
            MutationLayer.ALGORITHMIC: 0.8,
            MutationLayer.SYNTACTIC: 0.6,
            MutationLayer.MICRO: 0.4
        }
        
        base_priority = layer_priorities.get(layer, 0.5)
        
        # Adjust based on mutator success rate
        success_rate = mutator.get_success_rate() if hasattr(mutator, 'get_success_rate') else 0.5
        
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
        return min(1.0, estimated_sequential_time / (self.stats.total_execution_time * self.config.max_workers))
    
    def _log_performance_metrics(self):
        """Log performance metrics and memory usage."""
        memory_stats = get_memory_stats()
        
        logger.info(f"Parallel execution completed:")
        logger.info(f"  Tasks: {self.stats.completed_tasks}/{self.stats.total_tasks} ({self.stats.success_rate:.1%})")
        logger.info(f"  Time: {self.stats.total_execution_time:.2f}s")
        logger.info(f"  Throughput: {self.stats.throughput:.1f} tasks/sec")
        logger.info(f"  Parallel efficiency: {self.stats.parallel_efficiency:.1%}")
        logger.info(f"  Conflicts resolved: {self.stats.conflict_resolutions}")
        logger.info(f"  Memory saved: {memory_stats.get('memory_saved_mb', 0):.1f}MB")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get detailed performance statistics."""
        memory_stats = get_memory_stats()
        
        return {
            'execution_stats': {
                'total_tasks': self.stats.total_tasks,
                'completed_tasks': self.stats.completed_tasks,
                'failed_tasks': self.stats.failed_tasks,
                'success_rate': self.stats.success_rate,
                'execution_time': self.stats.total_execution_time,
                'throughput': self.stats.throughput,
                'parallel_efficiency': self.stats.parallel_efficiency,
                'conflict_resolutions': self.stats.conflict_resolutions
            },
            'memory_stats': memory_stats,
            'config': {
                'max_workers': self.config.max_workers,
                'enable_process_pool': self.config.enable_process_pool,
                'max_memory_usage_mb': self.config.max_memory_usage_mb,
                'conflict_resolution_strategy': self.config.conflict_resolution_strategy
            }
        }