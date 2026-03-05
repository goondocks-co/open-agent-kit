---
name: oak
description: >-
  Find out what happened, what was decided, and what depends on what in your
  codebase. Use this skill whenever you need to: recall past decisions or
  discussions ("what did we decide about X?"), check what might break before
  refactoring ("what depends on this module?"), find conceptually similar code
  that grep would miss ("all the retry/backoff logic"), look up past bugs,
  gotchas, or learnings, query session history or agent run costs, store
  observations about the codebase, or understand how components connect
  end-to-end. Powered by semantic search, memory lookup, and direct SQL against
  the Oak CI database (.oak/ci/activities.db). Also use when the user mentions
  oak_search, oak_context, oak_remember, oak_resolve_memory, or asks to run
  queries against activities.db or oak.
allowed-tools: Bash, Read
user-invocable: true
---

# OAK

Prefer MCP tools (`oak_search`, `oak_context`, `oak_remember`, `oak_resolve_memory`) over CLI when available. Fall back to CLI or direct SQL for queries not covered by MCP tools. If `.oak/ci/activities.db` does not exist, inform the user to run `{oak-cli-command} team start` first.

## Quick Start

### MCP tools (preferred when available)

```
# Semantic search for code or memories
oak_search(query="form validation logic", search_type="code")
oak_search(query="authentication refactor decision", search_type="memory")

# Impact analysis — get context for a specific file
oak_context(task="impact of changes to executor", files=["src/features/agent_runtime/executor.py"])

# Store an observation
oak_remember(observation="The backup dir uses a 3-tier priority", memory_type="decision")

# Mark a resolved gotcha
oak_resolve_memory(id="<uuid from oak_search>")
```

### CLI fallback

```bash
# Semantic search
{oak-cli-command} ci search "retry with exponential backoff" --type code

# Browse memories by type
{oak-cli-command} ci memories --type decision

# Get impact context for a specific file
{oak-cli-command} ci context "impact of changes" -f src/services/auth.py
```

### Direct SQL (for aggregations, history, custom queries)

```bash
# Recent sessions
sqlite3 -readonly -header -column .oak/ci/activities.db \
  "SELECT id, agent, title, status, datetime(created_at_epoch, 'unixepoch', 'localtime') as started FROM sessions ORDER BY created_at_epoch DESC LIMIT 5;"

# Query anything
sqlite3 -readonly -header -column .oak/ci/activities.db "SELECT count(*) FROM sessions;"
```

## Commands Reference

### CLI commands

| Command | Purpose |
|---------|---------|
| `{oak-cli-command} ci search "query" --type code` | Semantic vector search for code |
| `{oak-cli-command} ci search "query" --type memory` | Semantic search for memories |
| `{oak-cli-command} ci search "query" -n 20` | Broader search with more results |
| `{oak-cli-command} ci context "task" -f <file>` | Get context for current work |
| `{oak-cli-command} ci remember "observation"` | Store a memory (NOT via SQL) |
| `{oak-cli-command} ci memories --type gotcha` | Browse memories by type |
| `{oak-cli-command} ci memories --status active` | Browse memories by lifecycle status |
| `{oak-cli-command} ci resolve <id>` | Mark observation as resolved |
| `{oak-cli-command} ci resolve --session <id>` | Bulk-resolve all observations from a session |
| `{oak-cli-command} ci sessions` | List session summaries |
| `{oak-cli-command} team status` | Check daemon status |

### MCP tools

| MCP Tool | CLI Equivalent | Purpose |
|----------|---------------|---------|
| `oak_search` | `{oak-cli-command} ci search "query"` | Semantic vector search |
| `oak_remember` | `{oak-cli-command} ci remember "observation"` | Store a memory |
| `oak_context` | `{oak-cli-command} ci context "task"` | Get task-relevant context |
| `oak_resolve_memory` | `{oak-cli-command} ci resolve <uuid>` | Mark observation resolved/superseded (UUID from `oak_search`) |

### Direct SQL

```bash
sqlite3 -readonly -header -column .oak/ci/activities.db "YOUR QUERY HERE"
```

## When to Use What

