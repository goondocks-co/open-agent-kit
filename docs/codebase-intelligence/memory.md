# Memory & Integration

The core power of Codebase Intelligence is its ability to learn and remember. This page explains how the **Memory Engine** works and how it integrates with your existing tools.

## The Memory Lifecycle

1.  **Observation**: An event occurs (a bug is fixed, a decision is made).
2.  **Capture**: The event is captured either manually or automatically via hooks.
3.  **Storage**: The observation is stored in the Activity Log (SQLite) and embedded into the Vector Store.
4.  **Recall**: When a future task matches the semantic context of the memory, it is proactively retrieved and injected into the agent's prompt.

## Rebuilding Memory Embeddings

If the memory embedding format changes (for example, adding path or tag labels), you must rebuild the memory index so existing observations are re-embedded. Use the DevTools endpoint `POST /api/devtools/rebuild-memories` (see `docs/codebase-intelligence/devtools.md`).

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `gotcha` | Non-obvious behaviors or warnings. | "The API requires basic auth, not bearer token." |
| `decision` | Architectural or design choices. | "We use polling instead of websockets for stability." |
| `bug_fix` | Solutions to specific errors. | "Fixed race condition in transaction handler." |
| `discovery` | Facts learned about the codebase. | "The user table is sharded by region." |
| `session_summary` | High-level summary of a coding session. | "Implemented user login flow." |

## Auto-Capture Hooks

OAK CI **automatically installs** hooks into supported agents during `oak init`. No manual configuration is required.

### Supported Integrations

| Agent | Capability | Integration Method |
|-------|------------|--------------------|
| **Claude Code** | Full (Input/Output Analysis) | `settings.json` hook scripts (auto-synced) |
| **Gemini CLI** | Full (Input/Output Analysis) | `settings.json` hook scripts (auto-synced) |
| **Cursor** | Context Injection | `.cursor/rules.md` (auto-managed) |
| **Copilot** | Context Injection | `.github/copilot-instructions.md` |
| **MCP Agents** | Tools + Context | Auto-registered MCP Server |

### Post-Tool Analysis
When using fully supported agents (Claude/Gemini), the CI daemon analyzes every tool output (e.g., `Bash`, `Edit`, `Write`).

-   **Error Detection**: If a command fails, it records the error as a `gotcha` (e.g., "Missing dependency").
-   **Fix Detection**: If you `Edit` a file after an error, it correlates the fix with the error and stores a `bug_fix`.
-   **Summarization**: At the end of a session, a local LLM summarizes the work and updates the project memory.

## Manual Memory

You can also explicitly teach the system using the CLI. This is useful for documenting decisions that aren't captured by code changes.

```bash
# Record a design decision
oak ci remember "We are deprecating the v1 API in favor of GraphQL" -t decision

# Record a known issue
oak ci remember "The test suite is flaky on Windows" -t gotcha

# Add context to a specific file
oak ci remember "This module is performance-critical" -f src/core/engine.py
```

## Agent Hooks API

If you are building your own tools or agent integrations, you can hit the hook endpoints directly:

```http
POST /api/hook/session-start
{
  "agent": "custom-agent",
  "project_path": "/path/to/project"
}
```

See the [Developer API](developer-api.md) reference for more details.
