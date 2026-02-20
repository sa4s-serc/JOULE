#!/usr/bin/env python3
"""
Comprehensive EvoEval Benchmark Runner for HEDGE

This script runs the HEDGE optimization tool on all EvoEval benchmark problems,
collects detailed results, and generates comprehensive visualizations and documentation.
"""

import json
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import shutil

# Rich for beautiful terminal output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: 'rich' not installed. Install with: pip install rich")

console = Console() if RICH_AVAILABLE else None


# EvoEval problems to benchmark
EVOEVAL_PROBLEMS = [
    "EvoEval_difficult_4",
    "EvoEval_difficult_16",
    "EvoEval_difficult_52",
    "EvoEval_difficult_53",
    "EvoEval_difficult_61",
    "EvoEval_difficult_63",
    "EvoEval_difficult_66",
    "EvoEval_difficult_79",
    "EvoEval_difficult_90",
]


class EvoEvalBenchmarkRunner:
    """Orchestrates the complete EvoEval benchmark study."""
    
    def __init__(
        self,
        level: str = "standard",
        generations: int = 15,
        population_size: int = 10,
        output_dir: str = None,
        visualize: bool = True,
        llm_provider: str = "gemini",
        test_iterations: int = 3,
        test_warmup_iterations: int = 5,
        test_seed: int = 42,
    ):
        self.level = level
        self.generations = generations
        self.population_size = population_size
        self.visualize = visualize
        self.llm_provider = llm_provider
        self.test_iterations = test_iterations
        self.test_warmup_iterations = test_warmup_iterations
        self.test_seed = test_seed
        
        # Setup output directory
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"evoeval_results_{timestamp}"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {}
        self.summary_stats = {
            "total_problems": len(EVOEVAL_PROBLEMS),
            "successful": 0,
            "failed": 0,
            "total_time": 0,
            "improvements": [],
        }
    
    def run_all_benchmarks(self):
        """Run optimization on all EvoEval problems."""
        if RICH_AVAILABLE:
            console.print(Panel.fit(
                "[bold cyan]HEDGE EvoEval Benchmark Study[/bold cyan]\n"
                f"Level: {self.level} | Generations: {self.generations} | "
                f"Population: {self.population_size}",
                border_style="cyan"
            ))
        else:
            print(f"\n=== HEDGE EvoEval Benchmark Study ===")
            print(f"Level: {self.level} | Generations: {self.generations}")
        
        start_time = time.time()
        
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task(
                    "Running benchmarks...",
                    total=len(EVOEVAL_PROBLEMS)
                )
                
                for problem in EVOEVAL_PROBLEMS:
                    progress.update(task, description=f"Optimizing {problem}...")
                    self._run_single_problem(problem)
                    progress.advance(task)
        else:
            for i, problem in enumerate(EVOEVAL_PROBLEMS, 1):
                print(f"\n[{i}/{len(EVOEVAL_PROBLEMS)}] Optimizing {problem}...")
                self._run_single_problem(problem)
        
        self.summary_stats["total_time"] = time.time() - start_time
        
        # Generate comprehensive report
        self._generate_report()
        self._save_results()
        
        if RICH_AVAILABLE:
            self._display_summary()
        else:
            self._display_summary_simple()
    
    def _run_single_problem(self, problem_name: str):
        """Run HEDGE optimization on a single problem."""
        problem_dir = Path("evoeval_benchmark") / problem_name
        target_file = problem_dir / "target.py"
        test_file = problem_dir / "test_target.py"
        
        if not target_file.exists() or not test_file.exists():
            self.results[problem_name] = {
                "status": "error",
                "error": "Files not found"
            }
            self.summary_stats["failed"] += 1
            return
        
        # Create output directory for this problem
        problem_output = self.output_dir / problem_name
        problem_output.mkdir(parents=True, exist_ok=True)
        
        # Build command
        cmd = [
            sys.executable,
            "hedge.py",
            "optimize",
            str(target_file),
            str(test_file),
            "--level", self.level,
            "--generations", str(self.generations),
            "--population-size", str(self.population_size),
            "--out-dir", str(problem_output),
            # Add test iteration flags for consistent optimization
            "--test-iterations", str(self.test_iterations),
            "--test-warmup-iterations", str(self.test_warmup_iterations),
            "--test-seed", str(self.test_seed),
        ]
        
        if self.visualize:
            cmd.append("--visualize")
        
        if self.level in ["advanced", "aggressive"]:
            cmd.extend(["--llm", self.llm_provider])
        
        # Run optimization
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=36000  # 45 minute timeout per problem
            )
            
            execution_time = time.time() - start_time
            
            # Parse results
            if result.returncode == 0:
                problem_result = self._parse_results(problem_output, execution_time)
                problem_result["status"] = "success"
                self.summary_stats["successful"] += 1
                
                if "improvement_percent" in problem_result:
                    self.summary_stats["improvements"].append(
                        problem_result["improvement_percent"]
                    )
            else:
                problem_result = {
                    "status": "failed",
                    "error": result.stderr[-500:] if result.stderr else "Unknown error",
                    "execution_time": execution_time
                }
                self.summary_stats["failed"] += 1
            
            self.results[problem_name] = problem_result
            
        except subprocess.TimeoutExpired:
            self.results[problem_name] = {
                "status": "timeout",
                "error": "Execution exceeded 45 minutes"
            }
            self.summary_stats["failed"] += 1
        except Exception as e:
            self.results[problem_name] = {
                "status": "error",
                "error": str(e)
            }
            self.summary_stats["failed"] += 1
    
    def _parse_results(self, problem_output: Path, execution_time: float) -> Dict[str, Any]:
        """Parse optimization results from output directory."""
        result = {"execution_time": execution_time}
        
        # Load Pareto results
        pareto_file = problem_output / "pareto_results.json"
        if pareto_file.exists():
            try:
                with open(pareto_file) as f:
                    pareto_data = json.load(f)
                    result["pareto_solutions"] = pareto_data
                    result["pareto_count"] = len(pareto_data)
                    
                    # Calculate improvement
                    if len(pareto_data) >= 2 and "metrics" in pareto_data[0]:
                        baseline = pareto_data[0]["metrics"]
                        best = min(pareto_data, key=lambda x: x["metrics"].get("latency_ms", float('inf')))
                        
                        baseline_latency = baseline.get("latency_ms", 0)
                        best_latency = best["metrics"].get("latency_ms", 0)
                        
                        if baseline_latency and baseline_latency > 0:
                            improvement = ((baseline_latency - best_latency) / baseline_latency) * 100
                            result["improvement_percent"] = improvement
                            result["baseline_latency_ms"] = baseline_latency
                            result["best_latency_ms"] = best_latency
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                result["pareto_error"] = f"Failed to parse Pareto results: {e}"
        
        # Load statistics
        stats_file = problem_output / "statistics.json"
        if stats_file.exists():
            try:
                with open(stats_file) as f:
                    result["statistics"] = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                result["statistics_error"] = f"Failed to parse statistics: {e}"
        
        # Check for optimized code
        optimized_file = problem_output / "optimized.py"
        if optimized_file.exists():
            result["optimized_code_available"] = True
        
        return result
    
    def _generate_report(self):
        """Generate comprehensive markdown report."""
        report_path = self.output_dir / "BENCHMARK_REPORT.md"
        
        with open(report_path, 'w') as f:
            f.write("# HEDGE EvoEval Benchmark Study Report\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Configuration**:\n")
            f.write(f"- Optimization Level: `{self.level}`\n")
            f.write(f"- Generations: {self.generations}\n")
            f.write(f"- Population Size: {self.population_size}\n")
            f.write(f"- LLM Provider: {self.llm_provider}\n")
            f.write(f"- Test Iterations: {self.test_iterations}\n")
            f.write(f"- Test Warmup Iterations: {self.test_warmup_iterations}\n")
            f.write(f"- Test Seed: {self.test_seed}\n\n")
            
            f.write("## Executive Summary\n\n")
            f.write(f"- **Total Problems**: {self.summary_stats['total_problems']}\n")
            f.write(f"- **Successful**: {self.summary_stats['successful']}\n")
            f.write(f"- **Failed**: {self.summary_stats['failed']}\n")
            f.write(f"- **Total Time**: {self.summary_stats['total_time']:.2f} seconds\n")
            
            if self.summary_stats["improvements"]:
                avg_improvement = sum(self.summary_stats["improvements"]) / len(self.summary_stats["improvements"])
                max_improvement = max(self.summary_stats["improvements"])
                min_improvement = min(self.summary_stats["improvements"])
                f.write(f"- **Average Improvement**: {avg_improvement:.2f}%\n")
                f.write(f"- **Best Improvement**: {max_improvement:.2f}%\n")
                f.write(f"- **Worst Improvement**: {min_improvement:.2f}%\n")
            
            f.write("\n## Detailed Results\n\n")
            f.write("| Problem | Status | Improvement | Baseline (ms) | Best (ms) | Pareto Solutions | Time (s) |\n")
            f.write("|---------|--------|-------------|---------------|-----------|------------------|----------|\n")
            
            for problem, data in self.results.items():
                status = data.get("status", "unknown")
                
                # Safely format numeric values
                try:
                    improvement = f"{float(data.get('improvement_percent', 0)):.2f}%" if "improvement_percent" in data else "N/A"
                except (ValueError, TypeError):
                    improvement = "N/A"
                    
                try:
                    baseline = f"{float(data.get('baseline_latency_ms', 0)):.2f}" if "baseline_latency_ms" in data else "N/A"
                except (ValueError, TypeError):
                    baseline = "N/A"
                    
                try:
                    best = f"{float(data.get('best_latency_ms', 0)):.2f}" if "best_latency_ms" in data else "N/A"
                except (ValueError, TypeError):
                    best = "N/A"
                    
                pareto_count = data.get("pareto_count", 0)
                exec_time = f"{data.get('execution_time', 0):.2f}"
                
                f.write(f"| {problem} | {status} | {improvement} | {baseline} | {best} | {pareto_count} | {exec_time} |\n")
            
            f.write("\n## Problem-Specific Analysis\n\n")
            for problem, data in self.results.items():
                f.write(f"### {problem}\n\n")
                
                if data.get("status") == "success":
                    f.write(f"**Status**: ✅ Success\n\n")
                    
                    if "improvement_percent" in data:
                        try:
                            improvement = float(data['improvement_percent'])
                            f.write(f"**Performance Improvement**: {improvement:.2f}%\n\n")
                            f.write(f"- Baseline Latency: {float(data.get('baseline_latency_ms', 0)):.2f} ms\n")
                            f.write(f"- Optimized Latency: {float(data.get('best_latency_ms', 0)):.2f} ms\n")
                        except (ValueError, TypeError):
                            f.write(f"**Performance Improvement**: N/A\n\n")
                            f.write(f"- Baseline Latency: N/A\n")
                            f.write(f"- Optimized Latency: N/A\n")
                        f.write(f"- Pareto Solutions Found: {data.get('pareto_count', 0)}\n\n")
                    
                    if "statistics" in data:
                        stats = data["statistics"]
                        f.write(f"**Optimization Statistics**:\n")
                        
                        # Safely format statistics values
                        try:
                            total_mutations = int(stats.get('total_mutations', 0))
                            f.write(f"- Total Mutations: {total_mutations}\n")
                        except (ValueError, TypeError):
                            f.write(f"- Total Mutations: N/A\n")
                            
                        try:
                            successful_mutations = int(stats.get('successful_mutations', 0))
                            f.write(f"- Successful Mutations: {successful_mutations}\n")
                        except (ValueError, TypeError):
                            f.write(f"- Successful Mutations: N/A\n")
                            
                        try:
                            success_rate = float(stats.get('success_rate', 0))
                            f.write(f"- Success Rate: {success_rate:.2f}%\n\n")
                        except (ValueError, TypeError):
                            f.write(f"- Success Rate: N/A\n\n")
                    
                    f.write(f"**Artifacts**:\n")
                    f.write(f"- Optimized Code: `{self.output_dir}/{problem}/optimized.py`\n")
                    f.write(f"- Pareto Results: `{self.output_dir}/{problem}/pareto_results.json`\n")
                    if self.visualize:
                        f.write(f"- Visualization: `{self.output_dir}/{problem}/report.html`\n")
                    f.write("\n")
                else:
                    f.write(f"**Status**: ❌ {data.get('status', 'Unknown')}\n\n")
                    if "error" in data:
                        f.write(f"**Error**: {data['error']}\n\n")
                
                f.write("---\n\n")
            
            f.write("## Visualization\n\n")
            f.write("Individual problem visualizations are available in each problem's subdirectory.\n\n")
            f.write("To view a specific problem's results:\n")
            f.write("```bash\n")
            f.write(f"# Open HTML report\n")
            f.write(f"open {self.output_dir}/[problem_name]/report.html\n")
            f.write("```\n\n")
            
            f.write("## Conclusion\n\n")
            if self.summary_stats["successful"] == self.summary_stats["total_problems"]:
                f.write("✅ All problems were successfully optimized!\n\n")
            elif self.summary_stats["successful"] > 0:
                f.write(f"⚠️ {self.summary_stats['successful']} out of {self.summary_stats['total_problems']} problems were successfully optimized.\n\n")
            else:
                f.write("❌ No problems were successfully optimized. Check error messages above.\n\n")
            
            if self.summary_stats["improvements"]:
                avg_improvement = sum(self.summary_stats["improvements"]) / len(self.summary_stats["improvements"])
                f.write(f"The average performance improvement across successful optimizations was **{avg_improvement:.2f}%**.\n\n")
            
            f.write("---\n\n")
            f.write("*Generated by HEDGE EvoEval Benchmark Runner*\n")
        
        if RICH_AVAILABLE:
            console.print(f"\n[green]✓[/green] Report generated: {report_path}")
        else:
            print(f"\n✓ Report generated: {report_path}")
    
    def _save_results(self):
        """Save raw results as JSON."""
        results_file = self.output_dir / "benchmark_results.json"
        
        output_data = {
            "configuration": {
                "level": self.level,
                "generations": self.generations,
                "population_size": self.population_size,
                "llm_provider": self.llm_provider,
                "test_iterations": self.test_iterations,
                "test_warmup_iterations": self.test_warmup_iterations,
                "test_seed": self.test_seed,
                "timestamp": datetime.now().isoformat()
            },
            "summary": self.summary_stats,
            "results": self.results
        }
        
        with open(results_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        if RICH_AVAILABLE:
            console.print(f"[green]✓[/green] Results saved: {results_file}")
        else:
            print(f"✓ Results saved: {results_file}")
    
    def _display_summary(self):
        """Display summary table using Rich."""
        console.print("\n")
        
        # Summary statistics
        table = Table(title="Benchmark Summary", box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="yellow")
        table.add_column("Value", justify="right", style="green")
        
        table.add_row("Total Problems", str(self.summary_stats["total_problems"]))
        table.add_row("Successful", str(self.summary_stats["successful"]))
        table.add_row("Failed", str(self.summary_stats["failed"]))
        table.add_row("Total Time", f"{self.summary_stats['total_time']:.2f}s")
        
        if self.summary_stats["improvements"]:
            avg_improvement = sum(self.summary_stats["improvements"]) / len(self.summary_stats["improvements"])
            table.add_row("Avg Improvement", f"{avg_improvement:.2f}%")
            table.add_row("Best Improvement", f"{max(self.summary_stats['improvements']):.2f}%")
        
        console.print(table)
        
        # Detailed results
        console.print("\n")
        results_table = Table(title="Problem Results", box=box.ROUNDED, show_header=True, header_style="bold cyan")
        results_table.add_column("Problem", style="yellow")
        results_table.add_column("Status", justify="center")
        results_table.add_column("Improvement", justify="right", style="green")
        results_table.add_column("Pareto Solutions", justify="right", style="blue")
        
        for problem, data in self.results.items():
            status_icon = "✅" if data.get("status") == "success" else "❌"
            improvement = f"{data.get('improvement_percent', 0):.2f}%" if "improvement_percent" in data else "N/A"
            pareto_count = str(data.get("pareto_count", 0))
            
            results_table.add_row(problem, status_icon, improvement, pareto_count)
        
        console.print(results_table)
        
        console.print(f"\n[bold green]✓ Complete![/bold green] Results saved to: {self.output_dir}")
    
    def _display_summary_simple(self):
        """Display summary without Rich."""
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        print(f"Total Problems: {self.summary_stats['total_problems']}")
        print(f"Successful: {self.summary_stats['successful']}")
        print(f"Failed: {self.summary_stats['failed']}")
        print(f"Total Time: {self.summary_stats['total_time']:.2f}s")
        
        if self.summary_stats["improvements"]:
            avg_improvement = sum(self.summary_stats["improvements"]) / len(self.summary_stats["improvements"])
            print(f"Average Improvement: {avg_improvement:.2f}%")
        
        print("\n" + "="*60)
        print("PROBLEM RESULTS")
        print("="*60)
        
        for problem, data in self.results.items():
            status = "✓" if data.get("status") == "success" else "✗"
            improvement = f"{data.get('improvement_percent', 0):.2f}%" if "improvement_percent" in data else "N/A"
            print(f"{status} {problem}: {improvement}")
        
        print(f"\n✓ Results saved to: {self.output_dir}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run comprehensive HEDGE benchmark on EvoEval problems"
    )
    parser.add_argument(
        "--level",
        choices=["micro", "basic", "standard", "advanced", "aggressive"],
        default="aggressive",
        help="Optimization level (default: standard)"
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=15,
        help="Number of generations per problem (default: 15)"
    )
    parser.add_argument(
        "--population-size",
        type=int,
        default=10,
        help="Population size (default: 10)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for results (default: evoeval_results_<timestamp>)"
    )
    parser.add_argument(
        "--no-visualize",
        action="store_true",
        help="Disable visualization generation"
    )
    parser.add_argument(
        "--llm",
        choices=["gemini", "openai"],
        default="gemini",
        help="LLM provider for advanced/aggressive levels (default: gemini)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: reduced generations for faster testing"
    )
    parser.add_argument(
        "--test-iterations",
        type=int,
        default=10,
        help="Number of test iterations per candidate (default: 3)"
    )
    parser.add_argument(
        "--test-warmup-iterations",
        type=int,
        default=3,
        help="Number of warmup iterations before each test (default: 5)"
    )
    parser.add_argument(
        "--test-seed",
        type=int,
        default=42,
        help="Base seed for reproducible test execution (default: 42)"
    )
    
    args = parser.parse_args()
    
    # Adjust for quick mode
    if args.quick:
        args.generations = max(5, args.generations // 3)
        print(f"Quick mode: Using {args.generations} generations")
    
    # Create and run benchmark
    runner = EvoEvalBenchmarkRunner(
        level=args.level,
        generations=args.generations,
        population_size=args.population_size,
        output_dir=args.output_dir,
        visualize=not args.no_visualize,
        llm_provider=args.llm,
        test_iterations=args.test_iterations,
        test_warmup_iterations=args.test_warmup_iterations,
        test_seed=args.test_seed
    )
    
    runner.run_all_benchmarks()


if __name__ == "__main__":
    main()
