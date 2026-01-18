"""Code analysis command for HEDGE CLI."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path

from src.infrastructure.parsing.python_parser import PythonParser
from src.domain.ir.metrics import IRMetricsCollector
from cli.utils.banner import print_success, print_error, print_step, create_progress_table

console = Console()

@click.command()
@click.argument('code', type=click.Path(exists=True, path_type=Path))
@click.option('--output', '-o', type=click.Path(path_type=Path), help='Save analysis to JSON file')
@click.option('--detailed', is_flag=True, help='Show detailed analysis including function-level metrics')
@click.option('--format', type=click.Choice(['table', 'json', 'yaml']), default='table', help='Output format')
def analyze_cmd(code, output, detailed, format):
    """
    Analyze Python code complexity and structure.
    
    CODE: Python file to analyze
    """
    try:
        console.print(f"\n[bold cyan]Analyzing Code: {code}[/bold cyan]")
        print_step(1, 3, "Reading and parsing code")
        
        # Read and parse code
        with open(code, 'r') as f:
            source_code = f.read()
        
        parser = PythonParser()
        ir = parser.parse(source_code)
        
        print_step(2, 3, "Collecting metrics and analyzing complexity")
        collector = IRMetricsCollector()
        metrics = collector.collect(ir)
        
        print_step(3, 3, "Generating analysis report")
        
        if format == 'table':
            _display_table_format(metrics, detailed)
        elif format == 'json':
            _display_json_format(metrics, output)
        elif format == 'yaml':
            _display_yaml_format(metrics, output)
        
        print_success("Analysis completed successfully!")
        
        return 0
        
    except Exception as e:
        print_error(f"Analysis failed: {str(e)}")
        return 1

def _display_table_format(metrics, detailed=False):
    """Display metrics in table format."""
    # Main metrics table
    table = create_progress_table("Code Complexity Analysis", [
        ("Metric", "cyan"),
        ("Value", "green"),
        ("Description", "dim")
    ])
    
    table.add_row("Total Nodes", str(metrics.total_nodes), "Total IR nodes in the code")
    table.add_row("Statements", str(metrics.total_statements), "Number of statements")
    table.add_row("Expressions", str(metrics.total_expressions), "Number of expressions")
    table.add_row("Max Depth", str(metrics.max_depth), "Maximum nesting depth")
    table.add_row("Cyclomatic Complexity", str(metrics.cyclomatic_complexity), "Code complexity measure")
    table.add_row("Functions", str(metrics.function_count), "Number of function definitions")
    table.add_row("Classes", str(getattr(metrics, 'class_count', 0)), "Number of class definitions")
    table.add_row("Loops", str(metrics.loop_count), "Number of loop constructs")
    table.add_row("Conditionals", str(metrics.conditional_count), "Number of if/elif/else statements")
    
    console.print(table)
    
    # Complexity assessment with visual indicator
    complexity_level = _assess_complexity(metrics.cyclomatic_complexity)
    complexity_colors = {
        'Low': ('green', 'Low'),
        'Moderate': ('yellow', 'Moderate'), 
        'High': ('red', 'High'),
        'Very High': ('bold red', 'Very High')
    }
    color, level_text = complexity_colors.get(complexity_level, ('white', 'Unknown'))
    
    console.print(f"\n[bold]Complexity Assessment:[/bold] [{color}]{level_text}[/{color}]")
    
    if detailed:
        _display_detailed_analysis(metrics)

def _display_detailed_analysis(metrics):
    """Display detailed function-level analysis."""
    console.print("\n[bold]Detailed Analysis:[/bold]")
    
    # Function complexity breakdown (if available)
    if hasattr(metrics, 'function_metrics'):
        func_table = Table(title="Function-Level Metrics", show_header=True, header_style="bold yellow")
        func_table.add_column("Function", style="yellow")
        func_table.add_column("Complexity", justify="right", style="green")
        func_table.add_column("Lines", justify="right", style="blue")
        func_table.add_column("Parameters", justify="right", style="magenta")
        
        for func_name, func_metrics in metrics.function_metrics.items():
            func_table.add_row(
                func_name,
                str(func_metrics.get('complexity', 0)),
                str(func_metrics.get('lines', 0)),
                str(func_metrics.get('parameters', 0))
            )
        
        console.print(func_table)
    
    # Recommendations
    recommendations = _generate_recommendations(metrics)
    if recommendations:
        console.print("\n[bold]Optimization Recommendations:[/bold]")
        for i, rec in enumerate(recommendations, 1):
            console.print(f"  {i}. {rec}")

def _display_json_format(metrics, output_path):
    """Display metrics in JSON format."""
    import json
    
    metrics_dict = {
        'total_nodes': metrics.total_nodes,
        'total_statements': metrics.total_statements,
        'total_expressions': metrics.total_expressions,
        'max_depth': metrics.max_depth,
        'cyclomatic_complexity': metrics.cyclomatic_complexity,
        'function_count': metrics.function_count,
        'loop_count': metrics.loop_count,
        'conditional_count': metrics.conditional_count,
        'complexity_level': _assess_complexity(metrics.cyclomatic_complexity)
    }
    
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(metrics_dict, f, indent=2)
        print_success(f"Analysis saved to {output_path}")
    else:
        console.print_json(data=metrics_dict)

def _display_yaml_format(metrics, output_path):
    """Display metrics in YAML format."""
    try:
        import yaml
    except ImportError:
        print_error("PyYAML not installed. Use 'pip install pyyaml' to enable YAML output.")
        return
    
    metrics_dict = {
        'code_analysis': {
            'structure': {
                'total_nodes': metrics.total_nodes,
                'statements': metrics.total_statements,
                'expressions': metrics.total_expressions,
                'max_depth': metrics.max_depth
            },
            'complexity': {
                'cyclomatic_complexity': metrics.cyclomatic_complexity,
                'level': _assess_complexity(metrics.cyclomatic_complexity)
            },
            'components': {
                'functions': metrics.function_count,
                'loops': metrics.loop_count,
                'conditionals': metrics.conditional_count
            }
        }
    }
    
    yaml_output = yaml.dump(metrics_dict, default_flow_style=False, indent=2)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(yaml_output)
        print_success(f"Analysis saved to {output_path}")
    else:
        console.print(yaml_output)

def _assess_complexity(cyclomatic_complexity):
    """Assess complexity level based on cyclomatic complexity."""
    if cyclomatic_complexity <= 5:
        return "Low"
    elif cyclomatic_complexity <= 10:
        return "Moderate"
    elif cyclomatic_complexity <= 20:
        return "High"
    else:
        return "Very High"

def _generate_recommendations(metrics):
    """Generate optimization recommendations based on metrics."""
    recommendations = []
    
    if metrics.cyclomatic_complexity > 10:
        recommendations.append("Consider breaking down complex functions into smaller ones")
    
    if metrics.max_depth > 4:
        recommendations.append("Reduce nesting depth by extracting nested logic into functions")
    
    if metrics.loop_count > metrics.function_count * 2:
        recommendations.append("Consider using list comprehensions or built-in functions to reduce explicit loops")
    
    if metrics.total_nodes > 500:
        recommendations.append("Large codebase - consider modularization and separation of concerns")
    
    return recommendations