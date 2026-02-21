---
title: Maintenance Agent
description: An autonomous agent that keeps OAK's memory store healthy through consolidation, cleanup, and data hygiene.
---

The Maintenance Agent is OAK's "brain maintenance" system — an autonomous AI agent that keeps your memory store healthy by consolidating duplicate observations, resolving stale memories, and maintaining data hygiene between ChromaDB and SQLite.

Unlike the other OAK agents which produce outputs (documentation, reports, code), the Maintenance Agent works *on* the CI system itself. It's the only agent with **memory_write** access, allowing it to create, resolve, and archive observations directly.

## How It Works

The agent has read-only file access (to check if referenced files still exist) and full CI access including the ability to mutate observations:

| CI Tool | What the agent uses it for |
|---------|---------------------------|
| `ci_search` | Find semantically similar observations for deduplication |
| `ci_memories` | List observations by type and status |
| `ci_sessions` | Access recent sessions for pattern detection |
| `ci_project_stats` | Get baseline metrics before/after maintenance |
| `ci_query` | Direct SQL for detailed breakdowns and analysis |
| `ci_remember` | Create new synthesized observations |
| `ci_resolve` | Mark observations as resolved or superseded |
| `ci_archive` | Remove old observations from the search index |

**Key distinction:** This is the only agent that can modify the memory store. All other agents are read-only with respect to CI data.

## Built-in Tasks

OAK ships two built-in maintenance tasks. Run them from the Agents page in the dashboard, or schedule them to run automatically.

### Memory Consolidation

The "sleep cycle" for OAK's brain. Consolidates duplicate observations, resolves irrelevant memories, and synthesizes cross-session patterns into new wisdom.

**What it does:**

1. **Inventory** — Gets baseline counts by type and status
2. **Duplicate Detection** — For each memory type, finds semantically similar observations using vector search and groups them into clusters
3. **Consolidation** — For each cluster:
   - If truly redundant (same insight, different wording): keeps the most comprehensive version, supersedes the rest
   - If complementary (different facets of same insight): creates a merged observation, supersedes the originals
4. **Relevance Review** — Finds observations referencing files that no longer exist or have substantially changed, resolves them with reasoning
5. **Pattern Recognition** — Analyzes recent sessions for recurring themes not yet captured, creates new observations for strong patterns
6. **Decisions Summary** — Reports all consolidation decisions, relevance resolutions, new wisdom created, and before/after metrics

**Output:** Captured in the run record (no files written to project).

**Suggested schedule:** Weekly Sunday at 3 AM — `0 3 * * SUN`

### Data Hygiene

Health checks and archival for the memory store. Analyzes store health, archives old resolved/superseded observations from the search index, and verifies ChromaDB/SQLite sync.

**What it does:**

1. **Health Inventory** — Builds a comprehensive health picture:
   - Observations by status and type
   - Recent observation activity (30-day trend)
   - Session counts and average observations per session
   - Code chunks indexed
2. **Archive Stale Search Entries** — Removes old resolved/superseded observations from ChromaDB (they remain in SQLite as history):
   - Resolved observations older than 30 days
   - Superseded observations older than 14 days
3. **Sync Verification** — Checks consistency between ChromaDB and SQLite, flags any discrepancies
4. **Health Summary** — Reports store health, archival actions, sync status, and recommendations

**Output:** Captured in the run record (no files written to project).

**Suggested schedule:** Weekly Wednesday at 4 AM — `0 4 * * WED`

## Running Tasks

1. Navigate to the **Agents** page in the dashboard
2. Select a maintenance task from the task list
3. Click **Run** to start the agent
4. Watch progress in real time — the agent reports its decisions as it works
5. View completed runs in the **Run History** section

### Run History

Every agent run is recorded with:
- **Status** — Running, completed, failed, or cancelled
- **Output** — Full agent output including decisions and health reports
- **Timing** — Start time, duration, and token usage
- **Cancellation** — Cancel a running agent at any time

## Scheduling

Maintenance tasks are ideal for automated scheduling. They run quietly in the background and keep your memory store healthy without manual intervention.

**Recommended schedules:**

| Task | Cron | Frequency | Rationale |
|------|------|-----------|-----------|
| Memory Consolidation | `0 3 * * SUN` | Weekly Sunday 3 AM | Run after a week of development, before the new week starts |
| Data Hygiene | `0 4 * * WED` | Weekly Wednesday 4 AM | Mid-week health check, catches issues before they accumulate |

Enable schedules from the Agents page in the dashboard by editing the task's schedule settings.

## When to Run Maintenance

**Memory Consolidation** is most valuable when:
- You've had many sessions on related features (lots of potential duplicates)
- Session summaries are capturing similar gotchas repeatedly
- Search results feel noisy with redundant observations
- You want to synthesize wisdom from a sprint or project phase

**Data Hygiene** is most valuable when:
- You notice search results including old, irrelevant observations
- The DevTools stats show a large gap between SQLite and ChromaDB counts
- You've recently refactored or deleted significant code
- It's been a while since the last health check

## Custom Tasks

You can create custom maintenance tasks that the agent will automatically pick up. Custom tasks live in `oak/agents/` (git-tracked) and use the same YAML format as built-in tasks.

### Example: Targeted File Cleanup

```yaml
# oak/agents/file-cleanup.yaml
name: file-cleanup
display_name: "File-Specific Cleanup"
agent_type: maintenance
description: "Resolve observations for deleted or moved files"

default_task: |
  Find and resolve observations referencing files that no longer exist.

  1. Use ci_query to get all observations with non-null context (file paths)
  2. For each unique file path, use Glob to check if the file exists
  3. For files that don't exist:
     - Use ci_resolve to mark observations as resolved
     - Reason: "Referenced file no longer exists"
  4. Report: files checked, observations resolved, any issues

execution:
  timeout_seconds: 300
  max_turns: 50

schema_version: 1
```

### Key Fields for Maintenance Tasks

| Field | Required | Description |
|-------|----------|-------------|
| `agent_type` | Yes | Must be `maintenance` |
| `default_task` | Yes | The methodology prompt — what the agent should do |

:::caution[Memory Write Access]
Maintenance tasks have `memory_write` access by default. They can create, resolve, and archive observations. Test custom tasks carefully, and consider using `dry_run` parameters where available.
:::

## Provider Configuration

The Maintenance Agent uses the shared OAK Agents provider configured in **Agents page → Settings** (`/agents/settings`).

See [OAK Agents](/open-agent-kit/features/codebase-intelligence/agents/#provider-configuration) for supported providers and setup details.

## Security

The Maintenance Agent operates within strict boundaries:

**Allowed file access:**
- Read-only access to check if referenced files exist
- Uses `Glob`, `Grep`, `Read` tools

**Blocked file access:**
- `.env`, `*.pem`, `*.key` — sensitive files are never accessible

**Blocked tools:**
- `Bash` (no shell access)
- `Task` (no sub-agent spawning)
- `Write`, `Edit` (no file modifications)

**CI access:**
- Full read access (search, memories, sessions, stats, SQL queries)
- Write access for observations only (`ci_remember`, `ci_resolve`, `ci_archive`)
