"""
Evolutionary Engine - IR-Only Optimization System

This is the core orchestration layer that coordinates:
- IR parsing and validation
- Mutation generation
- Code reconstruction
- Evaluation and Pareto optimization

Key principles:
1. IR is the single source of truth
2. All mutations are validated before evaluation
3. Code is reconstructed from IR (never cached)
4. Comprehensive metrics and instrumentation
"""
import logging
import uuid
import hashlib
import math
import random
from typing import List, Dict, Tuple, Optional, Set, Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.domain.interfaces import Mutator, CodeRunner
from src.domain.ir.schema import Module
from src.domain.ir.validators import IRValidator
from src.domain.ir.metrics import IRMetricsCollector, MutationStatistics
from src.domain.ir.serialization import IRSerializer
from src.infrastructure.parsing.python_parser import PythonParser
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.application.engine.crossover import CrossoverManager
from src.application.mutators.base import MutationOrchestrator, MutationLayer

logger = logging.getLogger(__name__)


@dataclass
class Solution:
    """Represents a candidate solution in the evolutionary search."""
    ir: Module
    metrics: Dict[str, float]
    variant_id: str
    parent_id: str
    mutation_type: str
    generation: int


@dataclass
class EngineConfig:
    """Configuration for the evolutionary engine."""
    generations: int = 10
    population_size: int = 5
    archive_max_size: int = 50
    crossover_rate: float = 0.3
    min_mutator_prob: float = 0.2
    save_ir_snapshots: bool = False
    
    
class ParetoArchive:
    """
    Maintains a set of non-dominated solutions with diversity preservation.
    
    Uses NSGA-II style crowding distance for diversity maintenance.
    """
    
    __slots__ = ('solutions', 'max_size', '_objectives')
    
    def __init__(self, max_size: int = 50, objectives: Tuple[str, ...] = ("energy_joules", "duration_seconds")):
        self.solutions: List[Solution] = []
        self.max_size = max_size
        self._objectives = objectives
    
    def _get_objective(self, sol: Solution, obj: str) -> float:
        """Get objective value with default for missing metrics."""
        return sol.metrics.get(obj, float('inf'))
    
    def _dominates(self, sol_a: Solution, sol_b: Solution) -> bool:
        """Check if sol_a dominates sol_b (better in at least one, no worse in all)."""
        dominated_in_one = False
        
        for obj in self._objectives:
            a_val = self._get_objective(sol_a, obj)
            b_val = self._get_objective(sol_b, obj)
            
            if a_val > b_val:  # Worse in this objective
                return False
            if a_val < b_val:  # Better in this objective
                dominated_in_one = True
        
        return dominated_in_one
    
    def _crowding_distance(self, solutions: List[Solution]) -> Dict[str, float]:
        """Calculate crowding distance for diversity preservation."""
        n = len(solutions)
        if n <= 2:
            return {sol.variant_id: float('inf') for sol in solutions}
        
        distances = {sol.variant_id: 0.0 for sol in solutions}
        
        for obj in self._objectives:
            # Sort by objective
            sorted_sols = sorted(solutions, key=lambda s: self._get_objective(s, obj))
            
            # Boundary solutions get infinite distance
            distances[sorted_sols[0].variant_id] = float('inf')
            distances[sorted_sols[-1].variant_id] = float('inf')
            
            # Calculate range
            obj_min = self._get_objective(sorted_sols[0], obj)
            obj_max = self._get_objective(sorted_sols[-1], obj)
            obj_range = obj_max - obj_min
            
            if obj_range > 0:
                for i in range(1, n - 1):
                    if distances[sorted_sols[i].variant_id] != float('inf'):
                        prev_val = self._get_objective(sorted_sols[i-1], obj)
                        next_val = self._get_objective(sorted_sols[i+1], obj)
                        distances[sorted_sols[i].variant_id] += (next_val - prev_val) / obj_range
        
        return distances
    
    def update(self, new_solution: Solution) -> bool:
        """Add solution if non-dominated, maintaining diversity."""
        # Check if dominated by existing solution
        for sol in self.solutions:
            if self._dominates(sol, new_solution):
                return False
        
        # Remove solutions dominated by new one
        self.solutions = [s for s in self.solutions if not self._dominates(new_solution, s)]
        self.solutions.append(new_solution)
        
        # Maintain diversity if over capacity
        if len(self.solutions) > self.max_size:
            self._prune_crowded()
        
        return True
    
    def _prune_crowded(self):
        """Remove most crowded solutions to maintain max_size."""
        if len(self.solutions) <= self.max_size:
            return
        
        distances = self._crowding_distance(self.solutions)
        # Sort ascending by distance, remove most crowded
        self.solutions.sort(key=lambda s: distances[s.variant_id])
        num_remove = len(self.solutions) - self.max_size
        self.solutions = self.solutions[num_remove:]


