#!/bin/bash
# Phase 7: Optimization Runs on Top Hotspots
# Runs `joule run` on each top hotspot using the final baselines as baseline.
# CSV must contain absolute file paths (written by Phase 5).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/experiment_config.sh"

REPO="${1:-}"
HOTSPOTS_FILE="${2:-}"
BUDGET="${3:-${OPTIMIZATION_BUDGET}}"

if [ -z "${REPO}" ] || [ -z "${HOTSPOTS_FILE}" ]; then
    echo "Usage: $0 <repo> <hotspots_file> [budget]"
    echo "Example: $0 black ../results/final_baselines/black_top_hotspots.csv 10"
    exit 1
fi

if [ ! -f "${HOTSPOTS_FILE}" ]; then
    log_error "Hotspots file not found: ${HOTSPOTS_FILE}"
    exit 1
fi

data_lines=$(tail -n +2 "${HOTSPOTS_FILE}" | grep -c '[^[:space:]]' || true)
if [ "${data_lines}" -eq 0 ]; then
    log_error "Hotspots file has no data rows: ${HOTSPOTS_FILE}"
    log_error "Phase 5 must complete successfully before running Phase 7."
    exit 1
fi

log_info "=== Phase 7: Optimization for ${REPO} (budget=${BUDGET}, ${data_lines} targets) ==="

repo_path="${REPOS_DIR}/${REPO}"
output_dir="${RESULTS_DIR}/optimizations/${REPO}_optimizations"
mkdir -p "${output_dir}"

JOULE_BIN="${JOULE_SRC}/joule"

success_count=0
fail_count=0
skip_count=0

tmp_csv=$(mktemp)
tail -n +2 "${HOTSPOTS_FILE}" > "${tmp_csv}"

while IFS=',' read -r file_path function_name line total_runtime occurrence_count; do
    [ -z "${file_path}" ] && continue
    file_path="${file_path//\"/}"
    function_name="${function_name//\"/}"

    if [ ! -f "${file_path}" ]; then
        log_warn "File not found, skipping: ${file_path}"
        (( skip_count++ )) || true
        continue
    fi

    func_output_dir="${output_dir}/${function_name}"
    mkdir -p "${func_output_dir}"

    log_info "Optimizing ${function_name} (baseline_runtime=${total_runtime}s, budget=${BUDGET})"

    joule_log="${func_output_dir}/joule_optimize.log"

    if "${JOULE_BIN}" run \
            "${file_path}" \
            --function "${function_name}" \
            --budget "${BUDGET}" \
            --analysis \
            --output json \
            --no-dashboard \
            > "${joule_log}" 2>&1; then

        log_info "  ✓ optimization complete for ${function_name}"
        (( success_count++ )) || true

        # Deterministic artifact copy using run_id
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
            latest_run=$(ls -t "${repo_path}/.joule/runs" 2>/dev/null | head -1)
            if [ -n "${latest_run}" ]; then
                cp -r "${repo_path}/.joule/runs/${latest_run}/." "${func_output_dir}/" 2>/dev/null || true
                log_warn "  run_id not found; copied latest run ${latest_run}"
            fi
        fi
    else
        log_error "  ✗ optimization failed for ${function_name} — see ${joule_log}"
        (( fail_count++ )) || true
    fi

    sleep 2  # longer throttle — optimizations are resource-intensive
done < "${tmp_csv}"

rm -f "${tmp_csv}"

log_info "=== Phase 7 Complete for ${REPO}: ${success_count} ok, ${fail_count} failed, ${skip_count} skipped ==="
log_info "Optimization results: ${output_dir}"

# Phase 7 is allowed to have partial failures; just report.
if [ "${success_count}" -eq 0 ] && [ "${data_lines}" -gt 0 ]; then
    log_warn "No successful optimizations for ${REPO} — review logs in ${output_dir}"
fi