| Need | Tool | Example |
|------|------|---------|
| Find similar implementations | `{oak-cli-command} ci search --type code` | "retry with exponential backoff" |
| Understand component relationships | `{oak-cli-command} ci context` | "how auth middleware relates to session handling" |
| Assess refactoring risk | `{oak-cli-command} ci search --type code -n 20` | "PaymentProcessor error handling" |
| Find past decisions/gotchas | `{oak-cli-command} ci search --type memory` | "gotchas with auth changes" |
| Recall previous discussions | `sqlite3 -readonly` | `SELECT title, summary FROM sessions WHERE ...` |
| Find what was done before | `{oak-cli-command} ci memories` / `sqlite3` | "what did we decide about caching?" |
| Query session history | `sqlite3 -readonly` | `SELECT * FROM sessions ORDER BY ...` |
| Aggregate usage stats | `sqlite3 -readonly` | `SELECT agent_name, sum(cost_usd) FROM agent_runs ...` |
| Resolve stale observations | `{oak-cli-command} ci resolve` | After completing work that addresses a gotcha |
| Find unresolved planning items | `sqlite3 -readonly` | `SELECT ... WHERE status='active' AND session_origin_type='planning'` |
| Run automated analysis | `{oak-cli-command} ci agent run` | `{oak-cli-command} ci agent run usage-report` |

## Why Semantic Search Over Grep

| Grep | Semantic Search |
|------|-----------------|
| Finds "UserService" literally | Finds code about user management regardless of naming |
| Misses synonyms (auth vs authentication) | Understands concepts are related |
| Can't find "conceptually similar" code | Groups code by purpose, not text |
| No relevance ranking | Returns most relevant first |

## Core Tables Overview

<!-- BEGIN GENERATED CORE TABLES -->
| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `memory_observations` | Extracted memories/learnings | `observation`, `memory_type`, `status`, `context`, `tags`, `importance`, `session_origin_type` |
| `sessions` | Coding sessions (launch to exit) | `id`, `agent`, `status`, `summary`, `title`, `title_manually_edited`, `started_at`, `created_at_epoch` |
| `prompt_batches` | User prompts within sessions | `session_id`, `user_prompt`, `classification`, `response_summary` |
| `activities` | Raw tool executions | `session_id`, `tool_name`, `file_path`, `success`, `error_message` |
| `agent_runs` | CI agent executions | `agent_name`, `task`, `status`, `result`, `cost_usd`, `turns_used` |
| `session_link_events` | Session linking analytics | `session_id`, `event_type`, `old_parent_id`, `new_parent_id` |
| `session_relationships` | Semantic session relationships | `session_a_id`, `session_b_id`, `relationship_type`, `similarity_score` |
| `agent_schedules` | Cron scheduling state | `task_name`, `cron_expression`, `enabled`, `additional_prompt`, `last_run_at`, `next_run_at` |
| `resolution_events` | Cross-machine resolution propagation | `observation_id`, `action`, `source_machine_id`, `applied`, `content_hash` |
| `governance_audit_events` | Audit trail for governance actions | `session_id`, `agent`, `tool_name`, `action`, `rule_id`, `enforcement_mode`, `created_at` |
| `team_outbox` | Outbound sync queue for team relay | `event_type`, `payload`, `source_machine_id`, `content_hash`, `status`, `created_at` |
| `team_pull_cursor` | Inbound sync cursor per relay | `server_url`, `cursor_value`, `updated_at` |
| `team_sync_state` | Team relay sync metadata | `key`, `value`, `updated_at` |
| `team_reconcile_state` | Per-machine reconciliation tracking | `machine_id`, `last_reconcile_at`, `last_hash_count`, `last_missing_count` |
<!-- END GENERATED CORE TABLES -->

### Memory Types

The `memory_type` column in `memory_observations` uses these values:
- `gotcha` — Non-obvious behavior or quirk
- `bug_fix` — Solution to a bug with root cause
- `decision` — Architectural/design decision with rationale
- `discovery` — General insight about the codebase
- `trade_off` — Trade-off that was made and why
- `session_summary` — LLM-generated session summary

### Observation Status

The `status` column tracks lifecycle state:
- `active` — Current and relevant (default for all new observations)
- `resolved` — Issue was addressed in a later session
- `superseded` — Replaced by a newer, more accurate observation

### Resolving Observations

When `oak_search` or `oak_context` surfaces a gotcha, bug_fix, or discovery that you then address during your session, **resolve it** so future sessions don't see stale guidance:

1. Note the observation UUID from the `oak_search` results (e.g., `"id": "8430042a-1b01-4c86-8026-6ede46cd93d9"`).
2. After completing the fix or addressing the issue, call:
   - **MCP:** `oak_resolve_memory(id="8430042a-1b01-4c86-8026-6ede46cd93d9")`
   - **CLI:** `{oak-cli-command} ci resolve 8430042a-1b01-4c86-8026-6ede46cd93d9`
