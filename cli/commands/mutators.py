"""
Mutator inspection and management commands for HEDGE CLI.
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.utils.mutator_factory import create_mutators
from src.application.mutators.base import MutationLayer
from src.application.mutators.registry import get_registry

console = Console()


@click.group()
def mutators_cmd():
    """Inspect and manage HEDGE mutators."""


@mutators_cmd.command("list")
@click.option(
    "--level",
    type=click.Choice(["micro", "basic", "standard", "advanced", "aggressive"]),
    default="standard",
    help="Show mutators for specific optimization level",
)
@click.option(
    "--layer",
    type=click.Choice(["semantic", "algorithmic", "syntactic", "micro"]),
    help="Filter by specific layer",
)
@click.option("--detailed", "-d", is_flag=True, help="Show detailed strategy information")
def list_mutators(level, layer, detailed):
    """List all available mutators and their strategies."""

    console.print(f"\n[bold cyan]🔧 HEDGE Mutators - Level: {level}[/bold cyan]")

    try:
        mutators, enabled_layers_set, llm_client = create_mutators(level=level)
        registry = get_registry()
        all_mutators = registry.list_all_mutators()

        # Filter layers if specified
        if layer:
            layer_enum = MutationLayer(layer)
            enabled_layers_set = {layer_enum} if layer_enum in enabled_layers_set else set()

        layer_colors = {
            MutationLayer.SEMANTIC: "red",
            MutationLayer.ALGORITHMIC: "blue",
            MutationLayer.SYNTACTIC: "green",
            MutationLayer.MICRO: "yellow",
        }

        layer_descriptions = {
            MutationLayer.SEMANTIC: "High-level algorithmic transformations using LLM",
            MutationLayer.ALGORITHMIC: "Data structure and complexity optimizations",
            MutationLayer.SYNTACTIC: "Pythonic idioms and code pattern improvements",
            MutationLayer.MICRO: "Low-level optimizations and peephole improvements",
        }

        total_mutators = 0
        total_strategies = 0

        for layer_enum in [
            MutationLayer.SEMANTIC,
            MutationLayer.ALGORITHMIC,
            MutationLayer.SYNTACTIC,
            MutationLayer.MICRO,
        ]:
            if layer_enum not in enabled_layers_set:
                continue

            layer_mutators = registry.get_layer_mutators(layer_enum)
            if not layer_mutators:
                continue

            # Layer header
            layer_color = layer_colors.get(layer_enum, "white")
            console.print(
                f"\n[bold {layer_color}]📁 {layer_enum.value.upper()} LAYER[/bold {layer_color}]"
            )
            console.print(f"[dim]{layer_descriptions[layer_enum]}[/dim]")

            if detailed:
                # Detailed table for this layer
                mutator_table = Table(show_header=True, header_style=f"bold {layer_color}")
                mutator_table.add_column("Mutator", style="white", width=25)
                mutator_table.add_column("Strategies", style="yellow", width=50)
                mutator_table.add_column("Dependencies", style="cyan", width=20)

                for mutator_name in layer_mutators:
                    if mutator_name in all_mutators:
                        mutator_info = all_mutators[mutator_name]

                        # Check if this mutator is active
                        mutator_active = any(
                            m.__class__.__name__ == mutator_info.mutator_class.__name__
                            for m in mutators
                        )

                        if mutator_active:
                            total_mutators += 1
                            strategies = list(mutator_info.strategies)
                            total_strategies += len(strategies)

                            # Format strategies with line breaks for readability
                            strategy_text = "\n".join(f"• {s}" for s in strategies)

                            dependencies = (
                                ", ".join(mutator_info.dependencies)
                                if mutator_info.dependencies
                                else "None"
                            )

                            mutator_table.add_row(
                                mutator_info.mutator_class.__name__.replace("Mutator", "").replace(
                                    "Optimizer", ""
                                ),
                                strategy_text,
                                dependencies,
                            )

                console.print(mutator_table)
            else:
                # Simple list for this layer
                active_mutators = []
                for mutator_name in layer_mutators:
                    if mutator_name in all_mutators:
                        mutator_info = all_mutators[mutator_name]
                        mutator_active = any(
                            m.__class__.__name__ == mutator_info.mutator_class.__name__
                            for m in mutators
                        )
                        if mutator_active:
                            total_mutators += 1
                            strategies = list(mutator_info.strategies)
                            total_strategies += len(strategies)

                            name = mutator_info.mutator_class.__name__.replace(
                                "Mutator", ""
                            ).replace("Optimizer", "")
                            active_mutators.append(f"• {name} ({len(strategies)} strategies)")

                if active_mutators:
                    console.print("\n".join(active_mutators))

        # Summary
        console.print(f"\n[bold green]📊 Summary[/bold green]")
        console.print(f"Total Active Mutators: {total_mutators}")
        console.print(f"Total Strategies: {total_strategies}")
        console.print(f"LLM Support: {'✓ Enabled' if llm_client else '✗ Disabled'}")

        if not llm_client and MutationLayer.SEMANTIC in enabled_layers_set:
            console.print(
                "[yellow]⚠ Warning: Semantic layer is enabled but LLM is not configured. Semantic mutations will be limited.[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@mutators_cmd.command("info")
@click.argument("mutator_name")
def mutator_info(mutator_name):
    """Show detailed information about a specific mutator."""

    registry = get_registry()
    all_mutators = registry.list_all_mutators()

    # Try to find the mutator (case-insensitive, partial match)
    found_mutator = None
    for name, info in all_mutators.items():
        if (
            mutator_name.lower() in name.lower()
            or mutator_name.lower() in info.mutator_class.__name__.lower()
        ):
            found_mutator = (name, info)
            break

    if not found_mutator:
        console.print(f"[red]Mutator '{mutator_name}' not found.[/red]")
        console.print("\n[dim]Use 'hedge mutators list' to see available mutators.[/dim]")
        return

    name, info = found_mutator

    console.print(f"\n[bold cyan]🔍 Mutator Information: {info.mutator_class.__name__}[/bold cyan]")

    # Basic info panel
    info_text = f"""
