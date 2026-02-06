"""Interactive help system for HEDGE CLI."""

import click
from rich.box import DOUBLE, ROUNDED
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def show_optimization_levels_help():
    """Show detailed help about optimization levels."""
    console.print("\n[bold cyan]🚀 HEDGE Optimization Levels[/bold cyan]\n")
    console.print("[dim]Choose the right balance of speed and optimization depth.[/dim]\n")

    levels = [
        {
            "name": "micro",
            "icon": "⚡",
            "speed": "Very Fast",
            "description": "Safe micro-optimizations",
            "features": ["Constant folding", "Dead code elimination", "Strength reduction"],
            "use_case": "Production code, quick wins",
            "api_key": False,
        },
        {
            "name": "basic",
            "icon": "🧹",
            "speed": "Fast",
            "description": "Python idioms and patterns",
            "features": ["Micro optimizations", "List comprehensions", "Built-in functions"],
            "use_case": "Code cleanup, Python best practices",
            "api_key": False,
        },
        {
            "name": "standard",
            "icon": "⚖️",
            "speed": "Moderate",
            "description": "Algorithmic improvements",
            "features": ["Basic optimizations", "Data structure selection", "Complexity reduction"],
            "use_case": "General optimization (recommended)",
            "api_key": False,
        },
        {
            "name": "advanced",
            "icon": "🧠",
            "speed": "Slower",
            "description": "AI-powered semantic optimization",
            "features": ["Standard optimizations", "Algorithm intent", "LLM-based improvements"],
            "use_case": "Maximum optimization, research",
            "api_key": True,
        },
        {
            "name": "aggressive",
            "icon": "🔥",
            "speed": "Slowest",
            "description": "All optimizations enabled",
            "features": ["All layers active", "Experimental features", "Maximum settings"],
            "use_case": "Research, experimental optimization",
            "api_key": True,
        },
    ]

    for level in levels:
        # Create level panel
        features_text = "\n".join([f"[green]✓[/green] {feature}" for feature in level["features"]])
        api_text = (
            "[bold yellow]Requires API Key[/bold yellow]"
            if level["api_key"]
            else "[bold green]No API Key Needed[/bold green]"
        )

        # Header
        header = Text(f"{level['icon']} {level['name'].upper()}", style="bold cyan")

        content_table = Table(show_header=False, box=None, padding=(0, 2))
        content_table.add_column("Key", style="dim")
        content_table.add_column("Value")

        content_table.add_row("Description:", level["description"])
        content_table.add_row("Speed:", level["speed"])
        content_table.add_row("Use Case:", level["use_case"])

        grid = Table.grid(expand=True)
        grid.add_column()
        grid.add_column(justify="right")
        grid.add_row(content_table, Text(features_text))

        panel = Panel(
            grid,
            title=header,
            subtitle=api_text,
            border_style="cyan" if not level["api_key"] else "yellow",
            box=ROUNDED,
            padding=(1, 2),
        )
        console.print(panel)
        console.print()


