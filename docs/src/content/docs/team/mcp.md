---
title: MCP
description: Team MCP tools and cloud agent configuration for the Team relay.
sidebar:
  order: 1
---

When connected to a team, the relay exposes your local MCP tools through a Streamable HTTP endpoint. Any AI agent that supports MCP can connect — Claude.ai, ChatGPT, Claude Code, Cursor, Windsurf, and more.

## What You Need

After connecting to a team (via the dashboard or `oak team cloud-init`), you need two values:

- **MCP Server URL**: `https://<your-worker>.workers.dev/mcp`
- **Agent Token**: Displayed on the Teams page (masked with reveal/copy buttons)

Also stored in `.oak/config.yaml` and `oak/cloud-relay/wrangler.toml`.

## MCP Config File (mcp.json)

Many MCP-compatible clients read configuration from a `mcp.json` file:

```json
{
  "mcpServers": {
    "oak-team": {
      "url": "https://<team-worker>.workers.dev/mcp",
      "headers": {
        "Authorization": "Bearer <agent_token>"
      }
    }
  }
}
```

Place the file in your project root for per-project config, or in your home directory for global config.

| Client | Config File Location |
|--------|---------------------|
| **Claude Code** | `.claude/mcp.json` |
| **Cursor** | `.cursor/mcp.json` |
| **Windsurf** | `.windsurf/mcp.json` |
| **VS Code Copilot** | `.vscode/mcp.json` |

:::tip
The dashboard generates this JSON config block with your actual URL and token pre-filled. Click the copy button to grab it.
:::

## Claude.ai

1. Open Claude.ai and go to **Settings**
2. Navigate to the **MCP Servers** section
3. Click **Add MCP Server**
4. Enter:
   - **Name**: A descriptive label (e.g., "My Project — OAK")
   - **URL**: `https://<your-worker>.workers.dev/mcp`
   - **Authentication**: Bearer token — paste your `agent_token`
5. Save the configuration

Claude.ai connects to your relay and discovers available tools. Verify by asking Claude to list available tools or run a code search.

## ChatGPT

1. Open ChatGPT and go to **Settings** > **Connected Tools**
2. Click **Add Tool** and select MCP
3. Enter the MCP server URL: `https://<your-worker>.workers.dev/mcp`
4. Authenticate using your agent token when prompted

Refer to OpenAI's documentation for the current MCP configuration interface.

## Other MCP-Compatible Agents

Any AI agent that supports MCP Streamable HTTP can connect:

| Setting | Value |
|---------|-------|
| **URL** | `https://<your-worker>.workers.dev/mcp` |
| **Transport** | Streamable HTTP (POST) |
| **Auth header** | `Authorization: Bearer <agent_token>` |
| **Content-Type** | `application/json` |

## Agent Token

The **agent token** authenticates cloud AI agents to the relay's MCP endpoint.

- Generated automatically during team deployment (`oak team cloud-init`)
- Stored in `.oak/config.yaml` and the Worker's secrets (encrypted at rest on Cloudflare)
- Accepted in two formats: `Authorization: Bearer <token>` (standard) or `Authorization: <token>` (raw)
- All cloud agents share the same agent token

To rotate the token and revoke all agent access, see [Token Rotation](/team/sync/#token-rotation).

## Testing with curl

Verify the relay is working before configuring a cloud agent:

```bash
# List available tools
curl -X POST https://<your-worker>.workers.dev/mcp \
  -H "Authorization: Bearer <agent_token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

A successful response returns a JSON-RPC result with the tool list. If the local daemon is not connected, you'll receive an error indicating the instance is offline.

### Test a Tool Call

```bash
curl -X POST https://<your-worker>.workers.dev/mcp \
  -H "Authorization: Bearer <agent_token>" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"oak_search","arguments":{"query":"authentication"}},"id":2}'
