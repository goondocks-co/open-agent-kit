# open-agent-kit Quick Start Guide

Get started with open-agent-kit in under 5 minutes.

## Installation

### Using uv (Recommended)

```bash
# Install via SSH (requires SSH key configured)
uv tool install git+ssh://git@github.com/sirkirby/open-agent-kit.git

# Verify installation
oak --version
```

### Alternative: Using pip

```bash
# Via SSH
pip install git+ssh://git@github.com/sirkirby/open-agent-kit.git

# Or via HTTPS with GitHub token
pip install git+https://${GITHUB_TOKEN}@github.com/sirkirby/open-agent-kit.git
```

## Step 1: Initialize Your Project

Navigate to your project directory and run:

```bash
oak init
```

This will:

1. Prompt you to select one or more AI agents (Claude, Copilot, Codex, Cursor, Gemini, Windsurf)
2. Create the `.oak` directory structure
3. Copy document templates (RFCs, constitutions, etc.)
4. Generate configuration file
5. Install agent command templates

**Multi-Agent Support**: Select multiple agents for teams where engineers use different AI tools.

**Non-interactive mode**:

```bash
# Single agent
oak init --agent claude

# Multiple agents
oak init --agent claude --agent copilot --agent cursor

# Add more agents later (idempotent)
oak init --agent gemini
```

## Step 2: Create Your Constitution

A **constitution** formalizes your project's engineering standards, architecture patterns, and team conventions. This is the foundation for all other oak workflows.

### Why Create a Constitution First?

- **Guides all AI agents** - Every agent references the constitution for context
- **Codifies team conventions** - Makes implicit standards explicit
- **Required for other workflows** - RFC and issue workflows depend on constitution context

### Creating Your Constitution

Use your AI agent's command:

```text
/oak.constitution-create
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

# Validate structure
# In your AI agent:
/oak.constitution-validate

# Add amendments as standards evolve
/oak.constitution-amend
```

## Step 3: Create and Manage RFCs

With your constitution in place, use RFCs to document technical decisions.

### Create an RFC

```text
/oak.rfc-create Implement user authentication system with OAuth2
```

The AI agent will create a comprehensive RFC at `oak/rfc/RFC-001-*.md` with all required sections filled in.

### List and Validate RFCs

```text
/oak.rfc-list
/oak.rfc-validate RFC-001
```

For the complete RFC workflow including lifecycle states and best practices, see [docs/rfc-workflow.md](docs/rfc-workflow.md).

## Upgrading

Keep your open-agent-kit installation up to date:

```bash
# Preview what would be upgraded
oak upgrade --dry-run

# Upgrade everything (with confirmation)
oak upgrade

# Upgrade only agent commands (safe)
oak upgrade --commands

# Upgrade only templates
oak upgrade --templates --force
```

## Troubleshooting

### oak command not found

```bash
# Check if installed
which oak

# Reinstall if needed
uv tool install git+ssh://git@github.com/sirkirby/open-agent-kit.git
```

### .oak directory not found

Run `oak init` first to initialize the project.

### AI agent commands not showing up

```bash
# Add an agent to existing installation
oak init --agent claude
```

Agent commands are installed in their native directories (`.claude/commands/`, `.github/agents/`, etc.).

## Next Steps

- Read the [full documentation](README.md)
- Review the [RFC workflow](docs/rfc-workflow.md)
- Review the [issue workflow](docs/issue-workflow.md)

## Getting Help

- Run `oak --help` for available CLI commands
- Use agent commands: `/oak.rfc-create`, `/oak.constitution-create`, etc.
- Check the [issue tracker](https://github.com/sirkirby/open-agent-kit/issues)
