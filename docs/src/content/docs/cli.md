---
title: CLI Commands
description: Reference for oak CLI commands used in setup and maintenance.
---

:::note[CLI + Dashboard]
The CLI handles **setup, upgrades, and daemon management** (`oak init`, `oak upgrade`, `oak ci start/stop/sync`). For search, memory, configuration, and activity browsing, use the **[Dashboard](/open-agent-kit/features/codebase-intelligence/dashboard/)**.
:::

## Setup

### `oak init`

Initialize Open Agent Kit in the current project. Creates the `.oak` directory structure with configuration, agent command directories, and Codebase Intelligence data.

**Options:**

| Flag | Description |
|------|-------------|
| `--agent, -a` | Choose AI agent(s) — can be specified multiple times (claude, vscode-copilot, codex, cursor, gemini, windsurf) |
| `--force, -f` | Force re-initialization |
| `--no-interactive` | Skip interactive prompts and use defaults |

Language selection happens interactively during `oak init` when you choose which AST parsers to install.

**Examples:**

```bash
# Interactive mode with multi-select checkboxes
oak init

# With specific agent
oak init --agent claude

# Multiple agents
oak init --agent claude --agent vscode-copilot

# Add agents to existing installation
oak init --agent cursor
```

### `oak upgrade`

Upgrade Open Agent Kit templates and agent commands to the latest versions.

**What gets upgraded:**
- Agent commands: Updates command templates with latest features
- Feature templates: Replaced with latest versions
- Agent settings: Smart merge with existing settings (your custom settings are preserved)
- Database migrations: Applied automatically (schema changes, cleanup tasks)

**Options:**

| Flag | Description |
|------|-------------|
| `--commands, -c` | Upgrade only agent command templates |
| `--templates, -t` | Upgrade only RFC templates |
| `--dry-run, -d` | Preview changes without applying them |
| `--force, -f` | Skip confirmation prompts |

**Examples:**

```bash
oak upgrade --dry-run    # Preview changes
oak upgrade              # Upgrade everything
oak upgrade --commands   # Upgrade only commands
```

## AI Agent Skills

Skills provide specialized capabilities to your AI agent:

- **project-governance** — Create and maintain project constitutions, agent instruction files, and RFC/ADR documents
- **codebase-intelligence** — Semantic search, impact analysis, and database queries against the Oak CI database

```bash
oak skill list         # List available skills
oak skill install <n>  # Install a skill
oak skill remove <n>   # Remove a skill
oak skill refresh      # Refresh all installed skills
```

## Language Parsers

Add language support for better code understanding:

```bash
oak languages list                        # List parsers and status
oak languages add python javascript       # Add parsers
oak languages add --all                   # Install all 13 languages
oak languages remove ruby php             # Remove parsers
```

**Supported languages**: Python, JavaScript, TypeScript, Java, C#, Go, Rust, C, C++, Ruby, PHP, Kotlin, Scala

## Codebase Intelligence

These commands manage the daemon lifecycle. Once the daemon is running, use the **[Dashboard](/open-agent-kit/features/codebase-intelligence/dashboard/)** for configuration, search, and memory management.

```bash
oak ci start       # Start the daemon
oak ci start -o    # Start and open dashboard in browser
oak ci stop        # Stop the daemon
oak ci restart     # Restart the daemon
oak ci status      # Show daemon status and index statistics
oak ci sync        # Sync daemon after OAK upgrade (re-indexes if needed)
oak ci reset       # Clear all indexed data
oak ci logs -f     # Follow daemon logs
oak ci port        # Show the daemon's port number
oak ci backup      # Create a backup
oak ci restore     # Restore from backup
```

### Team Sync

```bash
oak ci team status     # Show team sync connection and relay status
oak ci team members    # List online team members
```

### Cloud Relay

```bash
oak ci cloud-init          # Deploy relay Worker and connect (turnkey)
oak ci cloud-init --force  # Re-scaffold and re-deploy with latest template
oak ci cloud-connect [url] # Connect to a specific Worker URL
oak ci cloud-disconnect    # Disconnect from the relay
oak ci cloud-status        # Show relay connection state
oak ci cloud-url           # Print Worker URL (for scripting)
```

:::tip
After running `oak upgrade`, run `oak ci sync` to ensure the daemon picks up any schema changes and re-indexes if needed.
:::

## Agent Client Protocol (ACP)

OAK can act as a coding agent in ACP-compatible editors like Zed. See the [ACP documentation](/open-agent-kit/features/codebase-intelligence/acp/) for full details.

```bash
oak acp serve      # Start the ACP agent server (stdio transport for editors)
```

The ACP server requires the daemon to be running (`oak ci start`). It communicates with the daemon over HTTP and translates between the ACP JSON-RPC protocol and the daemon's REST API.

## Project Removal

```bash
oak remove         # Remove OAK configuration and files from the project
```

This removes:
- `.oak/` directory (including the daemon port file and all CI data)
- Agent command files and settings (`.claude/commands/`, `.cursor/commands/`, etc.)
- Agent task YAML files in `oak/agents/` that were created by OAK
- OAK-managed hooks, MCP registrations, and skills

It does **not** remove user content in `oak/` (RFCs, constitution, insights, etc.) or the CLI tool itself.
