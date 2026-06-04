#!/bin/bash
# Phase 9: Report Generation
# Compiles the final experiment report from all phase outputs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/experiment_config.sh"

log_info "=== Phase 9: Report Generation ==="

REPORT_FILE="${REPORT_DIR}/experiment_report.md"
ANALYSIS_FILE="${RESULTS_DIR}/analysis/aggregated_results.json"

# ── Header ────────────────────────────────────────────────────────────────────
cat > "${REPORT_FILE}" << EOF
# JOULE Large Repository Experiment Report

**Generated:** $(date '+%Y-%m-%d %H:%M:%S')
**Experiment Root:** ${EXPERIMENT_ROOT}
**JOULE Source:** ${JOULE_SRC}

## Experiment Configuration

| Parameter | Value |
|-----------|-------|
| Profile | ${JOULE_PROFILE} |
| Energy Backend | ${JOULE_BACKEND} |
| Baseline Repetitions | ${BASELINE_REPETITIONS} |
| Optimization Budget | ${OPTIMIZATION_BUDGET} |
| Workload Discovery Limit | ${WORKLOAD_DISCOVERY_LIMIT} |
| Hotspot Limit | ${HOTSPOT_LIMIT} |
| Improvement Threshold | ${FINAL_IMPROVEMENT_MIN} |
| Memory Regression Limit | ${MEMORY_REGRESSION_LIMIT} |
| Sample Size (Phase 3) | ${SAMPLE_SIZE} |
| Top Hotspots Limit (Phase 5) | ${TOP_HOTSPOTS_LIMIT} |

### Energy Backend Note
EOF

if [ "${JOULE_BACKEND}" = "rapl" ]; then
    echo "Energy measurements use the **RAPL** hardware backend — results reflect real CPU energy consumption." >> "${REPORT_FILE}"
else
    echo "Energy measurements use the **mock** backend — energy values are synthetic. Set \`JOULE_BACKEND=rapl\` and re-run for real energy data." >> "${REPORT_FILE}"
fi

# ── Repository info ───────────────────────────────────────────────────────────
cat >> "${REPORT_FILE}" << EOF

### Target Repositories

| Repo | Branch | Commit | Path |
|------|--------|--------|------|
EOF

