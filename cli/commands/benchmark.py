"""Benchmark command for HEDGE CLI."""

import json
import time
from pathlib import Path

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from cli.utils.banner import print_error, print_info, print_success

console = Console()

# Built-in benchmark problems
BENCHMARK_PROBLEMS = {
    "fibonacci": {
        "target": "examples/target_fib.py",
        "tests": "examples/test_target_fib.py",
        "description": "Recursive Fibonacci optimization (O(2^n) → O(n))",
        "expected_improvement": 95.0,
    },
    "search": {
        "target": "examples/target_search.py",
        "tests": "examples/test_target_search.py",
        "description": "Linear search optimization",
        "expected_improvement": 50.0,
    },
    "complex": {
        "target": "examples/target_complex.py",
        "tests": "examples/test_target_complex.py",
        "description": "Complex algorithm with multiple inefficiencies",
        "expected_improvement": 70.0,
    },
    "formal": {
        "target": "examples/target_formal.py",
        "tests": "examples/test_target_formal.py",
        "description": "Formal verification example",
        "expected_improvement": 30.0,
    },
}


@click.command()
@click.option(
    "--problems",
    type=str,
    help="Comma-separated list of problems to run (fibonacci,search,complex,formal)",
)
@click.option(
    "--level",
    type=click.Choice(["micro", "basic", "standard", "advanced"]),
    default="standard",
    help="Optimization level",
)
@click.option("--generations", type=int, default=10, help="Number of generations per problem")
@click.option(
    "--output-dir", "-o", type=click.Path(path_type=Path), help="Output directory for results"
)
@click.option("--compare-levels", is_flag=True, help="Compare different optimization levels")
@click.option("--quick", is_flag=True, help="Quick benchmark with reduced generations")
@click.option("--quick", is_flag=True, help="Quick benchmark with reduced generations")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML configuration file",
)
def benchmark_cmd(problems, level, generations, output_dir, compare_levels, quick, config=None):
    """
    Run benchmarks on example problems to evaluate HEDGE performance.

    This command runs optimization on built-in example problems and compares
    the results against expected performance improvements.
    """
    console.print("\n[bold cyan]Running HEDGE Benchmarks[/bold cyan]\n")

    # Adjust parameters for quick mode
    if quick:
        generations = max(3, generations // 3)
        console.print("[yellow]Quick mode enabled - using reduced generations[/yellow]\n")

    # Setup output directory
    if not output_dir:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"benchmarks/run_{timestamp}")

    output_dir.mkdir(parents=True, exist_ok=True)
    print_info(f"Benchmark results will be saved to: {output_dir}")

    # Determine which problems to run
    if problems:
        problem_list = [p.strip() for p in problems.split(",")]
        problem_list = [p for p in problem_list if p in BENCHMARK_PROBLEMS]
    else:
        problem_list = list(BENCHMARK_PROBLEMS.keys())

    if not problem_list:
        print_error("No valid problems specified")
        return 1

    # Run benchmarks
    if compare_levels:
        results = _run_level_comparison(problem_list, generations, output_dir, config)
    else:
        results = _run_single_level(problem_list, level, generations, output_dir, config)

    # Display results
    _display_benchmark_results(results, compare_levels)

    # Save results
    results_file = output_dir / "benchmark_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print_success(f"Benchmark completed! Results saved to {results_file}")

    return 0


def _run_single_level(problem_list, level, generations, output_dir, config_path=None):
    """Run benchmarks at a single optimization level."""
    results = {"level": level, "generations": generations, "problems": {}}

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:

        task = progress.add_task("Running benchmarks...", total=len(problem_list))

        for problem_name in problem_list:
            problem_info = BENCHMARK_PROBLEMS[problem_name]
            progress.update(task, description=f"Optimizing {problem_name}...")

            # Check if files exist
            target_path = Path(problem_info["target"])
            tests_path = Path(problem_info["tests"])

            if not target_path.exists() or not tests_path.exists():
                console.print(f"[yellow]Skipping {problem_name} - files not found[/yellow]")
                continue

            # Run optimization
            problem_result = _run_optimization(
                target_path, tests_path, level, generations, output_dir / problem_name, config_path
            )

            # Calculate improvement
            if problem_result and "solutions" in problem_result:
                improvement = _calculate_improvement(problem_result)
                expected = problem_info["expected_improvement"]

                problem_result.update(
                    {
                        "improvement_percent": improvement,
                        "expected_improvement": expected,
                        "meets_expectation": improvement >= expected * 0.8,  # 80% of expected
                        "description": problem_info["description"],
                    }
                )

            results["problems"][problem_name] = problem_result
            progress.advance(task)

    return results


