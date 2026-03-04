# Querying Oak Databases

Query the Oak CI SQLite database directly for detailed data analysis, browsing, and investigation.

## When to Use

Oak CI has three layers of team, each with a distinct purpose:

1. **MCP tools** (`oak_search`, `oak_remember`, `oak_context`) — the primary interface for everyday coding. Use for semantic search, storing memories, and getting task context during normal workflows.
2. **Semantic search workflows** (finding-related-code, impact-analysis) — guided workflows for code-level intelligence like finding similar implementations or assessing refactoring risk.
3. **Direct SQL queries** — for when the user wants to **understand their data** at a deeper level than the daemon dashboard or MCP tools provide.

Use direct SQL when browsing the dashboard is insufficient and detailed analysis is needed:
- Aggregations and statistics (agent costs, tool usage counts, activity trends over time)
- Cross-table investigation (trace a memory back to its originating session and prompt)
- Browsing and filtering structured data (all gotchas, recent sessions with error counts)
- Agent run history with cost and token breakdowns
- Schedule status and overdue tasks
- Full-text keyword search (FTS5 `MATCH` — different from semantic vector search)
- When the CI daemon is not running (SQLite is always readable directly)

**Never write to the database directly.** Always use `-readonly` with `sqlite3`. To store memories, use `oak_remember` or `oak-dev ci remember`.

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

## Session Statuses

The `status` column in `sessions`: `active`, `completed`, `abandoned`

## Agent Run Statuses

The `status` column in `agent_runs`: `pending`, `running`, `completed`, `failed`, `cancelled`, `timeout`

## MCP Tools and CLI Reference

For everyday team (semantic search, storing memories, retrieving context), always prefer the MCP tools or equivalent CLI commands:

| MCP Tool | CLI Equivalent | Purpose |
|----------|---------------|---------|
| `oak_search` | `oak-dev ci search "query"` | Semantic vector search (code, memories, plans) |
| `oak_remember` | `oak-dev ci remember "observation"` | Store a memory or learning |
| `oak_context` | `oak-dev ci context "task"` | Get task-relevant context |
| — | `oak-dev ci memories --type gotcha` | Browse memories by type |
| — | `oak-dev ci sessions` | List session summaries |

Check daemon status with `oak-dev team status`. Start with `oak-dev team start` if needed.

## Important Notes

- Always use `-readonly` flag with `sqlite3` to prevent accidental writes
- The database uses WAL mode — safe to read while the daemon is writing
- Epoch timestamps are Unix seconds — use `datetime(col, 'unixepoch', 'localtime')` to format
- FTS5 tables (`activities_fts`, `memories_fts`) use `MATCH` syntax, not `LIKE`
- JSON columns (`tool_input`, `files_affected`, `files_created`) can be queried with `json_extract()`

## Additional Resources

### Reference Files

For complete schema DDL and advanced query patterns, consult:
- **`schema.md`** — Full CREATE TABLE statements, indexes, FTS5 tables, and triggers
- **`queries.md`** — Advanced query cookbook with joins, aggregations, and debugging queries
- **`analysis-playbooks.md`** — Structured multi-query workflows for usage, productivity, codebase activity, and prompt quality analysis

### Automated Analysis

For automated analysis that runs these queries and produces reports, use the analysis agent:

```bash
oak-dev ci agent run usage-report              # Cost and token usage trends
oak-dev ci agent run productivity-report       # Session quality and error rates
oak-dev ci agent run codebase-activity-report  # File hotspots and tool patterns
oak-dev ci agent run prompt-analysis           # Prompt quality and recommendations
```

Reports are written to `oak/insights/` (git-tracked, team-shareable).
