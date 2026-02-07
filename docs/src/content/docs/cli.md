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
| `--agent, -a` | Choose AI agent(s) — can be specified multiple times (claude, copilot, codex, cursor, gemini, windsurf) |
| `--language, -l` | Choose language(s) for code intelligence — can be specified multiple times |
| `--force, -f` | Force re-initialization |
| `--no-interactive` | Skip interactive prompts and use defaults |

**Examples:**

```bash
# Interactive mode with multi-select checkboxes
oak init

# With specific agent and languages
oak init --agent claude --language python --language typescript

# Multiple agents
oak init --agent claude --agent copilot

# Add agents to existing installation
oak init --agent cursor
```

### `oak upgrade`

Upgrade Open Agent Kit templates and agent commands to the latest versions.

**What gets upgraded:**
- Agent commands: Updates command templates with latest features
- Feature templates: Replaced with latest versions
- Agent settings: Smart merge with existing settings (your custom settings are preserved)

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

- **project-rules** — Create and maintain project constitutions
- **creating-rfcs** — Create RFC documents for technical decisions
- **reviewing-rfcs** — Review and validate RFC documents

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

:::tip
After running `oak upgrade`, run `oak ci sync` to ensure the daemon picks up any schema changes and re-indexes if needed.
:::

## Project Removal

```bash
oak remove         # Remove OAK configuration and files from the project
```

This removes `.oak/`, agent command files, and agent settings. It does **not** remove user content in `oak/` (RFCs, constitution, etc.) or the CLI tool itself.
