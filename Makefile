# open-agent-kit Makefile
# Common development tasks for the project
#
# Prerequisites:
#   - Python 3.13+
#   - uv (https://docs.astral.sh/uv/getting-started/installation/)
#
# Quick start:
#   make setup    # Install dependencies
#   make check    # Run all checks

.PHONY: help venv setup install install-dev sync lock uninstall test test-fast test-cov lint format format-check typecheck check clean build

# Default target
help:
	@echo "open-agent-kit development commands"
	@echo ""
	@echo "Prerequisites: Python 3.13+, uv (https://docs.astral.sh/uv)"
	@echo ""
	@echo "  Setup:"
	@echo "    make venv         Setup virtual environment and show activation command"
	@echo "    make setup        Install all dependencies (recommended first step)"
	@echo "    make sync         Sync dependencies with lockfile"
	@echo "    make lock         Update lockfile after changing pyproject.toml"
	@echo "    make uninstall    Remove dev environment (to test live package)"
	@echo ""
	@echo "  Testing:"
	@echo "    make test         Run all tests with coverage"
	@echo "    make test-fast    Run tests without coverage (faster)"
	@echo "    make test-cov     Run tests and open coverage report"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint         Run ruff linter"
	@echo "    make format       Format code with black and ruff --fix"
	@echo "    make format-check Check formatting without changes (CI mode)"
	@echo "    make typecheck    Run mypy type checking"
	@echo "    make check        Run all CI checks (format-check, typecheck, test)"
	@echo ""
	@echo "  Build:"
	@echo "    make build        Build package"
	@echo "    make clean        Remove build artifacts and cache"

# Setup targets
venv:
	@command -v uv >/dev/null 2>&1 || { echo "Error: uv is not installed. Visit https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		uv sync --extra dev; \
	else \
		echo "Virtual environment already exists."; \
	fi
	@echo "\nTo activate the virtual environment, run:"
	@echo "  source .venv/bin/activate"

setup:
	@command -v uv >/dev/null 2>&1 || { echo "Error: uv is not installed. Visit https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	uv sync --extra dev
	@echo "\nSetup complete! Run 'make check' to verify everything works."

install:
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev]"

sync:
	uv sync --extra dev

lock:
	uv lock
	@echo "Lockfile updated. Run 'make sync' to install."

uninstall:
	uv pip uninstall open-agent-kit 2>/dev/null || true
	rm -rf .venv
	@echo "Dev environment removed. To test the live package: uv tool install open-agent-kit"

# Testing targets
test:
	uv run pytest tests/ -v

test-fast:
	uv run pytest tests/ -v --no-cov

test-cov:
	uv run pytest tests/ -v
	@echo "\nOpening coverage report..."
	@open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || echo "Open htmlcov/index.html in your browser"

# Code quality targets
lint:
	uv run ruff check src/ tests/

format:
	uv run black src/ tests/
	uv run ruff check --fix src/ tests/

format-check:
	uv run black src/ tests/ --check --diff
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/open_agent_kit

# Combined check (mirrors CI pr-check.yml)
check: format-check typecheck test
	@echo "\nAll checks passed!"

# Build targets
build:
	uv build

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf src/*.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
