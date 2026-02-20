---
title: MCP Tools Reference
description: Reference documentation for the MCP tools exposed by the Codebase Intelligence daemon.
---

The Codebase Intelligence daemon exposes eight tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). These tools are automatically registered when you run `oak init` and are available to any MCP-compatible agent.

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

## oak_search

Search the codebase, project memories, and past implementation plans using semantic similarity.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | — | Natural language search query (e.g., "authentication middleware") |
| `search_type` | string | No | `"all"` | What to search: `"all"`, `"code"`, `"memory"`, `"plans"`, or `"sessions"` |
| `include_resolved` | boolean | No | `false` | Include resolved/superseded memories in results |
| `limit` | integer | No | `10` | Maximum results to return (1–50) |

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

Get project intelligence statistics including indexed code chunks, unique files, memory count, and observation status breakdown. Use this for a quick health check of the codebase intelligence system.

### Parameters

This tool takes no parameters.

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
