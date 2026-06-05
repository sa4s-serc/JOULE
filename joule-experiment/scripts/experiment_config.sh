#!/bin/bash
# JOULE Large Repo Experiment Configuration
# Source this file in other scripts to access configuration

# Experiment paths (can be overridden by environment variables)
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REPOS_DIR="${EXPERIMENT_ROOT}/repos"
RESULTS_DIR="${EXPERIMENT_ROOT}/results"
SCRIPTS_DIR="${EXPERIMENT_ROOT}/scripts"
REPORT_DIR="${EXPERIMENT_ROOT}/report"

# JOULE source path (can be overridden)
JOULE_SRC="${JOULE_SRC:-}"
if [ -z "${JOULE_SRC}" ]; then
    if [ -f "${EXPERIMENT_ROOT}/../joule" ] || [ -f "${EXPERIMENT_ROOT}/../src/joule/__init__.py" ]; then
        JOULE_SRC="$(cd "${EXPERIMENT_ROOT}/.." && pwd)"
    elif [ -d "${EXPERIMENT_ROOT}/../hedge" ]; then
        JOULE_SRC="$(cd "${EXPERIMENT_ROOT}/../hedge" && pwd)"
    elif [ -d "${EXPERIMENT_ROOT}/../../hedge" ]; then
        JOULE_SRC="$(cd "${EXPERIMENT_ROOT}/../../hedge" && pwd)"
    elif [ -d "${EXPERIMENT_ROOT}/hedge" ]; then
        JOULE_SRC="${EXPERIMENT_ROOT}/hedge"
    else
        echo "Warning: JOULE source not found automatically."
        echo "Please set JOULE_SRC environment variable to the hedge directory."
        echo "Example: export JOULE_SRC=/path/to/hedge"
        JOULE_SRC=""
    fi
fi

# Repository list
REPOS="${REPOS:-black networkx sympy}"

# JOULE configuration
JOULE_PROFILE="${JOULE_PROFILE:-thorough}"
# Default to mock; override with JOULE_BACKEND=rapl if RAPL is available on the machine.
# Real energy measurements require RAPL (Linux, Intel/AMD with powercap enabled).
# Check availability: cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
JOULE_BACKEND="${JOULE_BACKEND:-mock}"
BASELINE_REPETITIONS="${BASELINE_REPETITIONS:-8}"
OPTIMIZATION_BUDGET="${OPTIMIZATION_BUDGET:-10}"
WORKLOAD_DISCOVERY_LIMIT="${WORKLOAD_DISCOVERY_LIMIT:-20}"
HOTSPOT_LIMIT="${HOTSPOT_LIMIT:-30}"
FINAL_IMPROVEMENT_MIN="${FINAL_IMPROVEMENT_MIN:-0.10}"
MEMORY_REGRESSION_LIMIT="${MEMORY_REGRESSION_LIMIT:-0.10}"
DISCOVERY_LIMIT="${DISCOVERY_LIMIT:-150}"
MIN_WORKLOADS_PREFLIGHT="${MIN_WORKLOADS_PREFLIGHT:-1}"
MIN_ALIGNMENT_PREFLIGHT="${MIN_ALIGNMENT_PREFLIGHT:-3.0}"
MIN_SINGLE_OCCURRENCE_RUNTIME="${MIN_SINGLE_OCCURRENCE_RUNTIME:-0.05}"

# Resource limits
MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES:-4}"
MAX_PARALLEL_OPTIMIZATIONS="${MAX_PARALLEL_OPTIMIZATIONS:-2}"
WORKLOAD_TIMEOUT_S="${WORKLOAD_TIMEOUT_S:-300}"

# Hotspot selection
SAMPLE_SIZE="${SAMPLE_SIZE:-80}"
TOP_HOTSPOTS_LIMIT="${TOP_HOTSPOTS_LIMIT:-30}"

# Logging
LOG_DIR="${EXPERIMENT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/experiment.log"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Export variables for subshells
export EXPERIMENT_ROOT REPOS_DIR RESULTS_DIR SCRIPTS_DIR REPORT_DIR
export JOULE_SRC JOULE_PROFILE JOULE_BACKEND
export BASELINE_REPETITIONS OPTIMIZATION_BUDGET WORKLOAD_DISCOVERY_LIMIT
export HOTSPOT_LIMIT FINAL_IMPROVEMENT_MIN MEMORY_REGRESSION_LIMIT
export DISCOVERY_LIMIT MIN_WORKLOADS_PREFLIGHT MIN_ALIGNMENT_PREFLIGHT MIN_SINGLE_OCCURRENCE_RUNTIME
export MAX_PARALLEL_BASELINES MAX_PARALLEL_OPTIMIZATIONS WORKLOAD_TIMEOUT_S
export SAMPLE_SIZE TOP_HOTSPOTS_LIMIT
export LOG_DIR LOG_FILE LOG_LEVEL

# Create necessary directories
mkdir -p "${LOG_DIR}"
mkdir -p "${RESULTS_DIR}/discovery"
mkdir -p "${RESULTS_DIR}/hotspots"
mkdir -p "${RESULTS_DIR}/final_baselines"
mkdir -p "${RESULTS_DIR}/optimizations"
mkdir -p "${RESULTS_DIR}/analysis"
mkdir -p "${REPORT_DIR}"

# Logging functions — write to both stderr and the log file
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}" >&2
}

log_info()  { log "INFO"  "$@"; }
log_warn()  { log "WARN"  "$@"; }
log_error() { log "ERROR" "$@"; }

log_info "Configuration loaded. Experiment root: ${EXPERIMENT_ROOT}"
