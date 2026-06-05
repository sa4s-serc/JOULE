#!/bin/bash
# Phase 2: Discovery — runs `joule discover` on a single repository.
# Called once per repo by the orchestrator: 02_discover.sh <repo>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/experiment_config.sh"

# BUG FIX: accept repo as argument rather than looping internally,
# so the orchestrator controls iteration without running all repos 3× per call.
REPO="${1:-}"
if [ -z "${REPO}" ]; then
    log_error "Usage: $0 <repo>"
    log_error "Example: $0 black"
    exit 1
fi

log_info "=== Phase 2: Discovery for ${REPO} ==="

repo_path="${REPOS_DIR}/${REPO}"
output_file="${RESULTS_DIR}/discovery/${REPO}_discovery.json"
JOULE_BIN="${JOULE_SRC}/joule"

if [ ! -d "${repo_path}" ]; then
    log_error "Repository not found: ${repo_path}"
    exit 1
fi

if [ -f "${output_file}" ]; then
    log_info "Discovery already exists for ${REPO}, skipping"
    log_info "Delete to re-run: ${output_file}"
    exit 0
fi

log_info "Running JOULE discover on ${REPO}..."
if "${JOULE_BIN}" discover "${repo_path}" \
    --limit "${DISCOVERY_LIMIT:-150}" \
    --output json > "${output_file}" 2>&1; then
    count=$(python3 -c "import json; print(len(json.load(open('${output_file}'))))" 2>/dev/null || echo "?")
    log_info "Discovery complete for ${REPO}: ${count} candidate functions"
    log_info "Output: ${output_file}"
else
    log_error "Discovery failed for ${REPO}"
    rm -f "${output_file}"
    exit 1
fi