class EvolutionaryEngine:
    """
    Main evolutionary optimization engine.
    
    Enforces IR-Only mutations with strict validation.
    Provides comprehensive instrumentation and metrics.
    """
    
    def __init__(
        self,
        mutators: List[Mutator],
        runner: CodeRunner,
        generations: int = 10,
        population_size: int = 5,
        experiment_dir: Optional[Path] = None,
        save_ir_snapshots: bool = False
    ):
        self.mutators = mutators
        self.runner = runner
        self.config = EngineConfig(
            generations=generations,
            population_size=population_size,
            save_ir_snapshots=save_ir_snapshots
        )
        self.experiment_dir = experiment_dir
        
        # Core components
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()
        self.validator = IRValidator()
        self.metrics_collector = IRMetricsCollector()
        
        # State
        self.archive = ParetoArchive(max_size=self.config.archive_max_size)
        self.cache: Dict[str, Dict[str, float]] = {}
        self.statistics = MutationStatistics()
        self.crossover_manager = CrossoverManager()
        self.mutation_orchestrator = MutationOrchestrator()
        self.enabled_layers: Optional[Set[MutationLayer]] = None
        
        # Setup experiment directory
        self._setup_experiment_dir()
    
    def _setup_experiment_dir(self):
        """Initialize experiment directory structure."""
        if self.experiment_dir:
            self.experiment_dir.mkdir(parents=True, exist_ok=True)
            if self.config.save_ir_snapshots:
                (self.experiment_dir / "ir_snapshots").mkdir(exist_ok=True)
    
    def _evaluate(self, ir: Module, test_code: str) -> Tuple[bool, Dict[str, float], str]:
        """Evaluate solution: reconstruct code, run tests, cache results."""
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
        """Select parents using fitness-proportionate selection."""
        if not parents:
            return []
        
        fitness_scores = [self._compute_fitness(p) for p in parents]
        total_fitness = sum(fitness_scores)
        probs = [s / total_fitness for s in fitness_scores]
        
        indices = random.choices(range(len(parents)), weights=probs, k=num_select)
        return [parents[i] for i in indices]
    
    def _select_mutators(self) -> List[Mutator]:
        """Adaptively select mutators based on past performance."""
        if not self.statistics.mutator_stats:
            return self.mutators
        
        scores = {}
        for m in self.mutators:
            name_prefix = m.__class__.__name__.replace("Mutator", "")
            total_improved = 0
            total_attempts = 0
            
            for strat, data in self.statistics.mutator_stats.items():
                if strat.startswith(name_prefix):
                    total_improved += data["improved"]
                    total_attempts += data["total"]
            
            rate = total_improved / total_attempts if total_attempts > 0 else 0.0
            scores[m] = rate + 0.01  # Ensure non-zero
        
        if not scores:
            return self.mutators
        
        # Select based on relative performance
        max_score = max(scores.values())
        selected = []
        
        for m in self.mutators:
            prob = self.config.min_mutator_prob + (1 - self.config.min_mutator_prob) * (scores[m] / max_score)
            if random.random() < prob:
                selected.append(m)
        
        return selected or [random.choice(self.mutators)]
    
    def _generate_mutations(self, parent: Solution) -> List[Tuple[Module, str]]:
        """Generate mutation variants from a parent."""
        variants = []
        active_mutators = self._select_mutators()
        
        for mutator in active_mutators:
            try:
                for variant_ir, strategy_name in mutator.mutate(parent.ir):
                    self.statistics.record_attempt(strategy_name)
                    
                    val_result = self.validator.validate(variant_ir)
                    if val_result.valid:
                        self.statistics.record_success(strategy_name)
                        variants.append((variant_ir, strategy_name))
                    else:
                        logger.debug(f"Variant rejected: {val_result.errors}")
                        self.statistics.failed_validations += 1
            except Exception as e:
                logger.error(f"Mutator {mutator.__class__.__name__} failed: {e}")
        
        return variants
    
    def _generate_crossovers(self, parents: List[Solution]) -> List[Tuple[Module, str]]:
        """Generate crossover offspring from parents."""
        if len(parents) < 2:
            return []
        
        variants = []
        num_crossovers = min(len(parents) // 2, 3)
        
        for _ in range(num_crossovers):
            parent1, parent2 = random.sample(parents, 2)
            
            try:
                for child_ir in self.crossover_manager.perform_crossover(parent1.ir, parent2.ir):
                    self.statistics.record_attempt("Crossover")
                    
                    val_result = self.validator.validate(child_ir)
                    if val_result.valid:
                        self.statistics.record_success("Crossover")
                        variants.append((child_ir, "Crossover"))
                    else:
                        logger.debug(f"Crossover rejected: {val_result.errors}")
                        self.statistics.failed_validations += 1
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
            IRSerializer.save(solution.ir, filepath)
        except Exception as e:
            logger.error(f"Failed to save IR snapshot: {e}")
    
    def optimize(
        self, 
        initial_code: str, 
        test_code: str, 
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> List[Solution]:
        """
        Main optimization loop.
        
        Args:
            initial_code: Source code to optimize
            test_code: Test harness code
            progress_callback: Optional callback for progress reporting
            
        Returns:
            List of Pareto-optimal solutions
        """
        # Parse and validate baseline
        logger.info("Parsing baseline code...")
        try:
            baseline_ir = self.parser.parse(initial_code)
        except Exception as e:
            logger.error(f"Failed to parse baseline: {e}")
            return []
        
        val_result = self.validator.validate(baseline_ir)
        if not val_result.valid:
            logger.error(f"Baseline validation failed: {val_result.errors}")
            return []
        
        # Evaluate baseline
        logger.info("Evaluating baseline...")
        try:
            success, metrics, output = self._evaluate(baseline_ir, test_code)
        except Exception as e:
            logger.error(f"Baseline evaluation failed: {e}")
            return []
        
        if not success:
            logger.error(f"Baseline execution failed: {output}")
            return []
        
        # Initialize archive with baseline
        root_id = str(uuid.uuid4())
        baseline = Solution(
            ir=baseline_ir,
            metrics=metrics,
            variant_id=root_id,
            parent_id="ROOT",
            mutation_type="BASELINE",
            generation=0
        )
        self.archive.update(baseline)
        self._save_ir_snapshot(baseline)
        logger.info(f"Baseline metrics: {metrics}")
        
        # Evolutionary loop
        for gen in range(1, self.config.generations + 1):
            logger.info(f"Generation {gen}/{self.config.generations}...")
            
            parents = self.archive.solutions
            if not parents:
                break
            
            # Select parents and generate candidates
            selected = self._select_parents(parents, len(parents))
            candidates = []
            
            # Mutations
            for parent in selected:
                for variant_ir, strategy in self._generate_mutations(parent):
                    candidates.append((variant_ir, parent, strategy))
            
            # Crossovers
            for variant_ir, strategy in self._generate_crossovers(selected):
                candidates.append((variant_ir, selected[0], strategy))
            
            if not candidates:
                logger.info("No valid variants. Stopping.")
                break
            
            # Evaluate candidates
            for variant_ir, parent, strategy in candidates:
                success, metrics, _ = self._evaluate(variant_ir, test_code)
                
                if progress_callback:
                    progress_callback(1)
                
                if success:
                    new_sol = Solution(
                        ir=variant_ir,
                        metrics=metrics,
                        variant_id=str(uuid.uuid4()),
                        parent_id=parent.variant_id,
                        mutation_type=strategy,
                        generation=gen
                    )
                    self._save_ir_snapshot(new_sol)
                    
                    if self.archive.update(new_sol):
                        self.statistics.record_improvement(strategy)
                        logger.info(f"New Pareto solution! [{strategy}] {metrics}")
            
            logger.info(f"Generation {gen} complete. Archive: {len(self.archive.solutions)}")
        
        return self.archive.solutions
    
    def set_enabled_layers(self, enabled_layers: Set[MutationLayer]):
        """Set which mutation layers are enabled."""
        self.enabled_layers = enabled_layers
    
    def apply_layered_mutations(self, ir: Module) -> List[Tuple[Module, str]]:
        """Apply mutations using the layered orchestrator."""
        return self.mutation_orchestrator.apply_layered_mutations(ir, self.enabled_layers)
