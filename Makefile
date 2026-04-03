.DEFAULT_GOAL := help

PYTHON ?= python3
VENV_PYTHON := $(CURDIR)/.venv/bin/python

ifeq ($(wildcard $(VENV_PYTHON)),)
PYTHON_BIN := $(PYTHON)
else
PYTHON_BIN := $(VENV_PYTHON)
endif

SRC_DIR := src
TEST_DIR := tests
ARGS ?=
PIP := $(PYTHON_BIN) -m pip

.PHONY: help install-dev run smoke-example test typecheck check clean clean-artifacts shell

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install-dev: ## Create or reuse .venv and install editable dev dependencies
	python3 -m venv .venv
	$(CURDIR)/.venv/bin/python -m pip install --upgrade pip
	$(CURDIR)/.venv/bin/python -m pip install -e .[dev]

run: ## Run the CLI entrypoint (use ARGS='--help' for flags)
	./joule $(ARGS)

smoke-example: ## Run an end-to-end smoke check against example/mock_repo
	$(PYTHON_BIN) scripts/smoke_example.py

test: ## Run the test suite (use ARGS='-q' for extra pytest flags)
	$(PYTHON_BIN) -m pytest $(ARGS)

typecheck: ## Run mypy over src/ and tests/
	$(PYTHON_BIN) -m mypy $(SRC_DIR) $(TEST_DIR)

check: ## Run the fast verification suite
	$(PYTHON_BIN) -m compileall $(SRC_DIR) $(TEST_DIR)
	$(MAKE) --no-print-directory test ARGS="$(ARGS)"

shell: ## Open a Python REPL in the project environment
	$(PYTHON_BIN)

clean: ## Remove Python caches and build outputs
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find $(SRC_DIR) $(TEST_DIR) -type d -name '__pycache__' -prune -exec rm -rf {} +
	find $(SRC_DIR) $(TEST_DIR) -type f -name '*.pyc' -delete

clean-artifacts: ## Remove Joule runtime artifacts
	rm -rf .joule .joule.lock
