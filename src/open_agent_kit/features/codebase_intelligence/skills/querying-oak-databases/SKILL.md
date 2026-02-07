---
name: querying-oak-databases
description: This skill should be used when the user asks to "query the Oak database", "check session history", "look up activity logs", "check agent runs", "query activities.db", "find what I worked on", "show recent sessions", "check agent costs", "what files were edited", "browse memories by type", or needs to run SQL queries against the Oak CI SQLite database for browsing, aggregation, or investigation. Do NOT use this skill for semantic search or storing memories — use the oak_search, oak_remember, and oak_context MCP tools (or `oak ci` CLI commands) for those operations instead.
allowed-tools: Bash, Read
user-invocable: true
---

# Querying Oak Databases

Query the Oak CI SQLite database directly for detailed data analysis, browsing, and investigation. This skill provides the full schema and ready-to-use queries so the agent can query immediately without discovering the database first.

## When to Use This Skill

Oak CI has three layers of codebase intelligence, each with a distinct purpose:

1. **MCP tools** (`oak_search`, `oak_remember`, `oak_context`) — the primary interface for everyday coding. Use for semantic search, storing memories, and getting task context during normal workflows.
2. **Code skills** (`finding-related-code`, `analyzing-code-change-impacts`) — guided workflows for code-level intelligence like finding similar implementations or assessing refactoring risk.
3. **This skill** — for when the user wants to **understand their data** at a deeper level than the daemon dashboard or MCP tools provide.

Use this skill when browsing the dashboard is insufficient and detailed analysis is needed:
- Aggregations and statistics (agent costs, tool usage counts, activity trends over time)
- Cross-table investigation (trace a memory back to its originating session and prompt)
- Browsing and filtering structured data (all gotchas, recent sessions with error counts)
- Agent run history with cost and token breakdowns
- Schedule status and overdue tasks
- Full-text keyword search (FTS5 `MATCH` — different from semantic vector search)
- When the CI daemon is not running (SQLite is always readable directly)

**Never write to the database directly.** Always use `-readonly` with `sqlite3`. To store memories, use `oak_remember` or `oak ci remember`.

## Database Location

The Oak CI database is a SQLite file at a known, fixed path relative to the project root:

```
.oak/ci/activities.db
```

To confirm it exists:

```bash
ls -la .oak/ci/activities.db
```

## Quick Start

Open the database in read-only mode to avoid accidental writes:

```bash
sqlite3 -readonly .oak/ci/activities.db
```

For one-off queries from the command line:

```bash
sqlite3 -readonly .oak/ci/activities.db "SELECT count(*) FROM sessions;"
```

For formatted output with headers:

```bash
sqlite3 -readonly -header -column .oak/ci/activities.db "YOUR QUERY HERE"
```

## Core Tables Overview

<!-- BEGIN GENERATED CORE TABLES -->
| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `memory_observations` | Extracted memories/learnings | `observation`, `memory_type`, `context`, `tags`, `importance` |
| `sessions` | Coding sessions (launch to exit) | `id`, `agent`, `status`, `summary`, `title`, `started_at`, `created_at_epoch` |
| `prompt_batches` | User prompts within sessions | `session_id`, `user_prompt`, `classification`, `response_summary` |
| `activities` | Raw tool executions | `session_id`, `tool_name`, `file_path`, `success`, `error_message` |
| `agent_runs` | CI agent executions | `agent_name`, `task`, `status`, `result`, `cost_usd`, `turns_used` |
| `session_link_events` | Session linking analytics | `session_id`, `event_type`, `old_parent_id`, `new_parent_id` |
| `session_relationships` | Semantic session relationships | `session_a_id`, `session_b_id`, `relationship_type`, `similarity_score` |
| `agent_schedules` | Cron scheduling state | `task_name`, `cron_expression`, `enabled`, `last_run_at`, `next_run_at` |
<!-- END GENERATED CORE TABLES -->

### Memory Types

The `memory_type` column in `memory_observations` uses these values:
- `gotcha` — Non-obvious behavior or quirk
- `bug_fix` — Solution to a bug with root cause
- `decision` — Architectural/design decision with rationale
- `discovery` — General insight about the codebase
- `trade_off` — Trade-off that was made and why
- `session_summary` — LLM-generated session summary

### Session Statuses

The `status` column in `sessions`: `active`, `completed`, `abandoned`

### Agent Run Statuses

The `status` column in `agent_runs`: `pending`, `running`, `completed`, `failed`, `cancelled`, `timeout`

