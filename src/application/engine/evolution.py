"""
Evolutionary Engine - High-Performance IR-Only Optimization System

This is the core orchestration layer that coordinates:
- IR parsing and validation
- Mutation generation with parallel processing
- Code reconstruction
- Evaluation and Pareto optimization
- Intelligent mutation selection
- Memory-optimized IR handling

Key principles:
1. IR is the single source of truth
2. All mutations are validated before evaluation
3. Code is reconstructed from IR (never cached)
4. Comprehensive metrics and instrumentation
5. Parallel processing for optimal performance
"""

import hashlib
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.application.engine.crossover import CrossoverManager
from src.application.mutators.base import MutationLayer
from src.application.mutators.intelligent_selector import \
    get_intelligent_selector
from src.application.mutators.parallel_orchestrator import (
    ParallelConfig, ParallelMutationOrchestrator)
from src.domain.interfaces import CodeRunner, Mutator
from src.domain.ir.lazy_wrapper import create_lazy_wrapper, get_memory_stats
from src.domain.ir.metrics import IRMetricsCollector, MutationStatistics
from src.domain.ir.schema import Module
from src.domain.ir.serialization import IRSerializer
from src.domain.ir.validators import IRValidator
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.llm.batch_client import create_batch_llm_client
from src.infrastructure.parsing.python_parser import PythonParser

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types for optimization hooks."""

    OPTIMIZATION_START = "optimization_start"
    OPTIMIZATION_COMPLETE = "optimization_complete"
    GENERATION_START = "generation_start"
    GENERATION_COMPLETE = "generation_complete"
    MUTATION_ATTEMPT = "mutation_attempt"
    MUTATION_RESULT = "mutation_result"
    NEW_BEST_SOLUTION = "new_best_solution"


@dataclass
class OptimizationEvent:
    """Event data structure."""

    type: EventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class Solution:
    """Enhanced solution with lazy IR wrapper."""

    ir: Module
    metrics: Dict[str, float]
    variant_id: str
    parent_id: str
    mutation_type: str
    generation: int
    lazy_wrapper: Optional[Any] = None  # LazyIRWrapper

    def __post_init__(self):
        """Initialize lazy wrapper if not provided."""
        if self.lazy_wrapper is None:
            self.lazy_wrapper = create_lazy_wrapper(self.ir)


@dataclass
class EngineConfig:
    """Configuration for the evolutionary engine."""

    generations: int = 10
    population_size: int = 5
    archive_max_size: int = 50
    crossover_rate: float = 0.3
    min_mutator_prob: float = 0.2
    save_ir_snapshots: bool = False

    # Performance optimizations
    enable_parallel_mutations: bool = True
    enable_intelligent_selection: bool = True
    enable_batch_llm: bool = True
    enable_memory_optimization: bool = True

    # Resource limits
    max_memory_usage_mb: int = 2048
    max_concurrent_mutations: int = 8
    llm_batch_size: int = 5

    # Adaptive parameters
    adaptive_population_size: bool = True
    adaptive_mutation_rate: bool = True
    early_stopping_patience: int = 5


class ParetoArchive:
    """Pareto archive with memory optimization and diversity preservation."""

    def __init__(
        self,
        max_size: int = 50,
        objectives: Tuple[str, ...] = ("energy_joules", "duration_seconds"),
    ):
        self.solutions: List[Solution] = []
        self.max_size = max_size
        self._objectives = objectives
        self._solution_hashes: Set[str] = set()

    def _get_solution_hash(self, solution: Solution) -> str:
        """Get hash for solution deduplication, ignoring non-functional metadata."""
        import json

        def _clean_node(node):
            if hasattr(node, "model_dump"):
                d = node.model_dump()
                # Crucial: include node type for disambiguation
                res = {"_type": node.__class__.__name__}
                for k, v in d.items():
                    if k not in {
                        "metadata",
                        "lineno",
                        "col_offset",
                        "end_lineno",
                        "end_col_offset",
                    }:
                        res[k] = _clean_node(getattr(node, k))
                return res
            elif isinstance(node, dict):
                return {k: _clean_node(v) for k, v in node.items()}
            elif isinstance(node, list):
                return [_clean_node(x) for x in node]
            return node

        ir_dict = _clean_node(solution.ir)
        serialized = json.dumps(ir_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _get_objective(self, sol: Solution, obj: str) -> float:
        """Get objective value with default for missing metrics."""
        return sol.metrics.get(obj, float("inf"))

    def _dominates(self, sol_a: Solution, sol_b: Solution) -> bool:
        """Check if sol_a dominates sol_b."""
        dominated_in_one = False

        for obj in self._objectives:
            a_val = self._get_objective(sol_a, obj)
            b_val = self._get_objective(sol_b, obj)

            if a_val > b_val:
                return False
            if a_val < b_val:
                dominated_in_one = True

        return dominated_in_one

    def update(self, new_solution: Solution) -> bool:
        """Add solution if non-dominated and not duplicate."""
        # Check for duplicates
        solution_hash = self._get_solution_hash(new_solution)
        if solution_hash in self._solution_hashes:
            logger.debug(
                f"Solution {new_solution.variant_id[:8]} rejected as duplicate")
            return False

        # Check if dominated by existing solution
        for sol in self.solutions:
            if self._dominates(sol, new_solution):
                logger.debug(
                    f"Solution {new_solution.variant_id[:8]} dominated by {sol.variant_id[:8]}"
                )
                return False

        # Remove solutions dominated by new one
        original_count = len(self.solutions)
        self.solutions = [
            s for s in self.solutions if not self._dominates(new_solution, s)]
        removed_count = original_count - len(self.solutions)
        if removed_count > 0:
            logger.debug(
                f"Solution {new_solution.variant_id[:8]} dominated {removed_count} existing solutions"
            )

        # Update hash set
        self._solution_hashes = {
            self._get_solution_hash(s) for s in self.solutions}

        # Add new solution
        self.solutions.append(new_solution)
        self._solution_hashes.add(solution_hash)
        logger.debug(
            f"Solution {new_solution.variant_id[:8]} added to archive (total: {len(self.solutions)})"
        )

        # Maintain diversity if over capacity
        if len(self.solutions) > self.max_size:
            self._prune_crowded()

        return True

    def _prune_crowded(self):
        """Remove most crowded solutions."""
        if len(self.solutions) <= self.max_size:
            return

        distances = self._crowding_distance(self.solutions)
        self.solutions.sort(key=lambda s: distances[s.variant_id])
        num_remove = len(self.solutions) - self.max_size

        # Remove most crowded solutions
        removed_solutions = self.solutions[:num_remove]
        self.solutions = self.solutions[num_remove:]

        # Update hash set
        for sol in removed_solutions:
            sol_hash = self._get_solution_hash(sol)
            self._solution_hashes.discard(sol_hash)

    def _crowding_distance(self, solutions: List[Solution]) -> Dict[str, float]:
        """Calculate crowding distance for diversity preservation."""
        n = len(solutions)
        if n <= 2:
            return {sol.variant_id: float("inf") for sol in solutions}

        distances = {sol.variant_id: 0.0 for sol in solutions}

        for obj in self._objectives:
            sorted_sols = sorted(
                solutions, key=lambda s: self._get_objective(s, obj))

            distances[sorted_sols[0].variant_id] = float("inf")
            distances[sorted_sols[-1].variant_id] = float("inf")

            obj_min = self._get_objective(sorted_sols[0], obj)
            obj_max = self._get_objective(sorted_sols[-1], obj)
            obj_range = obj_max - obj_min

            if obj_range > 0:
                for i in range(1, n - 1):
                    if distances[sorted_sols[i].variant_id] != float("inf"):
                        prev_val = self._get_objective(sorted_sols[i - 1], obj)
                        next_val = self._get_objective(sorted_sols[i + 1], obj)
                        distances[sorted_sols[i].variant_id] += (
                            next_val - prev_val) / obj_range

        return distances


class EvolutionaryEngine:
    """
    High-performance evolutionary optimization engine with advanced features.

    Features:
    - Parallel mutation processing with intelligent coordination
    - ML-driven mutation selection based on code patterns
    - Memory-optimized IR handling with copy-on-write
    - Batch LLM processing for semantic mutations
    - Advanced performance monitoring and adaptive optimization
    """

    # Type hints for attributes
    mutators: List[Mutator]
    runner: CodeRunner
    config: EngineConfig
    experiment_dir: Optional[Path]
    llm_client: Any
    event_callback: Optional[Callable[[OptimizationEvent], None]]
    parser: PythonParser
    codegen: PythonCodeGenerator
    validator: IRValidator
    metrics_collector: IRMetricsCollector
    crossover_manager: CrossoverManager
    serializer: IRSerializer
    orchestrator: Optional[ParallelMutationOrchestrator]
    intelligent_selector: Optional[Any]
    batch_llm_client: Optional[Any]
    archive: ParetoArchive
    cache: Dict[str, Dict[str, float]]
    statistics: MutationStatistics
    generation: int
    best_solution: Optional[Solution]
    stagnation_counter: int
    performance_history: List[Dict[str, Any]]

    def __init__(
        self,
        mutators: List[Mutator],
        runner: CodeRunner,
        config: Optional[EngineConfig] = None,
        llm_client=None,
        experiment_dir: Optional[Path] = None,
        event_callback: Optional[Callable[[OptimizationEvent], None]] = None,
    ):
        self.mutators = mutators
        self.runner = runner
        self.config = config or EngineConfig()
        self.experiment_dir = experiment_dir
        self.llm_client = llm_client
        self.event_callback = event_callback

        # Core components
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()
        self.validator = IRValidator(strict=False)
        self.metrics_collector = IRMetricsCollector()
        self.crossover_manager = CrossoverManager()
        self.serializer = IRSerializer()

        # Enhanced components
        if self.config.enable_parallel_mutations:
            parallel_config = ParallelConfig(
                max_workers=self.config.max_concurrent_mutations,
                max_memory_usage_mb=self.config.max_memory_usage_mb,
                adaptive_scaling=True,
            )
            self.orchestrator = ParallelMutationOrchestrator(parallel_config)
        else:
            self.orchestrator = None

        if self.config.enable_intelligent_selection:
            self.intelligent_selector = get_intelligent_selector()
        else:
            self.intelligent_selector = None

        if self.config.enable_batch_llm and llm_client:
            provider = "openai" if "OpenAI" in llm_client.__class__.__name__ else "gemini"
            model_name = getattr(
                llm_client, "model_name", "gpt-4" if provider == "openai" else "gemini-2.5-flash"
            )

            self.batch_llm_client = create_batch_llm_client(
                provider=provider,
                model=model_name,
                api_key=getattr(llm_client, "api_key", None),
                max_concurrent_requests=self.config.llm_batch_size,
            )
            if self.batch_llm_client is None:
                logger.warning(
                    "Batch LLM client creation failed, disabling batch processing")
        else:
            self.batch_llm_client = None

        # State
        self.archive = ParetoArchive(max_size=self.config.archive_max_size)
        self.cache: Dict[str, Dict[str, float]] = {}
        self.statistics = MutationStatistics()
        self.generation = 0
        self.best_solution: Optional[Solution] = None
        self.stagnation_counter = 0

        # Performance tracking
        self.performance_history: List[Dict[str, float]] = []

        # Setup experiment directory
        self._setup_experiment_dir()

        logger.info(f"Initialized EvolutionaryEngine:")
        logger.info(f"  Mutators: {len(mutators)}")
        logger.info(
            f"  Parallel mutations: {self.config.enable_parallel_mutations}")
        logger.info(
            f"  Intelligent selection: {self.config.enable_intelligent_selection}")
        logger.info(f"  Batch LLM: {self.config.enable_batch_llm}")
        if self.config.enable_memory_optimization:
            logger.info(
                f"  Memory optimization: {self.config.enable_memory_optimization}")

    def _emit_event(self, event_type: EventType, data: Dict[str, Any]):
        """Emit an optimization event."""
        if self.event_callback:
            try:
                event = OptimizationEvent(type=event_type, data=data)
                self.event_callback(event)
            except Exception as e:
                logger.warning(f"Event callback failed: {e}")

    def _setup_experiment_dir(self):
        """Initialize experiment directory structure."""
        if self.experiment_dir:
            self.experiment_dir.mkdir(parents=True, exist_ok=True)
            if self.config.save_ir_snapshots:
                (self.experiment_dir / "ir_snapshots").mkdir(exist_ok=True)
            (self.experiment_dir / "performance_logs").mkdir(exist_ok=True)

    def _evaluate(self, solution: Solution, test_code: str) -> Tuple[bool, Dict[str, float], str]:
        """Evaluate solution with caching and memory optimization."""
        # Use lazy wrapper for memory efficiency
        ir = solution.lazy_wrapper.ir if solution.lazy_wrapper else solution.ir
        code = self.codegen.generate(ir)
        code_hash = hashlib.md5(code.encode()).hexdigest()

        # Check cache
        if code_hash in self.cache:
            return True, self.cache[code_hash], "Cached"

        # Run evaluation
        success, metrics, output = self.runner.run(code, test_code)

        if success:
            self.cache[code_hash] = metrics

        return success, metrics, output

    def _compute_fitness(self, solution: Solution) -> float:
        """Compute fitness score for parent selection."""
        energy = max(solution.metrics.get("energy_joules", 1e-6), 1e-9)
        duration = max(solution.metrics.get("duration_seconds", 1e-6), 1e-9)
        return 1.0 / (energy * duration)

    def _select_parents(self, parents: List[Solution], num_select: int) -> List[Solution]:
        """Select parents using tournament selection."""
        if not parents:
            return []

        selected = []
        tournament_size = min(3, len(parents))

        for _ in range(num_select):
            tournament = random.sample(parents, tournament_size)
            winner = max(tournament, key=self._compute_fitness)
            selected.append(winner)

        return selected

    def _generate_mutations_enhanced(
        self, parents: List[Solution], enabled_layers: Optional[Set[MutationLayer]] = None
    ) -> List[Solution]:
        """Generate mutations using enhanced orchestration."""
        all_variants = []

        for parent in parents:
            try:
                # Use intelligent selection if enabled
                if self.intelligent_selector:
                    selected_mutators = self.intelligent_selector.select_mutators(
                        parent.ir, enabled_layers, max_mutators=10, llm_client=self.llm_client
                    )

                    # Create lookup map for learning
                    strategy_map = {s: (m, c) for m, s, c in selected_mutators}

                    if self.orchestrator:
                        # Parallel execution of selected mutations
                        mutation_results = self.orchestrator.orchestrate_parallel_mutations(
                            parent.ir,
                            enabled_layers,
                            self.batch_llm_client,
                            selected_mutations=selected_mutators,
                        )

                        for result in mutation_results:
                            val_result = self.validator.validate(result.ir)
                            mutator_info = strategy_map.get(
                                result.strategy_name)
                            mutator = mutator_info[0] if mutator_info else None
                            mutator_name = mutator.__class__.__name__ if mutator else "Unknown"

                            if val_result.valid:
                                self.statistics.record_success(mutator_name)
                                all_variants.append(
                                    Solution(
                                        ir=result.ir,
                                        metrics={},
                                        variant_id=str(uuid.uuid4()),
                                        parent_id=parent.variant_id,
                                        mutation_type=result.strategy_name,
                                        generation=self.generation + 1,
                                    )
                                )

                                if mutator:
                                    self.intelligent_selector.record_mutation_outcome(
                                        parent.ir,
                                        mutator,
                                        result.strategy_name,
                                        True,
                                        result.confidence,
                                    )

                                self._emit_event(
                                    EventType.MUTATION_RESULT,
                                    {
                                        "success": True,
                                        "strategy": result.strategy_name,
                                        "mutator": mutator_name,
                                    },
                                )
                            else:
                                self.statistics.failed_validations += 1
                                if mutator:
                                    self.intelligent_selector.record_mutation_outcome(
                                        parent.ir,
                                        mutator,
                                        result.strategy_name,
                                        False,
                                        0.0,
                                    )
                                self._emit_event(
                                    EventType.MUTATION_RESULT,
                                    {
                                        "success": False,
                                        "error": "Validation failed",
                                        "strategy": result.strategy_name,
                                    },
                                )

                    else:
                        # Fallback to sequential execution
                        for m, strategy, confidence in selected_mutators:
                            self._emit_event(
                                EventType.MUTATION_ATTEMPT,
                                {
                                    "mutator": m.__class__.__name__,
                                    "strategy": strategy,
                                    "parent": parent.variant_id,
                                },
                            )
                            self.statistics.record_attempt(
                                m.__class__.__name__)
                            variants = m.mutate(parent.ir)
                            for result in variants:
                                if result.strategy_name == strategy:
                                    # Validate variant
                                    val_result = self.validator.validate(
                                        result.ir)
                                    if val_result.valid:
                                        self.statistics.record_success(
                                            m.__class__.__name__)
                                        solution = Solution(
                                            ir=result.ir,
                                            metrics={},
                                            variant_id=str(uuid.uuid4()),
                                            parent_id=parent.variant_id,
                                            mutation_type=f"{m.__class__.__name__}:{strategy}",
                                            generation=self.generation + 1,
                                        )
                                        all_variants.append(solution)

                                        # Record outcome for learning
                                        self.intelligent_selector.record_mutation_outcome(
                                            parent.ir, m, strategy, True, confidence  # type: ignore
                                        )
                                        self._emit_event(
                                            EventType.MUTATION_RESULT,
                                            {
                                                "success": True,
                                                "strategy": strategy,
                                                "mutator": m.__class__.__name__,
                                            },
                                        )
                                    else:
                                        self.statistics.failed_validations += 1
                                        self._emit_event(
                                            EventType.MUTATION_RESULT,
                                            {
                                                "success": False,
                                                "error": "Validation failed",
                                                "strategy": strategy,
                                            },
                                        )
                                        # Record failed outcome
                                        if self.intelligent_selector:
                                            self.intelligent_selector.record_mutation_outcome(
                                                parent.ir, m, strategy, False, 0.0  # type: ignore
                                            )

                # Use parallel orchestration if enabled
                elif self.orchestrator:
                    mutation_results = self.orchestrator.orchestrate_parallel_mutations(
                        parent.ir, enabled_layers, self.batch_llm_client
                    )

                    for result in mutation_results:
                        self.statistics.record_attempt("ParallelOrchestrator")
                        val_result = self.validator.validate(result.ir)
                        if val_result.valid:
                            self.statistics.record_success(
                                "ParallelOrchestrator")
                            solution = Solution(
                                ir=result.ir,
                                metrics={},
                                variant_id=str(uuid.uuid4()),
                                parent_id=parent.variant_id,
                                mutation_type=result.strategy_name,
                                generation=self.generation + 1,
                            )
                            all_variants.append(solution)
                        else:
                            self.statistics.failed_validations += 1

                # Fallback to traditional mutation
                else:
                    for mutator in self.mutators:
                        self.statistics.record_attempt(
                            mutator.__class__.__name__)

                        # Log attempt
                        self._emit_event(
                            EventType.MUTATION_ATTEMPT,
                            {"mutator": mutator.__class__.__name__,
                                "parent": parent.variant_id},
                        )

                        results = mutator.mutate(parent.ir)
                        if results:
                            logger.info(
                                f"Mutator {mutator.__class__.__name__} produced {len(results)} variants"
                            )
                            self.statistics.record_success(
                                mutator.__class__.__name__)

                        for result in results:
                            val_result = self.validator.validate(result.ir)
                            if val_result.valid:
                                solution = Solution(
                                    ir=result.ir,
                                    metrics={},
                                    variant_id=str(uuid.uuid4()),
                                    parent_id=parent.variant_id,
                                    mutation_type=result.strategy_name,
                                    generation=self.generation + 1,
                                )
                                all_variants.append(solution)
                                self._emit_event(
                                    EventType.MUTATION_RESULT,
                                    {
                                        "success": True,
                                        "strategy": result.strategy_name,
                                        "mutator": mutator.__class__.__name__,
                                    },
                                )
                            else:
                                self.statistics.failed_validations += 1
                                self._emit_event(
                                    EventType.MUTATION_RESULT,
                                    {
                                        "success": False,
                                        "error": "Validation failed",
                                        "strategy": result.strategy_name,
                                    },
                                )

            except Exception as e:
                logger.error(
                    f"Mutation generation failed for parent {parent.variant_id}: {e}")

        return all_variants

    def _adaptive_population_size(self) -> int:
        """Calculate adaptive population size based on performance."""
        if not self.config.adaptive_population_size:
            return self.config.population_size

        base_size = self.config.population_size

        # Increase population if stagnating
        if self.stagnation_counter > 2:
            return min(base_size * 2, 20)

        # Decrease if converging quickly
        if len(self.archive.solutions) > base_size and self.generation > 3:
            diversity = self._calculate_diversity()
            if diversity < 0.1:  # Low diversity
                return max(base_size // 2, 3)

        return base_size

    def _calculate_diversity(self) -> float:
        """Calculate population diversity."""
        if len(self.archive.solutions) < 2:
            return 1.0

        # Simple diversity measure based on fitness variance
        fitness_scores = [self._compute_fitness(
            sol) for sol in self.archive.solutions]
        if not fitness_scores:
            return 1.0

        mean_fitness = sum(fitness_scores) / len(fitness_scores)
        variance = sum((f - mean_fitness) **
                       2 for f in fitness_scores) / len(fitness_scores)

        return min(1.0, variance / (mean_fitness**2 + 1e-9))

    def _log_performance_metrics(self):
        """Log performance metrics and memory usage."""
        memory_stats = get_memory_stats()

        performance_data = {
            "generation": self.generation,
            "archive_size": len(self.archive.solutions),
            "cache_size": len(self.cache),
            "stagnation_counter": self.stagnation_counter,
            "memory_saved_mb": memory_stats.get("memory_saved_mb", 0),
            "copy_ratio": memory_stats.get("copy_ratio", 0),
            "sharing_efficiency": memory_stats.get("sharing_efficiency", 0),
        }

        if self.orchestrator and hasattr(self.orchestrator, "get_performance_stats"):
            orchestrator_stats = self.orchestrator.get_performance_stats()
            performance_data.update(
                orchestrator_stats.get("execution_stats", {}))

        self.performance_history.append(performance_data)

        logger.info(f"Generation {self.generation} performance:")
        logger.info(f"  Archive size: {len(self.archive.solutions)}")
        logger.info(
            f"  Memory saved: {memory_stats.get('memory_saved_mb', 0):.1f}MB")
        logger.info(
            f"  Copy efficiency: {memory_stats.get('sharing_efficiency', 0):.1%}")

        if self.best_solution:
            best_energy = self.best_solution.metrics.get("energy_joules", 0)
            best_time = self.best_solution.metrics.get("duration_seconds", 0)
            logger.info(
                f"  Best solution: {best_energy:.6f}J, {best_time:.6f}s")

    def optimize(
        self,
        initial_code: str,
        test_code: str,
        enabled_layers: Optional[Set[MutationLayer]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Solution]:
        """
        Main optimization loop with advanced features.

        Args:
            initial_code: Source code to optimize
            test_code: Test harness code
            enabled_layers: Set of enabled mutation layers
            progress_callback: Optional progress callback

        Returns:
            List of optimized solutions from Pareto archive
        """
        start_time = time.time()

        # Parse initial code
        try:
            initial_ir = self.parser.parse(initial_code)
            val_result = self.validator.validate(initial_ir)
            if not val_result.valid:
                raise ValueError(
                    f"Initial code validation failed: {val_result.errors}")
        except Exception as e:
            logger.error(f"Failed to parse initial code: {e}")
            return []

        self._emit_event(
            EventType.OPTIMIZATION_START,
            {
                "target": "initial_code",
                "generations": self.config.generations,
                "population_size": self.config.population_size,
            },
        )

        # Evaluate baseline
        success, baseline_metrics, output = self._evaluate(
            Solution(
                ir=initial_ir,
                metrics={},
                variant_id="baseline",
                parent_id="",
                mutation_type="baseline",
                generation=0,
            ),
            test_code,
        )

        if not success:
            logger.error(f"Baseline evaluation failed: {output}")
            return []

        # Create initial solution
        initial_solution = Solution(
            ir=initial_ir,
            metrics=baseline_metrics,
            variant_id="initial",
            parent_id="",
            mutation_type="initial",
            generation=0,
        )

        self.archive.update(initial_solution)
        self.best_solution = initial_solution

        # Save baseline snapshot
        if self.config.save_ir_snapshots:
            self._save_ir_snapshot(initial_solution)

        logger.info(f"Baseline metrics: {baseline_metrics}")

        # Evolution loop
        for generation in range(self.config.generations):
            self.generation = generation
            self._emit_event(
                EventType.GENERATION_START,
                {
                    "generation": generation,
                    "total_generations": self.config.generations,
                    "population_fitness": [
                        self._compute_fitness(s) for s in self.archive.solutions
                    ],
                },
            )
            generation_start = time.time()
            logger.info(f"--- Starting Generation {generation} ---")

            # Adaptive population size
            current_pop_size = self._adaptive_population_size()

            # Select parents
            parents = self._select_parents(
                self.archive.solutions, current_pop_size)

            # Generate mutations
            logger.info(f"Generating mutations for {len(parents)} parents...")
            variants = self._generate_mutations_enhanced(
                parents, enabled_layers)
            logger.info(f"Generated {len(variants)} variants.")

            # Generate crossovers
            if len(parents) >= 2 and random.random() < self.config.crossover_rate:
                crossover_variants = self._generate_crossovers(parents)
                variants.extend(crossover_variants)

            # Evaluate variants
            improved_count = 0
            logger.info("Evaluating variants...")
            for i, variant in enumerate(variants):
                logger.debug(
                    f"Evaluating variant {i+1}/{len(variants)}: {variant.mutation_type}")
                success, metrics, output = self._evaluate(variant, test_code)

                if success:
                    variant.metrics = metrics

                    # Update archive
                    if self.archive.update(variant):
                        improved_count += 1
                        self.statistics.record_improvement(
                            variant.mutation_type)

                        # Update best solution
                        if not self.best_solution or self._compute_fitness(
                            variant
                        ) > self._compute_fitness(self.best_solution):
                            self.best_solution = variant
                            self.stagnation_counter = 0

                            self._emit_event(
                                EventType.NEW_BEST_SOLUTION,
                                {
                                    "energy": variant.metrics.get("energy_joules"),
                                    "time": variant.metrics.get("duration_seconds"),
                                    "generation": generation,
                                    "mutation": variant.mutation_type,
                                    "code": self.codegen.generate(variant.ir),
                                },
                            )

                        # Save IR snapshot
                        if self.config.save_ir_snapshots:
                            self._save_ir_snapshot(variant)

            # Update stagnation counter
            if improved_count == 0:
                self.stagnation_counter += 1

            # Log progress
            generation_time = time.time() - generation_start
            logger.info(
                f"Generation {generation}: {improved_count}/{len(variants)} improvements in {generation_time:.2f}s"
            )

            # Progress callback
            if progress_callback:
                progress_callback(generation + 1, self.config.generations)

            # Log performance metrics
            self._log_performance_metrics()

            # Early stopping
            if self.stagnation_counter >= self.config.early_stopping_patience:
                logger.info(
                    f"Early stopping after {self.stagnation_counter} generations without improvement"
                )
                break

            self._emit_event(
                EventType.GENERATION_COMPLETE,
                {
                    "generation": generation,
                    "improved_count": improved_count,
                    "duration": generation_time,
                    "best_metrics": self.best_solution.metrics if self.best_solution else {},
                },
            )

        total_time = time.time() - start_time
        logger.info(f"Optimization completed in {total_time:.2f}s")
        logger.info(f"Final archive size: {len(self.archive.solutions)}")

        self._emit_event(
            EventType.OPTIMIZATION_COMPLETE,
            {
                "total_solutions": len(self.archive.solutions),
                "best_metrics": self.best_solution.metrics if self.best_solution else {},
                "best_code": (
                    self.codegen.generate(
                        self.best_solution.ir) if self.best_solution else ""
                ),
                "duration": total_time,
            },
        )

        # Save performance history
        if self.experiment_dir:
            self._save_performance_history()

        return self.archive.solutions

    def _generate_crossovers(self, parents: List[Solution]) -> List[Solution]:
        """Generate crossover variants."""
        variants = []
        num_crossovers = min(len(parents) // 2, 3)

        for _ in range(num_crossovers):
            parent1, parent2 = random.sample(parents, 2)

            try:
                for child_ir in self.crossover_manager.perform_crossover(parent1.ir, parent2.ir):
                    val_result = self.validator.validate(child_ir)
                    if val_result.valid:
                        solution = Solution(
                            ir=child_ir,
                            metrics={},
                            variant_id=str(uuid.uuid4()),
                            parent_id=f"{parent1.variant_id}+{parent2.variant_id}",
                            mutation_type="Crossover",
                            generation=self.generation + 1,
                        )
                        variants.append(solution)
            except Exception as e:
                logger.error(f"Crossover failed: {e}")

        return variants

    def _save_ir_snapshot(self, solution: Solution):
        """Save IR snapshot for a solution."""
        if not self.config.save_ir_snapshots or not self.experiment_dir:
            return

        filename = f"gen_{solution.generation:03d}_{solution.variant_id[:8]}.json"
        filepath = self.experiment_dir / "ir_snapshots" / filename

        try:
            self.serializer.save(solution.ir, filepath)
        except Exception as e:
            logger.error(f"Failed to save IR snapshot: {e}")

    def _save_performance_history(self):
        """Save performance history to file."""
        if not self.experiment_dir:
            return

        try:
            import json

            filepath = self.experiment_dir / "performance_logs" / "performance_history.json"

            with open(filepath, "w") as f:
                json.dump(self.performance_history, f, indent=2)

            logger.info(f"Saved performance history to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save performance history: {e}")

    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get comprehensive optimization summary."""
        memory_stats = get_memory_stats()

        summary = {
            "generations_completed": self.generation,
            "total_solutions": len(self.archive.solutions),
            "best_solution_metrics": self.best_solution.metrics if self.best_solution else {},
            "cache_efficiency": len(self.cache),
            "memory_optimization": memory_stats,
            "stagnation_counter": self.stagnation_counter,
        }

        if self.intelligent_selector:
            summary["learning_stats"] = self.intelligent_selector.get_learning_stats()

        if self.orchestrator and hasattr(self.orchestrator, "get_performance_stats"):
            summary["parallel_stats"] = self.orchestrator.get_performance_stats()

        if self.batch_llm_client:
            summary["llm_stats"] = self.batch_llm_client.get_stats()

        return summary
