---
title: Configuration
description: How OAK is configured — via the dashboard and project files.
---

:::note[Configure from the dashboard]
Most settings are managed through the **[Dashboard](/team/dashboard/)** — open it with `oak team start --open` and click **Configuration** in the sidebar. The dashboard provides a visual interface for embedding providers, summarization, exclusions, and more.
:::

## Project Configuration

OAK project settings are stored in `.oak/config.yaml`:

```yaml
version: 0.1.0
agents:
  - claude
  - copilot

rfc:
  directory: oak/rfc
  template: engineering
  validate_on_create: true
```

## Team Daemon Settings

The Team daemon stores its configuration in `.oak/config.yaml` under the `team` section. **You don't need to edit this file directly** — the dashboard reads and writes it for you.

Settings managed via the dashboard:
- **Embedding provider and model** (Ollama, LM Studio, OpenAI-compatible)
- **Summarization provider and model** (optional)
- **Session quality thresholds** (minimum activities, stale timeout)
- **Log rotation** (max file size, backup count)
- **Directory exclusions** (patterns to skip during indexing)

See the [Dashboard](/team/dashboard/) page for details on each setting.

## RFC Templates

Available RFC templates (specified via `--template` on `oak rfc create`):

| Template | Description |
|----------|-------------|
| `engineering` | Engineering RFC Template (default) |
| `architecture` | Architecture Decision Record |
| `feature` | Feature Proposal |
| `process` | Process Improvement |

## Agent Auto-Approval Settings

During initialization, OAK installs agent-specific settings that enable auto-approval
for the configured OAK CLI command (`oak` by default):

| Agent | Settings File |
|-------|---------------|
| Claude | `.claude/settings.json` |
| VS Code Copilot | `.vscode/settings.json` |
| Cursor | `.cursor/settings.json` |
| Gemini | `.gemini/settings.json` |
| Windsurf | `.windsurf/settings.json` |

Run `oak upgrade` to update agent settings to the latest version.

If you need a different command in one repository (for example `oak-dev`), set:

```bash
oak ci config --cli-command oak-dev
```

This updates managed integrations in that project to use the new command.
See [Team Configuration](/team/configuration/#cli-command-for-managed-integrations) for details.

## Agent Instruction Files

OAK creates and manages instruction files that reference your project constitution:

| Agent | Instruction File |
|-------|-----------------|
| Claude Code | `.claude/CLAUDE.md` |
| VS Code Copilot | `.github/copilot-instructions.md` |
| Codex / Cursor / OpenCode | `AGENTS.md` (root level, shared) |
| Gemini | `GEMINI.md` (root level) |
| Windsurf | `.windsurf/rules/rules.md` |

If your team already has these files, OAK will **append** constitution references (not overwrite). Backups are created automatically.

## MCP Tools

The daemon exposes tools for agents via the Model Context Protocol:

| Tool | Description |
|------|-------------|
| `oak_search` | Semantic search over code, memories, plans, and sessions |
| `oak_remember` | Store observations for future sessions |
| `oak_context` | Get relevant context for the current task |
| `oak_resolve_memory` | Mark observations as resolved or superseded |
| `oak_sessions` | List recent coding sessions |
| `oak_memories` | Browse stored memories/observations |
| `oak_stats` | Get project intelligence statistics |
| `oak_activity` | View tool execution history for a session |
| `oak_archive_memories` | Archive observations from the search index |
| `oak_fetch` | Fetch full content for specific chunk IDs |
| `oak_nodes` | List connected team relay nodes |

**Team federation:** When [Team Sync](/team/sync/) is active, several tools (`oak_search`, `oak_context`, `oak_sessions`, `oak_memories`, `oak_stats`) support `include_network=true` to fan out queries across all connected nodes on the same project. Tools like `oak_resolve_memory`, `oak_activity`, and `oak_archive_memories` support `node_id` to target a specific remote node.

**Swarm tools:** When connected to a [Swarm](/swarm/), additional tools (`swarm_search`, `swarm_fetch`, `swarm_nodes`, `swarm_status`) are available for cross-project queries across different projects.

See the [MCP Tools Reference](/team/mcp/) for full parameter documentation.
