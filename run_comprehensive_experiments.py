#!/usr/bin/env python3
"""
Comprehensive HEDGE Experiment Suite
=====================================
Runs exhaustive experiments across multiple optimization levels and examples
to showcase the full potential of the HEDGE optimizer.
"""
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime
import time

# Experiment configurations
EXPERIMENTS = [
    # Quick micro-optimizations
    {
        "name": "fib_micro",
        "target": "examples/target_fib.py",
        "tests": "examples/test_target_fib.py",
        "level": "micro",
        "generations": 10,
        "description": "Fibonacci - Micro optimizations only"
    },
    {
        "name": "formal_micro",
        "target": "examples/target_formal.py",
        "tests": "examples/test_target_formal.py",
        "level": "micro",
        "generations": 10,
        "description": "Formal example - Constant folding & dead code"
    },
    
    # Standard optimizations
    {
        "name": "search_standard",
        "target": "examples/target_search.py",
        "tests": "examples/test_target_search.py",
        "level": "standard",
        "generations": 15,
        "description": "Search - Standard optimizations (micro+syntactic+algorithmic)"
    },
    {
        "name": "complex_standard",
        "target": "examples/target_complex.py",
        "tests": "examples/test_target_complex.py",
        "level": "standard",
        "generations": 20,
        "description": "Complex - Multiple inefficiencies"
    },
    
    # Advanced with LLM
    {
        "name": "fib_advanced",
        "target": "examples/target_fib.py",
        "tests": "examples/test_target_fib.py",
        "level": "advanced",
        "generations": 25,
        "description": "Fibonacci - Advanced with semantic layer (LLM)"
    },
    {
        "name": "complex_advanced",
        "target": "examples/target_complex.py",
        "tests": "examples/test_target_complex.py",
        "level": "advanced",
        "generations": 30,
        "description": "Complex - Full advanced optimization"
    },
    
    # Aggressive long-running
    {
        "name": "complex_aggressive_long",
        "target": "examples/target_complex.py",
        "tests": "examples/test_target_complex.py",
        "level": "aggressive",
        "generations": 50,
        "description": "Complex - Aggressive long-running (50 generations)"
    },
    {
        "name": "fib_aggressive_long",
        "target": "examples/target_fib.py",
        "tests": "examples/test_target_fib.py",
        "level": "aggressive",
        "generations": 40,
        "description": "Fibonacci - Aggressive optimization"
    },
    
    # Custom layer combinations
    {
        "name": "complex_custom_algo_micro",
        "target": "examples/target_complex.py",
        "tests": "examples/test_target_complex.py",
        "layers": "algorithmic,micro",
        "generations": 20,
        "description": "Complex - Custom: Algorithmic + Micro only"
    },
]

def run_experiment(exp_config, base_dir):
    """Run a single experiment."""
    print(f"\n{'='*80}")
    print(f"EXPERIMENT: {exp_config['name']}")
    print(f"Description: {exp_config['description']}")
    print(f"{'='*80}\n")
    
    # Create experiment directory
    exp_dir = base_dir / exp_config['name']
    exp_dir.mkdir(parents=True, exist_ok=True)
    
    # Build command
    cmd = [
        sys.executable, "hedge.py", "optimize",
        exp_config['target'],
        exp_config['tests'],
        "--experiment-dir", str(exp_dir),
        "--visualize",
        "--save-ir",
        "--verbose"
    ]
    
    # Add level or layers
    if 'level' in exp_config:
        cmd.extend(["--level", exp_config['level']])
    if 'layers' in exp_config:
        cmd.extend(["--layers", exp_config['layers']])
    
    # Add generations
    if 'generations' in exp_config:
        cmd.extend(["--generations", str(exp_config['generations'])])
    
    # Save experiment config
    with open(exp_dir / "experiment_config.json", 'w') as f:
        json.dump(exp_config, f, indent=2)
    
    # Run experiment
    start_time = time.time()
    try:
        # Increased timeout to 1200s to handle heavier tests
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        duration = time.time() - start_time
        
        # Save output
        with open(exp_dir / "stdout.log", 'w') as f:
            f.write(result.stdout)
        with open(exp_dir / "stderr.log", 'w') as f:
            f.write(result.stderr)
        
        success = result.returncode == 0
        print(f"\n✓ Experiment completed in {duration:.2f}s")
        
        return {
            "name": exp_config['name'],
            "success": success,
            "duration": duration,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"\n✗ Experiment timed out after {duration:.2f}s")
        return {
            "name": exp_config['name'],
            "success": False,
            "duration": duration,
            "error": "timeout"
        }
    except Exception as e:
        duration = time.time() - start_time
        print(f"\n✗ Experiment failed: {e}")
        return {
            "name": exp_config['name'],
            "success": False,
            "duration": duration,
            "error": str(e)
        }

def main():
    """Run all experiments."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║              HEDGE COMPREHENSIVE EXPERIMENT SUITE                         ║
║              Exhaustive Optimization Testing                              ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
""")
    
    # Create base experiment directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = Path(f"experiments/comprehensive_{timestamp}")
    base_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Experiment Suite Directory: {base_dir}")
    print(f"Total Experiments: {len(EXPERIMENTS)}\n")
    
    # Run all experiments
    results = []
    for i, exp_config in enumerate(EXPERIMENTS, 1):
        print(f"\n[{i}/{len(EXPERIMENTS)}] Starting: {exp_config['name']}")
        result = run_experiment(exp_config, base_dir)
        results.append(result)
        
        # Brief pause between experiments
        time.sleep(2)
    
    # Generate summary
    print(f"\n\n{'='*80}")
    print("EXPERIMENT SUITE SUMMARY")
    print(f"{'='*80}\n")
    
    successful = sum(1 for r in results if r['success'])
    total_duration = sum(r['duration'] for r in results)
    
    print(f"Total Experiments: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(results) - successful}")
    print(f"Total Duration: {total_duration:.2f}s ({total_duration/60:.2f} minutes)")
    
    print("\nIndividual Results:")
    for r in results:
        status = "✓" if r['success'] else "✗"
        print(f"  {status} {r['name']}: {r['duration']:.2f}s")
    
    # Save summary
    summary = {
        "timestamp": timestamp,
        "total_experiments": len(results),
        "successful": successful,
        "failed": len(results) - successful,
        "total_duration": total_duration,
        "results": results
    }
    
    with open(base_dir / "suite_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✓ Summary saved to: {base_dir}/suite_summary.json")
    print(f"\nView individual experiment results in: {base_dir}/")
    
    return 0 if successful == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
