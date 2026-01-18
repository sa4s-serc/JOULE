"""Interactive help system for HEDGE CLI."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text

console = Console()

def show_optimization_levels_help():
    """Show detailed help about optimization levels."""
    console.print("\n[bold cyan]HEDGE Optimization Levels[/bold cyan]\n")
    
    levels = [
        {
            'name': 'micro',
            'speed': 'Very Fast',
            'description': 'Safe micro-optimizations',
            'features': ['Constant folding', 'Dead code elimination', 'Strength reduction'],
            'use_case': 'Production code, quick wins',
            'api_key': False
        },
        {
            'name': 'basic', 
            'speed': 'Fast',
            'description': 'Python idioms and patterns',
            'features': ['Micro optimizations', 'List comprehensions', 'Built-in functions'],
            'use_case': 'Code cleanup, Python best practices',
            'api_key': False
        },
        {
            'name': 'standard',
            'speed': 'Moderate',
            'description': 'Algorithmic improvements',
            'features': ['Basic optimizations', 'Data structure selection', 'Complexity reduction'],
            'use_case': 'General optimization (recommended)',
            'api_key': False
        },
        {
            'name': 'advanced',
            'speed': 'Slower', 
            'description': 'AI-powered semantic optimization',
            'features': ['Standard optimizations', 'Algorithm intent', 'LLM-based improvements'],
            'use_case': 'Maximum optimization, research',
            'api_key': True
        },
        {
            'name': 'aggressive',
            'speed': 'Slowest',
            'description': 'All optimizations enabled',
            'features': ['All layers active', 'Experimental features', 'Maximum settings'],
            'use_case': 'Research, experimental optimization',
            'api_key': True
        }
    ]
    
    for level in levels:
        # Create level panel
        features_text = '\n'.join([f"• {feature}" for feature in level['features']])
        api_text = "Requires API key" if level['api_key'] else "No API key needed"
        
        panel_content = (
            f"[bold]{level['description']}[/bold]\n\n"
            f"Speed: {level['speed']}\n"
            f"Use case: {level['use_case']}\n"
            f"{api_text}\n\n"
            f"[bold]Features:[/bold]\n{features_text}"
        )
        
        console.print(Panel(
            panel_content,
            title=f"{level['name'].upper()}",
            border_style="cyan" if not level['api_key'] else "yellow"
        ))
        console.print()

def show_mutators_help():
    """Show detailed help about mutators."""
    console.print("\n[bold cyan]HEDGE Mutator System[/bold cyan]\n")
    
    layers = {
        'Semantic Layer': {
            'description': 'AI-powered algorithm and intent optimization',
            'mutators': [
                ('AlgorithmicIntentMutator', 'Algorithm selection and Big-O optimization'),
                ('ProgramIntentMutator', 'Logic simplification and control flow')
            ],
            'examples': ['O(2^n) → O(n) Fibonacci', 'Recursive → Iterative'],
            'requires_llm': True
        },
        'Algorithmic Layer': {
            'description': 'Data structures and complexity optimization',
            'mutators': [
                ('DataStructureOptimizer', 'List → Set conversion, access patterns'),
                ('ComplexityReducer', 'Nested loop reduction, math optimizations')
            ],
            'examples': ['Linear search → Set membership', 'Nested loops → Single pass'],
            'requires_llm': False
        },
        'Syntactic Layer': {
            'description': 'Python idioms and code patterns',
            'mutators': [
                ('PythonicIdiomOptimizer', 'Comprehensions, built-ins, iterators'),
                ('CodePatternOptimizer', 'LLM-based pattern improvements')
            ],
            'examples': ['Manual loops → Comprehensions', 'range(len()) → enumerate()'],
            'requires_llm': False
        },
        'Micro Layer': {
            'description': 'Low-level code optimizations',
            'mutators': [
                ('ConstantOptimizer', 'Constant folding and propagation'),
                ('DeadCodeEliminator', 'Unreachable code removal'),
                ('LoopMicroOptimizer', 'Loop unrolling, strength reduction')
            ],
            'examples': ['24*60*60 → 86400', 'x**2 → x*x'],
            'requires_llm': False
        }
    }
    
    for layer_name, layer_info in layers.items():
        console.print(f"[bold]{layer_name}[/bold]")
        console.print(f"[dim]{layer_info['description']}[/dim]")
        
        if layer_info['requires_llm']:
            console.print("[yellow]Requires LLM API key[/yellow]")
        else:
            console.print("[green]No API key needed[/green]")
        
        # Mutators table
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Mutator", style="yellow")
        table.add_column("Description", style="dim")
        
        for mutator_name, mutator_desc in layer_info['mutators']:
            table.add_row(mutator_name, mutator_desc)
        
        console.print(table)
        
        # Examples
        console.print(f"[bold]Examples:[/bold] {', '.join(layer_info['examples'])}")
        console.print()

def show_examples_help():
    """Show examples and use cases."""
    console.print("\n[bold cyan]HEDGE Examples & Use Cases[/bold cyan]\n")
    
    examples = [
        {
            'title': 'Quick Optimization',
            'command': 'hedge optimize mycode.py tests.py',
            'description': 'Standard optimization with default settings',
            'use_case': 'General code improvement'
        },
        {
            'title': 'AI-Powered Optimization', 
            'command': 'hedge optimize mycode.py tests.py --level advanced',
            'description': 'Use LLM for semantic-level optimizations',
            'use_case': 'Maximum performance gains'
        },
        {
            'title': 'Custom Layer Selection',
            'command': 'hedge optimize mycode.py tests.py --layers algorithmic,micro',
            'description': 'Use only specific optimization layers',
            'use_case': 'Targeted optimizations'
        },
        {
            'title': 'With Visualization',
            'command': 'hedge optimize mycode.py tests.py --visualize',
            'description': 'Generate interactive charts and reports',
            'use_case': 'Analysis and presentation'
        },
        {
            'title': 'Code Analysis',
            'command': 'hedge analyze mycode.py --detailed',
            'description': 'Analyze code complexity and get recommendations',
            'use_case': 'Code quality assessment'
        },
        {
            'title': 'Performance Benchmarking',
            'command': 'hedge benchmark --quick',
            'description': 'Test HEDGE on built-in example problems',
            'use_case': 'Evaluate optimization effectiveness'
        },
        {
            'title': 'Project Management',
            'command': 'hedge project init my_optimization_project',
            'description': 'Create organized optimization project',
            'use_case': 'Structured optimization workflows'
        }
    ]
    
    for example in examples:
        console.print(Panel(
            f"[bold]{example['description']}[/bold]\n\n"
            f"[cyan]$ {example['command']}[/cyan]\n\n"
            f"[dim]Use case: {example['use_case']}[/dim]",
            title=example['title'],
            border_style="blue"
        ))
        console.print()

def show_troubleshooting_help():
    """Show troubleshooting guide."""
    console.print("\n[bold cyan]HEDGE Troubleshooting Guide[/bold cyan]\n")
    
    issues = [
        {
            'problem': 'LLM API Key Issues',
            'symptoms': ['Advanced level fails', 'Semantic layer disabled'],
            'solutions': [
                'Check .env file for OPENAI_API_KEY or GEMINI_API_KEY',
                'Verify API key is valid and has credits',
                'Try different provider: --llm-provider openai/gemini'
            ]
        },
        {
            'problem': 'Timeout Issues',
            'symptoms': ['Optimization takes too long', 'Process hangs'],
            'solutions': [
                'Increase timeout: --timeout 60',
                'Reduce generations: --generations 5',
                'Use lower optimization level: --level basic'
            ]
        },
        {
            'problem': 'No Improvements Found',
            'symptoms': ['Same code returned', 'No optimization gains'],
            'solutions': [
                'Code might already be optimal',
                'Try higher optimization level: --level advanced',
                'Check code analysis: hedge analyze mycode.py'
            ]
        },
        {
            'problem': 'Import Errors',
            'symptoms': ['Module not found', 'Import failures'],
            'solutions': [
                'Activate virtual environment: source .venv/bin/activate',
                'Reinstall dependencies: pip install -r requirements.txt',
                'Check Python version: python --version (need 3.8+)'
            ]
        }
    ]
    
    for issue in issues:
        console.print(f"[bold red]{issue['problem']}[/bold red]")
        
        console.print("[bold]Symptoms:[/bold]")
        for symptom in issue['symptoms']:
            console.print(f"  • {symptom}")
        
        console.print("[bold]Solutions:[/bold]")
        for solution in issue['solutions']:
            console.print(f"  • {solution}")
        
        console.print()

@click.command()
@click.option('--topic', type=click.Choice(['levels', 'mutators', 'examples', 'troubleshooting']), 
              help='Show help for specific topic')
def help_cmd(topic):
    """Show interactive help and guidance."""
    if topic == 'levels':
        show_optimization_levels_help()
    elif topic == 'mutators':
        show_mutators_help()
    elif topic == 'examples':
        show_examples_help()
    elif topic == 'troubleshooting':
        show_troubleshooting_help()
    else:
        # Show help menu
        console.print("\n[bold cyan]HEDGE Interactive Help[/bold cyan]\n")
        
        help_topics = [
            ("levels", "Optimization Levels", "Learn about micro, basic, standard, advanced, aggressive"),
            ("mutators", "Mutator System", "Understand the 4-layer hierarchical mutation system"),
            ("examples", "Examples & Use Cases", "See practical examples and common workflows"),
            ("troubleshooting", "Troubleshooting", "Solve common issues and problems")
        ]
        
        console.print("[bold]Available Help Topics:[/bold]\n")
        
        for topic_name, title, description in help_topics:
            console.print(f"[cyan]hedge help --topic {topic_name}[/cyan]")
            console.print(f"  {title} - {description}\n")
        
        console.print("[dim]You can also use 'hedge COMMAND --help' for command-specific help[/dim]")