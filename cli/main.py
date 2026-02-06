#!/usr/bin/env python3
"""
HEDGE - Hierarchical Evolutionary Domain-Guided Engine
======================================================

Modern CLI interface with improved usability and organization.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import click
from rich.console import Console

from cli.commands.analyze import analyze_cmd
from cli.commands.app import app_cmd
from cli.commands.benchmark import benchmark_cmd
from cli.commands.config import config_cmd
from cli.commands.mutators import mutators_cmd
from cli.commands.optimize import optimize_cmd
from cli.commands.project import project_cmd
from cli.commands.serve import serve_cmd
from cli.commands.visualize import visualize_cmd
from cli.utils.banner import (console, print_banner, print_command_help,
                              print_feature_highlights, print_welcome)
from cli.utils.interactive_help import help_cmd

console = Console()


@click.group(invoke_without_command=True)
@click.option("--features", is_flag=True, help="Show feature highlights")
@click.pass_context
def cli(ctx, features):
    """
    HEDGE - Hierarchical Evolutionary Domain-Guided Engine

    A code optimization system using evolutionary strategies for Python code improvement.
    """
    if features:
        print_banner()
        print_feature_highlights()
        return

    if ctx.invoked_subcommand is None:
        print_banner()
        print_welcome()

        # Show available commands with descriptions
        commands_info = [
            (
                "optimize",
                "Optimize Python code using evolutionary strategies",
                [
                    "hedge optimize mycode.py tests.py",
                    "hedge optimize mycode.py tests.py --level advanced --visualize",
                ],
            ),
            (
                "mutators",
                "Inspect and manage HEDGE mutators",
                [
                    "hedge mutators list --detailed",
                    "hedge mutators info AdvancedAlgorithmicOptimizer",
                ],
            ),
            (
                "analyze",
                "Analyze code complexity and structure",
                ["hedge analyze mycode.py --detailed", "hedge analyze mycode.py --format json"],
            ),
            (
                "visualize",
                "Generate visualizations from optimization results",
                [
                    "hedge visualize experiments/run_20250118_120000",
                    "hedge visualize results/ --interactive",
                ],
            ),
            (
                "benchmark",
                "Run performance benchmarks on example problems",
                ["hedge benchmark --quick", "hedge benchmark --compare-levels"],
            ),
            (
                "config",
                "Manage HEDGE configuration settings",
                ["hedge config init", "hedge config show"],
            ),
            (
                "help",
                "Interactive help and guidance",
                ["hedge help --topic levels", "hedge help --topic troubleshooting"],
            ),
            ("app", "Start the interactive web interface", ["hedge app", "hedge app --port 3000"]),
        ]

        console.print("\n[bold]Available Commands:[/bold]")
        for cmd, desc, examples in commands_info:
            print_command_help(cmd, desc, examples[:1])  # Show one example each

        console.print(
            "[dim]Use 'hedge COMMAND --help' for detailed information about each command.[/dim]"
        )
        console.print(
            "[dim]New to HEDGE? Try: [cyan]hedge config init[/cyan] to get started.[/dim]"
        )


# Register command groups
cli.add_command(optimize_cmd, name="optimize")
cli.add_command(mutators_cmd, name="mutators")
cli.add_command(analyze_cmd, name="analyze")
cli.add_command(visualize_cmd, name="visualize")
cli.add_command(benchmark_cmd, name="benchmark")
cli.add_command(config_cmd, name="config")
cli.add_command(project_cmd, name="project")
cli.add_command(serve_cmd, name="serve")
cli.add_command(app_cmd, name="app")
cli.add_command(help_cmd, name="help")

if __name__ == "__main__":
    cli()
