# Open Agent Kit

```bash
╭─────────────────────────────────────────────────────────╮
│                                                         │
│              ██████╗  █████╗ ██╗  ██╗                   │
│             ██╔═══██╗██╔══██╗██║ ██╔╝                   │
│             ██║   ██║███████║█████╔╝                    │
│             ██║   ██║██╔══██║██╔═██╗                    │
│             ╚██████╔╝██║  ██║██║  ██╗                   │
│              ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝                   │
│                                                         │
│   Open Agent Kit - AI-Powered Development Workflows.    │
│                                                         │
╰─────────────────────────────────────────────────────────╯
```

[![PR Check](https://github.com/sirkirby/open-agent-kit/actions/workflows/pr-check.yml/badge.svg)](https://github.com/sirkirby/open-agent-kit/actions/workflows/pr-check.yml)
[![Release](https://github.com/sirkirby/open-agent-kit/actions/workflows/release.yml/badge.svg)](https://github.com/sirkirby/open-agent-kit/actions/workflows/release.yml)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/sirkirby/open-agent-kit?sort=semver)

[![Python](https://img.shields.io/badge/python-3.13%2B-blue?style=flat-square)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000?style=flat-square)](https://github.com/astral-sh/ruff)

**AI-Powered Development Workflows**

Open Agent Kit brings multi-agent spec-driven development, SDLC integration, skills, and other valuable workflows to your local AI coding assistants. Use Constitution commands to establish multi-agent project rules and standards (works with AGENTS.md, CLAUDE.md, copilot_instructions.md, etc), Use RFC agent commands to codify architectural decisions, and integrate issues, stories, and tasks from Azure DevOps or GitHub Issues - all through your favorite AI agent (Claude, Copilot, Cursor, Codex, Gemini/Antigravity, Windsurf).

## Features

- **Multi-Agent Support**: Work with Claude, Copilot, Cursor, Codex, Gemini, and Windsurf in the same project seamlessly
- **Engineering Constitution**: Build cross-agent coding standards, architectural patterns, and team conventions. Easily amend and version your constitution.
- **AI-Driven Workflows**: Leverage AI agents to guide you through complex workflows with interactive prompts and validations. Leverages oak CLI under the hood for scaffolding, validation, integrations, and consistency
- **Beautiful CLI**: Rich, interactive command-line interface for project setup, agent configuration, and easy updates
- **Project-Based**: Simple `.oak` installation directory and `oak` asset directory structure

## Installation

### Using uv (Recommended)

```bash
# Install via SSH (requires SSH key configured with GitHub)
uv tool install git+ssh://git@github.com/sirkirby/open-agent-kit.git

# Or via HTTPS
uv tool install git+https://github.com/sirkirby/open-agent-kit.git
```

### Using pip

```bash
# Via SSH
pip install git+ssh://git@github.com/sirkirby/open-agent-kit.git

# Or via HTTPS
pip install git+https://github.com/sirkirby/open-agent-kit.git
```

## Quick Start

```bash
# Interactive mode (select agents, IDEs, and features with checkboxes):
oak init

# Single agent with all default features:
oak init --agent claude

# Multiple agents (for teams using different tools):
oak init --agent claude --agent copilot

# Select specific features:
oak init --agent claude --feature constitution --feature rfc
```

## IDE Auto-Approval Settings

During initialization, Open Agent Kit can install IDE settings that enable auto-approval for `oak` commands:

- **VSCode**: Creates/updates `.vscode/settings.json`
- **Cursor**: Creates/updates `.cursor/settings.json`

These settings configure your IDE to:

- Auto-approve `oak` commands referenced in agent prompts
- Recommend Open Agent Kit prompt files in your AI assistant

**Smart Merging**: Settings are intelligently merged with your existing configuration - your custom settings are preserved, and only new Open Agent Kit settings are added.

**Upgrading**: Run `oak upgrade` to update IDE settings to the latest version.

## Features

Open Agent Kit uses a modular feature system that lets you install only the workflows you need:

| Feature | Description | Dependencies |
|---------|-------------|--------------|
| **constitution** | Engineering standards, architectural patterns, team conventions | None |
| **rfc** | RFC workflow for documenting technical decisions | constitution |
| **plan** | Issue-driven implementation planning with research, task breakdown, and validation | constitution |

### Feature Selection

During `oak init`, you can select which features to install. Features with dependencies automatically include their required features (e.g., selecting `rfc` will also install `constitution`).

### Managing Features

```bash
# Interactive feature management
oak feature

# List installed and available features
oak feature list

# Add a feature
oak feature add rfc

# Remove a feature (with dependency check)
oak feature remove plan

# Refresh features after config changes
oak feature refresh
```

### Refreshing Features

The `oak feature refresh` command re-renders all installed feature commands using your current configuration. This is useful when you've modified agent capabilities in `.oak/config.yaml` and want to apply those changes without upgrading the package.

```bash
# Edit agent capabilities in .oak/config.yaml
# Then refresh to apply changes
oak feature refresh
```

## Commands

### Setup

#### `oak init`

Initialize Open Agent Kit in the current project. Creates the `.oak` directory structure with templates, configuration, and IDE settings.

**Multi-Agent Support**: You can initialize with multiple agents to support teams using different AI tools. Running `oak init` on an already-initialized project will let you add more agents.

**IDE Configuration**: During init, you'll be prompted to select which IDEs to configure (VSCode, Cursor, or none). This installs auto-approval settings for `oak` commands.

Options:

- `--agent, -a`: Choose AI agent(s) - can be specified multiple times (claude, copilot, codex, cursor, gemini, windsurf)
- `--ide, -i`: Choose IDE(s) to configure - can be specified multiple times (vscode, cursor, none)
- `--feature, -f`: Choose feature(s) to install - can be specified multiple times (constitution, rfc, issues, none)
- `--force`: Force re-initialization
- `--no-interactive`: Skip interactive prompts

Examples:

```bash
# Interactive mode with multi-select checkboxes (agents, IDEs, and features)
oak init

# With specific agent, IDE, and features
oak init --agent claude --ide vscode --feature constitution --feature rfc

# Multiple agents and IDEs with all features
oak init --agent claude --agent copilot --ide vscode --ide cursor

# Skip IDE configuration, install only constitution
oak init --agent claude --ide none --feature constitution

# Add agents to existing installation (preserves existing features)
oak init --agent cursor  # Adds Cursor to existing setup
```

#### `oak upgrade`

Upgrade Open Agent Kit templates, agent commands, and IDE settings to the latest versions from the package.

**What gets upgraded:**

- **Agent commands**: Updates command templates with latest features
- **Feature templates**: Replaced with latest versions
- **IDE settings**: Smart merge with existing settings - your custom settings are preserved
- **Core**: Updates shared scripts, config, and state

Options:

- `--commands, -c`: Upgrade only agent command templates
- `--templates, -t`: Upgrade only RFC templates
- `--dry-run, -d`: Preview changes without applying them
- `--force, -f`: Skip confirmation prompts

Examples:
```bash
# Preview what would be upgraded
oak upgrade --dry-run

# Upgrade everything (with confirmation) - includes IDE settings
oak upgrade

# Upgrade only agent commands (safe)
oak upgrade --commands

# Upgrade only command templates
oak upgrade --templates --force
```

### AI Agent Commands (Primary Workflow)

These commands are available in your AI agent interface after running `oak init --agent <name>`:

- [Constitution Management](docs/features/constitution.md)
- [RFC Management](docs/features/rfc.md)
- [Plan Management](docs/features/plan.md) - Issue-driven implementation planning

## Configuration

Configuration is stored in `.oak/config.yaml`:

```yaml
version: 0.1.0
agents:
  - claude
  - copilot

features:
  enabled:
    - constitution
    - rfc
    - plan

rfc:
  directory: oak/rfc
  template: engineering
  auto_number: true
  validate_on_create: true

# Agent capabilities (auto-populated from agent manifests)
agent_capabilities:
  claude:
    has_background_agents: true
    has_native_web: true
    has_mcp: true
    research_strategy: null
  copilot:
    has_background_agents: false
    has_native_web: false
    has_mcp: false
    research_strategy: null
```

### Agent Capabilities

Agent capabilities control how feature commands are rendered for each agent. These are auto-populated from agent manifests during `oak init`, but you can override them:

| Capability | Description |
|-----------|-------------|
| `has_background_agents` | Agent supports spawning background/parallel agents |
| `has_native_web` | Agent has built-in web search/fetch capabilities |
| `has_mcp` | Agent supports Model Context Protocol servers |
| `research_strategy` | Custom research approach (e.g., "deep_research") |

**Customizing Capabilities:**

1. Edit `.oak/config.yaml` to change capability values
2. Run `oak feature refresh` to re-render commands with new capabilities

This allows you to enable or disable agent-specific features without upgrading the package.

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

### Using uv

```bash
# Remove open-agent-kit
uv tool uninstall open-agent-kit
```

### Using pip

```bash
# Remove open-agent-kit
pip uninstall open-agent-kit
```

**Note**: This removes the CLI tool but does not delete project files created by `oak init` (`.oak/`, agent command directories, etc.). To clean up a project, manually delete:

- `.oak/` - Configuration and templates
- `.vscode/settings.json` - VSCode settings (if no other settings)
- `.cursor/settings.json` - Cursor settings (if no other settings)
- `.claude/commands/oak.*` - Claude commands
- `.github/agents/oak.*` - Copilot commands
- Agent instruction file references to `oak/constitution.md`

## Removing from a Project

To remove Open Agent Kit from a specific project without uninstalling the CLI tool:

```bash
# Remove OAK configuration and files from the current project
oak remove
```

This command will:
- Remove the `.oak` directory
- Remove agent-specific command files (e.g., `.claude/commands/oak.*`)
- Remove IDE settings added by OAK (unless `--keep-ide-settings` is used)
- Clean up empty directories created by OAK

It will **not** remove:
- Generated artifacts in the `oak/` directory (RFCs, constitution, etc.)
- Files you have modified after OAK created them
- The `oak` CLI tool itself

## Troubleshooting

### ModuleNotFoundError after upgrade

If you see `ModuleNotFoundError` for packages like `httpx` after upgrading:

```bash
# Reinstall with force flag to update all dependencies
uv tool install --force --editable .
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
python3 -m pip show open-agent-kit

# If installed with --user flag, add to PATH:
export PATH="$HOME/.local/bin:$PATH"
```

### Changes not taking effect (editable install)

If you're developing Open Agent Kit and changes aren't reflected:

**For Python code changes:** They should work immediately with editable mode

**For dependency or entry point changes:** Reinstall with force:

```bash
uv tool install --force --editable .
```

### Permission denied errors

If you get permission errors during installation:

**Using uv:** Should work without sudo (installs to ~/.local)

**Using pip:** Don't use sudo with pip, use the `--user` flag:

```bash
pip install --user git+ssh://git@github.com/sirkirby/open-agent-kit.git
```

## Development

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Setup

```bash
# Clone the repository
git clone https://github.com/sirkirby/open-agent-kit.git
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
- [Project Constitution](.constitution.md) - Standards and principles
- [Releasing Guide](docs/development/releasing.md) - Release procedures
- [Architecture](docs/architecture.md) - System design and component diagrams

## Links

- [GitHub Repository](https://github.com/sirkirby/open-agent-kit)
- [Issue Tracker](https://github.com/sirkirby/open-agent-kit/issues)
