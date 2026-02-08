# Contributing to open-agent-kit

Thank you for your interest in contributing to open-agent-kit! This guide covers the essentials for getting started.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/open-agent-kit.git
cd open-agent-kit
make setup      # Installs dependencies with uv

# Verify everything works
make check      # Runs all CI checks
```

## Prerequisites

- Python 3.12+ (3.13 recommended for development)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package manager)
- Git

> ⚠️ **Note**: The `make setup` command requires `uv` to be installed first. If you see errors, install uv via `pipx install uv` or the [official installer](https://docs.astral.sh/uv/getting-started/installation/).

## Development Workflow

### Available Commands

Run `make help` to see all available commands:

| Command | Description |
|---------|-------------|
| `make setup` | Install all dependencies |
| `make check` | Run all CI checks (format, typecheck, test) |
| `make test` | Run tests with coverage |
| `make test-fast` | Run tests without coverage |
| `make format` | Auto-format code |
| `make lint` | Run linter |
| `make typecheck` | Run type checking |

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

### Reporting Bugs

Before creating bug reports, check the issue tracker for duplicates. Include:

- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python version, oak version)
- Error messages or logs

### Suggesting Enhancements

Provide:

- Clear, descriptive title
- Detailed description of the enhancement
- Use cases and examples
- Why it would be useful

### Pull Request Requirements

- All CI checks pass (`make check`)
- Tests added for new functionality
- Documentation updated if needed
- Clean, descriptive commits

## Project References

| Topic | Documentation |
|-------|---------------|
| Architecture & patterns | [Architecture](docs/dev/architecture.md) |
| Coding standards | [Constitution](oak/constitution.md) |

## Questions?

- Check existing issues and discussions
- Open a new issue for questions
- See [QUICKSTART.md](QUICKSTART.md) for basic setup
- See [README.md](README.md) for project overview

Thank you for contributing!
