#!/bin/bash
# Master Orchestration Script for JOULE Large Repo Experiment
# Runs all phases in sequence with support for resumption and single-phase execution.
#
# Usage:
#   ./run_experiment.sh                   # run all phases from phase 1
#   ./run_experiment.sh --start-phase 3   # resume from phase 3
#   ./run_experiment.sh --phase 5         # run only phase 5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/experiment_config.sh"

# ── Argument parsing ──────────────────────────────────────────────────────────
START_PHASE=1
SINGLE_PHASE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase)
            SINGLE_PHASE="$2"; START_PHASE="$2"; shift 2 ;;
        --start-phase)
            START_PHASE="$2"; shift 2 ;;
        *)
            log_error "Unknown argument: $1"
            echo "Usage: $0 [--start-phase N] [--phase N]"
            exit 1 ;;
    esac
done

log_info "=== JOULE Large Repo Experiment Orchestration ==="
log_info "Experiment root : ${EXPERIMENT_ROOT}"
log_info "JOULE source    : ${JOULE_SRC}"
log_info "Repos           : ${REPOS}"
log_info "Energy backend  : ${JOULE_BACKEND}"
log_info "Start phase     : ${START_PHASE}${SINGLE_PHASE:+ (single phase mode)}"

# ── Phase implementations ─────────────────────────────────────────────────────

run_phase_1() {
    log_info "=== Running Phase 1: Setup ==="
    bash "${SCRIPT_DIR}/01_setup.sh"
}

run_phase_2() {
    log_info "=== Running Phase 2: Discovery ==="
    # BUG FIX: pass $repo as an argument; 02_discover.sh no longer loops internally.
    for repo in ${REPOS}; do
        bash "${SCRIPT_DIR}/02_discover.sh" "${repo}"
    done
}

run_phase_3() {
    log_info "=== Running Phase 3: Hotspot Selection ==="
    for repo in ${REPOS}; do
        log_info "Selecting hotspots for ${repo}..."
        if ! python3 "${SCRIPT_DIR}/03_select_hotspots.py" \
                --repo "${repo}" \
                --sample-size "${SAMPLE_SIZE}"; then
            log_error "Phase 3 failed for ${repo}"
            exit 1
        fi
    done
}

run_phase_35() {
    log_info "=== Running Phase 3.5: Workload Pre-flight ==="
    for repo in ${REPOS}; do
        log_info "Pre-flight workload check for ${repo}..."
        if ! python3 "${SCRIPT_DIR}/03b_preflight_workloads.py" \
                --repo "${repo}" \
                --min-workloads "${MIN_WORKLOADS_PREFLIGHT}" \
                --min-alignment "${MIN_ALIGNMENT_PREFLIGHT}" \
                --workload-limit "${WORKLOAD_DISCOVERY_LIMIT}"; then
            log_error "Phase 3.5 failed for ${repo}"
            exit 1
        fi
    done
}

run_phase_4() {
    log_info "=== Running Phase 4: Hotspot Baseline ==="
    for repo in ${REPOS}; do
        # Use preflight CSV if available; fall back to raw sample CSV
        preflight_file="${RESULTS_DIR}/hotspots/${repo}_preflight.csv"
        sample_file="${RESULTS_DIR}/hotspots/${repo}_sample_targets.csv"
        if [ -f "${preflight_file}" ]; then
            input_file="${preflight_file}"
        elif [ -f "${sample_file}" ]; then
            log_warn "Preflight CSV not found for ${repo}; using raw sample targets (run Phase 3.5 for better results)"
            input_file="${sample_file}"
        else
            log_error "No sample file found for ${repo}: ${preflight_file}"
            log_error "Run Phase 3 and Phase 3.5 first."
            exit 1
        fi
        bash "${SCRIPT_DIR}/04_hotspot_baseline.sh" "${repo}" "${input_file}"
    done
}

run_phase_5() {
    log_info "=== Running Phase 5: Top Hotspot Identification ==="
    for repo in ${REPOS}; do
        log_info "Identifying top hotspots for ${repo}..."
        if ! python3 "${SCRIPT_DIR}/05_identify_top_hotspots.py" \
                --repo "${repo}" \
                --limit "${TOP_HOTSPOTS_LIMIT}"; then
            log_error "Phase 5 failed for ${repo}"
            exit 1
        fi
    done
}

run_phase_6() {
    log_info "=== Running Phase 6: Final Baseline ==="
    for repo in ${REPOS}; do
        hotspots_file="${RESULTS_DIR}/final_baselines/${repo}_top_hotspots.csv"
        if [ ! -f "${hotspots_file}" ]; then
            log_error "Top hotspots file not found for ${repo}: ${hotspots_file}"
            log_error "Run Phase 5 first."
            exit 1
        fi
        bash "${SCRIPT_DIR}/06_final_baseline.sh" "${repo}" "${hotspots_file}"
    done
}

run_phase_7() {
    log_info "=== Running Phase 7: Optimization ==="
    for repo in ${REPOS}; do
        hotspots_file="${RESULTS_DIR}/final_baselines/${repo}_top_hotspots.csv"
        if [ ! -f "${hotspots_file}" ]; then
            log_error "Top hotspots file not found for ${repo}: ${hotspots_file}"
            log_error "Run Phase 5 first."
            exit 1
        fi
        bash "${SCRIPT_DIR}/07_optimize.sh" "${repo}" "${hotspots_file}" "${OPTIMIZATION_BUDGET}"
    done
}

run_phase_8() {
    log_info "=== Running Phase 8: Analysis ==="
    # Capture Python output into the experiment log
    python3 "${SCRIPT_DIR}/08_analyze_results.py" --repos "${REPOS}" 2>&1 | tee -a "${LOG_FILE}" >&2
}

run_phase_9() {
    log_info "=== Running Phase 9: Report Generation ==="
    bash "${SCRIPT_DIR}/09_generate_report.sh"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
# ALL_PHASES uses strings to accommodate phase 3.5
ALL_PHASES=(1 2 3 3.5 4 5 6 7 8 9)

_phase_fn() {
    # Convert "3.5" → "run_phase_35"; integers pass through as-is
    local p="${1//./_}"
    # Remove trailing underscore for integers (3 → run_phase_3, not run_phase_3_)
    echo "run_phase_${p//_0/}"
}

# Numeric comparison helper — bash can't compare floats natively
_phase_ge() {
    # Returns 0 (true) if phase $1 >= phase $2 using awk for float comparison
    awk -v a="$1" -v b="$2" 'BEGIN { exit !(a >= b) }'
}

run_from() {
    local from="$1"
    for phase in "${ALL_PHASES[@]}"; do
        if _phase_ge "${phase}" "${from}"; then
            local fn
            fn="$(_phase_fn "${phase}")"
            if declare -f "${fn}" > /dev/null 2>&1; then
                "${fn}"
            fi
        fi
    done
}

if [ -n "${SINGLE_PHASE}" ]; then
    fn="$(_phase_fn "${SINGLE_PHASE}")"
    if ! declare -f "${fn}" > /dev/null 2>&1; then
        log_error "Invalid phase: ${SINGLE_PHASE}. Valid: 1, 2, 3, 3.5, 4–9"
        exit 1
    fi
    "${fn}"
else
    run_from "${START_PHASE}"
fi

log_info "=== Experiment Complete ==="
log_info "Report: ${REPORT_DIR}/experiment_report.md"
log_info "Analysis: ${RESULTS_DIR}/analysis/aggregated_results.json"
