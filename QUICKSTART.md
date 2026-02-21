# open-agent-kit Quick Start Guide

Get started with open-agent-kit in under 5 minutes.

## Installation

### Homebrew (macOS — Recommended)

Homebrew handles Python version pinning automatically — no need to specify `--python`.

```bash
brew install goondocks-co/oak/oak-ci
```

### Install Script (macOS / Linux)

The install script detects your environment and handles everything automatically.

```bash
curl -fsSL https://raw.githubusercontent.com/goondocks-co/open-agent-kit/main/install.sh | sh
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/goondocks-co/open-agent-kit/main/install.ps1 | iex
```

### Alternative: Using pipx

> **Requires Python 3.12 or 3.13.** If your default `python3` is a different version (e.g. 3.14 via Homebrew), specify the interpreter explicitly with `--python`.

```bash
pipx install oak-ci --python python3.13
```

### Alternative: Using uv

> **Requires Python 3.12 or 3.13.** If your default Python is a different version, specify it with `--python`.

```bash
uv tool install oak-ci --python python3.13
```

### Alternative: Using pip

> **Requires Python 3.12 or 3.13.**

```bash
pip install oak-ci
```

**Verify installation:**

```bash
oak --version
```

## Step 1: Initialize Your Project

Navigate to your project directory and run:

```bash
oak init
```

This will:

1. Prompt you to select one or more AI agents (Claude, Copilot, Codex, Cursor, Gemini, Windsurf)
2. Prompt you to select which languages to support (Python, JavaScript, TypeScript)
3. Installs agent skills and mcp tools for your selected agents

## Step 2: Create Your Constitution

A **constitution** formalizes your project's engineering standards, architecture patterns, and team conventions. This is the foundation for all other oak workflows.

### Why Create a Constitution First?

- **Guides all AI agents** - Every agent references the constitution for context
- **Codifies team conventions** - Makes implicit standards explicit

### Creating Your Constitution

Use your AI agent's command:

```text
use the project governance skill to create my project's constitution
```

The AI will:

1. **Check for existing agent instructions** and use them as context
2. **Analyze your codebase** for patterns (testing, linting, CI/CD, etc.)
3. **Create** `oak/constitution.md` with comprehensive standards
4. **Update agent instruction files** with constitution references (additively)

### For Teams With Existing Agent Instructions

If your team already has agent instruction files (like `.github/copilot-instructions.md`), open-agent-kit will:

- **Preserve your existing content** - Never overwrites
- **Use it as context** - Incorporates your conventions into the constitution
- **Append references** - Links existing files to the new constitution
- **Create backups** - Saves `.backup` files before any changes

### After Creating Your Constitution

```bash
# View the constitution
cat oak/constitution.md
```

## Step 3: Start Codebase Intelligence (Optional)

The CI daemon provides semantic code search, session history, and project memories for your AI agents.

```bash
# Start the daemon with browser UI
oak ci start --open
```

This gives your agents access to:
- **Semantic search** across code and memories
- **Session history** to recall past decisions
- **MCP server** for direct tool access

## Troubleshooting

### Python 3.14+ errors

OAK requires **Python 3.12 or 3.13**. If your default `python3` points to 3.14 (common with Homebrew), the simplest fix is to use the Homebrew formula (which pins Python 3.13 automatically):

```bash
brew install goondocks-co/oak/oak-ci
```

Or reinstall with an explicit interpreter:

```bash
pipx install oak-ci --python python3.13 --force
```

### oak command not found

```bash
# Check if installed
which oak

# Reinstall via Homebrew (macOS)
brew reinstall oak-ci

# Or reinstall via the install script (macOS / Linux)
curl -fsSL https://raw.githubusercontent.com/goondocks-co/open-agent-kit/main/install.sh | sh

# Or reinstall via pipx
pipx install oak-ci --python python3.13
```

### .oak directory not found

Run `oak init` first to initialize the project.

### AI agent commands not showing up

```bash
# Add an agent to existing installation
oak init --agent claude
```

Agent commands are installed in their native directories (`.claude/commands/`, `.github/agents/`, etc.).

### CI Daemon Issues

> ⚠️ **Gotcha**: When the coding agent rebuilds the UI (e.g., during hot-reload), it restarts the MCP server process. The new process may use a stale auth token, causing authentication failures until you reconnect.

**MCP server authentication errors after restart:**

```bash
# Stop and restart the daemon
oak ci stop && oak ci start
```

> ⚠️ **Gotcha**: The daemon returns `401 Missing Authorization header` when the `.oak/ci/.daemon_token` file is absent or the `OAK_CI_TOKEN` environment variable was never set. The client reads the token file unconditionally and crashes if it doesn't exist.

**Daemon returns 401 on every request:**

```bash
# Stop the daemon, then restart — it will regenerate the token file
oak ci stop && oak ci start
```

If the problem persists, verify the token file exists:

```bash
ls -la .oak/ci/.daemon_token
```

> ⚠️ **Gotcha**: The port file contents must be purely numeric. If the file contains whitespace or non-numeric characters, the daemon may fail to start with a ValueError.

**Daemon fails to start with port error:**

```bash
# Clear stale port files
rm -f ~/.oak/daemon.port .oak/daemon.port
oak ci start
```

> ⚠️ **Gotcha**: If the repository is nested inside another git repo, the installer may identify the wrong project root, leading to mis-located hook files.

**Wrong project root detected:**

Ensure you run `oak init` from the actual project root (the directory containing your `.git` folder).

## Upgrading

```bash
# Homebrew
brew upgrade oak-ci

# pipx / uv
pipx upgrade oak-ci   # or: uv tool upgrade oak-ci
```

Then upgrade project templates: `oak upgrade --dry-run` to preview, `oak upgrade` to apply.

## Next Steps

- [Full documentation](https://openagentkit.app/) — features, CLI reference, workflows
- [RFC workflow](https://openagentkit.app/features/strategic-planning/) — technical decision documentation
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribute to the project
- [README.md](README.md) — project overview