3. For superseded observations (replaced by a better one), use `status="superseded"`.

**When to resolve:**
- You fixed a bug that was tracked as a `bug_fix` observation
- You addressed a `gotcha` (e.g., refactored the problematic code)
- A `discovery` about a problem is no longer accurate after your changes
- A `decision` was reversed or replaced by a new decision

**When NOT to resolve:**
- The observation is still accurate even after your changes
- You only partially addressed the issue
- The observation is a permanent architectural insight (e.g., "service X uses eventual consistency")

### Session Origin Types

The `session_origin_type` column classifies how the session that created the observation operated:
- `planning` — Planning-phase session (high read:edit ratio, few modifications)
- `investigation` — Exploration/debugging session (many reads, minimal edits)
- `implementation` — Active coding session (significant file modifications)
- `mixed` — Combined activity patterns

Planning/investigation observations are automatically capped at importance 5.

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

### What Files Were Touched in a Session

```sql
SELECT DISTINCT file_path, tool_name, count(*) as times
FROM activities
WHERE session_id = 'SESSION_ID' AND file_path IS NOT NULL
GROUP BY file_path, tool_name
ORDER BY times DESC;
```

### Recent Memories

```sql
SELECT memory_type, substr(observation, 1, 150) as observation,
       context,
       datetime(created_at_epoch, 'unixepoch', 'localtime') as created
FROM memory_observations
ORDER BY created_at_epoch DESC
LIMIT 20;
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

### Full-Text Search on Memories

```sql
SELECT m.memory_type, m.observation, m.context
FROM memory_observations m
JOIN memories_fts fts ON m.rowid = fts.rowid
WHERE memories_fts MATCH 'authentication'
ORDER BY rank
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

### Observation Lifecycle Status

```sql
SELECT status, count(*) as count
FROM memory_observations
GROUP BY status;
```

### Active Observations from Planning Sessions

```sql
SELECT substr(observation, 1, 120) as observation, memory_type,
       context, session_origin_type,
       datetime(created_at_epoch, 'unixepoch', 'localtime') as created
FROM memory_observations
WHERE status = 'active' AND session_origin_type = 'planning'
ORDER BY created_at_epoch DESC
LIMIT 20;
```

### Resolution Provenance (what resolved what)

```sql
SELECT m.id, substr(m.observation, 1, 100) as observation,
       m.resolved_by_session_id, s.title as resolving_session,
       m.resolved_at
FROM memory_observations m
LEFT JOIN sessions s ON m.resolved_by_session_id = s.id
WHERE m.status = 'resolved'
ORDER BY m.resolved_at DESC
LIMIT 10;
```

## Important Notes

- Always use `-readonly` flag with `sqlite3` to prevent accidental writes
- The database uses WAL mode — safe to read while the daemon is writing
- Epoch timestamps are Unix seconds — use `datetime(col, 'unixepoch', 'localtime')` to format
- FTS5 tables (`activities_fts`, `memories_fts`) use `MATCH` syntax, not `LIKE`
- JSON columns (`tool_input`, `files_affected`, `files_created`) can be queried with `json_extract()`
- Database location: `.oak/ci/activities.db`

## Automated Analysis

For automated analysis that runs queries and produces reports:

```bash
{oak-cli-command} ci agent run usage-report              # Cost and token usage trends
{oak-cli-command} ci agent run productivity-report       # Session quality and error rates
{oak-cli-command} ci agent run codebase-activity-report  # File hotspots and tool patterns
{oak-cli-command} ci agent run prompt-analysis           # Prompt quality and recommendations
```

Reports are written to `oak/insights/` (git-tracked, team-shareable).

## Deep Dives

Consult these reference documents when the task requires deeper detail:

- **`references/finding-related-code.md`** — Consult when searching for semantically related code across files or discovering component relationships
- **`references/impact-analysis.md`** — Consult before refactoring to assess blast radius and identify affected consumers
- **`references/querying-databases.md`** — Consult when writing custom SQL queries beyond the essential queries above
- **`references/schema.md`** — Consult for complete CREATE TABLE statements, indexes, and FTS5 table definitions (auto-generated)
- **`references/queries.md`** — Consult for advanced joins, aggregations, window functions, and debugging queries
- **`references/analysis-playbooks.md`** — Consult when running structured multi-query workflows for usage, productivity, or activity analysis
