---
title: Troubleshooting
description: Common issues and solutions for OAK.
---

## ModuleNotFoundError after upgrade

If you see `ModuleNotFoundError` for packages like `httpx` after upgrading:

```bash
# Reinstall to update all dependencies
pipx reinstall oak-ci

# Or with uv
uv tool install --force oak-ci
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

## Changes not taking effect (editable install)

If you're developing OAK and changes aren't reflected:

**For Python code changes:** They should work immediately with editable mode.

**For dependency or entry point changes:**

```bash
make setup
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
# Add an agent to existing installation
oak init --agent claude
```

Agent commands are installed in their native directories (`.claude/commands/`, `.github/agents/`, etc.).

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
