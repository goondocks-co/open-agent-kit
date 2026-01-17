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

.PHONY: help venv setup setup-minimal install-global install-global-dev sync lock uninstall test test-fast test-parallel test-cov lint format format-check typecheck check clean build ci-dev ci-start ci-stop ci-restart

# Default target
help:
	@echo "open-agent-kit development commands"
	@echo ""
	@echo "Prerequisites: Python 3.13+, uv (https://docs.astral.sh/uv)"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup          Install ALL dependencies including CI feature (recommended)"
	@echo "    make setup-minimal  Install only core dev dependencies (no CI feature)"
	@echo "    make venv           Setup virtual environment and show activation command"
	@echo "    make install-global Install 'oak' globally via uv tool (for end-users)"
	@echo "    make sync           Sync dependencies with lockfile"
	@echo "    make lock           Update lockfile after changing pyproject.toml"
	@echo "    make uninstall      Remove dev environment and stale global installs"
	@echo ""
	@echo "  Testing:"
	@echo "    make test          Run all tests with coverage"
	@echo "    make test-fast     Run tests in parallel without coverage (fastest)"
	@echo "    make test-parallel Run tests in parallel with coverage"
	@echo "    make test-cov      Run tests and open coverage report"
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
	@echo ""
	@echo "  Codebase Intelligence (CI daemon):"
	@echo "    make ci-dev       Run daemon with hot reload (development)"
	@echo "    make ci-start     Start the daemon"
	@echo "    make ci-stop      Stop the daemon"
	@echo "    make ci-restart   Stop and start the daemon (picks up code changes)"

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
	uv sync --all-extras
	@echo "\nSetup complete! All features installed (including CI)."
	@echo "Run 'make check' to verify everything works."
	@echo "For development, activate venv: source .venv/bin/activate"
	@echo ""
	@echo "CI feature dev workflow:"
	@echo "  make ci-dev      Run daemon with hot reload (auto-restarts on code changes)"
	@echo "  make ci-restart  Manual restart after code changes"

setup-minimal:
	@command -v uv >/dev/null 2>&1 || { echo "Error: uv is not installed. Visit https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	uv sync --extra dev
	@echo "\nMinimal setup complete (no CI feature deps)."
	@echo "For full dev setup with CI feature: make setup"

install-global:
	@echo "Installing oak globally via uv tool..."
	@echo "(For development, use 'make setup' instead - changes are picked up automatically)"
	@echo "(CI feature dependencies will be installed when you enable the feature)"
	uv tool install --editable . --force
	@echo "\n'oak' is now available globally from any directory."

install-global-dev:
	@echo "Installing oak globally with all dev dependencies..."
	@echo "(For development, use 'make setup' instead - changes are picked up automatically)"
	uv tool install --editable . --force --with ".[codebase-intelligence,ci-parsers]"
	@echo "\n'oak' is now available globally with CI feature pre-installed."

sync:
	uv sync --all-extras

lock:
	uv lock
	@echo "Lockfile updated. Run 'make sync' to install."

uninstall:
	uv pip uninstall open-agent-kit 2>/dev/null || true
	uv tool uninstall open-agent-kit 2>/dev/null || true
	rm -rf .venv
	@# Clean up stale pip --user installations
	@rm -f ~/.local/bin/oak 2>/dev/null || true
	@echo "Dev environment and global installs removed."
	@echo "To reinstall: make setup && make install-tool"

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
	@echo "Stopping CI daemon..."
	@pkill -f "uvicorn.*codebase_intelligence" 2>/dev/null && echo "Daemon stopped." || echo "No daemon running."

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
