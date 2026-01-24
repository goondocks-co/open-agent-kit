# open-agent-kit Makefile
# Common development tasks for the project
#
# Prerequisites:
#   - Python 3.13 (3.14+ not yet supported due to dependency constraints)
#   - uv (https://docs.astral.sh/uv/getting-started/installation/)
#
# Quick start:
#   make setup    # Install dependencies
#   make check    # Run all checks

.PHONY: help venv setup setup-full sync lock uninstall test test-fast test-parallel test-cov lint format format-check typecheck check clean build ci-dev ci-start ci-stop ci-restart ui-build ui-check ui-dev ui-restart dogfood-reset tool-reinstall

# Default target
help:
	@echo "open-agent-kit development commands"
	@echo ""
	@echo "Prerequisites: Python 3.13, uv (https://docs.astral.sh/uv)"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup         Install minimal dev dependencies (recommended for development)"
	@echo "    make setup-full    Install all dependencies including optional features"
	@echo "    make venv          Setup virtual environment and show activation command"
	@echo "    make sync          Sync dependencies with lockfile"
	@echo "    make lock          Update lockfile after changing pyproject.toml"
	@echo "    make uninstall     Remove dev environment and clean build artifacts"
	@echo ""
	@echo "  Testing:"
	@echo "    make test          Run all tests with coverage"
	@echo "    make test-fast     Run tests in parallel without coverage (fastest)"
	@echo "    make test-parallel Run tests in parallel with coverage"
	@echo "    make test-cov      Run tests and open coverage report"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint          Run ruff linter"
	@echo "    make format        Format code with black and ruff --fix"
	@echo "    make format-check  Check formatting without changes (CI mode)"
	@echo "    make typecheck     Run mypy type checking"
	@echo "    make check         Run all CI checks (format-check, typecheck, test)"
	@echo ""
	@echo "  Build:"
	@echo "    make build         Build package"
	@echo "    make clean         Remove build artifacts and cache"
	@echo ""
	@echo "  Codebase Intelligence (CI daemon):"
	@echo "    make ci-dev        Run daemon with hot reload (development)"
	@echo "    make ci-start      Start the daemon"
	@echo "    make ci-stop       Stop the daemon"
	@echo "    make ci-restart    Stop and start the daemon (picks up code changes)"
	@echo ""
	@echo "  UI Development:"
	@echo "    make ui-build      Build UI static assets"
	@echo "    make ui-check      Verify UI assets are in sync (for CI)"
	@echo "    make ui-dev        Run UI development server with hot reload"
	@echo "    make ui-restart    Build UI and restart daemon"
	@echo ""
	@echo "  Dogfooding:"
	@echo "    make dogfood-reset Reset oak environment (reinstall with all features)"
	@echo ""
	@echo "  Global Tool:"
	@echo "    make tool-reinstall  Reinstall global oak CLI with all extras (uses Python 3.13)"

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
	@echo "\nMinimal setup complete! Core dev dependencies installed."
	@echo "Run 'make check' to verify everything works."
	@echo "For development, activate venv: source .venv/bin/activate"
	@echo ""
	@echo "To install optional features:"
	@echo "  make setup-full           Install all dependencies (for full-stack dev)"
	@echo "  oak init --enable-ci      Install CI feature via oak installer (tests installer)"

setup-full:
	@command -v uv >/dev/null 2>&1 || { echo "Error: uv is not installed. Visit https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	uv sync --all-extras
	@echo "\nFull setup complete! All features installed (including CI)."
	@echo "Run 'make check' to verify everything works."
	@echo "For development, activate venv: source .venv/bin/activate"
	@echo ""
	@echo "CI feature dev workflow:"
	@echo "  make ci-dev      Run daemon with hot reload (auto-restarts on code changes)"
	@echo "  make ci-restart  Manual restart after code changes"
	@echo "  make ui-restart  Build UI and restart daemon (for UI changes)"

sync:
	uv sync --all-extras
	@echo "All dependencies synced with lockfile."

lock:
	uv lock
	@echo "Lockfile updated. Run 'make sync' to install."

uninstall:
	uv pip uninstall open-agent-kit 2>/dev/null || true
	rm -rf .venv
	@# Clean up any stale installations
	@rm -f ~/.local/bin/oak 2>/dev/null || true
	@echo "Dev environment removed."
	@echo "To reinstall: make setup"

# Testing targets
test:
	uv run pytest tests/ -v

test-fast:
	uv run pytest tests/ -v --no-cov -n auto

test-parallel:
	uv run pytest tests/ -v -n auto

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

# Codebase Intelligence daemon targets
#
# Dev workflow for CI feature:
#   1. make ci-dev     - Run with hot reload (best for development)
#   2. make ci-restart - Manual restart after code changes
#
# Note: 'make ci-dev' uses uvicorn --reload which auto-restarts on file changes
# in src/. This is the recommended way to develop the CI feature.

ci-dev:
	@echo "Starting CI daemon with hot reload (Ctrl+C to stop)..."
	@echo "The daemon will auto-restart when you modify files in src/"
	@echo ""
	OAK_CI_PROJECT_ROOT=$(PWD) uv run uvicorn open_agent_kit.features.codebase_intelligence.daemon.server:create_app --factory --host 127.0.0.1 --port 37800 --reload --reload-dir src/

ci-start:
	uv run oak ci start

ci-stop:
	uv run oak ci stop

ci-restart: ci-stop
	@sleep 1
	@echo "Starting CI daemon..."
	uv run oak ci start

# UI Development targets
ui-build:
	cd src/open_agent_kit/features/codebase_intelligence/daemon/ui && npm install && npm run build

ui-check:
	$(MAKE) ui-build
	@if [ -n "$$(git status --porcelain src/open_agent_kit/features/codebase_intelligence/daemon/static)" ]; then \
		echo "Error: UI assets are out of sync. Please run 'make ui-build' and commit the changes."; \
		exit 1; \
	fi

ui-dev:
	cd src/open_agent_kit/features/codebase_intelligence/daemon/ui && npm run dev

# Combo target: build UI and restart daemon (for UI development workflow)
ui-restart: ui-build ci-restart
	@echo "UI rebuilt and daemon restarted."

# Dogfooding target - reset oak environment (preserves oak/ user content)
dogfood-reset:
	@echo "Resetting oak dogfooding environment..."
	-uv run oak ci stop 2>/dev/null || true
	-uv run oak remove --force 2>/dev/null || true
	uv sync --all-extras
	uv run oak init --agent claude --no-interactive
	uv run oak feature add codebase-intelligence
	uv run oak feature add rules-management
	uv run oak feature add strategic-planning
	@echo ""
	@echo "Dogfooding environment reset. Run 'make ci-dev' to start daemon with hot reload."

# Global tool installation
# Use this when you need to update the global `oak` CLI after code changes.
# This ensures Python 3.13 is used (3.14 lacks wheels for some dependencies).
tool-reinstall:
	@echo "Reinstalling global oak CLI tool..."
	uv tool install . --python 3.13 --with ".[codebase-intelligence]" --with ".[ci-parsers]" --reinstall
	@echo ""
	@echo "Global oak CLI reinstalled. Verify with: oak --version"
