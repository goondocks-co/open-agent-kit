---
title: API Reference
description: REST API reference for the CI daemon (experimental).
sidebar:
  order: 12
---

:::caution[Experimental]
The API is currently used internally by the daemon UI and agent hooks. Endpoints may change without notice. We envision enabling other integrations to read and enhance CI functionality in the future.
:::

The CI daemon exposes a FastAPI REST interface at `http://localhost:{port}/api`.

## Base URL

The port is dynamic per project. Find it with:
```bash
oak ci port
```

## CORS

The daemon only allows requests from `localhost` and active tunnel URLs. External origins are blocked by the CORS middleware. To access the API from another machine, you'll need an active tunnel (see [Teams — Sharing](/open-agent-kit/features/codebase-intelligence/teams/#sharing)).

## Endpoints

### Health & Status

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Basic liveness check |
| `GET` | `/api/status` | Detailed daemon status and process info |
| `GET` | `/api/logs` | Get daemon/hook logs with pagination |

### Search & Memory

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/search` | Semantic search. Query params: `q`, `limit`, `type` |
| `POST` | `/api/search` | JSON body search |
| `POST` | `/api/fetch` | Retrieve full content for specific chunk IDs |
| `POST` | `/api/remember` | Store a memory observation |
| `POST` | `/api/context` | Get relevant context for a task |
| `GET` | `/api/memories` | List memories with filtering and pagination |
| `GET` | `/api/memories/tags` | List all unique memory tags |
| `POST` | `/api/memories/{id}/archive` | Archive a memory |
| `POST` | `/api/memories/{id}/unarchive` | Unarchive a memory |
| `PUT` | `/api/memories/{id}/status` | Update observation lifecycle status |
| `DELETE` | `/api/memories/{id}` | Delete a memory |
| `POST` | `/api/memories/bulk` | Bulk operations on memories |
| `POST` | `/api/memories/bulk-resolve` | Bulk-resolve observations by session or IDs |

### Agent Hooks

Hook endpoints receive data from AI coding agents. The prefix is `/api/oak/ci/`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/oak/ci/session-start` | Initialize session context |
| `POST` | `/api/oak/ci/prompt-submit` | Capture user prompt |
| `POST` | `/api/oak/ci/before-prompt` | Pre-prompt context injection |
| `POST` | `/api/oak/ci/post-tool-use` | Report tool execution |
| `POST` | `/api/oak/ci/post-tool-use-failure` | Report failed tool execution |
| `POST` | `/api/oak/ci/stop` | Finalize session and trigger summarization |
| `POST` | `/api/oak/ci/session-end` | Session end event |
| `POST` | `/api/oak/ci/subagent-start` | Sub-agent spawned |
| `POST` | `/api/oak/ci/subagent-stop` | Sub-agent completed |
| `POST` | `/api/oak/ci/agent-thought` | Agent reasoning capture |
| `POST` | `/api/oak/ci/pre-compact` | Before context compaction |
| `POST` | `/api/oak/ci/{event}` | Catch-all for other events |

### Activity

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/activity/sessions` | List sessions |
| `GET` | `/api/activity/sessions/{id}` | Get session details |
| `GET` | `/api/activity/sessions/{id}/activities` | List session activities |
| `GET` | `/api/activity/sessions/{id}/lineage` | Get session lineage |
| `GET` | `/api/activity/sessions/{id}/related` | Get related sessions |
| `POST` | `/api/activity/sessions/{id}/complete` | Manually complete a session |
| `POST` | `/api/activity/sessions/{id}/regenerate-summary` | Regenerate summary |
| `DELETE` | `/api/activity/sessions/{id}` | Delete session (cascade) |
| `GET` | `/api/activity/plans` | List plans |
| `GET` | `/api/activity/stats` | Get activity statistics |
| `GET` | `/api/activity/search` | Full-text search activities |

### Configuration

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/config` | Get current runtime config |
| `PUT` | `/api/config` | Update configuration |
| `POST` | `/api/config/test` | Test embedding provider connection |
| `POST` | `/api/config/test-summarization` | Test summarization provider |
| `POST` | `/api/config/discover-context` | Discover model context window |
| `GET` | `/api/config/exclusions` | Get exclusion patterns |
| `PUT` | `/api/config/exclusions` | Update exclusion patterns |
| `POST` | `/api/config/exclusions/reset` | Reset exclusions to defaults |
| `GET` | `/api/providers/models` | List embedding models from provider |
| `GET` | `/api/providers/summarization-models` | List LLM models |
| `POST` | `/api/restart` | Reload config and reinitialize embedding chain |
| `POST` | `/api/self-restart` | Trigger graceful daemon process restart |

### Agents

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/agents` | List agents, templates, and tasks |
| `POST` | `/api/agents/tasks/{name}/run` | Run a task |
| `GET` | `/api/agents/runs` | List agent runs |
| `GET` | `/api/agents/runs/{id}` | Get run details |
| `POST` | `/api/agents/runs/{id}/cancel` | Cancel a running agent |
| `GET` | `/api/agents/schedules` | List task schedules |
| `PUT` | `/api/agents/schedules/{name}` | Update schedule |
| `GET` | `/api/agents/settings` | Get agent settings |
| `PUT` | `/api/agents/settings` | Update agent settings |

### Backup

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/backup/status` | Check backup status and list backups |
| `POST` | `/api/backup/create` | Create database backup |
| `POST` | `/api/backup/restore` | Restore from backup |
| `POST` | `/api/backup/restore-all` | Restore all team backups |

### Tunnel

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/tunnel/start` | Start sharing tunnel |
| `POST` | `/api/tunnel/stop` | Stop sharing tunnel |
| `GET` | `/api/tunnel/status` | Get tunnel status |

### DevTools

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/devtools/rebuild-index` | Rebuild codebase index |
| `POST` | `/api/devtools/reset-processing` | Reset processing state |
| `POST` | `/api/devtools/trigger-processing` | Trigger background processing |
| `POST` | `/api/devtools/compact-chromadb` | Compact ChromaDB |
| `POST` | `/api/devtools/rebuild-memories` | Re-embed memories |
| `POST` | `/api/devtools/database-maintenance` | SQLite/ChromaDB maintenance |
| `POST` | `/api/devtools/regenerate-summaries` | Regenerate missing summaries |
| `POST` | `/api/devtools/cleanup-minimal-sessions` | Remove low-quality sessions |
| `POST` | `/api/devtools/reprocess-observations` | Reprocess observation extraction |
| `POST` | `/api/devtools/resolve-stale-observations` | Find and resolve stale observations |
| `GET` | `/api/devtools/memory-stats` | Get detailed memory statistics |

See also the [MCP Tools Reference](/open-agent-kit/api/mcp-tools/) for the MCP protocol tools exposed to agents.
