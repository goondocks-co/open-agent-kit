# Open Agent Kit

[![PR Check](https://github.com/goondocks-co/open-agent-kit/actions/workflows/pr-check.yml/badge.svg)](https://github.com/goondocks-co/open-agent-kit/actions/workflows/pr-check.yml)
[![Release](https://github.com/goondocks-co/open-agent-kit/actions/workflows/release.yml/badge.svg)](https://github.com/goondocks-co/open-agent-kit/actions/workflows/release.yml)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/goondocks-co/open-agent-kit?sort=semver)
[![PyPI](https://img.shields.io/pypi/v/oak-ci?style=flat-square)](https://pypi.org/project/oak-ci/)

[![Python](https://img.shields.io/badge/python-3.13%2B-blue?style=flat-square)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000?style=flat-square)](https://github.com/astral-sh/ruff)

**The Intelligence Layer for AI Agents**

Open Agent Kit (OAK) gives your AI coding assistants (Claude, Copilot, Cursor, etc.) **sight** and **memory**. It runs locally as a background service, indexing your codebase and remembering past decisions to prevent agents from making the same mistakes twice.

![OAK CI Dashboard](docs/images/ci-dashboard.png)

## Why OAK?

AI agents typically "forget" everything when you start a new session. OAK solves this:

1.  **Persistent Memory**: OAK remembers "gotchas", architectural decisions, and bug fixes across sessions.
2.  **Semantic Search**: Agents can find code by *concept* ("where is auth?") rather than just regex.
3.  **Live Auto-Capture**: OAK watches your agent's actions and automatically records new learnings.

## Quick Start
Add the intelligence layer to any project:

```bash
# Initialize OAK (interactive mode)
oak init

# Or specify agents directly
oak init --agent claude

# Start the Codebase Intelligence daemon
oak ci start
```

## Features

- **Codebase Intelligence**: Semantic code search, AST-aware indexing, and persistent memory via MCP tools (`oak_search`, `oak_remember`, `oak_context`).
- **Rules Management**: Create and maintain a project constitution with shared coding standards that AI agents follow.
- **Strategic Planning (RFCs)**: Manage RFC documents for technical decisions and architecture records.
- **Language Support**: Install tree-sitter parsers for 13 languages (Python, TypeScript, Go, Rust, and more).
- **Claude Agent Skills**: Installable skills for specialized agent workflows.
- **Universal Compatibility**: Works with Claude Code, Cursor, Copilot, Windsurf, Gemini, Codex, and any MCP-compatible agent.
- **Auto-Configuration**: Automatically configures MCP servers and agent instruction files during init.


## Installation

### Using pipx (Recommended)

```bash
pipx install oak-ci
```

### Using uv

```bash
uv tool install oak-ci
```

### Using pip

```bash
pip install oak-ci
```

## Quick Start

```bash
# Interactive mode (select agents and languages with checkboxes):
oak init

# Single agent with default languages (python, javascript, typescript):
oak init --agent claude

# Multiple agents (for teams using different tools):
oak init --agent claude --agent copilot

# Specify languages for code intelligence:
oak init --agent claude --language python --language go --language rust
```

## Agent Auto-Approval Settings

During initialization, Open Agent Kit installs agent-specific settings that enable auto-approval for `oak` commands. These settings are placed in each agent's configuration directory:

- **Claude**: `.claude/settings.json`
- **Copilot**: `.github/copilot-settings.json`
- **Cursor**: `.cursor/settings.json`
- **Gemini**: `.gemini/settings.json`
- **Windsurf**: `.windsurf/settings.json`

**Upgrading**: Run `oak upgrade` to update agent settings to the latest version.

## Core Features

Open Agent Kit includes three core features that are always enabled:

| Feature | Description |
|---------|-------------|
| **Rules Management** | Project constitution and coding standards for AI agents |
| **Strategic Planning** | RFC workflow for documenting technical decisions |
| **Codebase Intelligence** | Semantic code search, AST-aware indexing, and persistent memory |

### Language Parsers

Add language support for better code understanding:

```bash
# List available parsers and installation status
oak languages list

# Add language parsers
oak languages add python javascript typescript
oak languages add --all  # Install all 13 supported languages

# Remove parsers
oak languages remove ruby php
```

**Supported languages**: Python, JavaScript, TypeScript, Java, C#, Go, Rust, C, C++, Ruby, PHP, Kotlin, Scala

## Commands

### Setup

#### `oak init`

Initialize Open Agent Kit in the current project. Creates the `.oak` directory structure with configuration, agent command directories, and Codebase Intelligence data.

**Multi-Agent Support**: You can initialize with multiple agents to support teams using different AI tools. Running `oak init` on an already-initialized project will let you add more agents.

Options:

- `--agent, -a`: Choose AI agent(s) - can be specified multiple times (claude, copilot, codex, cursor, gemini, windsurf)
- `--language, -l`: Choose language(s) for code intelligence - can be specified multiple times (python, javascript, typescript, java, csharp, go, rust, c, cpp, ruby, php, kotlin, scala)
- `--force, -f`: Force re-initialization
- `--no-interactive`: Skip interactive prompts and use defaults

Examples:

```bash
# Interactive mode with multi-select checkboxes (agents and languages)
oak init

# With specific agent and languages
oak init --agent claude --language python --language typescript

# Multiple agents with default languages
oak init --agent claude --agent copilot

# Non-interactive with defaults
oak init --agent claude --no-interactive

# Add agents to existing installation
oak init --agent cursor  # Adds Cursor to existing setup
```

#### `oak upgrade`

Upgrade Open Agent Kit templates and agent commands to the latest versions from the package.

**What gets upgraded:**

- **Agent commands**: Updates command templates with latest features
- **Feature templates**: Replaced with latest versions
- **Agent settings**: Smart merge with existing settings - your custom settings are preserved

Options:

- `--commands, -c`: Upgrade only agent command templates
- `--templates, -t`: Upgrade only RFC templates
- `--dry-run, -d`: Preview changes without applying them
- `--force, -f`: Skip confirmation prompts

Examples:
```bash
# Preview what would be upgraded
oak upgrade --dry-run

# Upgrade everything (with confirmation)
oak upgrade

# Upgrade only agent commands
oak upgrade --commands

# Upgrade only templates
oak upgrade --templates --force
```

### AI Agent Skills

After initialization, skills provide specialized capabilities to your AI agent:

- **project-rules** — Create and maintain project constitutions with coding standards
- **creating-rfcs** — Create RFC documents for technical decisions
- **reviewing-rfcs** — Review and validate RFC documents

Manage skills with the `oak skill` command:

```bash
oak skill list         # List available skills
oak skill install <n>  # Install a skill
oak skill remove <n>   # Remove a skill
oak skill refresh      # Refresh all installed skills
```

## Configuration

Configuration is stored in `.oak/config.yaml`:

```yaml
version: 0.1.0
agents:
  - claude
  - copilot

rfc:
  directory: oak/rfc
  template: engineering
  auto_number: true
  number_format: sequential
  validate_on_create: true
```

### RFC Templates

Available RFC templates (specified via `--template` on `oak rfc create`):

- `engineering` — Engineering RFC Template (default)
- `architecture` — Architecture Decision Record
- `feature` — Feature Proposal
- `process` — Process Improvement

### Codebase Intelligence

The CI daemon runs locally and exposes MCP tools for AI agents:

| Tool | Description |
|------|-------------|
| `oak_search` | Semantic search over code, memories, and implementation plans |
| `oak_remember` | Store observations (gotchas, decisions, discoveries, bug fixes) for future sessions |
| `oak_context` | Get relevant context for the current task |

**Daemon Commands:**

```bash
oak ci status      # Show daemon status and index statistics
oak ci start       # Start the daemon
oak ci start -o    # Start and open dashboard in browser
oak ci stop        # Stop the daemon
oak ci restart     # Restart the daemon
oak ci reset       # Clear all indexed data
oak ci logs -f     # Follow daemon logs
```

## AI Agent Integration

Open Agent Kit integrates with AI coding assistants by installing command prompts in their native directories:

| Agent | Commands Directory | Command Format |
|-------|-------------------|----------------|
| **Claude Code** | `.claude/commands/` | `oak.rfc-create.md` |
| **GitHub Copilot** | `.github/agents/` | `oak.rfc-create.prompt.md` |
| **Cursor** | `.cursor/commands/` | `oak.rfc-create.md` |
| **Codex CLI** | `.codex/prompts/` | `oak.rfc-create.md` |
| **Gemini CLI** | `.gemini/commands/` | `oak.rfc-create.md` |
| **Windsurf** | `.windsurf/commands/` | `oak.rfc-create.md` |

After running `oak init --agent <agent-name>`, you can use commands like:

- `/oak.constitution-create` - Create engineering constitutions from codebase analysis
- `/oak.constitution-validate` - Validate constitution structure
- `/oak.constitution-amend` - Add amendments to constitutions

**No API keys required!** Commands are invoked through your agent's interface, which handles authentication.

### Agent Instruction Files

Open Agent Kit also creates and manages agent instruction files that reference your project constitution:

- `.claude/CLAUDE.md` - Claude Code instructions
- `.github/copilot-instructions.md` - GitHub Copilot instructions
- `AGENTS.md` - Codex/Cursor instructions (shared, root level)
- `GEMINI.md` - Gemini instructions (root level)
- `.windsurf/rules/rules.md` - Windsurf instructions

**IMPORTANT**: If your team already has these files with established conventions:

- Open Agent Kit will **append** constitution references (not overwrite)
- Backups are created automatically (`.backup` extension) as a failsafe
- Existing team conventions are preserved
- The constitution incorporates your existing patterns

### Multi-Agent Workflows

Open Agent Kit supports multiple agents in the same project, which is ideal for teams where engineers use different tools:

```bash
# Initialize with guided multi-select agent selection (recommended)
oak init

# Initialize with multiple agents
oak init --agent codex --agent copilot --agent cursor

# Or add agents incrementally
oak init --agent claude
# Later, add more:
oak init --agent copilot
```

**Benefits of multi-agent setup:**

- **Team flexibility**: Engineers can use their preferred AI tool
- **Consistent workflow**: Same commands (`/oak.rfc-create`, etc.) across all agents
- **Zero conflicts**: Each agent's commands live in separate directories and are updated independently from core templates

**Example team workflow:**

```bash
# Project lead initializes with all agents
oak init --agent claude --agent copilot --agent cursor

# Engineer using Claude creates an RFC
# In Claude Code:
/oak.rfc-create Add rate limiting to API

# Another engineer using Copilot reviews it
# In VS Code with Copilot:
/oak.rfc-validate RFC-001

# RFC files are shared, tools are not!
```

## Uninstallation

### Using pipx

```bash
pipx uninstall oak-ci
```

### Using uv

```bash
uv tool uninstall oak-ci
```

### Using pip

```bash
pip uninstall oak-ci
```

**Note**: This removes the CLI tool but does not delete project files created by `oak init` (`.oak/`, agent command directories, etc.). To clean up a project, run `oak remove` or manually delete:

- `.oak/` - Configuration and CI data
- `.claude/` - Claude commands and settings
- `.github/agents/` - Copilot commands
- `.cursor/commands/` - Cursor commands
- `.codex/prompts/` - Codex commands
- `.gemini/commands/` - Gemini commands
- `.windsurf/commands/` - Windsurf commands

## Removing from a Project

To remove Open Agent Kit from a specific project without uninstalling the CLI tool:

```bash
# Remove OAK configuration and files from the current project
oak remove
```

This command will:
- Remove the `.oak` directory (configuration and CI data)
- Remove agent-specific command files (e.g., `.claude/commands/oak.*`)
- Remove agent settings files added by OAK
- Clean up empty directories created by OAK

It will **not** remove:
- User content in the `oak/` directory (RFCs, constitution, etc.)
- The `oak` CLI tool itself

## Troubleshooting

### ModuleNotFoundError after upgrade

If you see `ModuleNotFoundError` for packages like `httpx` after upgrading:

```bash
# Reinstall to update all dependencies
pipx reinstall oak-ci

# Or with uv
uv tool install --force oak-ci
```

This can happen when new dependencies are added to the package but the global installation wasn't updated.

### Command not found: oak

If the `oak` command isn't found after installation:

**Using uv:**

```bash
# Ensure uv tools are in your PATH
# Add to ~/.bashrc, ~/.zshrc, or equivalent:
export PATH="$HOME/.local/bin:$PATH"

# Then reload your shell or run:
source ~/.bashrc  # or ~/.zshrc
```

**Using pip:**

```bash
# Check if pip's script directory is in PATH
python3 -m pip show oak-ci

# If installed with --user flag, add to PATH:
export PATH="$HOME/.local/bin:$PATH"
```

### Changes not taking effect (editable install)

If you're developing Open Agent Kit and changes aren't reflected:

**For Python code changes:** They should work immediately with editable mode

**For dependency or entry point changes:** Reinstall with force:

```bash
make setup
```

### Permission denied errors

If you get permission errors during installation:

**Using uv:** Should work without sudo (installs to ~/.local)

**Using pip:** Don't use sudo with pip, use the `--user` flag:

```bash
pip install --user oak-ci
```

## Development

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Setup

```bash
# Clone the repository
git clone https://github.com/goondocks-co/open-agent-kit.git
cd open-agent-kit

# Install all dependencies
make setup

# Verify everything works
make check
```

### Common Commands

```bash
make help          # Show all available commands
make setup         # Install dependencies (first time)
make sync          # Sync with lockfile (after git pull)
make lock          # Update lockfile (after changing pyproject.toml)
make test          # Run tests with coverage
make test-fast     # Run tests without coverage (faster)
make format        # Auto-format code
make check         # Run all CI checks (format, typecheck, test)
make uninstall     # Remove dev environment (to test live package)
```

### Code Quality

```bash
make check  # Runs format-check, typecheck, and tests
```

### GitHub Workflows

Open Agent Kit uses GitHub Actions for CI/CD:

- **PR Validation** - Runs on every pull request
  - Code linting and formatting
  - Type checking
  - Test suite across OS and Python versions
  - Template and script validation
  - Integration tests

- **Release Automation** - Triggers on version tags
  - Builds Python packages (wheel and sdist)
  - Creates template packages for each agent/script combination
  - Generates release notes
  - Creates GitHub release with all artifacts

See [RELEASING.md](RELEASING.md) for release process and [.github/WORKFLOWS.md](.github/WORKFLOWS.md) for workflow details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Documentation

### User Documentation

- [Quick Start Guide](QUICKSTART.md) - Get started in 5 minutes
- [Documentation Index](docs/README.md) - All documentation

### For Contributors

- [Contributing Guide](CONTRIBUTING.md) - How to contribute
- [Project Constitution](oak/constitution.md) - Standards and principles
- [Releasing Guide](docs/development/releasing.md) - Release procedures
- [Architecture](docs/architecture.md) - System design and component diagrams

## Links

- [GitHub Repository](https://github.com/goondocks-co/open-agent-kit)
- [Issue Tracker](https://github.com/goondocks-co/open-agent-kit/issues)
- [PyPI Package](https://pypi.org/project/oak-ci/)