def show_mutators_help():
    """Show detailed help about mutators."""
    console.print("\n[bold cyan]🧬 HEDGE Mutator System[/bold cyan]\n")
    console.print("[dim]A four-layer hierarchical system inspired by biological evolution.[/dim]\n")

    layers = {
        "Semantic Layer": {
            "icon": "🧠",
            "description": "AI-powered algorithm and intent optimization",
            "mutators": [
                ("AlgorithmicIntentMutator", "Algorithm selection and Big-O optimization"),
                ("ProgramIntentMutator", "Logic simplification and control flow"),
            ],
            "examples": ["O(2^n) → O(n) Fibonacci", "Recursive → Iterative"],
            "requires_llm": True,
            "color": "magenta",
        },
        "Algorithmic Layer": {
            "icon": "🧮",
            "description": "Data structures and complexity optimization",
            "mutators": [
                ("DataStructureOptimizer", "List → Set conversion, access patterns"),
                ("ComplexityReducer", "Nested loop reduction, math optimizations"),
            ],
            "examples": ["Linear search → Set membership", "Nested loops → Single pass"],
            "requires_llm": False,
            "color": "blue",
        },
        "Syntactic Layer": {
            "icon": "📝",
            "description": "Python idioms and code patterns",
            "mutators": [
                ("PythonicIdiomOptimizer", "Comprehensions, built-ins, iterators"),
                ("CodePatternOptimizer", "LLM-based pattern improvements"),
            ],
            "examples": ["Manual loops → Comprehensions", "range(len()) → enumerate()"],
            "requires_llm": False,
            "color": "green",
        },
        "Micro Layer": {
            "icon": "⚡",
            "description": "Low-level code optimizations",
            "mutators": [
                ("ConstantOptimizer", "Constant folding and propagation"),
                ("DeadCodeEliminator", "Unreachable code removal"),
                ("LoopMicroOptimizer", "Loop unrolling, strength reduction"),
            ],
            "examples": ["24*60*60 → 86400", "x**2 → x*x"],
            "requires_llm": False,
            "color": "yellow",
        },
    }

    for layer_name, layer_info in layers.items():
        color = layer_info["color"]

        # Mutators table
        table = Table(show_header=True, header_style=f"bold {color}", box=None, padding=(0, 1))
        table.add_column("Mutator", style="bold white")
        table.add_column("Description", style="dim")

        for mutator_name, mutator_desc in layer_info["mutators"]:
            table.add_row(mutator_name, mutator_desc)

        # Content assembly
        content = [
            f"[italic]{layer_info['description']}[/italic]",
            "",
            table,
            "",
            f"[bold]Examples:[/bold] {', '.join(layer_info['examples'])}",
        ]

        req_text = (
            "[bold yellow(Requires API Key)[/]"
            if layer_info["requires_llm"]
            else "[bold green](No API Key)[/]"
        )

        console.print(
            Panel(
                "\n".join(str(x) if not isinstance(x, Table) else "" for x in content),
                title=f"[{color}]{layer_info['icon']} {layer_name}[/{color}]",
                subtitle=req_text,
                border_style=color,
                box=ROUNDED,
            )
        )
        # Hack to print table inside panel correctly if mixed content
        # Actually rich handles tables in panels fine if passed directly.
        # Let's just print the table inside the loop for simplicity or reconstructed.
        # For now, simplistic rendering is fine but let's make it better.
        # Re-doing the panel content to be a renderable group is better.

        # (Self-correction: The above string join will miss the table object. Let's fix.)
        from rich.console import Group

        group = Group(
            Text(layer_info["description"], style="italic"),
            Text(""),
            table,
            Text(""),
            Text(f"Examples: {', '.join(layer_info['examples'])}", style="bold"),
        )

        console.print(
            Panel(
                group,
                title=f"[{color}]{layer_info['icon']} {layer_name}[/{color}]",
                subtitle=req_text,
                border_style=color,
                box=ROUNDED,
            )
        )
        console.print()


def show_examples_help():
    """Show examples and use cases."""
    console.print("\n[bold cyan]📚 HEDGE Examples & Use Cases[/bold cyan]\n")

    examples = [
        {
            "title": "Quick Optimization",
            "command": "hedge optimize mycode.py tests.py",
            "description": "Standard optimization with default settings",
            "use_case": "General code improvement",
        },
        {
            "title": "AI-Powered Optimization",
            "command": "hedge optimize mycode.py tests.py --level advanced",
            "description": "Use LLM for semantic-level optimizations",
            "use_case": "Maximum performance gains",
        },
        {
            "title": "Custom Layer Selection",
            "command": "hedge optimize mycode.py tests.py --layers algorithmic,micro",
            "description": "Use only specific optimization layers",
            "use_case": "Targeted optimizations",
        },
        {
            "title": "With Visualization",
            "command": "hedge optimize mycode.py tests.py --visualize",
            "description": "Generate interactive charts and reports",
            "use_case": "Analysis and presentation",
        },
        {
            "title": "Code Analysis",
            "command": "hedge analyze mycode.py --detailed",
            "description": "Analyze code complexity and get recommendations",
            "use_case": "Code quality assessment",
        },
        {
            "title": "Performance Benchmarking",
            "command": "hedge benchmark --quick",
            "description": "Test HEDGE on built-in example problems",
            "use_case": "Evaluate optimization effectiveness",
        },
        {
            "title": "Project Management",
            "command": "hedge project init my_optimization_project",
            "description": "Create organized optimization project",
            "use_case": "Structured optimization workflows",
        },
    ]

    example_panels = []
    for example in examples:
        p = Panel(
            f"[bold]{example['description']}[/bold]\n\n"
            f"[dim]Use case: {example['use_case']}[/dim]",
            title=f"[cyan]$ {example['command']}[/cyan]",
            subtitle=example["title"],
            border_style="blue",
            box=ROUNDED,
            padding=(1, 2),
        )
        example_panels.append(p)

    console.print(Columns(example_panels, equal=True, width=50, expand=True))
    console.print()


