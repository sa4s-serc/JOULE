#!/usr/bin/env python3
"""
HEDGE Examples Runner
=====================

Run all example optimizations to demonstrate HEDGE capabilities.
"""

import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

EXAMPLES = [
    {
        "name": "Fibonacci Optimization",
        "target": "examples/target_fib.py",
        "tests": "examples/test_target_fib.py",
        "level": "advanced",
        "description": "Recursive → Iterative Fibonacci (O(2^n) → O(n))",
        "expected_improvement": 95.0,
    },
    {
        "name": "Search Optimization",
        "target": "examples/target_search.py",
        "tests": "examples/test_target_search.py",
        "level": "standard",
        "description": "Linear search with Python idioms",
        "expected_improvement": 30.0,
    },
    {
        "name": "Complex Algorithm",
        "target": "examples/target_complex.py",
        "tests": "examples/test_target_complex.py",
        "level": "advanced",
        "description": "Multiple algorithmic improvements",
        "expected_improvement": 60.0,
    },
    {
        "name": "Formal Example",
        "target": "examples/target_formal.py",
        "tests": "examples/test_target_formal.py",
        "level": "basic",
        "description": "Syntactic and micro optimizations",
        "expected_improvement": 20.0,
    },
]


def check_files_exist():
    """Check if all example files exist."""
    missing_files = []

    for example in EXAMPLES:
        for file_key in ["target", "tests"]:
            file_path = Path(example[file_key])
            if not file_path.exists():
                missing_files.append(str(file_path))

    return missing_files


def run_example(example):
    """Run a single example optimization."""
    cli_script = "hedge.py"

    cmd = [
        sys.executable,
        cli_script,
        "optimize",
        example["target"],
        example["tests"],
        "--level",
        example["level"],
        "--generations",
        "8",  # Reduced for demo
        "--visualize",
        "--quiet",
    ]

    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start_time

    return {
        "success": result.returncode == 0,
        "duration": duration,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def extract_improvement(output):
    """Extract improvement percentage from output."""
    for line in output.split("\n"):
        if "% energy improvement" in line:
            try:
                # Extract percentage from line like "↓ 94.2% energy improvement"
                parts = line.split("%")
                if parts:
                    percent_part = parts[0].split()[-1]
                    return float(percent_part)
            except:
                pass
    return 0.0


def main():
    """Main function to run all examples."""
    console.print("\n[bold cyan]🚀 HEDGE Examples Demonstration[/bold cyan]\n")

    # Check if files exist
    missing_files = check_files_exist()
    if missing_files:
        console.print("[bold red]❌ Missing example files:[/bold red]")
        for file in missing_files:
            console.print(f"  • {file}")
        console.print("\nPlease ensure all example files are present.")
        return 1

    # Determine which CLI to use
    cli_name = "HEDGE CLI (hedge.py)"

    console.print(f"[bold]Using:[/bold] {cli_name}")
    console.print(f"[bold]Examples to run:[/bold] {len(EXAMPLES)}\n")

    results = []

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:

        for i, example in enumerate(EXAMPLES):
            task = progress.add_task(f"Running {example['name']}...", total=None)

            result = run_example(example)

            # Extract improvement if successful
            improvement = 0.0
            if result["success"]:
                improvement = extract_improvement(result["stdout"])

            results.append({"example": example, "result": result, "improvement": improvement})

            progress.update(task, description=f"✅ {example['name']} complete")
            progress.remove_task(task)

    # Display results
    console.print("\n[bold green]📊 Results Summary[/bold green]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Example", style="yellow")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right", style="blue")
    table.add_column("Improvement", justify="right", style="green")
    table.add_column("Expected", justify="right", style="dim")
    table.add_column("Description", style="dim")

    total_duration = 0
    successful_runs = 0

    for result_data in results:
        example = result_data["example"]
        result = result_data["result"]
        improvement = result_data["improvement"]

        status = "✅" if result["success"] else "❌"
        duration_str = f"{result['duration']:.1f}s"
        improvement_str = f"{improvement:.1f}%" if improvement > 0 else "N/A"
        expected_str = f"{example['expected_improvement']:.1f}%"

        table.add_row(
            example["name"],
            status,
            duration_str,
            improvement_str,
            expected_str,
            example["description"],
        )

        total_duration += result["duration"]
        if result["success"]:
            successful_runs += 1

    console.print(table)

    # Summary statistics
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  • Successful runs: {successful_runs}/{len(EXAMPLES)}")
    console.print(f"  • Total duration: {total_duration:.1f}s")
    console.print(f"  • Average per example: {total_duration/len(EXAMPLES):.1f}s")

    # Show any errors
    failed_examples = [r for r in results if not r["result"]["success"]]
    if failed_examples:
        console.print(f"\n[bold red]❌ Failed Examples:[/bold red]")
        for result_data in failed_examples:
            example = result_data["example"]
            result = result_data["result"]
            console.print(f"\n[bold]{example['name']}:[/bold]")
            if result["stderr"]:
                console.print(f"Error: {result['stderr']}")
            else:
                console.print("No error details available")

    # Next steps
    if successful_runs > 0:
        console.print(f"\n[bold green]🎉 Examples completed![/bold green]")
        console.print("Check the 'experiments/' directory for detailed results and visualizations.")
        console.print("\nNext steps:")
        console.print("  1. Open HTML reports in experiments/*/visualizations/report.html")
        console.print("  2. Compare optimized code files (*_optimized.py)")
        console.print("  3. Try running with different optimization levels")

    return 0 if successful_runs == len(EXAMPLES) else 1


if __name__ == "__main__":
    sys.exit(main())
