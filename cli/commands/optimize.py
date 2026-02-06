"""Optimization command for HEDGE CLI with advanced features."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from cli.utils.banner import (create_progress_table, print_error,
                              print_optimization_summary, print_step,
                              print_success, print_warning)
from cli.utils.mutator_factory import create_mutators
from src.application.engine.evolution import EngineConfig, EvolutionaryEngine
from src.application.mutators import initialize_mutator_system
from src.domain.ir.lazy_wrapper import get_memory_stats
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.execution.runner import GreenGymRunner
from src.infrastructure.llm.client import create_llm_client
from src.utils.config_manager import load_config
from src.utils.logging_config import setup_logging
from src.utils.performance_benchmark import PerformanceBenchmark
from src.utils.visualizer import ResultVisualizer

console = Console()


@click.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.argument("tests", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--level",
    type=click.Choice(["micro", "basic", "standard", "advanced", "aggressive"]),
    default="standard",
    help="Optimization level",
)
@click.option(
    "--layers",
    type=str,
    help="Comma-separated list of specific layers: semantic,algorithmic,syntactic,micro",
)
@click.option("--generations", type=int, default=10, help="Number of evolutionary generations")
@click.option("--population-size", type=int, default=8, help="Population size for evolution")
@click.option("--timeout", type=int, default=30, help="Execution timeout in seconds")
@click.option("--llm", type=str, help="LLM specification (e.g., gemini or openai:gpt-4)")
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), help="Output file for optimized code"
)
@click.option("--out-dir", type=click.Path(path_type=Path), help="Custom output directory")
@click.option("--visualize", is_flag=True, help="Generate visualizations after optimization")
@click.option("--save-ir", is_flag=True, help="Save IR snapshots for debugging")
@click.option("--exclude-mutators", type=str, help="Comma-separated list of mutators to exclude")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode - minimal output")
@click.option("--allowed-imports", type=str, help="Comma-separated list of allowed imports")
@click.option("--profile", is_flag=True, help="Enable performance profiling")
@click.option(
    "--parallel/--no-parallel", default=True, help="Enable/disable parallel mutation processing"
)
@click.option(
    "--intelligent/--no-intelligent",
    default=True,
    help="Enable/disable intelligent mutation selection",
)
@click.option(
    "--batch-llm/--no-batch-llm", default=True, help="Enable/disable batch LLM processing"
)
@click.option(
    "--memory-optimization/--no-memory-optimization",
    default=True,
    help="Enable/disable memory optimization",
)
@click.option("--max-workers", type=int, default=8, help="Maximum number of parallel workers")
@click.option("--max-memory-mb", type=int, default=2048, help="Maximum memory usage in MB")
@click.option("--benchmark", is_flag=True, help="Run performance benchmark comparison")
@click.option("--adaptive", is_flag=True, help="Enable adaptive optimization parameters")
@click.option("--log-file", type=click.Path(path_type=Path), help="Path to log file")
@click.option(
    "--log-to-file/--no-log-to-file", default=True, help="Whether to log to a file (default: True)"
)
@click.option(
    "--log-to-console/--no-log-to-console",
    default=None,
    help="Whether to log to console (default: False)",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML configuration file",
)
@click.option(
    "--show-mutators", is_flag=True, help="Show detailed mutator information before optimization"
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without running optimization"
)
def optimize_cmd(
    target,
    tests,
    level,
    layers,
    generations,
    population_size,
    timeout,
    llm,
    output,
    out_dir,
    visualize,
    save_ir,
    exclude_mutators,
    verbose,
    quiet,
    allowed_imports,
    profile,
    parallel,
    intelligent,
    batch_llm,
    memory_optimization,
    max_workers,
    max_memory_mb,
    benchmark,
    adaptive,
    log_file,
    log_to_file,
    log_to_console,
    config=None,
    show_mutators=False,
    dry_run=False,
):
    """
    Optimize Python code using hierarchical evolutionary strategies.

    This version includes:
    - Parallel mutation processing
    - Intelligent mutation selection with ML
    - Memory-optimized IR handling
    - Batch LLM processing
    - Advanced performance monitoring

    TARGET: Python file to optimize
    TESTS: Test file for validation
    """
    if not quiet:
        console.print("\n[bold cyan]🚀 Code Optimization[/bold cyan]")
        console.print(f"[dim]Target: {target} | Tests: {tests} | Level: {level}[/dim]")

        # Show enabled features
        features = []
        if parallel:
            features.append("Parallel Processing")
        if intelligent:
            features.append("Intelligent Selection")
        if batch_llm:
            features.append("Batch LLM")
        if memory_optimization:
            features.append("Memory Optimization")
        if adaptive:
            features.append("Adaptive Parameters")

        if features:
            console.print(f"[dim]Features: {', '.join(features)}[/dim]\n")

    # Parse LLM specification
    llm_provider = None
    llm_model = None
    if llm:
        if ":" in llm:
            llm_provider, llm_model = llm.split(":", 1)
        else:
            llm_provider = llm

    # Setup configuration and logging
    sys_config = load_config(config)

    # Overwrite defaults with config values if they weren't explicitly set in CLI
    # (Click doesn't make it easy to tell if a value was explicitly set or is just the default,
    # but we can check the context or just manually merge if needed.
    # For now, we'll let CLI take precedence as per standard practice).

    opt_cfg = sys_config.get("optimization", {})
    llm_cfg = sys_config.get("llm", {})
    out_cfg = sys_config.get("output", {})

    # Use configuration defaults if not explicitly provided
    # Note: generations, population_size, timeout have non-None defaults in Click,
    # so we should check if they match those defaults.
    perf_cfg = sys_config.get("performance", {})

    # Use configuration defaults if not explicitly provided
    if generations == 10:
        generations = opt_cfg.get("default_generations", generations)
    if population_size == 8:
        population_size = opt_cfg.get("default_population_size", population_size)
    if timeout == 30:
        timeout = opt_cfg.get("default_timeout", timeout)
    if level == "standard":
        level = opt_cfg.get("default_level", level)

    # Performance feature overrides (only if CLI defaults are used)
    # Default for Click options is True for these, so we check if they are True
    if parallel:
        parallel = perf_cfg.get("enable_parallel_mutations", parallel)
    if intelligent:
        intelligent = perf_cfg.get("enable_intelligent_selection", intelligent)
    if batch_llm:
        batch_llm = perf_cfg.get("enable_batch_llm", batch_llm)
    if memory_optimization:
        memory_optimization = perf_cfg.get("enable_memory_optimization", memory_optimization)
    if not adaptive:
        adaptive = perf_cfg.get("adaptive_population_size", adaptive)  # Default is False

    if max_workers == 8:
        max_workers = perf_cfg.get("max_workers", max_workers)
    if max_memory_mb == 2048:
        max_memory_mb = perf_cfg.get("max_memory_mb", max_memory_mb)

    # Output overrides
    if not visualize:
        visualize = out_cfg.get("auto_visualize", visualize)
    if not save_ir:
        save_ir = out_cfg.get("save_ir_snapshots", save_ir)

    log_cfg = sys_config.get("logging", {})

    # Priority: CLI argument > Config file > Default
    log_level = "DEBUG" if verbose else "WARNING" if quiet else (log_cfg.get("level", "INFO"))

    if log_to_console is None:
        log_to_console = log_cfg.get("log_to_console", False)

    effective_log_file = None
    if log_to_file:
        effective_log_file = log_file or Path(log_cfg.get("log_file", "hedge.log"))

    setup_logging(
        level=log_level, log_file=effective_log_file, log_to_console=log_to_console, verbose=verbose
    )
    logger = logging.getLogger(__name__)

    # Create mutators and show transparency information
    try:
        mutators, enabled_layers_set, llm_client = create_mutators(
            level=level,
            layers=layers,
            llm_provider=llm_provider,
            llm_model=llm_model,
            exclude_mutators=exclude_mutators,
            allowed_imports=set(allowed_imports.split(",")) if allowed_imports else set(),
        )

        # Show mutator information if requested or in verbose mode
        if show_mutators or verbose or dry_run:
            _display_mutator_information(mutators, enabled_layers_set, level, llm_client)

        # If dry run, show what would be done and exit
        if dry_run:
            _display_dry_run_summary(
                target,
                tests,
                level,
                generations,
                population_size,
                timeout,
                enabled_layers_set,
                mutators,
                llm_client,
            )
            return

    except Exception as e:
        print_error(f"Failed to initialize mutators: {e}")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        return

    if effective_log_file:
        logger.info(f"Logging initialized. Level: {log_level}, File: {effective_log_file}")

    try:
        # Run benchmark comparison if requested
        if benchmark:
            if not quiet:
                console.print("[bold yellow]Running Performance Benchmark...[/bold yellow]")

            benchmark_suite = PerformanceBenchmark()

            # Create temporary test for benchmarking
            with open(target, "r") as f:
                code_content = f.read()
            with open(tests, "r") as f:
                test_content = f.read()

            # Add to benchmark suite
            benchmark_suite.suites["custom"] = type(
                "BenchmarkSuite",
                (),
                {"name": "custom", "tests": [(target.stem, code_content, test_content)]},
            )()

            benchmark_results = benchmark_suite.run_benchmark_comparison(
                "custom", generations=min(5, generations), runs_per_test=2
            )

            if not quiet:
                console.print("[green]✓ Benchmark completed[/green]")
                console.print(f"[dim]Results saved to: {benchmark_suite.output_dir}[/dim]\n")

        # Read input files with progress
        if not quiet:
            print_step(1, 5, f"Loading target: {target}")
        with open(target, "r") as f:
            initial_code = f.read()

        if not quiet:
            print_step(2, 5, f"Loading tests: {tests}")
        with open(tests, "r") as f:
            test_code = f.read()

        # Setup output directory
        if out_dir:
            exp_dir = out_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exp_dir = Path(f"experiments/run_{timestamp}")

        exp_dir.mkdir(parents=True, exist_ok=True)
        if not quiet:
            print_step(3, 5, f"Output directory: {exp_dir}")

        # Save configuration
        config = {
            "target": str(target),
            "tests": str(tests),
            "level": level,
            "layers": layers,
            "allowed_imports": allowed_imports,
            "generations": generations,
            "population_size": population_size,
            "timeout": timeout,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "advanced_features": {
                "parallel_processing": parallel,
                "intelligent_selection": intelligent,
                "batch_llm": batch_llm,
                "memory_optimization": memory_optimization,
                "adaptive_parameters": adaptive,
                "max_workers": max_workers,
                "max_memory_mb": max_memory_mb,
            },
            "timestamp": datetime.now().isoformat(),
            "engine_type": "standard",
        }

        with open(exp_dir / "config.json", "w") as f:
            json.dump(config, f, indent=2)

        # Initialize components
        if not quiet:
            print_step(4, 5, "Initializing optimization components")

        # Ensure mutator system is fully initialized
        initialize_mutator_system()
        with Progress(
            SpinnerColumn(style="bold magenta"),
            TextColumn("[bold blue]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Setting up components...", total=None)

            # Create runner
            runner = GreenGymRunner(timeout_seconds=timeout, samples=3)
            progress.update(task, description="✓ Green Gym runner initialized")

            # Setup mutators
            # Parse allowed imports
            allowed_imports_set = set()
            if allowed_imports:
                allowed_imports_set = {i.strip() for i in allowed_imports.split(",")}

            # Create mutators
            mutators, enabled_layers, llm_client = create_mutators(
                level=level,
                layers=layers,
                llm_provider=llm_provider,
                llm_model=llm_model,
                exclude_mutators=exclude_mutators,
                allowed_imports=allowed_imports_set,
                progress=progress,
                task=task,
            )

            # Use the LLM client from mutator factory for batch processing if available
            if batch_llm and llm_client is None and (level in ["advanced", "aggressive"]):
                try:
                    llm_client = create_llm_client(llm_provider, None, llm_model)
                    progress.update(task, description="✓ LLM client initialized (fallback)")
                except Exception as e:
                    if not quiet:
                        print_warning(
                            f"LLM client initialization failed: {e}. Disabling batch LLM."
                        )
                    batch_llm = False

            # Create engine configuration
            engine_config = EngineConfig(
                generations=generations,
                population_size=population_size,
                archive_max_size=opt_cfg.get("archive_max_size", 50),
                crossover_rate=opt_cfg.get("crossover_rate", 0.3),
                save_ir_snapshots=save_ir,
                enable_parallel_mutations=parallel,
                enable_intelligent_selection=intelligent,
                enable_batch_llm=batch_llm,
                enable_memory_optimization=memory_optimization,
                max_memory_usage_mb=max_memory_mb,
                max_concurrent_mutations=max_workers,
                llm_batch_size=llm_cfg.get("batch_size", 5),
                adaptive_population_size=adaptive,
                adaptive_mutation_rate=adaptive,
                early_stopping_patience=opt_cfg.get("early_stopping_patience", 5),
                allowed_imports=list(allowed_imports_set),
            )

            # Event callback for status updates
            def on_event(event):
                if quiet:
                    return

                if event.type == "mutation_attempt":
                    mutator = event.data.get("mutator", "Unknown")
                    strategy = event.data.get("strategy", "Unknown")
                    status_text.plain = f"Mutating: {mutator} using {strategy}..."
                    status_text.style = "yellow"
                elif event.type == "mutation_result":
                    success = event.data.get("success", False)
                    if success:
                        status_text.plain = f"Mutation successful! ({event.data.get('strategy')})"
                        status_text.style = "green"
                    else:
                        status_text.plain = (
                            f"Mutation rejected: {event.data.get('error', 'Unknown error')}"
                        )
                        status_text.style = "red"
                elif event.type == "generation_start":
                    status_text.plain = f"Starting Generation {event.data.get('generation')}..."
                    status_text.style = "bold blue"
                elif event.type == "new_best_solution":
                    status_text.plain = (
                        f"✨ New Best Solution Found! (Energy: {event.data.get('energy', 0):.4f}J)"
                    )
                    status_text.style = "bold gold1"
                elif event.type == "optimization_complete":
                    status_text.plain = "Optimization Completed."
                    status_text.style = "bold green"

            # Create engine
            engine = EvolutionaryEngine(
                mutators=mutators,
                runner=runner,
                config=engine_config,
                llm_client=llm_client,
                experiment_dir=exp_dir,
                event_callback=on_event,
            )

            progress.update(task, description="✓ Engine initialized")

        # Run optimization with progress tracking
        if not quiet:
            print_step(5, 5, "Running optimization")
            console.print()

        start_time = time.time()

        # Create live progress display
        # Create live progress display
        progress_table = create_progress_table()
        status_text = Text("Ready to start...", style="italic cyan")

        # Combine table and status text
        display_group = Group(
            progress_table,
            Text(""),  # Spacer
            Panel(status_text, title="Current Activity", border_style="blue", padding=(0, 1)),
        )

        def update_progress(generation: int, total_generations: int):
            """Update progress callback with enhanced metrics."""
            if quiet:
                return

            # Get current stats
            memory_stats = get_memory_stats()
            engine.get_optimization_summary()

            # Update table
            # We recreate the rows because modifying cells directly is brittle with 3 columns
            # Clear cells to be safe or just overwrite?
            progress_table.columns[1]._cells = []
            # Actually, standard Rich way for live tables is to modify specific rows if possible, or just rebuild the table.
            # But since we passed the table object to the Live context, we must modify it in place.

            # Let's use a safer approach: direct cell access by row/col index if we knew the internal structure,
            # but modifying columns directly is what we did before.
            # New table has 3 columns.

            gen_str = f"{generation}/{total_generations}"
            energy_str = "N/A"
            time_str = "N/A"
            sols_str = "0"
            mem_str = "0MB"
            eff_str = "0%"
            # Estimate or get actual if possible
            threads_str = str(max_workers)

            trend_energy = ""
            trend_time = ""

            if engine.best_solution:
                energy = engine.best_solution.metrics.get("energy_joules", 0)
                time_val = engine.best_solution.metrics.get("duration_seconds", 0)
                energy_str = f"{energy:.6f}J"
                time_str = f"{time_val:.6f}s"
                sols_str = f"{len(engine.archive.solutions)}"
                mem_str = f"{memory_stats.get('memory_saved_mb', 0):.1f}MB"
                eff_str = f"{memory_stats.get('sharing_efficiency', 0):.1%}"

                # Simple trend simulation (would need history for real trend)
                trend_energy = "⬇"
                trend_time = "⟷"

            # Update the columns data directly
            progress_table.columns[1]._cells = [
                gen_str,
                energy_str,
                time_str,
                sols_str,
                mem_str,
                eff_str,
                threads_str,
            ]

            progress_table.columns[2]._cells = [
                "⟳",  # Generation
                trend_energy,
                trend_time,
                "⬆" if int(sols_str) > 0 else "",
                "⬆" if float(mem_str.replace("MB", "")) > 0 else "",
                "=",
                "Active",
            ]

        if not quiet:
            with Live(display_group, refresh_per_second=4, console=console):
                solutions = engine.optimize(
                    initial_code,
                    test_code,
                    enabled_layers=enabled_layers,
                    progress_callback=update_progress,
                )
        else:
            solutions = engine.optimize(initial_code, test_code, enabled_layers=enabled_layers)

        optimization_time = time.time() - start_time

        # Process results
        if not solutions:
            print_error("No valid solutions found!")
            return

        # Get the best solution
        best_solution = engine.best_solution or solutions[0]

        # Generate optimized code
        codegen = PythonCodeGenerator()
        optimized_code = codegen.generate(best_solution.ir)

        # Save optimized code
        if output:
            output_path = output
        else:
            output_path = exp_dir / f"optimized_{target.name}"

        with open(output_path, "w") as f:
            f.write(optimized_code)

        # Get comprehensive optimization summary
        optimization_summary = engine.get_optimization_summary()

        # Display results
        if not quiet:
            console.print()
            print_optimization_summary(
                best_solution, optimization_summary, optimization_time, output_path
            )

        # Save detailed results
        results = {
            "optimization_summary": optimization_summary,
            "best_solution": {
                "metrics": best_solution.metrics,
                "mutation_type": best_solution.mutation_type,
                "generation": best_solution.generation,
            },
            "total_solutions": len(solutions),
            "optimization_time": optimization_time,
            "output_file": str(output_path),
        }

        with open(exp_dir / "results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)

        # Generate visualizations
        if visualize:
            if not quiet:
                console.print("\n[bold blue]Generating visualizations...[/bold blue]")

            try:
                visualizer = ResultVisualizer(exp_dir)
                visualizer.create_visualizations(solutions, optimization_summary)

                if not quiet:
                    print_success(f"Visualizations saved to: {exp_dir / 'visualizations'}")
            except Exception as e:
                print_warning(f"Visualization generation failed: {e}")

        # Performance profiling summary
        if profile:
            if not quiet:
                console.print("\n[bold blue]Performance Profile:[/bold blue]")
                print_performance_profile(optimization_summary)

        if not quiet:
            console.print(f"\n[green]✓ Optimization completed in {optimization_time:.2f}s[/green]")
            console.print(f"[dim]Results saved to: {exp_dir}[/dim]")

    except KeyboardInterrupt:
        print_warning("Optimization interrupted by user")
        return
    except Exception as e:
        print_error(f"Optimization failed: {e}")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        return


def create_progress_table():
    """Create progress table for live updates."""
    table = Table(
        title="Optimization Progress", show_header=True, header_style="bold magenta", box=None
    )

    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold green")
    table.add_column("Trend", style="italic dim")

    table.add_row("Generation", "0/0", "")
    table.add_row("Best Energy", "N/A", "")
    table.add_row("Best Time", "N/A", "")
    table.add_row("Solutions Found", "0", "")
    table.add_row("Memory Saved", "0MB", "")
    table.add_row("Sharing Efficiency", "0%", "")
    table.add_row("Active Worker Threads", "0", "")

    return table


def print_optimization_summary(solution, summary, optimization_time, output_path):
    """Print optimization summary with detailed metrics."""
    console.print(
        Panel.fit("[bold green]Optimization Complete![/bold green]", border_style="green")
    )

    # Main results table
    results_table = Table(title="Optimization Results", show_header=True, header_style="bold cyan")
    results_table.add_column("Metric", style="cyan", no_wrap=True)
    results_table.add_column("Value", style="green")
    results_table.add_column("Details", style="dim")

    # Basic metrics
    energy = solution.metrics.get("energy_joules", 0)
    duration = solution.metrics.get("duration_seconds", 0)

    results_table.add_row("Energy Consumption", f"{energy:.6f}J", "Lower is better")
    results_table.add_row("Execution Time", f"{duration:.6f}s", "Lower is better")
    results_table.add_row(
        "Mutation Type", solution.mutation_type, f"Generation {solution.generation}"
    )
    results_table.add_row(
        "Total Solutions", str(summary.get("total_solutions", 0)), "Pareto archive size"
    )
    results_table.add_row("Optimization Time", f"{optimization_time:.2f}s", "Wall clock time")
    results_table.add_row("Output File", str(output_path), "Optimized code location")

    console.print(results_table)

    # Enhanced features summary
    if "memory_optimization" in summary:
        memory_stats = summary["memory_optimization"]

        memory_table = Table(
            title="Memory Optimization", show_header=True, header_style="bold yellow"
        )
        memory_table.add_column("Metric", style="yellow")
        memory_table.add_column("Value", style="green")

        memory_table.add_row("Memory Saved", f"{memory_stats.get('memory_saved_mb', 0):.1f}MB")
        memory_table.add_row("Copy Ratio", f"{memory_stats.get('copy_ratio', 0):.1%}")
        memory_table.add_row(
            "Sharing Efficiency", f"{memory_stats.get('sharing_efficiency', 0):.1%}"
        )
        memory_table.add_row("Active Wrappers", str(memory_stats.get("active_wrappers", 0)))

        console.print(memory_table)

    # Parallel processing summary
    if "parallel_stats" in summary:
        parallel_stats = summary["parallel_stats"].get("execution_stats", {})

        parallel_table = Table(
            title="Parallel Processing", show_header=True, header_style="bold blue"
        )
        parallel_table.add_column("Metric", style="blue")
        parallel_table.add_column("Value", style="green")

        parallel_table.add_row("Total Tasks", str(parallel_stats.get("total_tasks", 0)))
        parallel_table.add_row("Completed Tasks", str(parallel_stats.get("completed_tasks", 0)))
        parallel_table.add_row("Success Rate", f"{parallel_stats.get('success_rate', 0):.1%}")
        parallel_table.add_row(
            "Parallel Efficiency", f"{parallel_stats.get('parallel_efficiency', 0):.1%}"
        )
        parallel_table.add_row("Throughput", f"{parallel_stats.get('throughput', 0):.1f} tasks/sec")

        console.print(parallel_table)

    # Learning system summary
    if "learning_stats" in summary:
        learning_stats = summary["learning_stats"]

        learning_table = Table(
            title="Intelligent Selection", show_header=True, header_style="bold magenta"
        )
        learning_table.add_column("Metric", style="magenta")
        learning_table.add_column("Value", style="green")

        learning_table.add_row("Total Outcomes", str(learning_stats.get("total_outcomes", 0)))
        learning_table.add_row("Mutator Types", str(learning_stats.get("mutator_count", 0)))

        # Show top performing mutators
        top_mutators = learning_stats.get("top_mutators", [])[:3]
        for i, (mutator, success_rate, improvement) in enumerate(top_mutators):
            learning_table.add_row(
                f"Top Mutator #{i+1}",
                mutator.split(":")[0],
                f"{success_rate:.1%} success, {improvement:.3f} avg improvement",
            )

        console.print(learning_table)


def print_performance_profile(summary):
    """Print detailed performance profiling information."""
    profile_table = Table(title="Performance Profile", show_header=True, header_style="bold red")
    profile_table.add_column("Component", style="red")
    profile_table.add_column("Performance", style="green")
    profile_table.add_column("Recommendation", style="yellow")

    # Memory optimization
    memory_stats = summary.get("memory_optimization", {})
    memory_saved = memory_stats.get("memory_saved_mb", 0)
    sharing_eff = memory_stats.get("sharing_efficiency", 0)

    if memory_saved > 50:
        memory_rec = "Excellent memory optimization"
    elif memory_saved > 10:
        memory_rec = "Good memory savings"
    else:
        memory_rec = "Consider enabling memory optimization"

    profile_table.add_row(
        "Memory Optimization", f"{memory_saved:.1f}MB saved, {sharing_eff:.1%} sharing", memory_rec
    )

    # Parallel processing
    parallel_stats = summary.get("parallel_stats", {}).get("execution_stats", {})
    parallel_eff = parallel_stats.get("parallel_efficiency", 0)

    if parallel_eff > 0.7:
        parallel_rec = "Excellent parallelization"
    elif parallel_eff > 0.4:
        parallel_rec = "Good parallel performance"
    else:
        parallel_rec = "Consider tuning worker count"

    profile_table.add_row("Parallel Processing", f"{parallel_eff:.1%} efficiency", parallel_rec)

    # Learning system
    learning_stats = summary.get("learning_stats", {})
    total_outcomes = learning_stats.get("total_outcomes", 0)

    if total_outcomes > 100:
        learning_rec = "Learning system well-trained"
    elif total_outcomes > 20:
        learning_rec = "Learning system developing"
    else:
        learning_rec = "Run more optimizations to improve learning"

    profile_table.add_row(
        "Intelligent Selection", f"{total_outcomes} learning outcomes", learning_rec
    )

    console.print(profile_table)


def _display_mutator_information(mutators, enabled_layers_set, level, llm_client):
    """Display detailed information about active mutators."""
    from src.application.mutators.base import MutationLayer
    from src.application.mutators.registry import get_registry

    console.print("\n[bold cyan]🔧 Mutator Configuration[/bold cyan]")

    # Show optimization level info
    level_descriptions = {
        "micro": "Basic peephole and micro-optimizations (loops, constants)",
        "basic": "Simple algorithmic improvements and common patterns",
        "standard": "Balanced optimization with moderate AI assistance",
        "advanced": "LLM-powered semantic optimization and advanced patterns",
        "aggressive": "Maximum optimization with experimental techniques",
    }

    console.print(
        f"[dim]Level: {level} - {level_descriptions.get(level, 'Custom configuration')}[/dim]"
    )

    # Show LLM configuration
    if llm_client:
        console.print(
            f"[dim]LLM: {llm_client.__class__.__name__} enabled for semantic mutations[/dim]"
        )
    else:
        console.print("[dim]LLM: Disabled - semantic mutations will be limited[/dim]")

    # Create mutator information table
    mutator_table = Table(
        title="Active Mutators by Layer", show_header=True, header_style="bold green"
    )
    mutator_table.add_column("Layer", style="cyan", width=12)
    mutator_table.add_column("Mutator", style="white", width=25)
    mutator_table.add_column("Strategies", style="yellow", width=40)
    mutator_table.add_column("Status", style="green", width=15)

    registry = get_registry()
    all_mutators = registry.list_all_mutators()

    layer_colors = {
        MutationLayer.SEMANTIC: "red",
        MutationLayer.ALGORITHMIC: "blue",
        MutationLayer.SYNTACTIC: "green",
        MutationLayer.MICRO: "yellow",
    }

    total_strategies = 0
    for layer in [
        MutationLayer.SEMANTIC,
        MutationLayer.ALGORITHMIC,
        MutationLayer.SYNTACTIC,
        MutationLayer.MICRO,
    ]:
        if layer not in enabled_layers_set:
            continue

        layer_mutators = registry.get_layer_mutators(layer)
        for mutator_name in layer_mutators:
            if mutator_name in all_mutators:
                mutator_info = all_mutators[mutator_name]

                # Check if this mutator is actually in our active list
                mutator_active = any(
                    m.__class__.__name__ == mutator_info.mutator_class.__name__ for m in mutators
                )

                if mutator_active:
                    strategies = list(mutator_info.strategies)
                    total_strategies += len(strategies)

                    status = "✓ Active"
                    if layer == MutationLayer.SEMANTIC and not llm_client:
                        status = "⚠ Limited (No LLM)"

                    mutator_table.add_row(
                        f"[{layer_colors.get(layer, 'white')}]{layer.value.title()}[/{layer_colors.get(layer, 'white')}]",
                        mutator_info.mutator_class.__name__.replace("Mutator", "").replace(
                            "Optimizer", ""
                        ),
                        ", ".join(strategies[:3]) + ("..." if len(strategies) > 3 else ""),
                        status,
                    )

    console.print(mutator_table)
    console.print(
        f"[dim]Total: {len(mutators)} mutators with {total_strategies} strategies[/dim]\n"
    )


def _display_dry_run_summary(
    target,
    tests,
    level,
    generations,
    population_size,
    timeout,
    enabled_layers,
    mutators,
    llm_client,
):
    """Display what would be done in a dry run."""
    console.print("\n[bold yellow]🔍 Dry Run Summary[/bold yellow]")

    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Setting", style="cyan", width=20)
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Target File", str(target))
    summary_table.add_row("Test File", str(tests))
    summary_table.add_row("Optimization Level", level)
    summary_table.add_row("Generations", str(generations))
    summary_table.add_row("Population Size", str(population_size))
    summary_table.add_row("Timeout", f"{timeout}s")
    summary_table.add_row("Active Layers", ", ".join(layer.value for layer in enabled_layers))
    summary_table.add_row("Active Mutators", str(len(mutators)))
    summary_table.add_row("LLM Enabled", "Yes" if llm_client else "No")

    console.print(summary_table)

    console.print(
        "\n[dim]This would start the evolutionary optimization process with the above configuration.[/dim]"
    )
    console.print("[dim]Use --verbose or --show-mutators for more detailed information.[/dim]")


# Add the command to the CLI
optimize_cmd = optimize_cmd
