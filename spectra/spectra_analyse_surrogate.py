import numpy as np
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys

def analyze_surrogate(pkl_path: Path):
    if not pkl_path.exists():
        print(f"Error: {pkl_path} not found.")
        return

    with open(pkl_path, 'rb') as f:
        state = pickle.load(f)
    
    model = state['model']
    X = np.array(state['X'])
    y = np.array(state['y'])
    
    feature_names = [
        "For", "While", "ListComp", "Set/DictComp", "Calls", 
        "AST_Nodes", "Compare", "In_Tests", "LLM_Tier", "Depth", 
        "LLM_Ops", "Log_N", "Halstead", "Cyclomatic", "Mem_Density", "Alg_Depth"
    ]

    print(f"--- Model Insights ---")
    print(f"Total samples: {len(X)}")
    print(f"Energy range: {np.min(y):.2f}mJ - {np.max(y):.2f}mJ")
    
    # 1. Feature Importance (Permutation)
    # How much does shuffling one feature degrade the model's accuracy?
    baseline_score = model.score(X, y)
    importances = []
    for i in range(X.shape[1]):
        X_shuffled = X.copy()
        np.random.shuffle(X_shuffled[:, i])
        score = model.score(X_shuffled, y)
        importances.append(baseline_score - score)
    
    # Plot Feature Importance
    plt.figure(figsize=(10, 6))
    sns.barplot(x=importances, y=feature_names, palette="viridis")
    plt.title("Surrogate Feature Importance (Impact on Energy Prediction)")
    plt.xlabel("Accuracy Degradation (R² drop)")
    plt.tight_layout()
    plt.savefig("feature_importance.png")
    print("Saved: feature_importance.png")

    # 2. Benchmarking: Predicted vs Actual
    y_pred, y_std = model.predict(X, return_std=True)
    
    plt.figure(figsize=(8, 8))
    plt.scatter(y, y_pred, alpha=0.6, c=y_std, cmap="magma")
    plt.plot([min(y), max(y)], [min(y), max(y)], 'k--')
    plt.colorbar(label="Prediction Uncertainty (std)")
    plt.xlabel("Actual Energy (mJ)")
    plt.ylabel("Predicted Energy (mJ)")
    plt.title("Model Benchmarking: Predicted vs Actual")
    plt.tight_layout()
    plt.savefig("benchmark_scatter.png")
    print("Saved: benchmark_scatter.png")
    
    # 3. Correlation Matrix (Feature interactions)
    plt.figure(figsize=(10, 8))
    sns.heatmap(np.corrcoef(X, rowvar=False), xticklabels=feature_names, 
                yticklabels=feature_names, cmap="coolwarm")
    plt.title("Feature Interaction Correlation")
    plt.tight_layout()
    plt.savefig("feature_correlation.png")
    print("Saved: feature_correlation.png")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python spectra_analyze.py <path_to_surrogate.pkl>")
    else:
        analyze_surrogate(Path(sys.argv[1]))