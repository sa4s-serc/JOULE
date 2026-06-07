#!/usr/bin/env bash
# ============================================================
# JOULE × Energy-Smells Experiment — End-to-End Runner
# ============================================================
# Usage:
#   ./scripts/run_experiment.sh              # run all phases
#   ./scripts/run_experiment.sh --start-phase 3   # resume from phase 3
#   ./scripts/run_experiment.sh --phase 5         # run only phase 5
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$EXPERIMENT_DIR")"
VENV="$REPO_ROOT/.venv/bin/python"
LOG_FILE="$EXPERIMENT_DIR/logs/experiment.log"

mkdir -p "$EXPERIMENT_DIR/logs"

START_PHASE=0
END_PHASE=5
ONLY_PHASE=""

# ── Parse args ─────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --start-phase)
            START_PHASE="$2"; shift 2 ;;
        --phase)
            ONLY_PHASE="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -n "$ONLY_PHASE" ]]; then
    START_PHASE="$ONLY_PHASE"
    END_PHASE="$ONLY_PHASE"
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

run_phase() {
    local phase="$1"
    local script="$2"
    local name="$3"

    if [[ "$phase" -lt "$START_PHASE" ]] || [[ "$phase" -gt "$END_PHASE" ]]; then
        log "SKIP phase $phase ($name)"
        return
    fi

    log "START phase $phase: $name"
    local t_start=$SECONDS

    if "$VENV" "$SCRIPT_DIR/$script"; then
        local elapsed=$(( SECONDS - t_start ))
        log "DONE  phase $phase: $name [${elapsed}s]"
    else
        log "FAIL  phase $phase: $name — check $LOG_FILE for details"
        exit 1
    fi
}

# ── Check venv ─────────────────────────────────────────────
if [[ ! -x "$VENV" ]]; then
    echo "Virtual environment not found at $VENV"
    echo "Run: make install-dev"
    exit 1
fi

log "=============================================="
log "JOULE x Energy-Smells Experiment"
log "Phases $START_PHASE – $END_PHASE"
log "Repo root: $REPO_ROOT"
log "=============================================="

run_phase 0 "00_prep_dataset.py"        "Pre-process dataset"
run_phase 1 "01_scaffold_repos.py"      "Scaffold mini-repos"
run_phase 2 "02_run_baselines.py"       "Run baselines"
run_phase 3 "03_run_optimizations.py"   "Run optimizations"
run_phase 4 "04_harvest_results.py"     "Harvest results"
run_phase 5 "05_analyze_results.py"     "Analyze & generate plots"

log "=============================================="
log "Experiment complete."
log "Results: $EXPERIMENT_DIR/results/"
log "Report:  $EXPERIMENT_DIR/results/analysis/analysis_report.md"
log "=============================================="