## Essential Queries

### Recent Sessions

```sql
SELECT id, agent, title, status,
       datetime(created_at_epoch, 'unixepoch', 'localtime') as started,
       prompt_count, tool_count
FROM sessions
ORDER BY created_at_epoch DESC
LIMIT 10;
```

### Session Detail (prompts and what happened)

```sql
SELECT prompt_number, classification,
       substr(user_prompt, 1, 120) as prompt_preview,
       substr(response_summary, 1, 120) as response_preview,
       activity_count
FROM prompt_batches
WHERE session_id = 'SESSION_ID'
ORDER BY prompt_number;
```

### What Files Were Touched in a Session

```sql
SELECT DISTINCT file_path, tool_name, count(*) as times
FROM activities
WHERE session_id = 'SESSION_ID' AND file_path IS NOT NULL
GROUP BY file_path, tool_name
ORDER BY times DESC;
```

### Recent Memories (all types)

```sql
SELECT memory_type, substr(observation, 1, 150) as observation,
       context,
       datetime(created_at_epoch, 'unixepoch', 'localtime') as created
FROM memory_observations
ORDER BY created_at_epoch DESC
LIMIT 20;
```

### Memories by Type

```sql
SELECT substr(observation, 1, 200) as observation, context,
       datetime(created_at_epoch, 'unixepoch', 'localtime') as created
FROM memory_observations
WHERE memory_type = 'gotcha'
ORDER BY created_at_epoch DESC
LIMIT 20;
```

### Full-Text Search on Memories

```sql
SELECT m.memory_type, m.observation, m.context
FROM memory_observations m
JOIN memories_fts fts ON m.rowid = fts.rowid
WHERE memories_fts MATCH 'authentication'
ORDER BY rank
LIMIT 10;
```

### Agent Run History

```sql
SELECT agent_name, task, status, turns_used,
       printf('$%.4f', cost_usd) as cost,
       datetime(created_at_epoch, 'unixepoch', 'localtime') as created
FROM agent_runs
ORDER BY created_at_epoch DESC
LIMIT 10;
```

### Scheduled Tasks

```sql
SELECT task_name, enabled, cron_expression, description,
       datetime(last_run_at_epoch, 'unixepoch', 'localtime') as last_run,
       datetime(next_run_at_epoch, 'unixepoch', 'localtime') as next_run
FROM agent_schedules
ORDER BY next_run_at_epoch;
```

## MCP Tools and CLI Reference

For everyday codebase intelligence (semantic search, storing memories, retrieving context), always prefer the MCP tools or equivalent CLI commands:

| MCP Tool | CLI Equivalent | Purpose |
|----------|---------------|---------|
| `oak_search` | `oak ci search "query"` | Semantic vector search (code, memories, plans) |
| `oak_remember` | `oak ci remember "observation"` | Store a memory or learning |
| `oak_context` | `oak ci context "task"` | Get task-relevant context |
| — | `oak ci memories --type gotcha` | Browse memories by type |
| — | `oak ci sessions` | List session summaries |

Check daemon status with `oak ci status`. Start with `oak ci start` if needed.

## Important Notes

- Always use `-readonly` flag with `sqlite3` to prevent accidental writes
- The database uses WAL mode — safe to read while the daemon is writing
- Epoch timestamps are Unix seconds — use `datetime(col, 'unixepoch', 'localtime')` to format
- FTS5 tables (`activities_fts`, `memories_fts`) use `MATCH` syntax, not `LIKE`
- JSON columns (`tool_input`, `files_affected`, `files_created`) can be queried with `json_extract()`

## Additional Resources

### Reference Files

For complete schema DDL and advanced query patterns, consult:
- **`references/schema.md`** — Full CREATE TABLE statements, indexes, FTS5 tables, and triggers
- **`references/queries.md`** — Advanced query cookbook with joins, aggregations, and debugging queries
- **`references/analysis-playbooks.md`** — Structured multi-query workflows for usage, productivity, codebase activity, and prompt quality analysis

### Automated Analysis

For automated analysis that runs these queries and produces reports, use the analysis agent:

```bash
oak ci agent run usage-report              # Cost and token usage trends
oak ci agent run productivity-report       # Session quality and error rates
oak ci agent run codebase-activity-report  # File hotspots and tool patterns
oak ci agent run prompt-analysis           # Prompt quality and recommendations
```

Reports are written to `oak/insights/` (git-tracked, team-shareable).
