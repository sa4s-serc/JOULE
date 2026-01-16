#!/usr/bin/env python3
"""
HEDGE - Hierarchical Evolutionary Darwin-Green Engine
======================================================

A state-of-the-art IR-only code optimization system using evolutionary strategies.

Usage:
    hedge optimize <target> <tests> [options]
    hedge analyze <code> [options]
    hedge visualize <results_dir>
    hedge --help
"""
import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Set
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to import rich for better CLI output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.table import Table
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

from src.application.engine.evolution import EvolutionaryEngine
from src.application.mutators.structural import StructuralMutator
from src.application.mutators.semantic import SemanticMutator
from src.application.mutators.syntactic import SyntacticReasoningMutator
from src.application.mutators.external import ExternalLibraryMutator
from src.application.mutators.base import MutationLayer
from src.application.mutators.semantic_layer import AlgorithmicIntentMutator, ProgramIntentMutator
from src.application.mutators.algorithmic_layer import DataStructureOptimizer, ComplexityReducer
from src.application.mutators.syntactic_layer import PythonicIdiomOptimizer, CodePatternOptimizer
from src.application.mutators.micro_layer import ConstantOptimizer, DeadCodeEliminator, LoopMicroOptimizer

# Legacy imports for backward compatibility
from src.application.mutators.structural import StructuralMutator
from src.application.mutators.semantic import SemanticMutator
from src.application.mutators.syntactic import SyntacticReasoningMutator
from src.application.mutators.external import ExternalLibraryMutator



from src.infrastructure.execution.runner import GreenGymRunner
from src.infrastructure.llm.client import create_llm_client
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.domain.ir.metrics import IRMetricsCollector
from src.utils.visualizer import ResultVisualizer
from src.utils.logging_config import setup_logging, silence_noisy_libraries

def print_banner():
    """Print HEDGE banner."""
    if RICH_AVAILABLE:
        from rich.align import Align
        from rich.text import Text
        
        banner_text = Text("""
╦ ╦╔═╗╔╦╗╔═╗╔═╗
╠═╣║╣  ║║║ ╦║╣ 
╩ ╩╚═╝═╩╝╚═╝╚═╝
""", style="bold magenta")
        
        title = Text("Hierarchical Evolutionary Darwin-Green Engine", style="bold white")
        subtitle = Text("IR-Only Optimization System | v2.0", style="dim white")
        
        console.print(Panel(
            Align.center(banner_text + Text("\n") + title + Text("\n") + subtitle),
            style="bold magenta",
            border_style="magenta",
            subtitle="[dim]Google Deepmind [/dim]",
            subtitle_align="right"
        ))
    else:
        print("="*60)
        print(" HEDGE - Hierarchical Evolutionary Darwin-Green Engine")
        print(" IR-Only Optimization System | v2.0")
        print("="*60)

