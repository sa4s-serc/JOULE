# HEDGE Makefile
# ===============

.PHONY: help setup install test clean examples benchmark docs lint format

# Default target
help:
	@echo "HEDGE - Hierarchical Evolutionary Darwin-Green Engine"
	@echo "====================================================="
	@echo ""
	@echo "Available targets:"
	@echo "  setup      - Run automated setup script"
	@echo "  install    - Install dependencies"
	@echo "  test       - Run test suite"
	@echo "  examples   - Run example optimizations"
	@echo "  benchmark  - Run performance benchmarks"
	@echo "  clean      - Clean temporary files and caches"
	@echo "  lint       - Run code linting"
	@echo "  format     - Format code with black"
	@echo "  docs       - Generate documentation"
	@echo ""
	@echo "Quick start:"
	@echo "  make setup && source .venv/bin/activate"
	@echo "  make examples"

# Setup and installation
setup:
	python scripts/setup.py

install:
	pip install -r requirements.txt

# Testing
test:
	python -m pytest tests/ -v

test-coverage:
	python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

# Examples and benchmarks
examples:
	python scripts/run_examples.py

benchmark:
	python hedge.py benchmark --quick

benchmark-full:
	python hedge.py benchmark --compare-levels

# Cleaning
clean:
	python scripts/clean.py --all

clean-cache:
	python scripts/clean.py --cache

clean-experiments:
	python scripts/clean.py --experiments --keep-recent 3

# Code quality
lint:
	@echo "Running flake8..."
	-flake8 src/ cli/ --max-line-length=100 --ignore=E203,W503
	@echo "Running mypy..."
	-mypy src/ --ignore-missing-imports

format:
	@echo "Formatting with black..."
	black src/ cli/ scripts/ --line-length=100
	@echo "Sorting imports with isort..."
	isort src/ cli/ scripts/

# Documentation
docs:
	@echo "Documentation is in docs/ directory"
	@echo "Main files:"
	@echo "  - docs/QUICKSTART.md"
	@echo "  - docs/FEATURES.md"
	@echo "  - docs/ARCHITECTURE.md"
	@echo "  - docs/CLI.md"

# Development helpers
dev-install:
	pip install -r requirements.txt
	pip install black flake8 mypy isort pytest-cov

check-config:
	python hedge.py config validate

init-project:
	python hedge.py project init example_project --template advanced

# CI/CD helpers
ci-test: test lint

ci-benchmark:
	python hedge.py benchmark --problems fibonacci,search --quick

# Docker support (if Dockerfile exists)
docker-build:
	@if [ -f Dockerfile ]; then \
		docker build -t hedge:latest .; \
	else \
		echo "Dockerfile not found"; \
	fi

docker-run:
	@if [ -f Dockerfile ]; then \
		docker run -it --rm -v $(PWD):/workspace hedge:latest; \
	else \
		echo "Dockerfile not found"; \
	fi