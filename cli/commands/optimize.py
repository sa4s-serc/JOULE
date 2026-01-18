"""Optimization command for HEDGE CLI."""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Set

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table

from src.application.engine.evolution import EvolutionaryEngine, EngineConfig
from src.application.mutators.base import MutationLayer, MutationOrchestrator
from src.infrastructure.execution.runner import GreenGymRunner
from src.infrastructure.llm.client import create_llm_client
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.domain.ir.metrics import IRMetricsCollector
from src.utils.visualizer import ResultVisualizer
from cli.utils.banner import (
    print_success, print_error, print_warning, print_info, 
    print_step, print_optimization_summary, create_progress_table
)
from cli.utils.mutator_factory import create_mutators

console = Console()

@click.command()
@click.argument('target', type=click.Path(exists=True, path_type=Path))
@click.argument('tests', type=click.Path(exists=True, path_type=Path))
@click.option('--level', type=click.Choice(['micro', 'basic', 'standard', 'advanced', 'aggressive']), 
              default='standard', help='Optimization level')
@click.option('--layers', type=str, help='Comma-separated list of specific layers: semantic,algorithmic,syntactic,micro')
@click.option('--generations', type=int, default=10, help='Number of evolutionary generations')
@click.option('--population-size', type=int, default=8, help='Population size for evolution')
@click.option('--timeout', type=int, default=30, help='Execution timeout in seconds')
@click.option('--llm-provider', type=click.Choice(['openai', 'gemini']), default='gemini', help='LLM provider')
@click.option('--llm-model', type=str, help='Custom LLM model name')
@click.option('--output', '-o', type=click.Path(path_type=Path), help='Output file for optimized code')
@click.option('--experiment-dir', type=click.Path(path_type=Path), help='Custom experiment directory')
@click.option('--visualize', is_flag=True, help='Generate visualizations after optimization')
@click.option('--save-ir', is_flag=True, help='Save IR snapshots for debugging')
@click.option('--exclude-mutators', type=str, help='Comma-separated list of mutators to exclude')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Quiet mode - minimal output')
@click.option('--profile', is_flag=True, help='Enable performance profiling')
@click.option('--parallel', is_flag=True, help='Enable parallel mutation processing')
def optimize_cmd(target, tests, level, layers, generations, population_size, timeout, 
                llm_provider, llm_model, output, experiment_dir, visualize, save_ir, 
                exclude_mutators, verbose, quiet, profile, parallel):
    """
    Optimize Python code using hierarchical evolutionary strategies.
    
    TARGET: Python file to optimize
    TESTS: Test file for validation
    """
    if not quiet:
        console.print("\n[bold cyan]Starting Code Optimization[/bold cyan]")
        console.print(f"[dim]Target: {target} | Tests: {tests} | Level: {level}[/dim]\n")
    
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    logging.basicConfig(level=getattr(logging, log_level))
    logger = logging.getLogger(__name__)
    
    try:
        # Read input files with progress
        if not quiet:
            print_step(1, 4, f"Loading target: {target}")
        with open(target, "r") as f:
            initial_code = f.read()
        
        if not quiet:
            print_step(2, 4, f"Loading tests: {tests}")
        with open(tests, "r") as f:
            test_code = f.read()
        
        # Setup experiment directory
        if experiment_dir:
            exp_dir = experiment_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exp_dir = Path(f"experiments/run_{timestamp}")
        
        exp_dir.mkdir(parents=True, exist_ok=True)
        if not quiet:
            print_step(3, 4, f"Experiment directory: {exp_dir}")
        
        # Save configuration
        config = {
            'target': str(target),
            'tests': str(tests),
            'level': level,
            'layers': layers,
            'generations': generations,
            'population_size': population_size,
            'timeout': timeout,
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(exp_dir / "config.json", 'w') as f:
            json.dump(config, f, indent=2)
        
        # Initialize components
        if not quiet:
            print_step(4, 4, "Initializing optimization components")
            with Progress(
                SpinnerColumn(style="bold magenta"),
                TextColumn("[bold blue]{task.description}"),
                console=console,
                transient=True 
            ) as progress:
                task = progress.add_task("Setting up components...", total=None)
                
                # Create runner
                runner = GreenGymRunner(timeout_seconds=timeout)
                progress.update(task, description="✓ Green Gym runner initialized")
                
                # Setup mutators
                mutators, enabled_layers = create_mutators(
                    level=level,
                    layers=layers,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    exclude_mutators=exclude_mutators,
                    progress=progress,
                    task=task
                )
                
                # Create engine configuration
                engine_config = EngineConfig(
                    generations=generations,
                    population_size=population_size,
                    save_ir_snapshots=save_ir
                )
                
                # Create engine
                engine = EvolutionaryEngine(
                    mutators=mutators,
                    runner=runner,
                    config=engine_config,
                    experiment_dir=exp_dir
                )
                
                progress.update(task, description="✓ All components initialized")
        else:
            # Quiet initialization
            runner = GreenGymRunner(timeout_seconds=timeout)
            mutators, enabled_layers = create_mutators(
                level=level,
                layers=layers,
                llm_provider=llm_provider,
                llm_model=llm_model,
                exclude_mutators=exclude_mutators
            )
            
            engine_config = EngineConfig(
                generations=generations,
                population_size=population_size,
                save_ir_snapshots=save_ir
            )
            
            engine = EvolutionaryEngine(
                mutators=mutators,
                runner=runner,
                config=engine_config,
                experiment_dir=exp_dir
            )
        
        # Run optimization
        if not quiet:
            console.print(f"\n[bold yellow]Running Evolution[/bold yellow]")
            
            # Create optimization info panel
            info_table = create_progress_table("Optimization Configuration", [
                ("Parameter", "cyan"),
                ("Value", "green")
            ])
            info_table.add_row("Generations", str(generations))
            info_table.add_row("Population Size", str(population_size))
            info_table.add_row("Enabled Layers", ', '.join([layer.value for layer in enabled_layers]))
            info_table.add_row("Active Mutators", str(len(mutators)))
            info_table.add_row("Timeout", f"{timeout}s")
            
            console.print(info_table)
            console.print()
            
            with Progress(
                SpinnerColumn(style="bold yellow"),
                TextColumn("[bold yellow]{task.description}"),
                BarColumn(bar_width=None, style="yellow", complete_style="bold yellow"),
                TextColumn("[bold cyan]Solutions: {task.fields[solutions]}"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                opt_task = progress.add_task("Evolving solutions...", total=generations, solutions=0)
                
                def progress_callback(generation, solutions_count):
                    progress.update(opt_task, completed=generation, solutions=solutions_count)
                
                start_time = datetime.now()
                solutions = engine.optimize(initial_code, test_code, progress_callback=progress_callback)
                end_time = datetime.now()
                
                progress.update(opt_task, description="Evolution complete!", completed=generations)
        else:
            start_time = datetime.now()
            solutions = engine.optimize(initial_code, test_code)
            end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        # Display results
        _display_results(solutions, engine, duration, exp_dir, output or target.with_name(f"{target.stem}_optimized.py"), quiet)
        
        # Generate visualizations
        if visualize:
            if not quiet:
                print_info("Generating visualizations...")
            visualizer = ResultVisualizer(exp_dir)
            visualizer.generate_all()
            
            if not quiet:
                print_success("Visualizations generated!")
                console.print(f"  └─ View report: [link]file://{exp_dir}/visualizations/report.html[/link]")
        
        if not quiet:
            print_success("Optimization completed successfully!")
        
        return 0
        
    except Exception as e:
        print_error(f"Optimization failed: {str(e)}")
        if verbose:
            console.print_exception()
        return 1

def _display_results(solutions, engine, duration, exp_dir, output_path, quiet=False):
    """Display optimization results."""
    codegen = PythonCodeGenerator()
    metrics_collector = IRMetricsCollector()
    
    if not quiet:
        # Calculate improvement if we have solutions
        improvement = None
        if solutions and len(solutions) > 1:
            baseline_energy = solutions[0].metrics.get('energy_joules', 1)
            best_energy = min(sol.metrics.get('energy_joules', baseline_energy) for sol in solutions)
            if baseline_energy > 0:
                improvement = ((baseline_energy - best_energy) / baseline_energy) * 100
        
        print_optimization_summary(len(solutions), duration, improvement)
        
        if solutions:
            # Results table
            table = create_progress_table("Pareto-Optimal Solutions", [
                ("#", "dim"),
                ("Mutation Type", "yellow"),
                ("Energy (J)", "green"),
                ("Time (s)", "blue"),
                ("Complexity", "magenta")
            ])
            
            for i, sol in enumerate(solutions[:10]):  # Show top 10
                ir_metrics = metrics_collector.collect(sol.ir)
                table.add_row(
                    str(i+1),
                    sol.mutation_type,
                    f"{sol.metrics.get('energy_joules', 0):.4f}",
                    f"{sol.metrics.get('duration_seconds', 0):.4f}",
                    str(ir_metrics.cyclomatic_complexity)
                )
            
            console.print(table)
            
            # Show optimization insights
            if len(solutions) > 1:
                console.print(f"\n[bold]Optimization Insights:[/bold]")
                console.print(f"  • Found [green]{len(solutions)}[/green] non-dominated solutions")
                console.print(f"  • Success rate: [green]{engine.statistics.success_rate:.1f}%[/green]")
                console.print(f"  • Cache hits: [blue]{engine.statistics.cache_hits}[/blue]")
                
                if improvement and improvement > 0:
                    console.print(f"  • Best improvement: [bold green]{improvement:.1f}% energy reduction[/bold green]")
    
    # Save results
    results = []
    for sol in solutions:
        code = codegen.generate(sol.ir)
        ir_metrics = metrics_collector.collect(sol.ir)
        results.append({
            "id": sol.variant_id,
            "metrics": sol.metrics,
            "mutation": sol.mutation_type,
            "ir_metrics": {
                "complexity": ir_metrics.cyclomatic_complexity,
                "nodes": ir_metrics.total_nodes,
                "depth": ir_metrics.max_depth
            },
            "code": code
        })
    
    # Save results to experiment directory
    with open(exp_dir / "pareto_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    with open(exp_dir / "statistics.json", 'w') as f:
        json.dump(engine.statistics.to_dict(), f, indent=2)
    
    # Save best solution
    if solutions:
        best = min(solutions, key=lambda s: s.metrics.get("energy_joules", float('inf')))
        best_code = codegen.generate(best.ir)
        
        with open(output_path, 'w') as f:
            f.write(best_code)
        
        if not quiet:
            print_success(f"Best solution saved: {output_path}")
            console.print(f"  Full results: [cyan]{exp_dir}[/cyan]")
    else:
        if not quiet:
            print_warning("No valid solutions found")