def cmd_optimize(args):
    """Execute optimization command."""
    if RICH_AVAILABLE:
        console.print("\n[bold cyan]Starting Optimization[/bold cyan]\n")
    else:
        print("\nStarting Optimization\n")
    
    # Setup logging
    # Default to INFO, DEBUG if verbose
    log_level = "DEBUG" if args.verbose else "INFO"
    
    # Configure logging
    if RICH_AVAILABLE:
        # We need to configure root logger carefully to play nice with Progress
        # But Progress.console usually handles it.
        # Force INFO level
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)]
        )
    else:
        setup_logging(log_level, log_file, args.verbose)
    
    logger = logging.getLogger(__name__)
    
    # Read target code
    logger.info(f"Loading target: {args.target}")
    with open(args.target, "r") as f:
        initial_code = f.read()
    
    # Read test code
    logger.info(f"Loading tests: {args.tests}")
    with open(args.tests, "r") as f:
        test_code = f.read()
    
    # Setup experiment directory
    if args.experiment_dir:
        experiment_dir = Path(args.experiment_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_dir = Path(f"experiments/run_{timestamp}")
    
    experiment_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Experiment directory: {experiment_dir}")
    
    # Save configuration
    config = vars(args)
    with open(experiment_dir / "config.json", 'w') as f:
        json.dump(config, f, indent=2, default=str)
    
    # Initialize components with progress
    if RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(style="bold magenta"),
            TextColumn("[bold blue]{task.description}"),
            console=console,
            transient=True 
        ) as progress:
            task = progress.add_task("Initializing components...", total=None)
            
            runner = GreenGymRunner(timeout_seconds=args.timeout)
            progress.update(task, description="Green Gym runner initialized")
            
            mutators, enabled_layers = _setup_mutators(args, progress, task)
            progress.update(task, description="[green]✓[/green] All mutators initialized")
            
            # Create engine
            engine = EvolutionaryEngine(
                mutators=mutators,
                runner=runner,
                generations=args.generations,
                population_size=args.population_size,
                experiment_dir=experiment_dir,
                save_ir_snapshots=args.save_ir
            )
            
            # Start optimization task
            # Using a new progress instance for the main loop to control layout
            # We want this one to persist possibly, or be very visible
            pass
            
        # Optimization Loop Progress
        with Progress(
            SpinnerColumn(style="bold yellow"),
            TextColumn("[bold yellow]{task.description}"),
            BarColumn(bar_width=None, style="yellow", complete_style="bold yellow"),
            TextColumn("[bold cyan]Candidates: {task.fields[candidates]}"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            opt_task = progress.add_task("Optimizing...", total=None, candidates=0)
            
            candidates_count = 0
            def on_progress(inc):
                nonlocal candidates_count
                candidates_count += inc
                progress.update(opt_task, candidates=candidates_count)
            
            # Run optimization
            logger.info(f"\nStarting optimization with {args.generations} generations")
            logger.info(f"Mutators: {[m.__class__.__name__ for m in mutators]}\n")
            
            start_time = datetime.now()
            solutions = engine.optimize(initial_code, test_code, progress_callback=on_progress)
            
            progress.update(opt_task, description="[bold green]Optimization Complete!", completed=100)
            # progress.stop() handled by context manager

    else:
        print("Initializing components...")
        runner = GreenGymRunner(timeout_seconds=args.timeout)
        print("✓ Green Gym runner initialized")
        mutators, enabled_layers = _setup_mutators(args)
        print("✓ All mutators initialized")
        
        engine = EvolutionaryEngine(
            mutators=mutators,
            runner=runner,
            generations=args.generations,
            population_size=args.population_size,
            experiment_dir=experiment_dir,
            save_ir_snapshots=args.save_ir
        )
        
        # Register layered mutators with the engine
        for mutator in mutators:
            if hasattr(mutator, 'layer'):  # It's a layered mutator
                engine.mutation_orchestrator.register_mutator(mutator)
        
        # Set enabled layers
        engine.set_enabled_layers(enabled_layers)
        
        logger.info(f"\nStarting optimization with {args.generations} generations")
        logger.info(f"Mutators: {[m.__class__.__name__ for m in mutators]}\n")
        
        start_time = datetime.now()
        solutions = engine.optimize(initial_code, test_code)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Display results
    _display_results(solutions, engine, duration, experiment_dir, args)
    
    # Generate visualizations if requested
    if args.visualize:
        logger.info("\nGenerating visualizations...")
        visualizer = ResultVisualizer(experiment_dir)
        visualizer.generate_all()
        
        if RICH_AVAILABLE:
            console.print("\n[bold green]✓[/bold green] Visualizations generated!")
            console.print(f"  └─ View report at: [link]file://{experiment_dir}/visualizations/report.html[/link]")
    
    return 0

def _setup_mutators(args, progress=None, task=None):
    """Set up layered mutators based on optimization level and enabled layers."""
    
    # Determine enabled layers based on optimization level
    enabled_layers = _get_enabled_layers(args.level, args)
    
    # Initialize LLM if needed for semantic layers
    llm = None
    use_llm = any(layer in enabled_layers for layer in [MutationLayer.SEMANTIC])
    
    if use_llm:
        api_key = os.getenv(f"{args.llm_provider.upper()}_API_KEY")
        if api_key:
            llm = create_llm_client(args.llm_provider, api_key, args.llm_model)
        else:
            logging.warning(f"API key not found for {args.llm_provider}. Disabling semantic layer.")
            enabled_layers.discard(MutationLayer.SEMANTIC)
    
    # Create layered mutators
    mutators = []
    
    # Semantic Layer Mutators
    if MutationLayer.SEMANTIC in enabled_layers and llm:
        mutators.extend([
            AlgorithmicIntentMutator(llm),
            ProgramIntentMutator(llm)
        ])
        if progress:
            progress.update(task, description="[green]✓[/green] Semantic layer mutators enabled")
    
    # Algorithmic Layer Mutators  
    if MutationLayer.ALGORITHMIC in enabled_layers:
        mutators.extend([
            DataStructureOptimizer(),
            ComplexityReducer()
        ])
        if progress:
            progress.update(task, description="[green]✓[/green] Algorithmic layer mutators enabled")
    
    # Syntactic Layer Mutators
    if MutationLayer.SYNTACTIC in enabled_layers:
        syntactic_mutators = [PythonicIdiomOptimizer()]
        if llm:  # LLM-based syntactic mutators
            syntactic_mutators.append(CodePatternOptimizer(llm))
        mutators.extend(syntactic_mutators)
        if progress:
            progress.update(task, description="[green]✓[/green] Syntactic layer mutators enabled")
    
    # Micro Layer Mutators
    if MutationLayer.MICRO in enabled_layers:
        mutators.extend([
            ConstantOptimizer(),
            DeadCodeEliminator(), 
            LoopMicroOptimizer()
        ])
        if progress:
            progress.update(task, description="[green]✓[/green] Micro layer mutators enabled")
    
    # Legacy compatibility: Add old-style mutators if using legacy mode
    if getattr(args, 'legacy_mode', False):
        mutators.extend(_setup_legacy_mutators(args, llm))
        if progress:
            progress.update(task, description="[green]✓[/green] Legacy mutators enabled")
    
    # Filter excluded mutators
    if args.exclude_mutators:
        excluded = [m.strip() for m in args.exclude_mutators.split(',')]
        mutators = [m for m in mutators if m.__class__.__name__ not in excluded]
        if progress:
            progress.update(task, description=f"[green]✓[/green] Mutators filtered: {len(mutators)} active")
    
    return mutators, enabled_layers


def _get_enabled_layers(level: str, args) -> Set[MutationLayer]:
    """Determine which mutation layers are enabled based on optimization level."""
    
    # Parse custom layer specification if provided
    if hasattr(args, 'layers') and args.layers:
        layer_names = [name.strip().lower() for name in args.layers.split(',')]
        enabled_layers = set()
        for name in layer_names:
            try:
                enabled_layers.add(MutationLayer(name))
            except ValueError:
                logging.warning(f"Unknown layer: {name}")
        return enabled_layers
    
    # Default layer sets based on optimization level
    if level == 'micro':
        return {MutationLayer.MICRO}
    elif level == 'basic':
        return {MutationLayer.MICRO, MutationLayer.SYNTACTIC}
    elif level == 'standard':
        return {MutationLayer.MICRO, MutationLayer.SYNTACTIC, MutationLayer.ALGORITHMIC}
    elif level == 'advanced':
        return {MutationLayer.MICRO, MutationLayer.SYNTACTIC, MutationLayer.ALGORITHMIC, MutationLayer.SEMANTIC}
    elif level == 'aggressive':
        return set(MutationLayer)  # All layers
    else:
        # Default to standard
        return {MutationLayer.MICRO, MutationLayer.SYNTACTIC, MutationLayer.ALGORITHMIC}


def _setup_legacy_mutators(args, llm):
    """Set up legacy mutators for backward compatibility."""
    mutators = []
    
    # Legacy structural mutator
    mutators.append(StructuralMutator(use_context=not args.no_context))
    
    # Legacy LLM-based mutators
    if llm:
        if args.level in ['standard', 'advanced', 'aggressive']:
            mutators.append(SyntacticReasoningMutator(llm))
        
        if args.level in ['advanced', 'aggressive']:
            mutators.append(SemanticMutator(llm))
        
        if args.level == 'aggressive':
            mutators.append(ExternalLibraryMutator(llm))
    
    return mutators

def _display_results(solutions, engine, duration, experiment_dir, args):
    """Display optimization results."""
    codegen = PythonCodeGenerator()
    metrics_collector = IRMetricsCollector()
    
    if RICH_AVAILABLE:
        # Create results table
        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]Optimization Complete![/bold green]\n\n"
            f"Time: {duration:.2f}s\n"
            f"Solutions: {len(solutions)}\n"
            f"Success Rate: {engine.statistics.success_rate:.1f}%\n"
            f"Cache Hits: {engine.statistics.cache_hits}",
            border_style="green"
        ))
        
        # Results table
        table = Table(title="\nPareto-Optimal Solutions", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim")
        table.add_column("Mutation Type")
        table.add_column("Energy (J)", justify="right")
        table.add_column("Time (s)", justify="right")
        table.add_column("Complexity", justify="right")
        
        results = []
        for i, sol in enumerate(solutions):
            code = codegen.generate(sol.ir)
            ir_metrics = metrics_collector.collect(sol.ir)
            
            table.add_row(
                str(i+1),
                sol.mutation_type,
                f"{sol.metrics.get('energy_joules', 0):.4f}",
                f"{sol.metrics.get('duration_seconds', 0):.4f}",
                str(ir_metrics.cyclomatic_complexity)
            )
            
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
        
        console.print(table)
    else:
        print("\n" + "="*60)
        print("OPTIMIZATION COMPLETE")
        print("="*60)
        print(f"Time: {duration:.2f}s")
        print(f"Solutions: {len(solutions)}")
        print(f"Success Rate: {engine.statistics.success_rate:.1f}%")
        
        results = []
        for i, sol in enumerate(solutions):
            code = codegen.generate(sol.ir)
            ir_metrics = metrics_collector.collect(sol.ir)
            print(f"\nSolution {i+1} [{sol.mutation_type}]:")
            print(f"  Energy: {sol.metrics.get('energy_joules', 0):.4f} J")
            print(f"  Time: {sol.metrics.get('duration_seconds', 0):.4f} s")
            
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
    
    # Save results
    results_path = experiment_dir / "pareto_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    stats_path = experiment_dir / "statistics.json"
    with open(stats_path, 'w') as f:
        json.dump(engine.statistics.to_dict(), f, indent=2)
    
    # Save best solution
    if solutions:
        best = min(solutions, key=lambda s: s.metrics.get("energy_joules", float('inf')))
        best_code = codegen.generate(best.ir)
        
        if args.output_file:
            output_path = args.output_file
        else:
            output_path = args.target.replace(".py", "_optimized.py")
        with open(output_path, 'w') as f:
            f.write(best_code)
        
        baseline_energy = solutions[0].metrics.get('energy_joules', 1)
        improvement = ((baseline_energy - best.metrics.get('energy_joules', baseline_energy)) / baseline_energy * 100)
        
        if RICH_AVAILABLE:
            console.print(f"\n[bold green]✓[/bold green] Best solution saved: [cyan]{output_path}[/cyan]")
            if improvement > 0:
                console.print(f"  [green]↓ {improvement:.1f}% energy improvement[/green]\n")
        else:
            print(f"\n✓ Best solution saved: {output_path}")
            if improvement > 0:
                print(f"  ↓ {improvement:.1f}% energy improvement")

def cmd_analyze(args):
    """Analyze code complexity and structure."""
    from src.infrastructure.parsing.python_parser import PythonParser
    from src.domain.ir.metrics import IRMetricsCollector
    
    print_banner()
    
    with open(args.code, 'r') as f:
        code = f.read()
    
    parser = PythonParser()
    ir = parser.parse(code)
    
    collector = IRMetricsCollector()
    metrics = collector.collect(ir)
    
    if RICH_AVAILABLE:
        table = Table(title="Code Analysis", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")
        
        table.add_row("Total Nodes", str(metrics.total_nodes))
        table.add_row("Statements", str(metrics.total_statements))
        table.add_row("Expressions", str(metrics.total_expressions))
        table.add_row("Max Depth", str(metrics.max_depth))
        table.add_row("Cyclomatic Complexity", str(metrics.cyclomatic_complexity))
        table.add_row("Functions", str(metrics.function_count))
        table.add_row("Loops", str(metrics.loop_count))
        table.add_row("Conditionals", str(metrics.conditional_count))
        
        console.print(table)
    else:
        print("\nCode Analysis:")
        print(f"  Total Nodes: {metrics.total_nodes}")
        print(f"  Cyclomatic Complexity: {metrics.cyclomatic_complexity}")
        print(f"  Functions: {metrics.function_count}")
    
    return 0

def cmd_visualize(args):
    """Generate visualizations from results."""
    print_banner()
    
    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}")
        return 1
    
    visualizer = ResultVisualizer(results_dir)
    visualizer.generate_all()
    
    if RICH_AVAILABLE:
        console.print(f"\n[bold green]✓[/bold green] Visualizations generated!")
        console.print(f"  View report: [link]file://{results_dir}/visualizations/report.html[/link]\n")
    else:
        print(f"\n✓ Visualizations generated at: {results_dir}/visualizations/")
    
    return 0

def cmd_list_mutators(args):
    """List available mutators."""
    print_banner()
    
    if RICH_AVAILABLE:
        table = Table(title="\nAvailable Mutators", show_header=True, header_style="bold cyan")
        table.add_column("Category", style="cyan")
        table.add_column("Mutator", style="green")
        table.add_column("Level via --level", style="yellow")
        table.add_column("Description", style="dim")
        
        # Structural
        # Semantic Layer
        table.add_row("Semantic", "AlgorithmicIntentMutator", "advanced+", "Algorithm selection and complexity optimization")
        table.add_row("Semantic", "ProgramIntentMutator", "advanced+", "Program logic and intent optimization")
        
        # Algorithmic Layer
        table.add_row("Algorithmic", "DataStructureOptimizer", "standard+", "Data structure selection optimization")
        table.add_row("Algorithmic", "ComplexityReducer", "standard+", "Algorithmic complexity reduction")
        
        # Syntactic Layer
        table.add_row("Syntactic", "PythonicIdiomOptimizer", "basic+", "Python idiom and pattern optimization")
        table.add_row("Syntactic", "CodePatternOptimizer", "basic+", "LLM-based code pattern improvements")
        
        # Micro Layer
        table.add_row("Micro", "ConstantOptimizer", "micro+", "Constant folding and propagation")
        table.add_row("Micro", "DeadCodeEliminator", "micro+", "Dead code and unreachable code elimination")
        table.add_row("Micro", "LoopMicroOptimizer", "micro+", "Loop unrolling and micro-optimizations")
        
        # Legacy (when using --legacy-mode)
        table.add_row("Legacy", "StructuralMutator", "legacy", "Original structural transformations")
        table.add_row("Legacy", "SemanticMutator", "legacy", "Original LLM-based semantic optimization")
        table.add_row("Legacy", "ExternalLibraryMutator", "legacy", "External library optimization (pandas, numpy)")
        
        console.print(table)
        console.print("\n[bold]Layered System:[/bold]")
        console.print("• [cyan]--level micro[/cyan]: Only micro-optimizations (constant folding, dead code elimination)")
        console.print("• [cyan]--level basic[/cyan]: Micro + syntactic optimizations (Python idioms, patterns)")  
        console.print("• [cyan]--level standard[/cyan]: Basic + algorithmic optimizations (data structures, complexity)")
        console.print("• [cyan]--level advanced[/cyan]: Standard + semantic optimizations (algorithm intent, LLM-based)")
        console.print("• [cyan]--level aggressive[/cyan]: All layers enabled")
        console.print("\n[bold]Custom Control:[/bold]")
        console.print("• [cyan]--layers semantic,micro[/cyan]: Enable only specific layers")
        console.print("• [cyan]--legacy-mode[/cyan]: Use original mutator system")
        console.print("• [cyan]--exclude-mutators[/cyan]: Exclude specific mutator classes")
    else:
        print("\nAvailable Mutators:")
        print("\nLayered Mutator System:")
        print("  Semantic Layer (advanced+):")
        print("    - AlgorithmicIntentMutator: Algorithm selection optimization")
        print("    - ProgramIntentMutator: Program logic optimization")
        print("  Algorithmic Layer (standard+):")
        print("    - DataStructureOptimizer: Data structure selection")
        print("    - ComplexityReducer: Complexity reduction")
        print("  Syntactic Layer (basic+):")
        print("    - PythonicIdiomOptimizer: Python idioms")
        print("    - CodePatternOptimizer: Code patterns (LLM)")
        print("  Micro Layer (micro+):")
        print("    - ConstantOptimizer: Constant folding")
        print("    - DeadCodeEliminator: Dead code elimination")
        print("    - LoopMicroOptimizer: Loop optimizations")
        print("\nUse --layers to specify custom layer combinations")
        print("Use --legacy-mode for original mutator system")

    return 0

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="HEDGE - IR-Only Code Optimization System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Micro-optimizations only (constant folding, dead code elimination)
  hedge optimize fibonacci.py fibonacci_test.py --level micro
  
  # Standard layered optimization (micro + syntactic + algorithmic)
  hedge optimize fibonacci.py fibonacci_test.py --level standard
  
  # Advanced with semantic layer (includes LLM-based optimizations)
  hedge optimize fibonacci.py fibonacci_test.py --level advanced --llm-provider gemini
  
  # Custom layer selection
  hedge optimize fibonacci.py fibonacci_test.py --layers micro,algorithmic
  
  # Legacy mode (original mutator system)
  hedge optimize fibonacci.py fibonacci_test.py --legacy-mode --level advanced
  
  # List available mutators and layers
  hedge list-mutators
  
  # Analyze code complexity
  hedge analyze mycode.py
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List mutators command
    subparsers.add_parser('list-mutators', help='List all available optimization mutators')
    
    # Optimize command
    optimize_parser = subparsers.add_parser('optimize', help='Optimize Python code')
    optimize_parser.add_argument('target', type=str, help='Target Python file to optimize')
    optimize_parser.add_argument('tests', type=str, help='Test file')
    optimize_parser.add_argument('--level', type=str, default='standard', 
                                choices=['micro', 'basic', 'standard', 'advanced', 'aggressive'], 
                                help='Optimization level (micro=micro-opts only, basic=micro+syntactic, standard=+algorithmic, advanced=+semantic, aggressive=all)')
    optimize_parser.add_argument('--layers', type=str, default=None,
                                help='Comma-separated list of specific layers to enable: semantic,algorithmic,syntactic,micro')
    optimize_parser.add_argument('--legacy-mode', action='store_true', 
                                help='Use legacy mutator system instead of layered approach')
    optimize_parser.add_argument('--generations', type=int, default=5, help='Number of generations (default: 5)')
    optimize_parser.add_argument('--population-size', type=int, default=5, help='Population size (default: 5)')
    optimize_parser.add_argument('--timeout', type=int, default=20, help='Timeout for code execution (default: 20s)')
    optimize_parser.add_argument('--exclude-mutators', type=str, default=None, help='Comma-separated list of mutators to exclude (e.g. ExternalLibraryMutator)')
    optimize_parser.add_argument('--llm-provider', type=str, default='gemini', choices=['openai', 'gemini'], help='LLM provider')
    optimize_parser.add_argument('--llm-model', type=str, default=None, help='LLM model (optional)')
    optimize_parser.add_argument('--no-context', action='store_true', help='Disable context-aware mutations')
    optimize_parser.add_argument('--output-file', type=str, default=None, help='Path to save the optimized code')
    optimize_parser.add_argument('--save-ir', action='store_true', help='Save IR snapshots')
    optimize_parser.add_argument('--experiment-dir', type=str, default=None, help='Experiment directory')
    optimize_parser.add_argument('--visualize', action='store_true', help='Generate visualizations after optimization')
    optimize_parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze code complexity')
    analyze_parser.add_argument('code', type=str, help='Python file to analyze')
    
    # Visualize command
    viz_parser = subparsers.add_parser('visualize', help='Generate visualizations')
    viz_parser.add_argument('results_dir', type=str, help='Results directory')
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command is None:
        print_banner()
        parser.print_help()
        return 0
    
    # Execute command
    if args.command == 'optimize':
        print_banner()
        return cmd_optimize(args)
    elif args.command == 'analyze':
        return cmd_analyze(args)
    elif args.command == 'visualize':
        return cmd_visualize(args)
    elif args.command == 'list-mutators':
        return cmd_list_mutators(args)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
