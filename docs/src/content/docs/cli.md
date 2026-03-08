---
title: CLI Commands
description: Reference for oak CLI commands used in setup and maintenance.
---

:::note[CLI + Dashboard]
The CLI handles **setup, upgrades, and daemon management** (`oak init`, `oak upgrade`, `oak team start/stop`). For search, memory, configuration, and activity browsing, use the **[Dashboard](/team/dashboard/)**.
:::

## Setup

### `oak init`

Initialize Open Agent Kit in the current project. Creates the `.oak` directory structure with configuration, agent command directories, and team intelligence data.

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

- **oak** — Semantic search, impact analysis, memory, and database queries against the team intelligence database
- **project-governance** — Create and maintain project constitutions, agent instruction files, and RFC/ADR documents
- **context-engineering** — Prompt and context engineering guidance using the four strategies (Write, Select, Compress, Isolate)
- **swarm** — Cross-project search for collective knowledge, patterns, and decisions across swarm-connected projects

```bash
oak skill list         # List available skills
oak skill install <n>  # Install a skill
oak skill remove <n>   # Remove a skill
oak skill refresh      # Refresh all installed skills
```

## Rules Management

Manage project constitutions and agent instruction files:

```bash
oak rules analyze          # Analyze project for constitution creation
oak rules analyze --json   # Output JSON for agent parsing
oak rules sync-agents      # Sync agent instruction files with constitution
oak rules sync-agents --dry-run  # Preview changes
oak rules detect-existing  # Detect existing agent instruction files
```

### `oak rules analyze`

Performs comprehensive project analysis to determine if the project is greenfield, brownfield-minimal, or brownfield-mature. Useful for understanding the project context before creating a constitution.

**Options:**

| Flag | Description |
|------|-------------|
| `--json` | Output JSON for agent parsing |

### `oak rules sync-agents`

Ensures all configured agents have instruction files that reference the project constitution. Creates files for agents that don't have one, appends references to existing files.

**Options:**

| Flag | Description |
|------|-------------|
| `--json` | Output JSON for agent parsing |
| `--dry-run` | Show what would be done without making changes |

### `oak rules detect-existing`

Checks for existing agent instruction files (`.github/copilot-instructions.md`, `CLAUDE.md`, `AGENTS.md`, etc.) and reports what exists.

**Options:**

| Flag | Description |
|------|-------------|
| `--json` | Output JSON for agent parsing |

## Language Parsers

Add language support for better code understanding:

```bash
oak languages list                        # List parsers and status
oak languages add python javascript       # Add parsers
oak languages add --all                   # Install all 13 languages
oak languages remove ruby php             # Remove parsers
```

**Supported languages**: Python, JavaScript, TypeScript, Java, C#, Go, Rust, C, C++, Ruby, PHP, Kotlin, Scala

## Team (Daemon Lifecycle)

These commands manage the daemon lifecycle. Once the daemon is running, use the **[Dashboard](/team/dashboard/)** for configuration, search, and memory management.

```bash
oak team start       # Start the daemon
oak team start -o    # Start and open dashboard in browser
oak team stop        # Stop the daemon
oak team restart     # Restart the daemon
oak team status      # Show daemon status and index statistics
oak team reset       # Clear all indexed data
oak team logs -f     # Follow daemon logs
```

### Team Relay

```bash
oak team cloud-init          # Deploy relay Worker and connect (turnkey)
oak team cloud-init --force  # Re-scaffold and re-deploy with latest template
oak team cloud-connect [url] # Connect to a specific Worker URL
oak team cloud-disconnect    # Disconnect from the relay
oak team cloud-status        # Show relay connection state
oak team cloud-url           # Print Worker URL (for scripting)
```

### Team Members

```bash
oak team members status      # Show team sync status
oak team members list        # List online team members
```

### MCP Server

```bash
oak team mcp                 # Start the MCP server (used by agents)
```

## CI (Index & Data)

These commands manage the codebase index, search, and data operations.

```bash
oak ci sync        # Sync daemon after OAK upgrade (re-indexes if needed)
oak ci port        # Show the daemon's port number
oak ci backup      # Create a backup
oak ci restore     # Restore from backup
oak ci index       # Rebuild the codebase index
oak ci config      # Manage CI configuration
oak ci search QUERY # CLI semantic search
oak ci memories    # Query stored memories
oak ci sessions    # Query session history
```

:::tip
After running `oak upgrade`, run `oak ci sync` to ensure the daemon picks up any schema changes and re-indexes if needed.
:::

## Agent Client Protocol (ACP)

OAK can act as a coding agent in ACP-compatible editors like Zed. See the [ACP documentation](/team/acp/) for full details.

```bash
oak acp serve      # Start the ACP agent server (stdio transport for editors)
```

The ACP server requires the daemon to be running (`oak team start`). It communicates with the daemon over HTTP and translates between the ACP JSON-RPC protocol and the daemon's REST API.

## Swarm

Swarm enables cross-project federation — connecting multiple OAK projects into a unified search and agent network via a Cloudflare Worker.

```bash
oak swarm create -n NAME     # Create a new swarm configuration
oak swarm deploy -n NAME     # Deploy the swarm Worker to Cloudflare
oak swarm destroy -n NAME    # Remove the swarm Worker
oak swarm start -n NAME      # Start the swarm daemon
oak swarm stop -n NAME       # Stop the swarm daemon
oak swarm restart -n NAME    # Restart the swarm daemon
oak swarm status -n NAME     # Show swarm status and connected nodes
oak swarm mcp                # Start the swarm MCP server
```

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
