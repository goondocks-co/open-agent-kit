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
- **RFC Workflow**: Codify architectural decisions and features, and process changes with comprehensive RFC commands
- **Engineering Constitution**: Build cross-agent coding standards, architectural patterns, and team conventions. Easily amend and version your constitution.
- **Issue powered SDD**: Fetch and scaffold implementation plans from Azure DevOps or GitHub Issues, combining SDD with your SDLC
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

## Quick Start

```bash
# Interactive mode (select multiple with checkboxes):
oak init

# Single agent:
oak init --agent claude

# Or multiple agents (for teams using different tools):
oak init --agent claude --agent copilot
```

## IDE Auto-Approval Settings

During initialization, Open Agent Kit can install IDE settings that enable auto-approval for `oak` commands:

- **VSCode**: Creates/updates `.vscode/settings.json`
- **Cursor**: Creates/updates `.cursor/settings.json`

These settings configure your IDE to:

- Auto-approve `oak` commands referenced in agent prompts
- Auto-approve terminal commands from `.oak/scripts/` directories (future use)
- Recommend Open Agent Kit prompt files in your AI assistant

**Smart Merging**: Settings are intelligently merged with your existing configuration - your custom settings are preserved, and only new Open Agent Kit settings are added.

**Upgrading**: Run `oak upgrade` to update IDE settings to the latest version.

## Commands

### Setup

#### `oak init`

Initialize Open Agent Kit in the current project. Creates the `.oak` directory structure with templates, configuration, and IDE settings.

**Multi-Agent Support**: You can initialize with multiple agents to support teams using different AI tools. Running `oak init` on an already-initialized project will let you add more agents.

**IDE Configuration**: During init, you'll be prompted to select which IDEs to configure (VSCode, Cursor, or none). This installs auto-approval settings for `oak` commands.

Options:

- `--agent, -a`: Choose AI agent(s) - can be specified multiple times (claude, copilot, codex, cursor, gemini, windsurf)
- `--ide, -i`: Choose IDE(s) to configure - can be specified multiple times (vscode, cursor, none)
- `--force, -f`: Force re-initialization
- `--no-interactive`: Skip interactive prompts

Examples:

```bash
# Interactive mode with multi-select checkboxes (agents and IDEs)
oak init

# With specific agent and IDE
oak init --agent claude --ide vscode

# Multiple agents and IDEs
oak init --agent claude --agent copilot --ide vscode --ide cursor

# Skip IDE configuration
oak init --agent claude --ide none

# Add agents to existing installation
oak init --agent cursor  # Adds Cursor to existing setup
```

#### `oak upgrade`

Upgrade Open Agent Kit templates, agent commands, and IDE settings to the latest versions from the package.

**What gets upgraded:**

- **Agent commands**: Updates command templates with latest features
- **RFC templates**: Replaced with latest versions
- **IDE settings**: Smart merge with existing settings - your custom settings are preserved

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

#### `/oak.rfc-create <description>`

- Drive the RFC workflow through your agent. The prompt now guides you to confirm requirements, investigate existing context (brownfield and greenfield), choose the correct template, and synthesize a full draft before relying on any CLI scaffolding.
- Expect the agent to pause for clarification, surface related RFCs that may conflict or align, and request approval before running support commands (e.g., `oak rfc create`).
- After drafting, you will review the generated markdown, integrate additional evidence, and decide whether to run validation.

Example:

```bash
/oak.rfc-create Add OAuth2 authentication for API endpoints
```

The agent will collaborate with you to:

1. Gather additional context (stakeholders, constraints, related work)
2. Investigate the repository for patterns, dependencies, or prior RFCs
3. Select the best-fit template and outline section-by-section content
4. Scaffold the RFC file using the CLI and replace all placeholders with actionable content
5. Summarize open questions and next steps for manual review

#### `/oak.rfc-list [filter]`

- Produce analytical views of the RFC portfolio. The agent can call `oak rfc list --json` to compute status breakdowns, stale drafts, top contributors, or filtered subsets, then explain what requires attention.
- Natural language filters such as "draft RFCs older than 60 days" or "show approved RFCs tagged observability" are supported.

#### `/oak.rfc-validate <rfc-number>`

- Perform an interactive quality review. The agent combines manual evaluation with optional CLI validation (`oak rfc validate RFC-###`) after asking for consent.
- Findings are grouped by severity (critical/major/minor), and you can opt-in for assistance applying fixes in place.

> Tip: If no RFC number is provided, the agent will automatically target the most recent RFC.

#### `/oak.constitution-create [description]`

**Create an engineering constitution** - AI agent guides you through an interactive decision framework to generate a tailored project constitution.

Example:

```bash
/oak.constitution-create
```

The AI will:

1. **Analyze your project** (greenfield vs brownfield, existing patterns)
2. **Guide you through key decisions**:
   - Architectural pattern (Vertical Slice, Clean, Layered, etc.)
   - Testing strategy (Comprehensive, Balanced, Pragmatic)
   - Error handling approach (Result Pattern, exceptions, mixed)
   - Code review policies, documentation level, CI/CD enforcement