```

### MCP Inspector

For interactive testing, use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) — a visual tool for browsing and calling MCP server tools. Point it at your relay endpoint and provide the agent token.

## Multiple Agents

You can register the same relay with multiple cloud agents simultaneously. All agents share the same agent token and have access to the same set of tools. The Worker handles concurrent requests transparently.

---

## Tools

The Team daemon exposes the following tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). These are automatically registered when you run `oak init` and are available to any MCP-compatible agent — both local (via `oak team mcp`) and cloud (via the relay).

| Tool | Purpose |
|------|---------|
| [`oak_search`](#oak_search) | Semantic search across code, memories, plans, and sessions |
| [`oak_remember`](#oak_remember) | Store observations for future sessions |
| [`oak_context`](#oak_context) | Get task-relevant context |
| [`oak_resolve_memory`](#oak_resolve_memory) | Mark observations as resolved |
| [`oak_sessions`](#oak_sessions) | List recent coding sessions |
| [`oak_memories`](#oak_memories) | Browse stored memories |
| [`oak_stats`](#oak_stats) | Get project intelligence statistics |
| [`oak_activity`](#oak_activity) | View tool execution history |
| [`oak_archive_memories`](#oak_archive_memories) | Archive observations from search index |
| [`oak_fetch`](#oak_fetch) | Fetch full content for specific chunk IDs |
| [`oak_nodes`](#oak_nodes) | List connected team relay nodes |

### Federation Parameters

When [Team Sync](/team/sync/) is active, several tools support **federated queries** across all connected nodes (developers and machines on the *same* project):

| Parameter | Type | Available On | Description |
|-----------|------|--------------|-------------|
| `include_network` | boolean | `oak_search`, `oak_context`, `oak_sessions`, `oak_memories`, `oak_stats` | Fan out the query to all connected nodes and merge results |
| `node_id` | string | `oak_resolve_memory`, `oak_activity`, `oak_archive_memories` | Target a specific remote node (use `oak_nodes` to discover nodes) |

:::tip[Discover nodes first]
Use `oak_nodes` to list connected relay nodes and their capabilities before targeting them with `node_id` in other tools.
:::

:::note[Team vs Swarm]
Team federation fans out to nodes on the *same* project. For cross-project queries, see [Swarm MCP Configuration](/swarm/mcp/).
:::

---

## oak_search

Search the codebase, project memories, and past implementation plans using semantic similarity.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | — | Natural language search query (e.g., "authentication middleware") |
| `search_type` | string | No | `"all"` | What to search: `"all"`, `"code"`, `"memory"`, `"plans"`, or `"sessions"` |
| `include_resolved` | boolean | No | `false` | Include resolved/superseded memories in results |
| `limit` | integer | No | `10` | Maximum results to return (1–50) |
| `include_network` | boolean | No | `false` | Also search across connected team nodes. Not available for `"code"` searches. |

### Response

Returns ranked results with relevance scores. Each result includes:
- **Code results**: file path, line range, function name, code snippet, similarity score
- **Memory results**: observation text, memory type, context, similarity score
- **Plan results**: plan content, associated session, similarity score

### Examples

```json
{
  "query": "database connection handling",
  "search_type": "code",
  "limit": 5
}
```

```json
{
  "query": "why did we choose SQLite",
  "search_type": "memory"
}
```

---

## oak_remember

Store an observation, decision, or learning for future sessions. Use this when you discover something important about the codebase that would help in future work.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `observation` | string | Yes | — | The observation or learning to store |
| `memory_type` | string | No | `"discovery"` | Type of observation (see table below) |
| `context` | string | No | — | Related file path or additional context |

### Memory Types

| Type | When to use | Example |
|------|------------|---------|
| `gotcha` | Non-obvious behaviors or warnings | "The API requires basic auth, not bearer token." |
| `bug_fix` | Solutions to specific errors | "Fixed race condition in transaction handler." |
| `decision` | Architectural or design choices | "We use polling instead of websockets for stability." |
| `discovery` | Facts learned about the codebase | "The user table is sharded by region." |
| `trade_off` | Compromises made and why | "Chose eventual consistency for performance." |

### Response

Returns confirmation with the observation ID.

### Examples

```json
{
  "observation": "The auth module requires Redis to be running",
  "memory_type": "gotcha",
  "context": "src/auth/handler.py"
}
```

```json
{
  "observation": "We chose SQLite over Postgres for simplicity and local-first design",
  "memory_type": "decision"
}
```

---

## oak_context

Get relevant context for your current task. Call this when starting work on something to retrieve related code, past decisions, and applicable project guidelines.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task` | string | Yes | — | Description of what you're working on |
| `current_files` | array of strings | No | — | Files currently being viewed/edited |
| `max_tokens` | integer | No | `2000` | Maximum tokens of context to return |
| `include_network` | boolean | No | `false` | Also fetch memories from connected team nodes. Code context stays local-only. |

### Response

Returns a curated set of context optimized for the task, including:
- Relevant code snippets
- Related memories (gotchas, decisions, discoveries)
- Applicable project guidelines

### Examples

```json
{
  "task": "Implement user authentication with JWT",
  "current_files": ["src/auth/handler.py", "src/middleware/auth.py"],
  "max_tokens": 3000
}
```

```json
{
  "task": "Fix the failing database migration test"
}
```

---

## oak_resolve_memory

Mark a memory observation as resolved or superseded. Use this after completing work that addresses a gotcha, fixing a bug that was tracked as an observation, or when a newer observation replaces an older one.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | string | Yes | — | The observation ID to resolve |
| `status` | string | No | `"resolved"` | New status: `"resolved"` or `"superseded"` |
| `reason` | string | No | — | Optional reason for resolution |
| `node_id` | string | No | — | Target a specific remote node (use `oak_nodes` to discover nodes) |

### Response

Returns confirmation of the status update.

### Examples

```json
{
  "id": "obs_abc123",
  "status": "resolved",
  "reason": "Fixed in commit abc123"
}
```

```json
{
  "id": "obs_def456",
  "status": "superseded"
}
```

:::tip
Observation IDs are included in search results and injected context, so agents have what they need to call `oak_resolve_memory` without extra lookups.
:::