def _run_level_comparison(problem_list, generations, output_dir, config_path=None):
    """Run benchmarks comparing different optimization levels."""
    levels = ["micro", "basic", "standard", "advanced"]
    results = {"comparison": True, "levels": levels, "generations": generations, "problems": {}}

    total_tasks = len(problem_list) * len(levels)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:

        task = progress.add_task("Running level comparison...", total=total_tasks)

        for problem_name in problem_list:
            problem_info = BENCHMARK_PROBLEMS[problem_name]
            results["problems"][problem_name] = {
                "description": problem_info["description"],
                "expected_improvement": problem_info["expected_improvement"],
                "levels": {},
            }

            for level in levels:
                progress.update(task, description=f"Optimizing {problem_name} ({level})...")

                # Check if files exist
                target_path = Path(problem_info["target"])
                tests_path = Path(problem_info["tests"])

                if not target_path.exists() or not tests_path.exists():
                    console.print(f"[yellow]Skipping {problem_name} - files not found[/yellow]")
                    continue

                # Run optimization
                level_result = _run_optimization(
                    target_path,
                    tests_path,
                    level,
                    generations,
                    output_dir / f"{problem_name}_{level}",
                    config_path,
                )

                if level_result:
                    improvement = _calculate_improvement(level_result)
                    level_result["improvement_percent"] = improvement

                results["problems"][problem_name]["levels"][level] = level_result
                progress.advance(task)

    return results


def _run_optimization(target_path, tests_path, level, generations, exp_dir, config_path=None):
    """Run a single optimization and return results."""
    try:
        from click.testing import CliRunner

        from cli.commands.optimize import optimize_cmd

        # Create experiment directory
        exp_dir.mkdir(parents=True, exist_ok=True)

        # Run optimization using the CLI command
        runner = CliRunner()
        args = [
            str(target_path),
            str(tests_path),
            "--level",
            level,
            "--generations",
            str(generations),
            "--out-dir",
            str(exp_dir),
            "--quiet",
        ]

        if config_path:
            args.extend(["--config", str(config_path)])

        result = runner.invoke(optimize_cmd, args)

        if result.exit_code != 0:
            return {"error": f"Optimization failed: {result.output}"}

        # Load results
        results_file = exp_dir / "pareto_results.json"
        stats_file = exp_dir / "statistics.json"

        optimization_result = {}

        if results_file.exists():
            with open(results_file) as f:
                optimization_result["solutions"] = json.load(f)

        if stats_file.exists():
            with open(stats_file) as f:
                optimization_result["statistics"] = json.load(f)

        return optimization_result

    except Exception as e:
        return {"error": str(e)}


def _calculate_improvement(result):
    """Calculate energy improvement percentage from optimization result."""
    if "solutions" not in result or not result["solutions"]:
        return 0.0

    solutions = result["solutions"]
    if len(solutions) < 2:
        return 0.0

    # Assume first solution is baseline, find best solution
    baseline_energy = solutions[0]["metrics"].get("energy_joules", 1.0)
    best_energy = min(sol["metrics"].get("energy_joules", baseline_energy) for sol in solutions)

    if baseline_energy <= 0:
        return 0.0

    improvement = ((baseline_energy - best_energy) / baseline_energy) * 100
    return max(0.0, improvement)


def _display_benchmark_results(results, is_comparison):
    """Display benchmark results in a formatted table."""
    console.print("\n[bold green]Benchmark Results[/bold green]\n")

    if is_comparison:
        _display_comparison_results(results)
    else:
        _display_single_level_results(results)


def _display_single_level_results(results):
    """Display results for single-level benchmark."""
    table = Table(
        title=f"Optimization Results - Level: {results['level']}",
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Problem", style="yellow")
    table.add_column("Description", style="dim")
    table.add_column("Improvement", justify="right", style="green")
    table.add_column("Expected", justify="right", style="blue")
    table.add_column("Status", justify="center")

    for problem_name, problem_result in results["problems"].items():
        if "error" in problem_result:
            table.add_row(problem_name, "Error occurred", "N/A", "N/A", "[red]Error[/red]")
            continue

        improvement = problem_result.get("improvement_percent", 0)
        expected = problem_result.get("expected_improvement", 0)
        meets_expectation = problem_result.get("meets_expectation", False)

        status = "[green]Pass[/green]" if meets_expectation else "[yellow]Partial[/yellow]"

        table.add_row(
            problem_name,
            problem_result.get("description", ""),
            f"{improvement:.1f}%",
            f"{expected:.1f}%",
            status,
        )

    console.print(table)


def _display_comparison_results(results):
    """Display results for level comparison benchmark."""
    for problem_name, problem_data in results["problems"].items():
        console.print(f"\n[bold]{problem_name.title()}[/bold] - {problem_data['description']}")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Level", style="yellow")
        table.add_column("Improvement", justify="right", style="green")
        table.add_column("Solutions", justify="right", style="blue")
        table.add_column("Success Rate", justify="right", style="magenta")

        for level, level_result in problem_data["levels"].items():
            if "error" in level_result:
                table.add_row(level, "Error", "N/A", "N/A")
                continue

            improvement = level_result.get("improvement_percent", 0)
            solutions_count = len(level_result.get("solutions", []))
            success_rate = level_result.get("statistics", {}).get("success_rate", 0)

            table.add_row(
                level, f"{improvement:.1f}%", str(solutions_count), f"{success_rate:.1f}%"
            )

        console.print(table)
