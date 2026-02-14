---
title: MCP Tools Reference
description: Reference documentation for the oak_search, oak_remember, oak_context, and oak_resolve_memory MCP tools.
---

The Codebase Intelligence daemon exposes four tools via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). These tools are automatically registered when you run `oak init` and are available to any MCP-compatible agent.

## oak_search

Search the codebase, project memories, and past implementation plans using semantic similarity.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | — | Natural language search query (e.g., "authentication middleware") |
| `search_type` | string | No | `"all"` | What to search: `"all"`, `"code"`, `"memory"`, or `"plans"` |
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
