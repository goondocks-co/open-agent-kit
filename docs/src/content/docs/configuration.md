---
title: Configuration
description: How OAK is configured — via the dashboard and project files.
---

:::note[Configure from the dashboard]
Most Codebase Intelligence settings are managed through the **[Dashboard](/open-agent-kit/features/codebase-intelligence/dashboard/)** — open it with `oak ci start --open` and click **Configuration** in the sidebar. The dashboard provides a visual interface for embedding providers, summarization, exclusions, and more.
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
  auto_number: true
  number_format: sequential
  validate_on_create: true
```

## Codebase Intelligence Settings

The CI daemon stores its configuration in `.oak/ci/config.yaml`. **You don't need to edit this file directly** — the dashboard reads and writes it for you.

Settings managed via the dashboard:
- **Embedding provider and model** (Ollama, LM Studio, OpenAI-compatible)
- **Summarization provider and model** (optional)
- **Session quality thresholds** (minimum activities, stale timeout)
- **Log rotation** (max file size, backup count)
- **Directory exclusions** (patterns to skip during indexing)

See the [Dashboard](/open-agent-kit/features/codebase-intelligence/dashboard/) page for details on each setting.

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
See [Codebase Intelligence Configuration](/open-agent-kit/features/codebase-intelligence/configuration/#cli-command-for-managed-integrations) for details.

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
| `oak_search` | Semantic search over code, memories, and plans |
| `oak_remember` | Store observations for future sessions |
| `oak_context` | Get relevant context for the current task |

See the [MCP Tools Reference](/open-agent-kit/api/mcp-tools/) for full parameter documentation.
