#!/bin/bash
# Phase 1: Repository Setup and Environment Preparation
# Sets up virtual environments, installs JOULE, and writes JOULE config
# without clobbering existing repo pyproject.toml content.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/experiment_config.sh"

log_info "=== Phase 1: Repository Setup and Environment Preparation ==="

if [ -z "${JOULE_SRC}" ] || [ ! -d "${JOULE_SRC}" ]; then
    log_error "JOULE source directory not found: '${JOULE_SRC}'"
    log_error "Set JOULE_SRC to the hedge directory and re-run."
    exit 1
fi

# ── Install JOULE in development mode ────────────────────────────────────────
log_info "Installing JOULE in development mode from ${JOULE_SRC}..."
(
    cd "${JOULE_SRC}"
    if [ ! -d ".venv" ]; then
        log_info "Creating JOULE virtual environment..."
        python3 -m venv .venv
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    log_info "Installing JOULE dependencies..."
    make install-dev
)
log_info "JOULE installation complete"

JOULE_BIN="${JOULE_SRC}/joule"

# ── Setup each repository ─────────────────────────────────────────────────────
for repo in ${REPOS}; do
    log_info "=== Setting up ${repo} ==="
    repo_path="${REPOS_DIR}/${repo}"

    if [ ! -d "${repo_path}" ]; then
        log_error "Repository directory not found: ${repo_path}"
        log_error "Clone it first: git clone <url> ${repo_path}"
        exit 1
    fi

    # Create virtual environment if it doesn't exist
    venv_path="${repo_path}/.venv"
    if [ ! -d "${venv_path}" ]; then
        log_info "Creating virtual environment for ${repo}..."
        (
            cd "${repo_path}"
            python3 -m venv .venv
            # shellcheck disable=SC1091
            source .venv/bin/activate
            log_info "Installing ${repo} dependencies..."
            if [ -f "pyproject.toml" ]; then
                pip install -e ".[dev]" 2>/dev/null || pip install -e "."
            elif [ -f "setup.py" ]; then
                pip install -e ".[dev]" 2>/dev/null || pip install -e "."
            elif [ -f "requirements.txt" ]; then
                pip install -r requirements.txt
            else
                log_warn "No standard dependency file found for ${repo}, skipping install"
            fi
        )
    else
        log_info "Virtual environment already exists for ${repo}, skipping install"
    fi

    # ── Write JOULE config into pyproject.toml safely ────────────────────────
    # BUG FIX: Never overwrite the whole file — only add/replace [tool.joule].
    # We keep the repo's existing content intact by stripping any old [tool.joule]
    # block and appending the correct one.
    log_info "Writing [tool.joule] configuration for ${repo}..."

    pyproject="${repo_path}/pyproject.toml"

    # Determine the backend to embed (respect JOULE_BACKEND env var)
    embed_backend="${JOULE_BACKEND}"

    joule_block="[tool.joule]
profile = \"${JOULE_PROFILE}\"
artifact_dir = \".joule\"
default_backend = \"${embed_backend}\"
baseline_repetitions = ${BASELINE_REPETITIONS}
optimization_budget = ${OPTIMIZATION_BUDGET}
workload_discovery_limit = ${WORKLOAD_DISCOVERY_LIMIT}
hotspot_limit = ${HOTSPOT_LIMIT}
final_improvement_min = ${FINAL_IMPROVEMENT_MIN}
memory_regression_limit = ${MEMORY_REGRESSION_LIMIT}
search_branching_factor = 3
search_operator_beam_width = 3
search_convergence_patience = 6
search_composition_enabled = true
search_composition_width = 2
search_composition_max_hops = 2"

    if [ -f "${pyproject}" ]; then
        # Strip existing [tool.joule] block (from the header to the next [section] or EOF)
        python3 - "${pyproject}" "${joule_block}" <<'PYSTRIP'
import sys, re

pyproject_path = sys.argv[1]
new_block = sys.argv[2]

with open(pyproject_path) as f:
    content = f.read()

# Remove any existing [tool.joule] section
# Matches from [tool.joule] up to (but not including) the next top-level [section] or EOF
content = re.sub(
    r'\[tool\.joule\][^\[]*',
    '',
    content,
    flags=re.DOTALL
).rstrip()

content = content + '\n\n' + new_block + '\n'

with open(pyproject_path, 'w') as f:
    f.write(content)
PYSTRIP
    else
        # No pyproject.toml at all — create a minimal one
        printf '%s\n' "${joule_block}" > "${pyproject}"
    fi

    # ── Verify JOULE doctor ───────────────────────────────────────────────────
    log_info "Running JOULE doctor on ${repo}..."
    if "${JOULE_BIN}" doctor "${repo_path}"; then
        log_info "JOULE doctor passed for ${repo}"
    else
        log_error "JOULE doctor failed for ${repo} — check output above"
        exit 1
    fi

    log_info "${repo} setup complete"
done

log_info "=== Phase 1 Complete ==="
log_info "All repositories configured and ready for JOULE optimization"
