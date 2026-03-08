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

The daemon only allows requests from loopback origins (`http://localhost:{port}` and `http://127.0.0.1:{port}`). External origins are blocked by the CORS middleware. To access tools from another machine, connect to a [team](/team/sync/) to expose MCP tools through the relay.

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
| `POST` | `/api/search/network` | Federated search across connected relay nodes |
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
| `POST` | `/api/activity/sessions/{id}/related` | Add a related session relationship |
| `DELETE` | `/api/activity/sessions/{id}/related/{rid}` | Remove a related session relationship |
| `GET` | `/api/activity/sessions/{id}/suggested-related` | Suggested related sessions (semantic) |
| `POST` | `/api/activity/sessions/{id}/complete` | Manually complete a session |
| `POST` | `/api/activity/sessions/{id}/regenerate-summary` | Regenerate summary |
| `DELETE` | `/api/activity/sessions/{id}` | Delete session (cascade) |
| `GET` | `/api/activity/plans` | List plans |
| `POST` | `/api/activity/plans/{id}/refresh` | Refresh plan content from disk |
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
| `GET` | `/api/schedules` | List schedules |
| `GET` | `/api/schedules/{task_name}` | Get schedule details |
| `POST` | `/api/schedules` | Create a schedule |
| `PUT` | `/api/schedules/{task_name}` | Update schedule |
| `DELETE` | `/api/schedules/{task_name}` | Delete schedule |
| `POST` | `/api/schedules/{task_name}/run` | Trigger a schedule manually |
| `POST` | `/api/schedules/sync` | Remove orphaned schedules |
| `GET` | `/api/agents/settings` | Get agent settings |
| `PUT` | `/api/agents/settings` | Update agent settings |

### ACP Interactive Sessions

Endpoints for the [Agent Client Protocol](/team/acp/) integration. These manage long-lived interactive sessions between ACP-compatible editors and the OAK daemon.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/acp/sessions` | Create a new interactive session |
| `POST` | `/api/acp/sessions/{id}/prompt` | Send a prompt (streams NDJSON execution events) |
| `POST` | `/api/acp/sessions/{id}/cancel` | Cancel an in-progress prompt |
| `PUT` | `/api/acp/sessions/{id}/mode` | Set permission mode (code, architect, ask) |
| `PUT` | `/api/acp/sessions/{id}/focus` | Set agent focus (oak, documentation, analysis, engineering, maintenance) |
| `POST` | `/api/acp/sessions/{id}/approve-plan` | Approve a proposed plan |
| `DELETE` | `/api/acp/sessions/{id}` | Close and clean up a session |

### ACP Server Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/acp/status` | Check if ACP server is running |
| `POST` | `/api/acp/start` | Start the ACP server subprocess |
| `POST` | `/api/acp/stop` | Stop the ACP server subprocess |
| `GET` | `/api/acp/logs` | Get recent ACP server logs |

### Governance

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/governance/config` | Get governance configuration |
| `PUT` | `/api/governance/config` | Save governance configuration |
| `GET` | `/api/governance/audit` | Query audit events with filters |
| `GET` | `/api/governance/audit/summary` | Aggregate audit stats for dashboard |
| `POST` | `/api/governance/audit/prune` | Manually prune old audit events |
| `POST` | `/api/governance/test` | Test a hypothetical tool call against policy |

### Release Channel

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/channel` | Get current channel, version, and PyPI availability |
| `POST` | `/api/channel/switch` | Switch release channel (stable/beta) |

### Notifications

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/oak/ci/notify` | Handle agent notification events (e.g., Codex notify) |

### OTEL (OpenTelemetry)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/logs` | OTLP HTTP logs receiver endpoint |

### Index

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/index/status` | Get codebase index status |
| `POST` | `/api/index/rebuild` | Trigger full index rebuild |
| `POST` | `/api/index/build` | Trigger index build |

### Swarm Configuration

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/swarm/join` | Join a swarm (save URL/token and connect) |
| `POST` | `/api/swarm/leave` | Leave the swarm (clear config and disconnect) |
| `GET` | `/api/swarm/status` | Get swarm connection status |
| `GET` | `/api/swarm/daemon/status` | Check if swarm daemon is running |
| `POST` | `/api/swarm/daemon/launch` | Create swarm daemon config and start |

### Backup

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/backup/status` | Check backup status and list backups |
| `POST` | `/api/backup/create` | Create database backup |
| `POST` | `/api/backup/restore` | Restore from backup |
| `POST` | `/api/backup/restore-all` | Restore all team backups |

### Cloud Relay

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/cloud/start` | Deploy/connect cloud relay (scaffold, deploy, connect) |
| `POST` | `/api/cloud/stop` | Stop cloud relay and clear local connection |
| `GET` | `/api/cloud/preflight` | Check scaffold/auth/deploy readiness |
| `PUT` | `/api/cloud/settings` | Update relay URL and token settings |
| `POST` | `/api/cloud/connect` | Connect daemon to an existing relay |
| `POST` | `/api/cloud/disconnect` | Disconnect daemon from relay |
| `GET` | `/api/cloud/status` | Get relay connection status |

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

### MCP

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/mcp/tools` | List available MCP tools |
| `POST` | `/api/mcp/call` | Call an MCP tool (query param: `tool_name`) |

### Team

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/team/status` | Team sync connection status |
| `GET` | `/api/team/members` | List online team members |
| `GET` | `/api/team/config` | Get team sync configuration |
| `POST` | `/api/team/config` | Update team sync configuration |

See also the [MCP Tools Reference](/team/mcp/) for the MCP protocol tools exposed to agents.
