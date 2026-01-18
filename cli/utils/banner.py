"""Banner and branding utilities for HEDGE CLI."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.table import Table
from .version import __version__, __description__

console = Console()

def print_banner():
    """Print the HEDGE banner with version information."""
    banner_text = Text("""
HEDGE
""", style="bold blue")
    
    title = Text(__description__, style="bold white")
    subtitle = Text(f"Version {__version__}", style="dim white")
    
    console.print(Panel(
        Align.center(banner_text + Text("\n") + title + Text("\n") + subtitle),
        style="bold blue",
        border_style="blue"
    ))

def print_welcome():
    """Print a welcome message with usage information."""
    welcome_panel = Panel(
        "[bold blue]HEDGE - Code Optimization System[/bold blue]\n\n"
        "[bold]Quick Start:[/bold]\n"
        "   • [cyan]hedge optimize target.py tests.py[/cyan] - Optimize code\n"
        "   • [cyan]hedge config init[/cyan] - Configure system\n"
        "   • [cyan]hedge project init project_name[/cyan] - Create project\n\n"
        "[bold]Help:[/bold]\n"
        "   • [cyan]hedge --help[/cyan] - Show all commands\n"
        "   • [cyan]hedge COMMAND --help[/cyan] - Command help\n"
        "   • [cyan]docs/QUICKSTART.md[/cyan] - Documentation",
        title="Getting Started",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(welcome_panel)

def print_feature_highlights():
    """Print system features in organized layout."""
    features = [
        ("AI Integration", "Semantic optimization\nwith LLM support"),
        ("Hierarchical System", "Four-layer mutation\narchitecture"),
        ("Multi-Objective", "Pareto optimization\nfor energy and time"),
        ("Code Analysis", "Complexity metrics\nand recommendations"),
        ("Visualizations", "Charts and reports\nfor results"),
        ("Project Management", "Templates and\nworkflow organization")
    ]
    
    feature_panels = []
    for title, desc in features:
        panel = Panel(
            f"[bold]{title}[/bold]\n[dim]{desc}[/dim]",
            border_style="blue",
            padding=(0, 1),
            width=20
        )
        feature_panels.append(panel)
    
    console.print("\n[bold]System Features:[/bold]")
    console.print(Columns(feature_panels, equal=True, expand=True))

def print_success(message: str):
    """Print a success message."""
    console.print(f"[bold green]Success:[/bold green] {message}")

def print_error(message: str):
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")

def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")

def print_info(message: str):
    """Print an information message."""
    console.print(f"[bold blue]Info:[/bold blue] {message}")

def print_step(step: int, total: int, message: str):
    """Print a step in a process."""
    console.print(f"[bold cyan]Step {step}/{total}:[/bold cyan] {message}")

def print_optimization_summary(solutions_count: int, duration: float, improvement: float = None):
    """Print optimization results summary."""
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_column(style="bold cyan")
    summary_table.add_column(style="green")
    
    summary_table.add_row("Solutions Found:", str(solutions_count))
    summary_table.add_row("Duration:", f"{duration:.1f}s")
    if improvement is not None:
        summary_table.add_row("Energy Improvement:", f"{improvement:.1f}%")
    
    console.print(Panel(
        summary_table,
        title="[bold green]Optimization Complete[/bold green]",
        border_style="green",
        padding=(1, 2)
    ))

def print_command_help(command: str, description: str, examples: list):
    """Print help information for a command."""
    console.print(f"\n[bold cyan]{command}[/bold cyan] - {description}\n")
    
    if examples:
        console.print("[bold]Examples:[/bold]")
        for example in examples:
            console.print(f"  [dim]$[/dim] [cyan]{example}[/cyan]")
        console.print()

def create_progress_table(title: str, columns: list):
    """Create a styled table for progress display."""
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for col_name, col_style in columns:
        table.add_column(col_name, style=col_style)
    return table