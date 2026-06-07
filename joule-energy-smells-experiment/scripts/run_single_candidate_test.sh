#!/usr/bin/env bash
# Run the full experiment end-to-end on a single candidate for verification

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$EXPERIMENT_DIR")"
VENV="$REPO_ROOT/.venv/bin/python"

echo "=========================================="
echo "Single Candidate End-to-End Test"
echo "=========================================="
echo ""

# Backup original config
CONFIG_FILE="$EXPERIMENT_DIR/experiment_config.py"
CONFIG_BACKUP="$EXPERIMENT_DIR/experiment_config.py.backup"

if [ ! -f "$CONFIG_BACKUP" ]; then
    cp "$CONFIG_FILE" "$CONFIG_BACKUP"
    echo "Backed up original config to $CONFIG_BACKUP"
fi

# Use test config
TEST_CONFIG="$EXPERIMENT_DIR/experiment_config_test.py"
cp "$TEST_CONFIG" "$CONFIG_FILE"
echo "Using test config (single candidate)"
echo ""

# Run each phase
PHASES=(
    "00_prep_dataset.py:Pre-process dataset"
    "01_scaffold_repos.py:Scaffold mini-repos"
    "02_run_baselines.py:Run baselines"
    "03_run_optimizations.py:Run optimizations"
    "04_harvest_results.py:Harvest results"
    "05_analyze_results.py:Analyze & generate plots"
)

for phase_info in "${PHASES[@]}"; do
    IFS=':' read -r script_name description <<< "$phase_info"
    echo "=========================================="
    echo "Running: $description"
    echo "Script: $script_name"
    echo "=========================================="
    
    if "$VENV" "$SCRIPT_DIR/$script_name"; then
        echo "✓ Phase completed successfully"
    else
        echo "✗ Phase failed"
        # Restore original config
        cp "$CONFIG_BACKUP" "$CONFIG_FILE"
        exit 1
    fi
    echo ""
done

# Restore original config
cp "$CONFIG_BACKUP" "$CONFIG_FILE"
echo "Restored original config"

echo "=========================================="
echo "All phases completed successfully!"
echo "=========================================="
echo ""
echo "Test results available in:"
echo "  $EXPERIMENT_DIR/results_test/"
echo "  $EXPERIMENT_DIR/workspaces_test/"
