---
title: Troubleshooting
description: Common issues and solutions for OAK.
---

## ModuleNotFoundError after upgrade

If you see `ModuleNotFoundError` for packages like `httpx` after upgrading:

```bash
# Reinstall to update all dependencies (requires Python 3.12 or 3.13)
pipx reinstall oak-ci

# Or with uv
uv tool install --force oak-ci --python python3.13
```

This can happen when new dependencies are added to the package but the global installation wasn't updated.

## Command not found: oak

**Using pipx or uv:**

```bash
# Ensure tools are in your PATH
# Add to ~/.bashrc, ~/.zshrc, or equivalent:
export PATH="$HOME/.local/bin:$PATH"

# Then reload your shell:
source ~/.bashrc  # or ~/.zshrc
```

**Using pip:**

```bash
# Check if pip's script directory is in PATH
python3 -m pip show oak-ci

# If installed with --user flag, add to PATH:
export PATH="$HOME/.local/bin:$PATH"
```

## Something feels broken

`oak init` is idempotent and safe to re-run. It's the first thing to try when something isn't working:

```bash
oak init          # Re-run initialization to repair setup
```

For CI-specific issues after an upgrade, `oak upgrade` followed by `oak ci sync` is the standard healing path:

```bash
oak upgrade       # Update templates and agent commands
oak ci sync       # Sync daemon, apply migrations, re-index if needed
```

## Changes not taking effect (editable install)

If you're developing OAK and changes aren't reflected:

**For Python code changes:** They should work immediately with editable mode.

**For dependency or entry point changes:**

```bash
make setup
```

## Python 3.14+ errors (chromadb / pydantic)

OAK requires **Python 3.12 or 3.13**. Python 3.14 is not yet supported due to dependency incompatibilities (notably chromadb and pydantic v1).

If your default `python3` points to 3.14 (common with Homebrew), reinstall with an explicit interpreter:

```bash
# Check your default version
python3 --version

# Reinstall with a supported version
pipx install oak-ci --python python3.13 --force

# Or with uv
uv tool install oak-ci --python python3.13 --force
```

If you don't have 3.13 installed:

```bash
# macOS
brew install python@3.13

# Linux (Debian/Ubuntu)
sudo apt install python3.13
```

## Permission denied errors

**Using pipx or uv:** Should work without sudo (installs to `~/.local`).

**Using pip:** Don't use sudo with pip — use the `--user` flag:

```bash
pip install --user oak-ci
```

## .oak directory not found

Run `oak init` first to initialize the project.

## AI agent commands not showing up

```bash
# Re-run init to install agent commands
oak init --agent claude
```

Agent commands are installed in their native directories (`.claude/commands/`, `.github/agents/`, etc.).

## Daemon won't start

Check if the daemon is already running:

```bash
oak ci status
```

If the port is in use or the daemon is in a bad state:

```bash
oak ci stop       # Stop any existing daemon
oak ci start      # Start fresh
```

## Uninstallation

```bash
# Using pipx
pipx uninstall oak-ci

# Using uv
uv tool uninstall oak-ci

# Using pip
pip uninstall oak-ci
```

This removes the CLI tool but does not delete project files created by `oak init`. To clean up a project, run `oak remove`.
