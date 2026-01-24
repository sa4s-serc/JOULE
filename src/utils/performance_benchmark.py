"""
Performance Benchmark Suite - Comprehensive Performance Testing

This module provides comprehensive benchmarking capabilities for HEDGE:
- Before/after performance comparison
- Memory usage analysis
- Optimization effectiveness metrics
- Regression testing for performance
"""

import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

try:
    import matplotlib.pyplot as plt
    import numpy as np

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt: Any = None  # type: ignore
    np: Any = None  # type: ignore

from src.application.engine.evolution import EngineConfig, EvolutionaryEngine
from src.application.mutators.registry import get_registry
from src.domain.ir.lazy_wrapper import get_memory_stats, lazy_ir_manager
from src.infrastructure.execution.runner import GreenGymRunner

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    test_name: str
    engine_type: str
    execution_time: float
    memory_peak_mb: float
    memory_saved_mb: float
    solutions_found: int
    best_energy_improvement: float
    best_time_improvement: float
    cache_hit_rate: float
    parallel_efficiency: float = 0.0
    learning_effectiveness: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "test_name": self.test_name,
            "engine_type": self.engine_type,
            "execution_time": self.execution_time,
            "memory_peak_mb": self.memory_peak_mb,
            "memory_saved_mb": self.memory_saved_mb,
            "solutions_found": self.solutions_found,
            "best_energy_improvement": self.best_energy_improvement,
            "best_time_improvement": self.best_time_improvement,
            "cache_hit_rate": self.cache_hit_rate,
            "parallel_efficiency": self.parallel_efficiency,
            "learning_effectiveness": self.learning_effectiveness,
        }


@dataclass
class BenchmarkSuite:
    """Collection of benchmark tests."""

    name: str
    tests: List[Tuple[str, str, str]] = field(default_factory=list)  # (name, code, test_code)

    def add_test(self, name: str, code: str, test_code: str):
        """Add a test to the suite."""
        self.tests.append((name, code, test_code))


class PerformanceBenchmark:
    """
    Comprehensive performance benchmark system.

    Features:
    - Before/after performance comparison
    - Memory usage analysis and optimization tracking
    - Parallel processing efficiency measurement
    - Learning system effectiveness evaluation
    - Regression testing for performance improvements
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("benchmark_results")
        self.output_dir.mkdir(exist_ok=True)

        # Initialize components
        self.registry = get_registry()
        self.runner = GreenGymRunner(timeout_seconds=30, samples=3)

        # Benchmark suites
        self.suites: Dict[str, BenchmarkSuite] = {}
        self._initialize_default_suites()

    def _initialize_default_suites(self):
        """Initialize default benchmark suites."""
        # Fibonacci suite
        fib_suite = BenchmarkSuite("fibonacci")
        fib_suite.add_test(
            "fibonacci_recursive",
            """
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)
            """.strip(),
            """
def test_fib():
    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(5) == 5
    assert fib(10) == 55
    
if __name__ == "__main__":
    test_fib()
    print("All tests passed!")
            """.strip(),
        )

        # Search suite
        search_suite = BenchmarkSuite("search")
        search_suite.add_test(
            "linear_search",
            """
def search_element(elements, target):
    found = False
    for i in range(len(elements)):
        if elements[i] == target:
            found = True
            break
    return found
            """.strip(),
            """
def test_search():
    assert search_element([1, 2, 3, 4, 5], 3) == True
    assert search_element([1, 2, 3, 4, 5], 6) == False
    assert search_element([], 1) == False
    
if __name__ == "__main__":
    test_search()
    print("All tests passed!")
            """.strip(),
        )

        # Complex algorithm suite
        complex_suite = BenchmarkSuite("complex")
        complex_suite.add_test(
            "nested_loops",
            """
def matrix_multiply(A, B):
    n = len(A)
    m = len(B[0])
    p = len(B)
    
    result = []
    for i in range(n):
        row = []
        for j in range(m):
            sum_val = 0
            for k in range(p):
                sum_val += A[i][k] * B[k][j]
            row.append(sum_val)
        result.append(row)
    
    return result
            """.strip(),
            """
def test_matrix_multiply():
    A = [[1, 2], [3, 4]]
    B = [[5, 6], [7, 8]]
    result = matrix_multiply(A, B)
    expected = [[19, 22], [43, 50]]
    assert result == expected
    
