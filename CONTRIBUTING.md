# Contributing to open-agent-kit

Thank you for your interest in contributing to open-agent-kit! This guide covers the essentials for getting started.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/open-agent-kit.git
cd open-agent-kit
make setup           # Installs dependencies and creates oak-dev symlink
oak-dev init         # Initializes .oak/, installs hooks, starts CI daemon

# Verify everything works
make check           # Runs all CI checks
```

> **Note**: `make setup` only installs the package — it does not initialize the project.
> `oak-dev init` is required before `oak-dev team start` will work.

## Prerequisites

- Python 3.12 or 3.13 (3.14+ not yet supported — see [QUICKSTART.md](QUICKSTART.md))
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package manager)
- Git

> ⚠️ **Note**: The `make setup` command requires `uv` to be installed first. If you see errors, install uv via `pipx install uv` or the [official installer](https://docs.astral.sh/uv/getting-started/installation/).

## Development Workflow

### Available Commands

Run `make help` to see all available commands:

| Command | Description |
|---------|-------------|
| `make setup` | Install all dependencies |
| `make sync` | Re-sync dependencies after `git pull` |
| `make check` | Run all CI checks (format, typecheck, test) |
| `make test` | Run tests with coverage |
| `make test-fast` | Run tests in parallel without coverage (fastest) |
| `make format` | Auto-format code |
| `make lint` | Run linter |
| `make typecheck` | Run type checking |
| `make skill-build` | Regenerate skill reference files (required after schema changes) |
| `make skill-check` | Verify skill files are in sync — run by CI separately from `make check` |
| `make ui-build` | Rebuild UI static assets (required after changes to `daemon/ui/src/`) |
| `make ui-check` | Verify UI assets are in sync — run by CI separately from `make check` |

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes** following the [coding standards](oak/constitution.md)

3. **Run checks before committing**
   ```bash
   make check
   ```

   > **Schema changes**: If you modified the CI database schema, also run `make skill-build`
   > to regenerate `skills/codebase-intelligence/references/schema.md` — CI runs
   > `make skill-check` separately and will fail if the file is stale.
   >
   > **UI changes**: If you modified files under `daemon/ui/src/`, also run `make ui-build`
   > to rebuild the static assets — CI runs `make ui-check` separately.
   >
   > ⚠️ **Gotcha**: When adding a new database migration, you must also bump
   > `CI_ACTIVITY_SCHEMA_VERSION` in
   > [`src/open_agent_kit/features/team/constants/paths.py`](src/open_agent_kit/features/team/constants/paths.py).
   > If you forget, the database is left at an intermediate version and subsequent
   > migrations may silently fail on fresh clones.

4. **Commit with conventional messages**
   - `Add:` new features
   - `Fix:` bug fixes
   - `Update:` changes to existing features
   - `Docs:` documentation changes
   - `Refactor:` code refactoring

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## How to Contribute

**Bugs** — check for duplicates first, then open an issue with: a clear title, reproduction
steps, expected vs actual behavior, OS / Python / oak version, and any error output.

**Enhancements** — describe the feature, use cases, and why it would be valuable.

**Pull Requests** — all CI checks must pass (`make check`), include tests for new
functionality, and update documentation if needed. Use clean, descriptive commits.

## Project References

| Topic | Documentation |
|-------|---------------|
| Full documentation | [openagentkit.app](https://openagentkit.app/) |
| Coding standards | [Constitution](oak/constitution.md) |

## Questions?

- Check existing issues and discussions
- Open a new issue for questions
- See [QUICKSTART.md](QUICKSTART.md) for basic setup
- See [README.md](README.md) for project overview

Thank you for contributing!