def show_troubleshooting_help():
    """Show troubleshooting guide."""
    console.print("\n[bold cyan]🔧 HEDGE Troubleshooting Guide[/bold cyan]\n")

    issues = [
        {
            "problem": "LLM API Key Issues",
            "symptoms": ["Advanced level fails", "Semantic layer disabled"],
            "solutions": [
                "Check .env file for OPENAI_API_KEY or GEMINI_API_KEY",
                "Verify API key is valid and has credits",
                "Try different provider: --llm openai/gemini",
            ],
        },
        {
            "problem": "Timeout Issues",
            "symptoms": ["Optimization takes too long", "Process hangs"],
            "solutions": [
                "Increase timeout: --timeout 60",
                "Reduce generations: --generations 5",
                "Use lower optimization level: --level basic",
            ],
        },
        {
            "problem": "No Improvements Found",
            "symptoms": ["Same code returned", "No optimization gains"],
            "solutions": [
                "Code might already be optimal",
                "Try higher optimization level: --level advanced",
                "Check code analysis: hedge analyze mycode.py",
            ],
        },
        {
            "problem": "Import Errors",
            "symptoms": ["Module not found", "Import failures"],
            "solutions": [
                "Activate virtual environment: source .venv/bin/activate",
                "Reinstall dependencies: pip install -r requirements.txt",
                "Check Python version: python --version (need 3.8+)",
            ],
        },
    ]

    for issue in issues:
        table = Table(box=ROUNDED, show_header=True, header_style="bold red", expand=True)
        table.add_column("Symptoms")
        table.add_column("Solutions")

        sym_text = "\n".join([f"• {s}" for s in issue["symptoms"]])
        sol_text = "\n".join([f"• {s}" for s in issue["solutions"]])

        table.add_row(sym_text, sol_text)

        console.print(
            Panel(
                table,
                title=f"[bold red]{issue['problem']}[/bold red]",
                border_style="red",
                box=DOUBLE,
            )
        )
        console.print()


@click.command()
@click.option(
    "--topic",
    type=click.Choice(["levels", "mutators", "examples", "troubleshooting"]),
    help="Show help for specific topic",
)
def help_cmd(topic):
    """Show interactive help and guidance."""
    if topic == "levels":
        show_optimization_levels_help()
    elif topic == "mutators":
        show_mutators_help()
    elif topic == "examples":
        show_examples_help()
    elif topic == "troubleshooting":
        show_troubleshooting_help()
    else:
        # Show help menu
        console.print("\n[bold cyan]❓ HEDGE Interactive Help[/bold cyan]\n")

        help_topics = [
            (
                "levels",
                "Optimization Levels 🚀",
                "Learn about micro, basic, standard, advanced, aggressive",
            ),
            (
                "mutators",
                "Mutator System 🧬",
                "Understand the 4-layer hierarchical mutation system",
            ),
            ("examples", "Examples & Use Cases 📚", "See practical examples and common workflows"),
            ("troubleshooting", "Troubleshooting 🔧", "Solve common issues and problems"),
        ]

        panels = []
        for topic_name, title, description in help_topics:
            p = Panel(
                f"[bold]{title}[/bold]\n\n"
                f"{description}\n\n"
                f"[cyan]Run: hedge help --topic {topic_name}[/cyan]",
                border_style="cyan",
                box=ROUNDED,
            )
            panels.append(p)

        console.print(Columns(panels, equal=True))
        console.print(
            "\n[dim]You can also use 'hedge COMMAND --help' for command-specific help[/dim]"
        )