[bold]Layer:[/bold] {info.layer.value.title()}
[bold]Class:[/bold] {info.mutator_class.__name__}
[bold]Strategies:[/bold] {len(info.strategies)}
[bold]Dependencies:[/bold] {', '.join(info.dependencies) if info.dependencies else 'None'}
[bold]Conflicts:[/bold] {', '.join(info.conflicts) if info.conflicts else 'None'}
    """.strip()

    console.print(Panel(info_text, title="Basic Information", border_style="blue"))

    # Strategies table
    if info.strategies:
        strategies_table = Table(
            title="Available Strategies", show_header=True, header_style="bold green"
        )
        strategies_table.add_column("Strategy", style="yellow", width=30)
        strategies_table.add_column("Description", style="white", width=50)

        for strategy in sorted(info.strategies):
            # Try to get description from the mutator class if available
            description = "No description available"
            try:
                # Create a temporary instance to get strategy descriptions
                temp_instance = info.mutator_class(enabled_strategies={strategy})
                if hasattr(temp_instance, "get_strategy_description"):
                    description = temp_instance.get_strategy_description(strategy)
            except:
                pass

            strategies_table.add_row(strategy, description)

        console.print(strategies_table)

    # Usage example
    example_text = f"""
[bold]CLI Usage:[/bold]
hedge optimize target.py tests.py --level advanced --layers {info.layer.value}

[bold]Programmatic Usage:[/bold]
from {info.mutator_class.__module__} import {info.mutator_class.__name__}
mutator = {info.mutator_class.__name__}(enabled_strategies={{"strategy_name"}})
    """.strip()

    console.print(Panel(example_text, title="Usage Examples", border_style="green"))


@mutators_cmd.command("test")
@click.argument("mutator_name")
@click.argument("code_file", type=click.Path(exists=True))
@click.option("--strategy", help="Test specific strategy")
def test_mutator(mutator_name, code_file, strategy):
    """Test a mutator on a code file without full optimization."""

    console.print(f"\n[bold cyan]🧪 Testing Mutator: {mutator_name}[/bold cyan]")
    console.print(f"[dim]File: {code_file}[/dim]")

    # This would implement mutator testing functionality
    # For now, show what would be done
    console.print("[yellow]⚠ Mutator testing functionality coming soon![/yellow]")
    console.print("[dim]This will allow testing individual mutators on code files.[/dim]")


# Export the command group
__all__ = ["mutators_cmd"]