for repo in ${REPOS}; do
    repo_path="${REPOS_DIR}/${repo}"
    if [ -d "${repo_path}" ]; then
        commit=$(git -C "${repo_path}" rev-parse --short HEAD 2>/dev/null || echo "unknown")
        branch=$(git -C "${repo_path}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        echo "| ${repo} | ${branch} | ${commit} | ${repo_path} |" >> "${REPORT_FILE}"
    else
        echo "| ${repo} | — | — | directory not found |" >> "${REPORT_FILE}"
    fi
done

# ── Phase 2: Discovery ────────────────────────────────────────────────────────
cat >> "${REPORT_FILE}" << 'EOF'

## Phase 2: Discovery Results

| Repo | Candidate Functions |
|------|---------------------|
EOF

for repo in ${REPOS}; do
    discovery_file="${RESULTS_DIR}/discovery/${repo}_discovery.json"
    if [ -f "${discovery_file}" ]; then
        count=$(python3 -c "import json; print(len(json.load(open('${discovery_file}'))))" 2>/dev/null || echo "0")
        echo "| ${repo} | ${count} |" >> "${REPORT_FILE}"
    else
        echo "| ${repo} | not run |" >> "${REPORT_FILE}"
    fi
done

# ── Phase 3/4: Hotspot sampling ───────────────────────────────────────────────
cat >> "${REPORT_FILE}" << 'EOF'

## Phase 3/4: Hotspot Baseline Results

| Repo | Functions Sampled | Baselines Succeeded |
|------|------------------|---------------------|
EOF

for repo in ${REPOS}; do
    sample_file="${RESULTS_DIR}/hotspots/${repo}_sample_targets.csv"
    baseline_dir="${RESULTS_DIR}/hotspots/${repo}_sample_baselines"
    if [ -f "${sample_file}" ]; then
        sampled=$(tail -n +2 "${sample_file}" | grep -c '[^[:space:]]' || echo "0")
    else
        sampled="not run"
    fi
    if [ -d "${baseline_dir}" ]; then
        succeeded=$(find "${baseline_dir}" -name "hotspots.json" | wc -l)
    else
        succeeded="0"
    fi
    echo "| ${repo} | ${sampled} | ${succeeded} |" >> "${REPORT_FILE}"
done

# ── Phase 5: Top hotspots ─────────────────────────────────────────────────────
cat >> "${REPORT_FILE}" << 'EOF'

## Phase 5: Top Hotspots Identified

EOF

for repo in ${REPOS}; do
    hotspots_file="${RESULTS_DIR}/final_baselines/${repo}_top_hotspots.csv"
    echo "### ${repo}" >> "${REPORT_FILE}"
    if [ -f "${hotspots_file}" ]; then
        count=$(tail -n +2 "${hotspots_file}" | grep -c '[^[:space:]]' || echo "0")
        echo "" >> "${REPORT_FILE}"
        echo "${count} top hotspots identified." >> "${REPORT_FILE}"
        echo "" >> "${REPORT_FILE}"
        count="${count// /}"  # strip whitespace from wc output
        if [ "${count}" -gt 0 ] 2>/dev/null; then
            echo "| Function | File | Runtime (s) | Occurrences |" >> "${REPORT_FILE}"
            echo "|----------|------|-------------|-------------|" >> "${REPORT_FILE}"
            tail -n +2 "${hotspots_file}" | head -5 | while IFS=',' read -r file_path function_name line total_runtime occurrence_count; do
                file_name=$(basename "${file_path}")
                echo "| ${function_name} | ${file_name} | ${total_runtime} | ${occurrence_count} |" >> "${REPORT_FILE}"
            done
        fi
    else
        echo "" >> "${REPORT_FILE}"
        echo "Not run." >> "${REPORT_FILE}"
    fi
    echo "" >> "${REPORT_FILE}"
done

# ── Phase 7: Optimization ─────────────────────────────────────────────────────
cat >> "${REPORT_FILE}" << 'EOF'

## Phase 7: Optimization Results

| Repo | Total Runs | Successful | Failed |
|------|-----------|------------|--------|
EOF

for repo in ${REPOS}; do
    opt_dir="${RESULTS_DIR}/optimizations/${repo}_optimizations"
    if [ -d "${opt_dir}" ]; then
        total=$(find "${opt_dir}" -maxdepth 1 -mindepth 1 -type d | wc -l)
        successful=$(find "${opt_dir}" -name "run_summary.json" | wc -l)
        failed=$(( total - successful ))
        echo "| ${repo} | ${total} | ${successful} | ${failed} |" >> "${REPORT_FILE}"
    else
        echo "| ${repo} | not run | — | — |" >> "${REPORT_FILE}"
    fi
done

# ── Phase 8: Aggregated analysis ──────────────────────────────────────────────
cat >> "${REPORT_FILE}" << 'EOF'

## Phase 8: Aggregated Analysis

EOF

if [ -f "${ANALYSIS_FILE}" ]; then
    # BUG FIX: Python block is a separate script file to avoid heredoc quoting
    # issues and ensure correct indentation throughout.
    python3 - "${ANALYSIS_FILE}" "${REPORT_FILE}" << 'PYEOF'
import json, sys
from pathlib import Path

analysis_path = sys.argv[1]
report_path = sys.argv[2]

with open(analysis_path) as f:
    data = json.load(f)

summary = data.get("summary", {})
lines = []
lines.append("### Summary\n")
lines.append(f"| Metric | Value |")
lines.append(f"|--------|-------|")
lines.append(f"| Total repos | {summary.get('total_repos', 0)} |")
lines.append(f"| Total optimization runs | {summary.get('total_runs', 0)} |")
lines.append(f"| Successful | {summary.get('total_successful', 0)} |")
lines.append(f"| Failed | {summary.get('total_failed', 0)} |")
lines.append(f"| Skipped | {summary.get('total_skipped', 0)} |")
rate = summary.get('overall_success_rate', 0)
lines.append(f"| Overall success rate | {rate:.1%} |")
lines.append("")

lines.append("### Per-Repository Details\n")
# BUG FIX: per-repo block is properly inside the loop
for repo_result in data.get("repos", []):
    repo_name = repo_result.get("repo", "unknown")
    lines.append(f"#### {repo_name}\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total runs | {repo_result.get('total_runs', 0)} |")
    lines.append(f"| Successful | {repo_result.get('successful_optimizations', 0)} |")
    lines.append(f"| Failed | {repo_result.get('failed_optimizations', 0)} |")
    if repo_result.get("successful_optimizations", 0) > 0:
        lines.append(f"| Avg energy improvement | {repo_result.get('avg_energy_improvement', 0):.2%} |")
        lines.append(f"| Avg latency improvement | {repo_result.get('avg_latency_improvement', 0):.2%} |")
        lines.append(f"| Avg memory improvement | {repo_result.get('avg_memory_improvement', 0):.2%} |")
    lines.append("")

    op_eff = repo_result.get("operator_effectiveness", {})
    if op_eff:
        lines.append("**Top operators:**\n")
        for op, count in sorted(op_eff.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"- {op}: {count} uses")
        lines.append("")

    fail_reasons = repo_result.get("common_failure_reasons", {})
    if fail_reasons:
        lines.append("**Failure reasons:**\n")
        for reason, count in sorted(fail_reasons.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {reason}: {count}")
        lines.append("")

with open(report_path, "a") as f:
    f.write("\n".join(lines) + "\n")
PYEOF
else
    echo "Analysis file not found. Run Phase 8 first." >> "${REPORT_FILE}"
fi

# ── Artifact summary ──────────────────────────────────────────────────────────
cat >> "${REPORT_FILE}" << EOF

## Artifacts

\`\`\`
${EXPERIMENT_ROOT}/
├── repos/         — target repositories
├── results/
│   ├── discovery/ — Phase 2 discovery JSON per repo
│   ├── hotspots/  — Phase 3/4 sample CSVs and baseline artifacts
│   ├── final_baselines/ — Phase 5/6 top hotspot CSVs and baselines
│   ├── optimizations/   — Phase 7 optimization artifacts
│   └── analysis/  — Phase 8 aggregated_results.json
└── report/        — this report
\`\`\`

---
*Report end*
EOF

log_info "Report written to: ${REPORT_FILE}"
log_info "=== Phase 9 Complete ==="
