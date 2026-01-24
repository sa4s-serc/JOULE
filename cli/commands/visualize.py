"""Visualization command for HEDGE CLI."""

from pathlib import Path

import click
from rich.console import Console

from cli.utils.banner import print_error, print_info, print_success
from src.utils.visualizer import ResultVisualizer

console = Console()


@click.command()
@click.argument("results_dir", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Custom output directory for visualizations",
)
@click.option(
    "--format",
    type=click.Choice(["html", "png", "svg", "pdf"]),
    default="html",
    help="Output format",
)
@click.option(
    "--charts",
    type=str,
    help="Comma-separated list of charts to generate: pareto,evolution,mutations,metrics",
)
@click.option("--interactive", is_flag=True, help="Generate interactive visualizations")
@click.option(
    "--theme",
    type=click.Choice(["light", "dark", "auto"]),
    default="auto",
    help="Visualization theme",
)
def visualize_cmd(results_dir, output_dir, format, charts, interactive, theme):
    """
    Generate visualizations from optimization results.

    RESULTS_DIR: Directory containing optimization results
    """
    try:
        console.print(f"\n[bold cyan]Generating Visualizations[/bold cyan]\n")
        print_info(f"Processing results from: {results_dir}")

        # Validate results directory
        if not (results_dir / "pareto_results.json").exists():
            print_error("Invalid results directory - missing pareto_results.json")
            return 1

        # Setup output directory
        if output_dir:
            viz_dir = output_dir
        else:
            viz_dir = results_dir / "visualizations"

        viz_dir.mkdir(exist_ok=True)

        # Create visualizer
        visualizer = ResultVisualizer(results_dir)

        # Configure visualizer options
        viz_options = {
            "format": format,
            "interactive": interactive,
            "theme": theme,
            "output_dir": viz_dir,
        }

        # Generate specific charts or all
        if charts:
            chart_list = [chart.strip() for chart in charts.split(",")]
            _generate_specific_charts(visualizer, chart_list, viz_options)
        else:
            _generate_all_charts(visualizer, viz_options)

        print_success("Visualizations generated successfully!")

        # Show output location
        if format == "html":
            report_path = viz_dir / "report.html"
            if report_path.exists():
                console.print(f"  View report: [link]file://{report_path}[/link]")

        console.print(f"  Output directory: {viz_dir}")

        return 0

    except Exception as e:
        print_error(f"Visualization failed: {str(e)}")
        return 1


def _generate_all_charts(visualizer, options):
    """Generate all available charts."""
    console.print("Generating all visualizations...")

    with console.status("[bold green]Creating charts..."):
        # Generate standard visualizations
        visualizer.generate_pareto_front()
        console.print("  Pareto front chart")

        visualizer.generate_evolution_progress()
        console.print("  Evolution progress chart")

        visualizer.generate_mutation_effectiveness()
        console.print("  Mutation effectiveness chart")

        visualizer.generate_metrics_history()
        console.print("  Metrics history chart")

        # Generate comprehensive report
        visualizer.generate_comprehensive_report()
        console.print("  Comprehensive HTML report")


def _generate_specific_charts(visualizer, chart_list, options):
    """Generate specific charts based on user selection."""
    chart_generators = {
        "pareto": (visualizer.generate_pareto_front, "Pareto front chart"),
        "evolution": (visualizer.generate_evolution_progress, "Evolution progress chart"),
        "mutations": (visualizer.generate_mutation_effectiveness, "Mutation effectiveness chart"),
        "metrics": (visualizer.generate_metrics_history, "Metrics history chart"),
    }

    for chart_name in chart_list:
        if chart_name in chart_generators:
            generator, description = chart_generators[chart_name]
            with console.status(f"[bold green]Generating {description}..."):
                generator()
            console.print(f"  {description}")
        else:
            console.print(f"  Unknown chart type: {chart_name}")

    # Always generate report if HTML format
    if options["format"] == "html":
        with console.status("[bold green]Generating HTML report..."):
            visualizer.generate_comprehensive_report()
        console.print("  Comprehensive HTML report")
