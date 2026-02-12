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
#
# CLI architecture:
#   oak-dev  → symlink to .venv/bin/oak (editable, from uv sync)
#   oak      → uv tool install oak-ci (stable from PyPI, separate venv)
#   Both can coexist simultaneously.

.PHONY: help setup setup-full sync lock uninstall cli-stable cli-dev cli-dual cli-verify test test-fast test-parallel test-cov lint format format-check typecheck check clean build ci-dev ci-start ci-stop ci-restart ui-build ui-check ui-lint ui-dev ui-restart skill-build skill-check docs-dev docs-build docs-preview dogfood-reset

# Where uv/pipx put global binaries (respect XDG on Linux)
USER_BIN_DIR := $(or $(shell uv tool dir --bin 2>/dev/null),$(HOME)/.local/bin)

# Default target
help:
	@echo "open-agent-kit development commands"
	@echo ""
	@echo "Prerequisites: Python 3.13, uv (https://docs.astral.sh/uv)"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup         Install dependencies and editable repo CLI (oak-dev)"
	@echo "    make sync          Re-sync dependencies after git pull"
	@echo "    make lock          Update lockfile after changing pyproject.toml"
	@echo "    make uninstall     Remove dev environment and local editable CLI install"
	@echo "    make cli-stable    Install/reinstall stable oak CLI from PyPI (oak)"
	@echo "    make cli-dev       Install/reinstall editable repo CLI (oak-dev)"
	@echo "    make cli-dual      Install both stable oak and editable oak-dev"
	@echo "    make cli-verify    Show where oak/oak-dev resolve and tool state"
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
	@echo "    make ui-lint       Run ESLint on UI code"
	@echo "    make ui-dev        Run UI development server with hot reload"
	@echo "    make ui-restart    Build UI and restart daemon"
	@echo ""
	@echo "  Skills:"
	@echo "    make skill-build   Generate skill reference files from schema"
	@echo "    make skill-check   Verify skill files are in sync (for CI)"
	@echo ""
	@echo "  Documentation:"
	@echo "    make docs-dev      Run docs site with hot reload (development)"
	@echo "    make docs-build    Build docs site for production"
	@echo "    make docs-preview  Preview built docs site locally"
	@echo ""
	@echo "  Dogfooding:"
	@echo "    make dogfood-reset Reset oak environment (reinstall with all features)"

# Setup targets
setup:
	@command -v uv >/dev/null 2>&1 || { echo "Error: uv is not installed. Visit https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	uv sync --extra dev
	@# oak-dev = symlink to .venv/bin/oak (editable install from uv sync)
	ln -sf "$(CURDIR)/.venv/bin/oak" "$(USER_BIN_DIR)/oak-dev"
	@echo "\nSetup complete! All dependencies installed."
	@echo "Run 'make check' to verify everything works."
	@echo ""
	@echo "Repo-local dev CLI: use 'oak-dev' in this repository."
	@echo "Global stable CLI remains 'oak' for other repositories."
	@echo ""
	@echo "CI feature dev workflow:"
	@echo "  make ci-dev      Run daemon with hot reload (auto-restarts on code changes)"
	@echo "  make ci-restart  Manual restart after code changes"
	@echo "  make ui-restart  Build UI and restart daemon (for UI changes)"

# Alias for backwards compatibility
setup-full: setup

sync:
	uv sync --extra dev
	@# Refresh oak-dev symlink (in case .venv was recreated)
	ln -sf "$(CURDIR)/.venv/bin/oak" "$(USER_BIN_DIR)/oak-dev"
	@echo "Dependencies synced and oak-dev symlink refreshed."

lock:
	uv lock
	@echo "Lockfile updated. Run 'make sync' to install."

uninstall:
	rm -f "$(USER_BIN_DIR)/oak-dev"
	uv tool uninstall oak-ci 2>/dev/null || true
	rm -rf .venv
	@echo "Dev environment and CLI installs removed."
	@echo "To reinstall: make setup"

cli-stable:
	uv tool install oak-ci --python python3.13 --force
	@echo "Stable CLI installed as 'oak'."

cli-dev: sync
	@echo "Editable CLI installed as 'oak-dev'."

cli-dual: cli-stable cli-dev
	@echo "Dual install complete: oak (stable from PyPI), oak-dev (editable from .venv)."

cli-verify:
	@echo "Command resolution:"
	@which -a oak oak-dev 2>/dev/null || true
	@echo ""
	@echo "oak-dev target:"
	@readlink "$(USER_BIN_DIR)/oak-dev" 2>/dev/null || echo "  (not installed)"
	@echo ""
	@echo "uv tools:"
	@uv tool list 2>/dev/null || true

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

ui-lint:
	cd src/open_agent_kit/features/codebase_intelligence/daemon/ui && npm run lint

ui-dev:
	cd src/open_agent_kit/features/codebase_intelligence/daemon/ui && npm run dev

# Combo target: build UI and restart daemon (for UI development workflow)
ui-restart: ui-build ci-restart
	@echo "UI rebuilt and daemon restarted."

# Skill asset generation targets
#
# Some skills include generated reference files (e.g., database schema docs).
# Generators are auto-discovered: features/*/skills/*/generate_*.py
# Pattern mirrors ui-build/ui-check for frontend assets.

skill-build:
	uv run python scripts/build_skill_assets.py

skill-check:
	uv run python scripts/build_skill_assets.py --check

# Documentation site targets
docs-dev:
	cd docs && npm install && npm run dev

docs-build:
	cd docs && npm ci && npm run build

docs-preview:
	cd docs && npm install && npm run preview

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