3. **Generate tailored constitution** matching YOUR needs (not prescriptive defaults)
4. **Additively update agent instruction files** with constitution references (never overwrites)

**For brownfield projects**: Detects and incorporates existing conventions from agent instruction files and codebase.

**For existing users**: See [Constitution Upgrade Guide](docs/constitution-upgrade-guide.md) for modernization options.

#### `/oak.constitution-validate`

**Validate and modernize** your constitution. The AI will:

- Check structure, metadata, and declarative language
- **Reality alignment checks**: Verify requirements match actual project capabilities
- **Detect old-style constitutions**: Offer modernization to decision-driven framework
- Provide three paths: standard validation, full modernization, or hybrid approach

See [Constitution Upgrade Guide](docs/constitution-upgrade-guide.md) for details on modernization options.

#### `/oak.constitution-amend <summary>`

**Add an amendment** to the constitution with proper versioning and ratification tracking. The AI helps you assess impact, choose the right version bump (major/minor/patch), and keeps agent instruction files in sync.

### Issue Commands

These commands integrate with issue trackers (Azure DevOps, GitHub Issues) to scaffold implementation plans.

#### `/oak.issue-plan <provider> <issue>`

Creates the implementation plan (context JSON + `plan.md`) and prepares the issue branch. The agent will:

1. Confirm provider + issue id with you.
2. Run `/oak.issue-plan <provider> <issue>` (which calls `oak issue plan <id> [--provider <key>]` under the hood) after `oak config issue-provider check` succeeds.
3. Capture objectives, constraints, risks, dependencies, and definition of done via the CLI prompts.
4. Review the generated artifacts in `oak/issue/<provider>/<issue>/` (including `codebase.md`, which snapshots the `src/` and `tests/` tree so the agent knows where to start exploring).

#### `/oak.issue-implement <provider> <issue>`

Consumes the stored plan plus any extra context you supply. The agent will:

1. Ensure `/oak.issue-plan` and `/oak.issue-validate` have already run.
2. Execute `/oak.issue-implement <provider> <issue> [notes...]` (invokes `oak issue implement …`).
3. The CLI re-checkouts the branch, echoes the plan/notes/codebase snapshot paths, and logs the additional context to `notes.md`.
4. You open `plan.md`, `notes.md`, and `codebase.md`, then study existing code before implementing.

> If you omit the issue id, the agent command infers it from the current branch or the most recent `/oak.issue-plan` entry and prints which one it chose so you can confirm.

#### `/oak.issue-validate <provider> <issue>`

Validates the artifacts created by `/oak.issue-implement`. The agent will:

1. Confirm the provider + issue id.
2. Run `/oak.issue-validate <provider> <issue>` (calls `oak issue validate …`).
3. Review the CLI summary for pending sections (objectives, risks, dependencies, definition of done) or missing acceptance criteria.
4. Report findings and help fill in any gaps so the implementation is truly review-ready.

> Validation can also infer the issue from your current branch or most recent plan if you omit the id; the agent command echoes what it selected.

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
  validate_on_create: true

issue:
  directory: oak/issue
  provider: ado
```

**Note**: The old `agent: claude` format is automatically migrated to `agents: [claude]` when you run any Open Agent Kit command.

### Issue Provider Configuration

Configure the tracker that feeds issue workflows. Use these commands to set up Azure DevOps or GitHub Issues integration:

#### `oak config issue-provider set`

Set the active provider and its required settings:

```bash
# Azure DevOps
oak config issue-provider set \
  --provider ado \
  --organization contoso \
  --project web \
  --pat-env AZURE_DEVOPS_PAT

# GitHub Issues
oak config issue-provider set \
  --provider github \
  --owner sirkirby \
  --repo open-agent-kit \
  --token-env GITHUB_TOKEN
```

#### `oak config issue-provider check`

Validates the active provider to ensure configuration and environment variables are in place:

```bash
oak config issue-provider check
```

#### `oak config issue-provider show`

Displays the stored configuration (minus secrets) for auditing:

```bash
oak config issue-provider show
```

## Templates

### Agent Command Templates

Agent command templates define how AI agents interact with Open Agent Kit. These templates:

- Use YAML frontmatter with `description` field
- Include `$ARGUMENTS` placeholder for user input
- Are maintained in `templates/commands/` in the Open Agent Kit package

When you run `oak init --agent <agent>`, these templates are installed to the appropriate agent directory (`.claude/commands/`, `.github/agents/`, etc.) with the correct file extension for that agent.

> **Note:** Don't manually edit the installed command files in `.claude/commands/` or `.github/agents/` - they will be overwritten when you upgrade Open Agent Kit. These files are managed by the package and updated with new versions.

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

- `/oak.rfc-create` - Create and enhance RFCs from natural language
- `/oak.rfc-list` - List and analyze project RFCs
- `/oak.rfc-validate` - Validate RFC structure and content
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

## License

MIT License - see LICENSE file for details.

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
