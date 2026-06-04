#!/bin/bash
# Phase 4: Hotspot Baseline Measurement
# Runs `joule baseline --hotspots` on each sampled function.
# The sample CSV must contain absolute file paths (written by Phase 3).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/experiment_config.sh"

REPO="${1:-}"
SAMPLE_FILE="${2:-}"

if [ -z "${REPO}" ] || [ -z "${SAMPLE_FILE}" ]; then
    echo "Usage: $0 <repo> <sample_file>"
    echo "Example: $0 black ../results/hotspots/black_sample_targets.csv"
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

success_count=0
fail_count=0
skip_count=0

# Read CSV — skip header, process each function
# BUG FIX: CSV now contains absolute paths from Phase 3; no path reconstruction needed.
# BUG FIX: use a temp file to avoid running the while loop in a subshell (pipe would
#           prevent exit-code propagation and variable updates).
tmp_csv=$(mktemp)
tail -n +2 "${SAMPLE_FILE}" > "${tmp_csv}"

while IFS=',' read -r file_path function_name qualname line_start score; do
    # Skip blank lines
    [ -z "${file_path}" ] && continue
    # Strip surrounding quotes (qualname may be quoted if it contains commas)
    file_path="${file_path//\"/}"
    function_name="${function_name//\"/}"

    if [ ! -f "${file_path}" ]; then
        log_warn "File not found, skipping: ${file_path}"
        (( skip_count++ )) || true
        continue
    fi

    func_output_dir="${output_dir}/${function_name}"
    mkdir -p "${func_output_dir}"

    log_info "Baselining ${function_name} (${file_path})"

    # Capture both stdout and stderr; redirect joule output to a dedicated log
    # so the experiment log stays clean.
    joule_log="${func_output_dir}/joule_baseline.log"

    if "${JOULE_BIN}" baseline \
            "${file_path}" \
            --function "${function_name}" \
            --hotspots \
            --hotspot-limit "${HOTSPOT_LIMIT}" \
            --output json \
            --no-dashboard \
            > "${joule_log}" 2>&1; then

        log_info "  ✓ baseline complete for ${function_name}"
        (( success_count++ )) || true

        # BUG FIX: copy run artifacts using the run_id embedded in the joule DB
        # rather than "latest timestamp" to avoid races under parallel execution.
        # We identify the run directory by parsing the run_id from the output log.
        run_id=$(python3 -c "
import json, sys
try:
    data = json.load(open('${joule_log}'))
    print(data.get('run_id', ''))
except Exception:
    pass
" 2>/dev/null || true)

        if [ -n "${run_id}" ] && [ -d "${repo_path}/.joule/runs/${run_id}" ]; then
            cp -r "${repo_path}/.joule/runs/${run_id}/." "${func_output_dir}/"
            log_info "  Artifacts copied from run ${run_id}"
        else
            # Fallback: copy the latest run but warn
            latest_run=$(ls -t "${repo_path}/.joule/runs" 2>/dev/null | head -1)
            if [ -n "${latest_run}" ]; then
                cp -r "${repo_path}/.joule/runs/${latest_run}/." "${func_output_dir}/" 2>/dev/null || true
                log_warn "  Could not determine run_id; copied latest run ${latest_run} (may be inaccurate under parallelism)"
            fi
        fi
    else
        log_error "  ✗ baseline failed for ${function_name} — see ${joule_log}"
        (( fail_count++ )) || true
    fi

    sleep 1  # brief throttle
done < "${tmp_csv}"

rm -f "${tmp_csv}"

log_info "=== Phase 4 Complete for ${REPO}: ${success_count} ok, ${fail_count} failed, ${skip_count} skipped ==="
log_info "Baseline results: ${output_dir}"

# Fail the phase if nothing succeeded (catches silent total failure)
if [ "${success_count}" -eq 0 ]; then
    log_error "FATAL: zero successful baselines for ${REPO}. Check logs in ${output_dir}."
    exit 1
fi
