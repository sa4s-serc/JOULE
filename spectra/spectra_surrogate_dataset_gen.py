import csv
import json
import logging
from pathlib import Path
from typing import Dict, Any

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def generate_dataset(spectra_output_dir: Path, output_csv: Path):
    """
    Parses all output directories from SPECTRA runs by reading the metrics JSON.
    Aggregates F3 evaluations into a single, deduplicated training CSV.
    """
    if not spectra_output_dir.exists():
        logging.error(f"Directory not found: {spectra_output_dir}")
        return

    dataset_rows: Dict[str, Dict[str, Any]] = {} # Use dict for deduplication by source code
    processed_runs = 0

    for run_dir in spectra_output_dir.iterdir():
        if not run_dir.is_dir():
            continue
            
        # Parse the JSON instead of the CSV. The JSON contains the actual source code.
        metrics_file = run_dir / f"{run_dir.name}_metrics.json"
        
        if not metrics_file.exists():
            logging.warning(f"Skipping {run_dir.name}: No metrics JSON found.")
            continue
            
        try:
            with open(metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse JSON in {metrics_file}")
            continue

        func_name = data.get("function_name", run_dir.name)
        
        # 1. Capture the BASELINE measurement
        # The baseline function is a valid, highly-accurate data point!
        original_source = data.get("original_source")
        baseline_mj = data.get("baseline_mj")
        if original_source and baseline_mj and original_source not in dataset_rows:
            dataset_rows[original_source] = {
                'function_name': func_name,
                'source': original_source,
                'operator': 'baseline',
                'tier': 'none',
                'is_llm': False,
                'chain_depth': 0,
                'energy_mJ': baseline_mj,
                'std_mJ': data.get("baseline_std_mj", 0.0),
                'cv': 0.0, # Baseline CV isn't explicitly at the top level, defaulting to 0
                'n_samples': 20 # Standard F3 reps
            }

        # 2. Capture all CANDIDATE measurements
        for iteration in data.get("iterations", []):
            for cand in iteration.get("candidates", []):
                
                # We only want candidates that reached F3 (Ground Truth)
                # SPECTRA v3 introduces trimmed_mean_mj, which is more robust than raw mean
                f3_mj = cand.get("f3_trimmed_mean_mj") or cand.get("f3_mj")
                
                if f3_mj is not None and float(f3_mj) > 0:
                    source = cand.get("transformed_source", "")
                    
                    # Skip if we already have this exact source code to prevent data leakage
                    if not source or source in dataset_rows:
                        continue
                        
                    # Calculate actual number of runs (SPECTRA v3 removes outliers at F3)
                    outliers_removed = cand.get("f3_outliers_removed", 0)
                    n_samples = 20 - outliers_removed 

                    dataset_rows[source] = {
                        'function_name': func_name,
                        'source': source,
                        'operator': cand.get("operator", "unknown"),
                        'tier': cand.get("tier", "unknown"),
                        'is_llm': cand.get("is_llm", False),
                        'chain_depth': cand.get("chain_depth", 1),
                        'energy_mJ': f3_mj,
                        'std_mJ': cand.get("f3_std_mj", 0.0),
                        'cv': cand.get("f3_cv", 0.0),
                        'n_samples': n_samples
                    }
        
        processed_runs += 1

    # 3. Write aggregated data to CSV
    if not dataset_rows:
        logging.error("No valid F3 data found across any directories.")
        return

    keys = [
        'function_name', 'source', 'operator', 'tier', 'is_llm', 
        'chain_depth', 'energy_mJ', 'std_mJ', 'cv', 'n_samples'
    ]
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(dataset_rows.values())
    
    logging.info(f"Processed {processed_runs} functions.")
    logging.info(f"Successfully generated {len(dataset_rows)} unique samples in {output_csv}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate ML training dataset from SPECTRA outputs.")
    parser.add_argument("--dir", required=True, help="Directory containing your spectra_output subfolders")
    parser.add_argument("--out", default="training_data.csv", help="Output CSV path")
    args = parser.parse_args()
    
    generate_dataset(Path(args.dir), Path(args.out))