if __name__ == "__main__":
    test_matrix_multiply()
    print("All tests passed!")
            """.strip(),
        )

        self.suites["fibonacci"] = fib_suite
        self.suites["search"] = search_suite
        self.suites["complex"] = complex_suite

    def run_benchmark_comparison(
        self, suite_name: str, generations: int = 5, runs_per_test: int = 3
    ) -> Dict[str, List[BenchmarkResult]]:
        """
        Run comprehensive benchmark comparison between engines.

        Args:
            suite_name: Name of benchmark suite to run
            generations: Number of generations for optimization
            runs_per_test: Number of runs per test for statistical significance

        Returns:
            Dictionary mapping test names to lists of benchmark results
        """
        if suite_name not in self.suites:
            raise ValueError(f"Unknown benchmark suite: {suite_name}")

        suite = self.suites[suite_name]
        results = {}

        logger.info(f"Running benchmark suite: {suite_name}")
        logger.info(f"Tests: {len(suite.tests)}, Runs per test: {runs_per_test}")

        for test_name, code, test_code in suite.tests:
            logger.info(f"Benchmarking test: {test_name}")

            test_results = []

            # Run with original engine
            for run in range(runs_per_test):
                logger.info(f"  Original engine - Run {run + 1}/{runs_per_test}")
                result = self._benchmark_original_engine(test_name, code, test_code, generations)
                test_results.append(result)

            # Run with optimized engine
            for run in range(runs_per_test):
                logger.info(f"  Optimized engine - Run {run + 1}/{runs_per_test}")
                result = self._benchmark_optimized_engine(test_name, code, test_code, generations)
                test_results.append(result)

            results[test_name] = test_results

        # Save results
        self._save_benchmark_results(suite_name, results)

        # Generate report
        self._generate_benchmark_report(suite_name, results)

        return results

    def _benchmark_original_engine(
        self, test_name: str, code: str, test_code: str, generations: int
    ) -> BenchmarkResult:
        """Benchmark the original evolutionary engine."""
        # Reset memory stats
        lazy_ir_manager.cleanup_unused_wrappers()

        # Monitor memory
        process = psutil.Process()
        memory_before = process.memory_info().rss / (1024 * 1024)  # MB

        start_time = time.time()

        # Create original engine
        config = EngineConfig(generations=generations, population_size=5, save_ir_snapshots=False)

        mutators = [mutator_class() for mutator_class in self.registry.get_all_mutator_classes()]  # type: ignore
        engine = EvolutionaryEngine(mutators=mutators, runner=self.runner, config=config)  # type: ignore

        # Run optimization
        try:
            solutions = engine.optimize(code, test_code)
            execution_time = time.time() - start_time

            # Calculate improvements
            best_energy_improvement = 0.0
            best_time_improvement = 0.0

            if solutions and hasattr(engine, "best_solution") and engine.best_solution:
                baseline_energy = solutions[0].metrics.get("energy_joules", 1.0)
                baseline_time = solutions[0].metrics.get("duration_seconds", 1.0)

                best_energy = engine.best_solution.metrics.get("energy_joules", baseline_energy)
                best_time = engine.best_solution.metrics.get("duration_seconds", baseline_time)

                best_energy_improvement = (baseline_energy - best_energy) / baseline_energy
                best_time_improvement = (baseline_time - best_time) / baseline_time

            # Memory usage
            memory_after = process.memory_info().rss / (1024 * 1024)  # MB
            memory_peak = memory_after - memory_before

            # Cache efficiency
            cache_hit_rate = (
                len(engine.cache) / max(1, len(solutions)) if hasattr(engine, "cache") else 0.0
            )

            return BenchmarkResult(
                test_name=test_name,
                engine_type="original",
                execution_time=execution_time,
                memory_peak_mb=memory_peak,
                memory_saved_mb=0.0,  # Original engine doesn't have memory optimization
                solutions_found=len(solutions),
                best_energy_improvement=best_energy_improvement,
                best_time_improvement=best_time_improvement,
                cache_hit_rate=cache_hit_rate,
            )

        except Exception as e:
            logger.error(f"Original engine benchmark failed: {e}")
            return BenchmarkResult(
                test_name=test_name,
                engine_type="original",
                execution_time=time.time() - start_time,
                memory_peak_mb=0.0,
                memory_saved_mb=0.0,
                solutions_found=0,
                best_energy_improvement=0.0,
                best_time_improvement=0.0,
                cache_hit_rate=0.0,
            )

    def _benchmark_optimized_engine(
        self, test_name: str, code: str, test_code: str, generations: int
    ) -> BenchmarkResult:
        """Benchmark the evolutionary engine."""
        # Reset memory stats
        lazy_ir_manager.cleanup_unused_wrappers()

        # Monitor memory
        process = psutil.Process()
        memory_before = process.memory_info().rss / (1024 * 1024)  # MB

        start_time = time.time()

        # Create engine
        config = EngineConfig(
            generations=generations,
            population_size=5,
            save_ir_snapshots=False,
            enable_parallel_mutations=True,
            enable_intelligent_selection=True,
            enable_memory_optimization=True,
            max_concurrent_mutations=4,
        )

        mutators = [mutator_class() for mutator_class in self.registry.get_all_mutator_classes()]  # type: ignore
        engine = EvolutionaryEngine(mutators=mutators, runner=self.runner, config=config)  # type: ignore

        # Run optimization
        try:
            solutions = engine.optimize(code, test_code)
            execution_time = time.time() - start_time

            # Get memory stats
            memory_stats = get_memory_stats()

            # Calculate improvements
            best_energy_improvement = 0.0
            best_time_improvement = 0.0

            if solutions and engine.best_solution:
                # Find baseline (first solution)
                baseline_solution = min(solutions, key=lambda s: s.generation)
                baseline_energy = baseline_solution.metrics.get("energy_joules", 1.0)
                baseline_time = baseline_solution.metrics.get("duration_seconds", 1.0)

                best_energy = engine.best_solution.metrics.get("energy_joules", baseline_energy)
                best_time = engine.best_solution.metrics.get("duration_seconds", baseline_time)

                best_energy_improvement = (baseline_energy - best_energy) / baseline_energy
                best_time_improvement = (baseline_time - best_time) / baseline_time

            # Memory usage
            memory_after = process.memory_info().rss / (1024 * 1024)  # MB
            memory_peak = memory_after - memory_before

            # Cache efficiency
            cache_hit_rate = len(engine.cache) / max(1, len(solutions))

            # Get performance stats
            summary = engine.get_optimization_summary()
            parallel_efficiency = 0.0
            learning_effectiveness = 0.0

            if "parallel_stats" in summary:
                parallel_stats = summary["parallel_stats"].get("execution_stats", {})
                parallel_efficiency = parallel_stats.get("parallel_efficiency", 0.0)

            if "learning_stats" in summary:
                learning_stats = summary["learning_stats"]
                # Simple learning effectiveness metric
                total_outcomes = learning_stats.get("total_outcomes", 0)
                learning_effectiveness = min(1.0, total_outcomes / 100.0)  # Normalize to [0, 1]

            return BenchmarkResult(
                test_name=test_name,
                engine_type="optimized",
                execution_time=execution_time,
                memory_peak_mb=memory_peak,
                memory_saved_mb=memory_stats.get("memory_saved_mb", 0.0),
                solutions_found=len(solutions),
                best_energy_improvement=best_energy_improvement,
                best_time_improvement=best_time_improvement,
                cache_hit_rate=cache_hit_rate,
                parallel_efficiency=parallel_efficiency,
                learning_effectiveness=learning_effectiveness,
            )

        except Exception as e:
            logger.error(f"Engine benchmark failed: {e}")
            return BenchmarkResult(
                test_name=test_name,
                engine_type="optimized",
                execution_time=time.time() - start_time,
                memory_peak_mb=0.0,
                memory_saved_mb=0.0,
                solutions_found=0,
                best_energy_improvement=0.0,
                best_time_improvement=0.0,
                cache_hit_rate=0.0,
            )

    def _save_benchmark_results(self, suite_name: str, results: Dict[str, List[BenchmarkResult]]):
        """Save benchmark results to JSON file."""
        output_file = self.output_dir / f"{suite_name}_benchmark_results.json"

        # Convert results to serializable format
        serializable_results = {}
        for test_name, test_results in results.items():
            serializable_results[test_name] = [result.to_dict() for result in test_results]

        try:
            with open(output_file, "w") as f:
                json.dump(serializable_results, f, indent=2)

            logger.info(f"Saved benchmark results to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save benchmark results: {e}")

    def _generate_benchmark_report(
        self, suite_name: str, results: Dict[str, List[BenchmarkResult]]
    ):
        """Generate comprehensive benchmark report."""
        report_file = self.output_dir / f"{suite_name}_benchmark_report.md"

        try:
            with open(report_file, "w") as f:
                f.write(f"# HEDGE Performance Benchmark Report - {suite_name.title()}\n\n")
                f.write(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # Summary statistics
                f.write("## Summary\n\n")

                original_results = []
                optimized_results = []

                for test_results in results.values():
                    for result in test_results:
                        if result.engine_type == "original":
                            original_results.append(result)
                        else:
                            optimized_results.append(result)

                if original_results and optimized_results:
                    # Calculate averages
                    avg_original_time = statistics.mean(r.execution_time for r in original_results)
                    avg_optimized_time = statistics.mean(
                        r.execution_time for r in optimized_results
                    )

                    avg_original_memory = statistics.mean(
                        r.memory_peak_mb for r in original_results
                    )
                    avg_optimized_memory = statistics.mean(
                        r.memory_peak_mb for r in optimized_results
                    )

                    avg_memory_saved = statistics.mean(r.memory_saved_mb for r in optimized_results)

                    speedup = (
                        avg_original_time / avg_optimized_time if avg_optimized_time > 0 else 1.0
                    )
                    memory_reduction = (
                        (avg_original_memory - avg_optimized_memory) / avg_original_memory
                        if avg_original_memory > 0
                        else 0.0
                    )

                    f.write(f"- **Average Speedup**: {speedup:.2f}x\n")
                    f.write(f"- **Memory Reduction**: {memory_reduction:.1%}\n")
                    f.write(f"- **Memory Saved by Optimization**: {avg_memory_saved:.1f}MB\n")
                    f.write(f"- **Original Engine Avg Time**: {avg_original_time:.2f}s\n")
                    f.write(f"- **Optimized Engine Avg Time**: {avg_optimized_time:.2f}s\n\n")

                # Detailed results
                f.write("## Detailed Results\n\n")

                for test_name, test_results in results.items():
                    f.write(f"### {test_name}\n\n")

                    # Group by engine type
                    original = [r for r in test_results if r.engine_type == "original"]
                    enhanced = [r for r in test_results if r.engine_type == "optimized"]

                    f.write("| Metric | Original Engine | Optimized Engine | Improvement |\n")
                    f.write("|--------|----------------|-----------------|-------------|\n")

                    if original and enhanced:
                        orig_time = statistics.mean(r.execution_time for r in original)
                        opt_time = statistics.mean(r.execution_time for r in enhanced)
                        time_improvement = (
                            (orig_time - opt_time) / orig_time if orig_time > 0 else 0.0
                        )

                        orig_memory = statistics.mean(r.memory_peak_mb for r in original)
                        opt_memory = statistics.mean(r.memory_peak_mb for r in enhanced)
                        memory_improvement = (
                            (orig_memory - opt_memory) / orig_memory if orig_memory > 0 else 0.0
                        )

                        avg_memory_saved = statistics.mean(r.memory_saved_mb for r in enhanced)
                        avg_parallel_eff = statistics.mean(r.parallel_efficiency for r in enhanced)

                        f.write(
                            f"| Execution Time | {orig_time:.2f}s | {opt_time:.2f}s | {time_improvement:.1%} |\n"
                        )
                        f.write(
                            f"| Memory Peak | {orig_memory:.1f}MB | {opt_memory:.1f}MB | {memory_improvement:.1%} |\n"
                        )
                        f.write(f"| Memory Saved | N/A | {avg_memory_saved:.1f}MB | - |\n")
                        f.write(f"| Parallel Efficiency | N/A | {avg_parallel_eff:.1%} | - |\n")

                    f.write("\n")

                # Performance insights
                f.write("## Performance Insights\n\n")

                if optimized_results:
                    high_parallel_eff = [
                        r for r in optimized_results if r.parallel_efficiency > 0.7
                    ]
                    high_memory_savings = [r for r in optimized_results if r.memory_saved_mb > 10.0]

                    f.write(
                        f"- **High Parallel Efficiency** (>70%): {len(high_parallel_eff)}/{len(optimized_results)} tests\n"
                    )
                    f.write(
                        f"- **Significant Memory Savings** (>10MB): {len(high_memory_savings)}/{len(optimized_results)} tests\n"
                    )

                    if high_parallel_eff:
                        avg_parallel = statistics.mean(
                            r.parallel_efficiency for r in high_parallel_eff
                        )
                        f.write(f"- **Average Parallel Efficiency**: {avg_parallel:.1%}\n")

                    if high_memory_savings:
                        avg_savings = statistics.mean(
                            r.memory_saved_mb for r in high_memory_savings
                        )
                        f.write(f"- **Average Memory Savings**: {avg_savings:.1f}MB\n")

                f.write("\n## Recommendations\n\n")

                if speedup > 1.5:
                    f.write(
                        "✅ **Excellent Performance**: Optimized engine shows significant speedup\n"
                    )
                elif speedup > 1.1:
                    f.write(
                        "✅ **Good Performance**: Optimized engine shows moderate improvement\n"
                    )
                else:
                    f.write("⚠️ **Limited Improvement**: Consider tuning optimization parameters\n")

                if memory_reduction > 0.2:
                    f.write(
                        "✅ **Excellent Memory Efficiency**: Significant memory usage reduction\n"
                    )
                elif memory_reduction > 0.1:
                    f.write("✅ **Good Memory Efficiency**: Moderate memory usage reduction\n")
                else:
                    f.write(
                        "⚠️ **Limited Memory Improvement**: Memory optimization may need tuning\n"
                    )

            logger.info(f"Generated benchmark report: {report_file}")

        except Exception as e:
            logger.error(f"Failed to generate benchmark report: {e}")

    def create_performance_plots(self, suite_name: str, results: Dict[str, List[BenchmarkResult]]):
        """Create performance visualization plots."""
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib not available, skipping plot generation")
            return

        try:
            import matplotlib.pyplot as plt
            import numpy as np

            # Create plots directory
            plots_dir = self.output_dir / "plots"
            plots_dir.mkdir(exist_ok=True)

            # Execution time comparison
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

            test_names = list(results.keys())
            original_times = []
            optimized_times = []

            for test_name in test_names:
                test_results = results[test_name]
                orig_results = [r for r in test_results if r.engine_type == "original"]
                opt_results = [r for r in test_results if r.engine_type == "optimized"]

                if orig_results and opt_results:
                    original_times.append(statistics.mean(r.execution_time for r in orig_results))
                    optimized_times.append(statistics.mean(r.execution_time for r in opt_results))
                else:
                    original_times.append(0)
                    optimized_times.append(0)

            # Execution time plot
            x = np.arange(len(test_names))
            width = 0.35

            ax1.bar(x - width / 2, original_times, width, label="Original Engine", alpha=0.8)
            ax1.bar(x + width / 2, optimized_times, width, label="Optimized Engine", alpha=0.8)

            ax1.set_xlabel("Test Cases")
            ax1.set_ylabel("Execution Time (seconds)")
            ax1.set_title("Execution Time Comparison")
            ax1.set_xticks(x)
            ax1.set_xticklabels(test_names, rotation=45)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Memory usage plot
            original_memory = []
            optimized_memory = []
            memory_saved = []

            for test_name in test_names:
                test_results = results[test_name]
                orig_results = [r for r in test_results if r.engine_type == "original"]
                opt_results = [r for r in test_results if r.engine_type == "optimized"]

                if orig_results and opt_results:
                    original_memory.append(statistics.mean(r.memory_peak_mb for r in orig_results))
                    optimized_memory.append(statistics.mean(r.memory_peak_mb for r in opt_results))
                    memory_saved.append(statistics.mean(r.memory_saved_mb for r in opt_results))
                else:
                    original_memory.append(0)
                    optimized_memory.append(0)
                    memory_saved.append(0)

            ax2.bar(x - width / 2, original_memory, width, label="Original Engine", alpha=0.8)
            ax2.bar(x + width / 2, optimized_memory, width, label="Optimized Engine", alpha=0.8)
            ax2.bar(
                x + width / 2,
                memory_saved,
                width,
                bottom=optimized_memory,
                label="Memory Saved",
                alpha=0.6,
                hatch="///",
            )

            ax2.set_xlabel("Test Cases")
            ax2.set_ylabel("Memory Usage (MB)")
            ax2.set_title("Memory Usage Comparison")
            ax2.set_xticks(x)
            ax2.set_xticklabels(test_names, rotation=45)
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(
                plots_dir / f"{suite_name}_performance_comparison.png", dpi=300, bbox_inches="tight"
            )
            plt.close()

            logger.info(f"Created performance plots in {plots_dir}")

        except ImportError:
            logger.warning("Matplotlib not available, skipping plot generation")
        except Exception as e:
            logger.error(f"Failed to create performance plots: {e}")

    def run_regression_test(self, baseline_file: Path) -> Dict[str, Any]:
        """Run regression test against baseline performance."""
        try:
            with open(baseline_file, "r") as f:
                baseline_data = json.load(f)

            # Run current benchmark
            current_results = self.run_benchmark_comparison(
                "fibonacci", generations=3, runs_per_test=2
            )

            # Compare with baseline
            regression_report: Dict[str, Any] = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "baseline_file": str(baseline_file),
                "regressions": [],
                "improvements": [],
                "status": "PASS",
            }

            for test_name, current_test_results in current_results.items():
                if test_name in baseline_data:
                    baseline_test_results = baseline_data[test_name]

                    # Compare enhanced engine results
                    current_optimized = [
                        r for r in current_test_results if r.engine_type == "optimized"
                    ]
                    baseline_optimized = [
                        r for r in baseline_test_results if r["engine_type"] == "optimized"
                    ]

                    if current_optimized and baseline_optimized:
                        current_time = statistics.mean(r.execution_time for r in current_optimized)
                        baseline_time = statistics.mean(
                            r["execution_time"] for r in baseline_optimized
                        )

                        time_change = (current_time - baseline_time) / baseline_time

                        if time_change > 0.1:  # 10% regression threshold
                            regression_report["regressions"].append(
                                {
                                    "test": test_name,
                                    "metric": "execution_time",
                                    "baseline": baseline_time,
                                    "current": current_time,
                                    "change": time_change,
                                }
                            )
                            regression_report["status"] = "FAIL"
                        elif time_change < -0.05:  # 5% improvement
                            regression_report["improvements"].append(
                                {
                                    "test": test_name,
                                    "metric": "execution_time",
                                    "baseline": baseline_time,
                                    "current": current_time,
                                    "change": time_change,
                                }
                            )

            # Save regression report
            report_file = self.output_dir / "regression_report.json"
            with open(report_file, "w") as f:
                json.dump(regression_report, f, indent=2)

            logger.info(f"Regression test completed: {regression_report['status']}")
            logger.info(f"Regressions: {len(regression_report['regressions'])}")
            logger.info(f"Improvements: {len(regression_report['improvements'])}")

            return regression_report

        except Exception as e:
            logger.error(f"Regression test failed: {e}")
            return {"status": "ERROR", "error": str(e)}


# Convenience functions
def run_quick_benchmark() -> Dict[str, Any]:
    """Run a quick benchmark for development testing."""
    benchmark = PerformanceBenchmark()
    results = benchmark.run_benchmark_comparison("fibonacci", generations=3, runs_per_test=2)
    benchmark.create_performance_plots("fibonacci", results)
    return results


def run_full_benchmark() -> Dict[str, Any]:
    """Run comprehensive benchmark suite."""
    benchmark = PerformanceBenchmark()

    all_results = {}
    for suite_name in ["fibonacci", "search", "complex"]:
        logger.info(f"Running benchmark suite: {suite_name}")
        results = benchmark.run_benchmark_comparison(suite_name, generations=5, runs_per_test=3)
        benchmark.create_performance_plots(suite_name, results)
        all_results[suite_name] = results

    return all_results


if __name__ == "__main__":
    # Run quick benchmark for testing
    results = run_quick_benchmark()
    print("Benchmark completed successfully!")
