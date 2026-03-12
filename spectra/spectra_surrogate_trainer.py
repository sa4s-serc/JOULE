import ast
import json
import csv
import pickle
import numpy as np
from pathlib import Path
# Assuming your main spectra_research.py is in the same folder
from spectra_research import EnergySurrogate 

def train_from_csv(csv_path: Path, output_pkl: Path):
    """
    Trains an EnergySurrogate from a CSV file.
    Expected CSV columns: source, chain_json, energy_mJ, std_mJ, n_samples
    """
    surrogate = EnergySurrogate()
    
    print(f"--- Loading data from {csv_path} ---")
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 1. Reconstruct chain from JSON string
            chain = json.loads(row['chain_json'])
            
            # 2. Extract numeric values
            energy = float(row['energy_mJ'])
            std = float(row['std_mJ'])
            n = float(row['n_samples'])
            source = row['source']
            
            # 3. Update surrogate
            surrogate.update(source, chain, energy, std, n)
            
    # 4. Final retrain to ensure model is optimized
    if surrogate.is_trained:
        print(f"Successfully trained on {len(surrogate._X)} samples.")
        surrogate.save(output_pkl)
        print(f"Model saved to {output_pkl}")
    else:
        print("Error: Not enough data or training failed.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="CSV file with columns: source, chain_json, energy_mJ, std_mJ, n_samples")
    parser.add_argument("--out", default="pre_trained_surrogate.pkl", help="Output .pkl file")
    args = parser.parse_args()
    
    train_from_csv(Path(args.data), Path(args.out))