#!/bin/bash
# Phase 4: Hotspot Baseline Measurement
# Runs `joule baseline --hotspots` on each pre-flight-approved function in parallel.
# The input CSV must contain absolute file paths (written by Phase 3.5).
#
# Parallelism: up to MAX_PARALLEL_BASELINES concurrent workers via xargs -P.
# Counters (success/fail/skip) are tracked through a shared temp directory so
# they survive xargs subshell scope.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/experiment_config.sh"

REPO="${1:-}"
SAMPLE_FILE="${2:-}"

if [ -z "${REPO}" ] || [ -z "${SAMPLE_FILE}" ]; then
    echo "Usage: $0 <repo> <sample_file>"
    echo "Example: $0 black ../results/hotspots/black_preflight.csv"
    exit 1
fi

if [ ! -f "${SAMPLE_FILE}" ]; then
    log_error "Sample file not found: ${SAMPLE_FILE}"
    exit 1
fi

log_info "=== Phase 4: Hotspot Baseline for ${REPO} ==="

repo_path="${REPOS_DIR}/${REPO}"
output_dir="${RESULTS_DIR}/hotspots/${REPO}_sample_baselines"
mkdir -p "${output_dir}"

JOULE_BIN="${JOULE_SRC}/joule"

# Shared counter directory — each worker atomically creates a file per outcome.
counter_dir=$(mktemp -d)
trap 'rm -rf "${counter_dir}"' EXIT

# ── Worker function ───────────────────────────────────────────────────────────
# Called by xargs -P; receives a single CSV row as one argument (TAB-separated).
# We export all variables the worker needs so bash -c subshells can access them.
export JOULE_BIN output_dir repo_path HOTSPOT_LIMIT counter_dir

baseline_worker() {
    local row="$1"
    # Parse TAB-separated fields produced from the CSV read below
    local file_path function_name
    file_path="$(echo "${row}" | cut -f1)"
    function_name="$(echo "${row}" | cut -f2)"

    # Strip surrounding quotes (qualname may be quoted if it contains commas)
    file_path="${file_path//\"/}"
    function_name="${function_name//\"/}"

    [ -z "${file_path}" ] && return

    if [ ! -f "${file_path}" ]; then
        echo "[WARN] File not found, skipping: ${file_path}" >&2
        touch "${counter_dir}/skip_$$_${RANDOM}"
        return
    fi

    local func_output_dir="${output_dir}/${function_name}"
    mkdir -p "${func_output_dir}"

    local joule_log="${func_output_dir}/joule_baseline.log"

    if "${JOULE_BIN}" baseline \
            "${file_path}" \
            --function "${function_name}" \
            --hotspots \
            --hotspot-limit "${HOTSPOT_LIMIT}" \
            --output json \
            --no-dashboard \
            > "${joule_log}" 2>&1; then

        echo "[INFO] ✓ baseline complete for ${function_name}" >&2
        touch "${counter_dir}/success_$$_${RANDOM}"

        # Copy run artifacts using run_id embedded in the JSON output
        local run_id
        run_id=$(python3 -c "
import json
try:
    data = json.load(open('${joule_log}'))
    print(data.get('run_id', ''))
except Exception:
    pass
" 2>/dev/null || true)

        if [ -n "${run_id}" ] && [ -d "${repo_path}/.joule/runs/${run_id}" ]; then
            cp -r "${repo_path}/.joule/runs/${run_id}/." "${func_output_dir}/"
        else
            # Fallback: copy the most recently modified run directory
            local latest_run
            latest_run=$(ls -t "${repo_path}/.joule/runs" 2>/dev/null | head -1)
            if [ -n "${latest_run}" ]; then
                cp -r "${repo_path}/.joule/runs/${latest_run}/." "${func_output_dir}/" 2>/dev/null || true
                echo "[WARN] run_id not found; copied latest run ${latest_run} (may be inaccurate)" >&2
            fi
        fi
    else
        echo "[ERROR] ✗ baseline failed for ${function_name} — see ${joule_log}" >&2
        touch "${counter_dir}/fail_$$_${RANDOM}"
    fi
}

export -f baseline_worker

# ── Build worker input: TAB-separated file_path<TAB>function_name per line ───
tmp_input=$(mktemp)
trap 'rm -f "${tmp_input}"; rm -rf "${counter_dir}"' EXIT

tail -n +2 "${SAMPLE_FILE}" | while IFS=',' read -r file_path function_name rest; do
    [ -z "${file_path}" ] && continue
    printf '%s\t%s\n' "${file_path}" "${function_name}"
done > "${tmp_input}"

row_count=$(wc -l < "${tmp_input}" | tr -d ' ')
log_info "Processing ${row_count} functions with up to ${MAX_PARALLEL_BASELINES} parallel workers"

# ── Run in parallel ───────────────────────────────────────────────────────────
if [ "${row_count}" -gt 0 ]; then
    xargs -P "${MAX_PARALLEL_BASELINES}" -I '{}' bash -c 'baseline_worker "$@"' _ '{}' \
        < "${tmp_input}" || true
fi

# ── Tally counters ────────────────────────────────────────────────────────────
success_count=$(find "${counter_dir}" -name 'success_*' 2>/dev/null | wc -l | tr -d ' ')
fail_count=$(find "${counter_dir}" -name 'fail_*' 2>/dev/null | wc -l | tr -d ' ')
skip_count=$(find "${counter_dir}" -name 'skip_*' 2>/dev/null | wc -l | tr -d ' ')

log_info "=== Phase 4 Complete for ${REPO}: ${success_count} ok, ${fail_count} failed, ${skip_count} skipped ==="
log_info "Baseline results: ${output_dir}"

# Fail the phase if nothing succeeded (catches silent total failure)
if [ "${success_count}" -eq 0 ] && [ "${row_count}" -gt 0 ]; then
    log_error "FATAL: zero successful baselines for ${REPO}. Check logs in ${output_dir}."
    exit 1
fi
