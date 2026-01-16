#!/usr/bin/env python3
"""
Ablation Study for HEDGE on target_complex.py
"""
import subprocess
import sys
import json
from pathlib import Path
import time
import os

TARGET = "examples/target_complex.py"
TESTS = "examples/test_target_complex.py"
BASE_OUTPUT_DIR = "experiments/ablation_complex"

CONFIGURATIONS = [
    {
        "name": "01_micro_only",
        "args": ["--level", "micro", "--generations", "5"]
    },
    {
        "name": "02_syntactic_only",
        "args": ["--layers", "syntactic", "--generations", "5"]
    },
    {
        "name": "03_algorithmic_only",
        "args": ["--layers", "algorithmic", "--generations", "5"]
    },
    {
        "name": "04_micro_syntactic",
        "args": ["--layers", "micro,syntactic", "--generations", "5"]
    },
    {
        "name": "05_micro_algorithmic",
        "args": ["--layers", "micro,algorithmic", "--generations", "5"]
    },
    {
        "name": "06_standard",
        "args": ["--level", "standard", "--generations", "5"]
    }
]

# Add advanced if API key is present
# We'll just try adding it, hedge handles missing key gracefully usually (logs warning)
# But let's check env var just in case to be safe? 
# hedge.py loads .env itself.
CONFIGURATIONS.append({
    "name": "07_advanced_semantic",
    "args": ["--level", "advanced", "--generations", "5", "--llm-provider", "gemini"]
})

import difflib


def run_ablation():
    print(f"Starting Ablation Study on {TARGET}")
    base_dir = Path(BASE_OUTPUT_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)
    
    results_summary = []

    for config in CONFIGURATIONS:
        name = config["name"]
        print(f"\nRunning configuration: {name}")
        
        exp_dir = base_dir / name
        exp_dir.mkdir(exist_ok=True)
        
        optimized_code_path = exp_dir / "optimized_code.py"
        
        cmd = [
            sys.executable, "hedge.py", "optimize",
            TARGET, TESTS,
            "--experiment-dir", str(exp_dir),
            "--save-ir",
            "--output-file", str(optimized_code_path)
        ] + config["args"]
        
        start_time = time.time()
        try:
            # Short timeout ensuring we don't hang forever
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            duration = time.time() - start_time
            
            # Save logs
            with open(exp_dir / "stdout.log", "w") as f:
                f.write(result.stdout)
            with open(exp_dir / "stderr.log", "w") as f:
                f.write(result.stderr)
                
            success = result.returncode == 0
            
            # Generate Diff if successful and file exists
            if success and optimized_code_path.exists():
                print(f"Saved optimized code to: {optimized_code_path}")
                
                original_code = Path(TARGET).read_text().splitlines()
                optimized_code = optimized_code_path.read_text().splitlines()
                
                diff = difflib.unified_diff(
                    original_code, 
                    optimized_code, 
                    fromfile='original', 
                    tofile='optimized', 
                    lineterm=''
                )
                
                diff_text = '\n'.join(diff)
                diff_path = exp_dir / "optimization.diff"
                diff_path.write_text(diff_text)
                print(f"Saved diff to: {diff_path}")
            
            # Try to read result json
            metrics = {}
            pareto_path = exp_dir / "pareto_results.json"
            if pareto_path.exists():
                with open(pareto_path, "r") as f:
                    data = json.load(f)
                    if data:
                        # Get best energy
                         best = min(data, key=lambda s: s["metrics"].get("energy_joules", float('inf')))
                         metrics = best["metrics"]
            
            summary = {
                "name": name,
                "success": success,
                "duration": duration,
                "best_energy": metrics.get("energy_joules"),
                "best_time": metrics.get("duration_seconds")
            }
            results_summary.append(summary)
            print(f"Completed {name}: Success={success}, Duration={duration:.2f}s")
            if not_success_msg := result.stderr if not success else "":
                print(f"Error (tail): {not_success_msg[-200:] if not_success_msg else 'None'}")

        except subprocess.TimeoutExpired:
            print(f"Timeout for {name}")
            results_summary.append({"name": name, "success": False, "error": "Timeout"})
        except Exception as e:
            print(f"Error running {name}: {e}")
            results_summary.append({"name": name, "success": False, "error": str(e)})

    # Print Report
    print("\n" + "="*50)
    print("ABLATION STUDY RESULTS")
    print("="*50)
    print(f"{'Configuration':<25} | {'Success':<7} | {'Time(s)':<8} | {'Energy(J)':<10}")
    print("-" * 60)
    for r in results_summary:
        energy = f"{r.get('best_energy', 0):.4f}" if r.get('best_energy') else "N/A"
        print(f"{r['name']:<25} | {str(r['success']):<7} | {r.get('duration', 0):<8.2f} | {energy:<10}")
    
    with open(base_dir / "summary.json", "w") as f:
        json.dump(results_summary, f, indent=2)

if __name__ == "__main__":
    run_ablation()
