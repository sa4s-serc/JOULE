#!/usr/bin/env python3
"""
Compare Original vs Optimized EvoEval Code
==========================================

This script measures the performance of original and optimized EvoEval benchmark
solutions using the same measurement methodology as HEDGE.

It uses HEDGE's GreenGymRunner infrastructure to ensure identical measurement
conditions for fair comparison.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import importlib.util

# Rich for beautiful terminal output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' not installed. Install with: pip install rich")

# Import HEDGE's measurement infrastructure
from src.infrastructure.execution.runner import GreenGymRunner

console = Console() if RICH_AVAILABLE else None


class EvoEvalComparer:
    """Compares original vs optimized EvoEval solutions using HEDGE's measurement methodology."""

    def __init__(
        self,
        original_dir: str = "evoeval_benchmark",
        optimized_dir: str = "evoeval_results_20260219_225745",
        test_iterations: int = 10,
        test_warmup_iterations: int = 3,
        test_seed: int = 42,
        timeout: int = 60,
    ):
        self.original_dir = Path(original_dir)
        self.optimized_dir = Path(optimized_dir)
        self.test_iterations = test_iterations
        self.test_warmup_iterations = test_warmup_iterations
        self.test_seed = test_seed
        self.timeout = timeout

        # Initialize results storage
        self.results: Dict[str, Dict[str, Any]] = {}

    def discover_problems(self) -> List[str]:
        """Discover all EvoEval problems that have both original and optimized versions."""
        problems = []

        if not self.original_dir.exists():
            raise ValueError(f"Original directory not found: {self.original_dir}")

        if not self.optimized_dir.exists():
            raise ValueError(f"Optimized directory not found: {self.optimized_dir}")

        # Find all problem directories in original
        for problem_dir in sorted(self.original_dir.glob("EvoEval_difficult_*")):
            if not problem_dir.is_dir():
                continue

            problem_name = problem_dir.name
            original_target = problem_dir / "target.py"
            original_test = problem_dir / "test_target.py"
            optimized_dir = self.optimized_dir / problem_name
            optimized_target = optimized_dir / "optimized_target.py"

            # Check if all required files exist
            if original_target.exists() and original_test.exists() and optimized_target.exists():
                problems.append(problem_name)
            else:
                if RICH_AVAILABLE:
                    console.print(f"[yellow]⚠[/yellow] Skipping {problem_name}: Missing files")
                else:
                    print(f"⚠ Skipping {problem_name}: Missing files")

        return problems

    def measure_code(
        self,
        target_file: Path,
        test_file: Path,
        label: str
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Measure a code solution using HEDGE's GreenGymRunner.

        Returns:
            (success, metrics) where metrics contains:
            - duration_seconds: Total execution time across all iterations
            - energy_joules: Total energy consumed across all iterations
            - emissions_kg: Total CO2 emissions
        """
        try:
            code_str = target_file.read_text()
            test_code_str = test_file.read_text()

            # Create runner with same config as HEDGE benchmark
            runner = GreenGymRunner(
                timeout_seconds=self.timeout,
                samples=self.test_iterations,
                warmup_iterations=self.test_warmup_iterations,
                base_seed=self.test_seed,
            )

            # Run measurement — run() takes code as strings, not file paths
            success, metrics, output = runner.run(
                code_str=code_str,
                test_code_str=test_code_str,
            )

            if not success:
                if RICH_AVAILABLE:
                    console.print(f"[red]✗[/red] {label} failed: {output[:200]}")
                else:
                    print(f"✗ {label} failed: {output[:200]}")
                return False, {}

            return True, metrics

        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"[red]✗[/red] {label} error: {e}")
            else:
                print(f"✗ {label} error: {e}")
            return False, {}

    def compare_problem(self, problem_name: str) -> Dict[str, Any]:
        """Compare original vs optimized for a single problem."""
        problem_dir = self.original_dir / problem_name
        original_target = problem_dir / "target.py"
        original_test = problem_dir / "test_target.py"

        optimized_dir = self.optimized_dir / problem_name
        optimized_target = optimized_dir / "optimized_target.py"

        result = {
            "problem": problem_name,
            "original": {},
            "optimized": {},
            "comparison": {},
        }

        # Measure original
        if RICH_AVAILABLE:
            console.print(f"  📊 Measuring original...")
        else:
            print(f"  📊 Measuring original...")

        success_orig, metrics_orig = self.measure_code(
            original_target,
            original_test,
            f"{problem_name} (original)"
        )

        if success_orig:
            result["original"] = metrics_orig
            result["original"]["success"] = True
        else:
            result["original"]["success"] = False
            result["status"] = "original_failed"
            return result

        # Measure optimized
        if RICH_AVAILABLE:
            console.print(f"  ⚡ Measuring optimized...")
        else:
            print(f"  ⚡ Measuring optimized...")

        success_opt, metrics_opt = self.measure_code(
            optimized_target,
            original_test,  # Use same test file
            f"{problem_name} (optimized)"
        )

        if success_opt:
            result["optimized"] = metrics_opt
            result["optimized"]["success"] = True
        else:
            result["optimized"]["success"] = False
            result["status"] = "optimized_failed"
            return result

        # Calculate improvements
        result["status"] = "success"
        result["comparison"] = self._calculate_improvements(metrics_orig, metrics_opt)

        return result

    def _calculate_improvements(
        self,
        original_metrics: Dict[str, float],
        optimized_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Calculate percentage improvements."""
        comparison = {}

        # Time improvement
        orig_time = original_metrics.get("duration_seconds", 0)
        opt_time = optimized_metrics.get("duration_seconds", 0)

        if orig_time > 0:
            time_improvement_pct = ((orig_time - opt_time) / orig_time) * 100
            time_speedup = orig_time / opt_time if opt_time > 0 else float('inf')
            comparison["time_improvement_percent"] = time_improvement_pct
            comparison["time_speedup"] = time_speedup
            comparison["time_saved_seconds"] = orig_time - opt_time

        # Energy improvement
        orig_energy = original_metrics.get("energy_joules", 0)
        opt_energy = optimized_metrics.get("energy_joules", 0)

        if orig_energy > 0:
            energy_improvement_pct = ((orig_energy - opt_energy) / orig_energy) * 100
            energy_ratio = orig_energy / opt_energy if opt_energy > 0 else float('inf')
            comparison["energy_improvement_percent"] = energy_improvement_pct
            comparison["energy_ratio"] = energy_ratio
            comparison["energy_saved_joules"] = orig_energy - opt_energy

        # Emissions improvement
        orig_emissions = original_metrics.get("emissions_kg", 0)
        opt_emissions = optimized_metrics.get("emissions_kg", 0)

        if orig_emissions > 0:
            emissions_improvement_pct = ((orig_emissions - opt_emissions) / orig_emissions) * 100
            comparison["emissions_improvement_percent"] = emissions_improvement_pct
            comparison["emissions_saved_kg"] = orig_emissions - opt_emissions

        return comparison

    def run_comparison(self):
        """Run comparison on all discovered problems."""
        problems = self.discover_problems()

        if not problems:
            print("No problems found to compare!")
            return

        if RICH_AVAILABLE:
            console.print(Panel.fit(
                f"[bold cyan]EvoEval Comparison: Original vs Optimized[/bold cyan]\n"
                f"Problems: {len(problems)} | Test Iterations: {self.test_iterations} | "
                f"Warmup: {self.test_warmup_iterations} | Seed: {self.test_seed}",
                border_style="cyan"
            ))
        else:
            print(f"\n=== EvoEval Comparison: Original vs Optimized ===")
            print(f"Problems: {len(problems)} | Test Iterations: {self.test_iterations}")

        # Run comparisons
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console
            ) as progress:
                task = progress.add_task("Comparing problems...", total=len(problems))

                for problem in problems:
                    progress.update(task, description=f"Comparing {problem}...")
                    result = self.compare_problem(problem)
                    self.results[problem] = result
                    progress.advance(task)
        else:
            for i, problem in enumerate(problems, 1):
                print(f"\n[{i}/{len(problems)}] Comparing {problem}...")
                result = self.compare_problem(problem)
                self.results[problem] = result

        # Generate reports
        self._display_summary()
        self._save_results()
        self._generate_markdown_report()

    def _display_summary(self):
        """Display summary of comparisons."""
        if not RICH_AVAILABLE:
            self._display_summary_simple()
            return

        console.print("\n")

        # Overall statistics
        successful = sum(1 for r in self.results.values() if r["status"] == "success")
        time_improvements = [
            r["comparison"]["time_improvement_percent"]
            for r in self.results.values()
            if r["status"] == "success" and "time_improvement_percent" in r["comparison"]
        ]
        energy_improvements = [
            r["comparison"]["energy_improvement_percent"]
            for r in self.results.values()
            if r["status"] == "success" and "energy_improvement_percent" in r["comparison"]
        ]

        # Summary table
        summary_table = Table(title="Overall Summary", box=box.ROUNDED, show_header=True, header_style="bold cyan")
        summary_table.add_column("Metric", style="yellow")
        summary_table.add_column("Value", justify="right", style="green")

        summary_table.add_row("Total Problems", str(len(self.results)))
        summary_table.add_row("Successful Comparisons", str(successful))

        if time_improvements:
            avg_time_imp = sum(time_improvements) / len(time_improvements)
            max_time_imp = max(time_improvements)
            min_time_imp = min(time_improvements)
            summary_table.add_row("Avg Time Improvement", f"{avg_time_imp:.2f}%")
            summary_table.add_row("Best Time Improvement", f"{max_time_imp:.2f}%")
            summary_table.add_row("Worst Time Improvement", f"{min_time_imp:.2f}%")

        if energy_improvements:
            avg_energy_imp = sum(energy_improvements) / len(energy_improvements)
            max_energy_imp = max(energy_improvements)
            min_energy_imp = min(energy_improvements)
            summary_table.add_row("Avg Energy Improvement", f"{avg_energy_imp:.2f}%")
            summary_table.add_row("Best Energy Improvement", f"{max_energy_imp:.2f}%")
            summary_table.add_row("Worst Energy Improvement", f"{min_energy_imp:.2f}%")

        console.print(summary_table)

        # Detailed results table
        console.print("\n")
        results_table = Table(
            title="Problem-by-Problem Comparison",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        results_table.add_column("Problem", style="yellow")
        results_table.add_column("Status", justify="center")
        results_table.add_column("Time Imp.", justify="right", style="green")
        results_table.add_column("Energy Imp.", justify="right", style="blue")
        results_table.add_column("Speedup", justify="right", style="magenta")

        for problem, result in self.results.items():
            status = "✅" if result["status"] == "success" else "❌"

            if result["status"] == "success":
                comp = result["comparison"]
                time_imp = f"{comp.get('time_improvement_percent', 0):.2f}%"
                energy_imp = f"{comp.get('energy_improvement_percent', 0):.2f}%"
                speedup = f"{comp.get('time_speedup', 0):.2f}x"
            else:
                time_imp = "N/A"
                energy_imp = "N/A"
                speedup = "N/A"

            results_table.add_row(problem, status, time_imp, energy_imp, speedup)

        console.print(results_table)

    def _display_summary_simple(self):
        """Display summary without Rich."""
        print("\n" + "="*80)
        print("COMPARISON SUMMARY")
        print("="*80)

        successful = sum(1 for r in self.results.values() if r["status"] == "success")
        print(f"Total Problems: {len(self.results)}")
        print(f"Successful Comparisons: {successful}")

        print("\nPROBLEM RESULTS:")
        print("-"*80)
        print(f"{'Problem':<40} {'Time Imp.':<15} {'Energy Imp.':<15} {'Speedup':<10}")
        print("-"*80)

        for problem, result in self.results.items():
            if result["status"] == "success":
                comp = result["comparison"]
                time_imp = f"{comp.get('time_improvement_percent', 0):.2f}%"
                energy_imp = f"{comp.get('energy_improvement_percent', 0):.2f}%"
                speedup = f"{comp.get('time_speedup', 0):.2f}x"
            else:
                time_imp = "FAILED"
                energy_imp = "FAILED"
                speedup = "N/A"

            print(f"{problem:<40} {time_imp:<15} {energy_imp:<15} {speedup:<10}")

    def _save_results(self):
        """Save raw results as JSON."""
        output_file = Path("comparison_results.json")

        output_data = {
            "configuration": {
                "test_iterations": self.test_iterations,
                "test_warmup_iterations": self.test_warmup_iterations,
                "test_seed": self.test_seed,
                "timeout": self.timeout,
                "timestamp": datetime.now().isoformat(),
            },
            "results": self.results,
        }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        if RICH_AVAILABLE:
            console.print(f"\n[green]✓[/green] Results saved: {output_file}")
        else:
            print(f"\n✓ Results saved: {output_file}")

    def _generate_markdown_report(self):
        """Generate a comprehensive markdown report."""
        output_file = Path("COMPARISON_REPORT.md")

        with open(output_file, 'w') as f:
            f.write("# EvoEval Comparison Report: Original vs Optimized\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("## Configuration\n\n")
            f.write(f"- Test Iterations: {self.test_iterations}\n")
            f.write(f"- Test Warmup Iterations: {self.test_warmup_iterations}\n")
            f.write(f"- Test Seed: {self.test_seed}\n")
            f.write(f"- Timeout: {self.timeout}s\n")
            f.write(f"- Original Code: `{self.original_dir}`\n")
            f.write(f"- Optimized Code: `{self.optimized_dir}`\n\n")

            # Calculate statistics
            successful = sum(1 for r in self.results.values() if r["status"] == "success")
            time_improvements = [
                r["comparison"]["time_improvement_percent"]
                for r in self.results.values()
                if r["status"] == "success" and "time_improvement_percent" in r["comparison"]
            ]
            energy_improvements = [
                r["comparison"]["energy_improvement_percent"]
                for r in self.results.values()
                if r["status"] == "success" and "energy_improvement_percent" in r["comparison"]
            ]

            f.write("## Summary\n\n")
            f.write(f"- **Total Problems**: {len(self.results)}\n")
            f.write(f"- **Successful Comparisons**: {successful}\n")

            if time_improvements:
                avg_time = sum(time_improvements) / len(time_improvements)
                f.write(f"- **Average Time Improvement**: {avg_time:.2f}%\n")
                f.write(f"- **Best Time Improvement**: {max(time_improvements):.2f}%\n")
                f.write(f"- **Worst Time Improvement**: {min(time_improvements):.2f}%\n")

            if energy_improvements:
                avg_energy = sum(energy_improvements) / len(energy_improvements)
                f.write(f"- **Average Energy Improvement**: {avg_energy:.2f}%\n")
                f.write(f"- **Best Energy Improvement**: {max(energy_improvements):.2f}%\n")
                f.write(f"- **Worst Energy Improvement**: {min(energy_improvements):.2f}%\n")

            f.write("\n## Detailed Results\n\n")
            f.write("| Problem | Status | Time Imp. | Energy Imp. | Speedup | Time Saved | Energy Saved |\n")
            f.write("|---------|--------|-----------|-------------|---------|------------|-------------|\n")

            for problem, result in self.results.items():
                status = "✅" if result["status"] == "success" else "❌"

                if result["status"] == "success":
                    comp = result["comparison"]
                    time_imp = f"{comp.get('time_improvement_percent', 0):.2f}%"
                    energy_imp = f"{comp.get('energy_improvement_percent', 0):.2f}%"
                    speedup = f"{comp.get('time_speedup', 0):.2f}x"
                    time_saved = f"{comp.get('time_saved_seconds', 0):.4f}s"
                    energy_saved = f"{comp.get('energy_saved_joules', 0):.2f}J"
                else:
                    time_imp = energy_imp = speedup = time_saved = energy_saved = "N/A"

                f.write(f"| {problem} | {status} | {time_imp} | {energy_imp} | {speedup} | {time_saved} | {energy_saved} |\n")

            f.write("\n## Problem-by-Problem Analysis\n\n")

            for problem, result in self.results.items():
                f.write(f"### {problem}\n\n")

                if result["status"] == "success":
                    orig = result["original"]
                    opt = result["optimized"]
                    comp = result["comparison"]

                    f.write("**Original Code:**\n")
                    f.write(f"- Duration: {orig.get('duration_seconds', 0):.6f} seconds\n")
                    f.write(f"- Energy: {orig.get('energy_joules', 0):.6f} joules\n")
                    f.write(f"- Emissions: {orig.get('emissions_kg', 0):.9f} kg CO₂\n\n")

                    f.write("**Optimized Code:**\n")
                    f.write(f"- Duration: {opt.get('duration_seconds', 0):.6f} seconds\n")
                    f.write(f"- Energy: {opt.get('energy_joules', 0):.6f} joules\n")
                    f.write(f"- Emissions: {opt.get('emissions_kg', 0):.9f} kg CO₂\n\n")

                    f.write("**Improvements:**\n")
                    f.write(f"- Time: {comp.get('time_improvement_percent', 0):.2f}% ({comp.get('time_speedup', 0):.2f}x speedup)\n")
                    f.write(f"- Energy: {comp.get('energy_improvement_percent', 0):.2f}%\n")
                    if "emissions_improvement_percent" in comp:
                        f.write(f"- Emissions: {comp.get('emissions_improvement_percent', 0):.2f}%\n")
                    f.write("\n")
                else:
                    f.write(f"**Status**: ❌ {result['status']}\n\n")

                f.write("---\n\n")

            f.write("## Methodology\n\n")
            f.write("This comparison uses HEDGE's exact measurement infrastructure:\n\n")
            f.write("- **Runner**: GreenGymRunner (subprocess isolation)\n")
            f.write("- **Energy Measurement**: CodeCarbon EmissionsTracker\n")
            f.write("- **Timing**: `time.perf_counter()` for high-precision wall-clock measurement\n")
            f.write(f"- **Test Iterations**: {self.test_iterations} measured iterations per solution\n")
            f.write(f"- **Warmup**: {self.test_warmup_iterations} warmup runs before measurement\n")
            f.write(f"- **Seed Management**: Base seed {self.test_seed}, incremented per iteration\n")
            f.write("- **Aggregation**: SUM of all iteration metrics (HEDGE's standard approach)\n\n")
            f.write("All measurements are performed in isolated subprocesses with identical test conditions.\n\n")

            f.write("---\n\n")
            f.write("*Generated by EvoEval Comparison Script*\n")

        if RICH_AVAILABLE:
            console.print(f"[green]✓[/green] Report saved: {output_file}")
        else:
            print(f"✓ Report saved: {output_file}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare original vs optimized EvoEval code using HEDGE's measurement methodology"
    )
    parser.add_argument(
        "--original-dir",
        type=str,
        default="evoeval_benchmark",
        help="Directory containing original code (default: evoeval_benchmark)"
    )
    parser.add_argument(
        "--optimized-dir",
        type=str,
        default="evoeval_results_20260219_225745",
        help="Directory containing optimized code "
    )
    parser.add_argument(
        "--test-iterations",
        type=int,
        default=10,
        help="Number of measured iterations per solution (default: 5)"
    )
    parser.add_argument(
        "--test-warmup-iterations",
        type=int,
        default=3,
        help="Number of warmup iterations before measurement (default: 10)"
    )
    parser.add_argument(
        "--test-seed",
        type=int,
        default=42,
        help="Base seed for reproducible test execution (default: 42)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout per test in seconds (default: 30)"
    )

    args = parser.parse_args()

    # Create and run comparer
    comparer = EvoEvalComparer(
        original_dir=args.original_dir,
        optimized_dir=args.optimized_dir,
        test_iterations=args.test_iterations,
        test_warmup_iterations=args.test_warmup_iterations,
        test_seed=args.test_seed,
        timeout=args.timeout,
    )

    comparer.run_comparison()


if __name__ == "__main__":
    main()
