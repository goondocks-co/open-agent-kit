---
title: Memory
description: How the Memory Engine captures, stores, and recalls project knowledge.
sidebar:
  order: 3
---

The core power of Codebase Intelligence is its ability to learn and remember. This page explains how the **Memory Engine** works and how it integrates with your existing tools.

## The Memory Lifecycle

1. **Observation**: An event occurs (a bug is fixed, a decision is made)
2. **Capture**: The event is captured either automatically via hooks or manually through the dashboard
3. **Storage**: The observation is stored in the Activity Log (SQLite) and embedded into the Vector Store
4. **Recall**: When a future task matches the semantic context of the memory, it is proactively retrieved and injected into the agent's prompt

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `gotcha` | Non-obvious behaviors or warnings | "The API requires basic auth, not bearer token." |
| `decision` | Architectural or design choices | "We use polling instead of websockets for stability." |
| `bug_fix` | Solutions to specific errors | "Fixed race condition in transaction handler." |
| `discovery` | Facts learned about the codebase | "The user table is sharded by region." |
| `session_summary` | High-level summary of a coding session | "Implemented user login flow." |

## Auto-Capture Hooks

OAK CI **automatically installs** hooks into supported agents during `oak init`. No manual configuration is required.

### Supported Integrations

| Agent | Capability | Integration Method |
|-------|------------|--------------------|
| **Claude Code** | Full (Input/Output Analysis) | `settings.json` hook scripts (auto-synced) |
| **Codex CLI** | Partial (Output Analysis) | OTLP log events & Notify |
| **Cursor** | Full (Input/Output Analysis) | `.cursor/hooks.json` (auto-synced) |
| **Gemini CLI** | Full (Input/Output Analysis) | `settings.json` hook scripts (auto-synced) |
| **OpenCode** | Partial (Output Analysis) | TypeScript plugin (auto-installed) |
| **Copilot** | Limited (Cloud-only) | `.github/hooks/hooks.json` |
| **Windsurf** | Partial (Output Analysis) | `.windsurf/hooks.json` (auto-synced) |
| **MCP Agents** | Tools + Context | Auto-registered MCP Server |

### Post-Tool Analysis
When using fully supported agents (Claude/Gemini), the CI daemon analyzes every tool output (e.g., `Bash`, `Edit`, `Write`).

- **Error Detection**: If a command fails, it records the error as a `gotcha`
- **Fix Detection**: If you `Edit` a file after an error, it correlates the fix with the error and stores a `bug_fix`
- **Summarization**: At the end of a session, a local LLM summarizes the work and updates the project memory

## Managing Memories

**The dashboard is the primary way to manage memories.** Open the **Activity > Memories** tab to:

- **Browse** all stored memories by type, date, or content
- **Search** memories using natural language queries
- **Delete** memories that are outdated or incorrect

<!-- TODO: screenshot of memories tab -->

Agents can also store memories programmatically using the MCP tools. See [MCP Tools](/open-agent-kit/api/mcp-tools/) for details on `oak_remember`.

## Rebuilding Memory Embeddings

If you change embedding models, rebuild the memory index from the dashboard's **[DevTools](/open-agent-kit/features/codebase-intelligence/devtools/)** page — click **Rebuild Memories** to re-embed all observations from SQLite into ChromaDB.

## Agent Hooks API

If you are building your own tools or agent integrations, you can hit the hook endpoints directly:

```http
POST /api/oak/ci/hooks/session/start
{
  "agent": "custom-agent",
  "project_path": "/path/to/project"
}
```

See the [API Reference](/open-agent-kit/features/codebase-intelligence/developer-api/) for more details.