---

## oak_sessions

List recent coding sessions with their status and summaries. Use this to understand what work has been done recently and find session IDs for deeper investigation with `oak_activity`.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | `10` | Maximum sessions to return (1–20) |
| `include_summary` | boolean | No | `true` | Include session summaries in output |
| `include_network` | boolean | No | `false` | Also fetch sessions from connected team nodes |

### Response

Returns a list of recent sessions with:
- Session ID (UUID)
- Status (active, completed, stale)
- Agent type (claude, cursor, gemini, etc.)
- Start time and last activity
- Summary (if `include_summary` is true)

### Examples

```json
{
  "limit": 5,
  "include_summary": true
}
```

```json
{
  "limit": 20,
  "include_summary": false
}
```

---

## oak_memories

Browse stored memories and observations. Use this to review what the system has learned about the codebase, including gotchas, bug fixes, decisions, discoveries, and trade-offs.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `memory_type` | string | No | — | Filter by type: `"gotcha"`, `"bug_fix"`, `"decision"`, `"discovery"`, `"trade_off"` |
| `limit` | integer | No | `20` | Maximum memories to return (1–100) |
| `status` | string | No | `"active"` | Filter by status: `"active"`, `"resolved"`, `"superseded"` |
| `include_resolved` | boolean | No | `false` | Include all statuses regardless of status filter |
| `include_network` | boolean | No | `false` | Also fetch memories from connected team nodes |

### Response

Returns a list of memories with:
- Observation ID
- Memory type
- Observation text
- Context (file path, if any)
- Status
- Created timestamp

### Examples

```json
{
  "memory_type": "gotcha",
  "limit": 15
}
```

```json
{
  "memory_type": "decision",
  "status": "active",
  "limit": 30
}
```

---

## oak_stats

Get project intelligence statistics including indexed code chunks, unique files, memory count, and observation status breakdown. Use this for a quick health check of the team intelligence system.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `include_network` | boolean | No | `false` | Also fetch stats from connected team nodes |

### Response

Returns project statistics including:
- Total indexed code chunks
- Unique files indexed
- Total memory observations
- Observation breakdown by status (active, resolved, superseded)

### Example

```json
{}
```

---

## oak_activity

View tool execution history for a specific session. Shows what tools were used, which files were affected, success/failure status, and output summaries. Use `oak_sessions` first to find session IDs.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | Yes | — | The session ID to get activities for |
| `tool_name` | string | No | — | Filter activities by tool name |
| `limit` | integer | No | `50` | Maximum activities to return (1–200) |
| `node_id` | string | No | — | Target a specific remote node (use `oak_nodes` to discover nodes) |

### Response

Returns a list of tool executions with:
- Tool name (Read, Edit, Write, Bash, etc.)
- File path (if applicable)
- Success/failure status
- Timestamp
- Output summary

### Examples

```json
{
  "session_id": "8430042a-1b01-4c86-8026-6ede46cd93d9",
  "limit": 100
}
```

```json
{
  "session_id": "8430042a-1b01-4c86-8026-6ede46cd93d9",
  "tool_name": "Bash",
  "limit": 20
}
```

---

## oak_archive_memories

Archive observations from the ChromaDB search index. Archived observations remain in SQLite for historical queries but stop appearing in vector search results. Use this for bulk cleanup of stale resolved or superseded observations.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ids` | array of strings | No | — | Specific observation IDs to archive |
| `status_filter` | string | No | — | Archive by status: `"resolved"`, `"superseded"`, or `"both"` |
| `older_than_days` | integer | No | — | Only archive observations older than this many days (minimum 1) |
| `dry_run` | boolean | No | `false` | If true, return count without actually archiving |
| `node_id` | string | No | — | Target a specific remote node (use `oak_nodes` to discover nodes) |

:::note
You must provide either `ids` or `status_filter` — at least one selection criterion is required.
:::

### Response

Returns the number of observations archived (or that would be archived in dry-run mode).

### Examples

```json
{
  "status_filter": "both",
  "older_than_days": 30,
  "dry_run": true
}
```

```json
{
  "ids": ["obs_abc123", "obs_def456"]
}
```

---

## oak_fetch

Fetch the full content for specific code chunk IDs returned by `oak_search`. Use this to retrieve the complete code snippet when search results only include a preview.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `ids` | array of strings | Yes | — | Chunk IDs to fetch (from search results) |

### Response

Returns the full content for each requested chunk, including file path, line range, and complete code text.

### Example

```json
{
  "ids": ["chunk_abc123", "chunk_def456"]
}
```

---

## oak_nodes

List connected team relay nodes. Shows machine IDs, online status, OAK version, and capabilities for each node. Use this to discover available nodes before targeting them with `node_id` in other tools.

### Parameters

This tool takes no parameters.

### Response

Returns a list of connected nodes with:
- Machine ID
- Online status
- OAK version
- Capabilities (`federated_tools_v1`)

### Example

```json
{}
```
