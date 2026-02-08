---
title: Documentation Agent
description: An autonomous agent that maintains project documentation using Codebase Intelligence.
---

The Documentation Agent is an autonomous AI agent that maintains project documentation by analyzing your code, session history, and CI memories. It runs locally within OAK's daemon, powered by the Claude Agent SDK.

Unlike external coding agents that you interact with directly, the Documentation Agent works autonomously — you give it a task, and it explores your codebase, gathers context from CI, and writes or updates documentation on its own.

## How It Works

The agent has access to both your filesystem (read/write markdown files) and CI's full knowledge base:

| CI Tool | What the agent uses it for |
|---------|---------------------------|
| `ci_search` | Semantic search across code, memories, and plans |
| `ci_memories` | Filter observations by type (gotcha, decision, discovery, bug_fix, trade_off) |
| `ci_sessions` | Access recent coding sessions with summaries |
| `ci_project_stats` | Get codebase structure and statistics |

For every task, the agent follows a consistent workflow:

1. **Gather context** — Query CI for relevant plans, code, memories, and sessions
2. **Extract insights** — Identify gotchas to surface as warnings, decisions to explain "why", recent changes to document
3. **Write documentation** — Create CI-enriched docs with code references and source links
4. **Verify claims** — Confirm code examples exist, configuration options match reality, file paths are valid

## Built-in Tasks

OAK ships four built-in tasks that cover the most common documentation needs. Run them from the Agents page in the dashboard, or trigger them via the API.

### README & Overview

Maintains your project's `README.md` by exploring the actual codebase and enriching it with CI context.

**What it does:**
- Reads the existing README completely
- Explores entry points, CLI, API, and features
- Enriches with gotchas, decisions, and recent discoveries from CI
- Updates incrementally — keeps what works, updates what changed
- Verifies code examples and installation commands still work

**CI queries:** Project stats, recent sessions, discoveries, and gotchas.

### Feature Documentation

Discovers and documents all features in your project. Finds undocumented features, updates outdated docs, and creates CI-enriched feature documentation.

**What it does:**
- Discovers features via glob patterns, manifests, and CI search
- Checks existing docs to identify gaps and stale content
- For each undocumented feature: explores implementation, gathers plans/decisions/gotchas, writes documentation
- Includes "Known Issues & Gotchas" and "Design Decisions" sections sourced directly from CI memories

**CI queries:** Feature implementations, design plans, decisions, gotchas, discoveries, and recent sessions.

### Changelog Generator

Generates changelog entries from CI session history. Can be scheduled to run weekly or monthly.

**What it does:**
- Reads existing `CHANGELOG.md` for format and last entry date
- Gathers session history since the last entry
- Categorizes changes: Added, Changed, Fixed, Deprecated, Removed, Security
- Enriches with gotchas as notes and decisions for context
- Links each entry back to the originating session

**Output format:** [Keep a Changelog](https://keepachangelog.com) — entries link to session titles in the dashboard.

### Architecture Documentation

Documents your project's architecture by exploring the codebase structure and enriching it with CI decisions and trade-offs. Creates ADR (Architecture Decision Record) files.

**What it does:**
- Checks for existing architecture docs (never overwrites historical ADRs)
- Explores directory structure, key abstractions, dependencies, and patterns
- Gathers the "why" from CI — decisions, trade-offs, gotchas, plans
- Creates new ADRs for undocumented decisions
- Updates the architecture overview if the structure changed

**CI queries:** Decisions and trade-offs (required), plans, gotchas, project stats, and recent sessions.

## Output Location

Generated documentation is written to `oak/docs/` (git-tracked), with two exceptions:

| Task | Output |
|------|--------|
| README & Overview | `README.md` (project root) |
| Changelog Generator | `CHANGELOG.md` (project root) |
| Feature Documentation | `oak/docs/` |
| Architecture Documentation | `oak/docs/` |

Custom tasks default to `oak/docs/` unless their `maintained_files` specify a different path.

## Running Tasks

1. Navigate to the **Agents** page in the dashboard
2. Select a task from the task list
3. Click **Run** to start the agent
4. Watch progress in real time — output streams as the agent works
5. View completed runs in the **Run History** section

### Run History

Every agent run is recorded with:
- **Status** — Running, completed, failed, or cancelled
- **Output** — Full agent output including any generated files
- **Timing** — Start time, duration, and token usage
- **Cancellation** — Cancel a running agent at any time

## Scheduling

Tasks can be scheduled to run automatically using cron expressions. Manage schedules from the Agents page in the dashboard.

**Common schedules:**

| Cron | Frequency |
|------|-----------|
| `0 9 * * MON` | Weekly on Monday at 9 AM |
| `0 0 * * *` | Daily at midnight |
| `0 0 1 * *` | Monthly on the 1st |
| `0 */6 * * *` | Every 6 hours |

## Custom Tasks

You can create custom tasks that the Documentation Agent will automatically pick up. Custom tasks live in `oak/agents/` (git-tracked) and use the same YAML format as built-in tasks.

### Task File Format

```yaml
name: my-task                           # Lowercase with hyphens
display_name: "My Custom Task"
agent_type: documentation
description: "What this task does"

default_task: |
  The prompt that the agent will execute.
  Can be multi-line markdown with detailed instructions.

execution:
  timeout_seconds: 300                  # 1–3600 (default: 600)
  max_turns: 50                         # 1–500 (default: 100)
  permission_mode: acceptEdits          # default | acceptEdits

maintained_files:
  - path: "{project_root}/README.md"
    purpose: "Project overview"
    auto_create: false

ci_queries:
  discovery:
    - tool: ci_sessions
      limit: 15
      include_summary: true
      purpose: "Recent work context"
  context:
    - tool: ci_memories
      filter: gotcha
      limit: 10
      purpose: "Known issues"

schedule:                               # Optional
  cron: "0 9 * * MON"
  description: "Weekly Monday morning"

schema_version: 1
```

### Task Schema Reference

#### Top-level fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier. Lowercase, hyphens only (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`). Max 50 chars. |
| `display_name` | Yes | Human-readable name for the dashboard. Max 100 chars. |
| `agent_type` | Yes | Must be `documentation`. |
| `description` | No | Brief description shown in the task list. |
| `default_task` | Yes | The prompt the agent executes. Multi-line markdown. |
| `schema_version` | No | Must be `1` if specified. |

#### `execution`

| Field | Default | Description |
|-------|---------|-------------|
| `timeout_seconds` | 600 | Wall-clock timeout. Range: 60–3600. |
| `max_turns` | 100 | Maximum API round-trips. Range: 1–500. |
| `permission_mode` | `acceptEdits` | `default` (approve all), `acceptEdits` (auto-accept file changes). |

#### `maintained_files[]`

| Field | Required | Description |
|-------|----------|-------------|
| `path` | Yes | File path or glob. Supports `{project_root}` placeholder. |
| `purpose` | No | What this file is for. |
| `naming` | No | Naming convention for new files (e.g., `docs/{feature_name}.md`). |
| `auto_create` | No | Create the file if it doesn't exist. Default: `false`. |

#### `ci_queries`

Queries are organized into phases: `discovery`, `context`, and `verification`. Each phase contains a list of query templates.

| Field | Required | Description |
|-------|----------|-------------|
| `tool` | Yes | `ci_search`, `ci_memories`, `ci_sessions`, or `ci_project_stats`. |
| `query_template` | No | Search query. Supports `{placeholders}`. |
| `search_type` | No | For `ci_search`: `all`, `code`, `memory`, or `plans`. |
| `filter` | No | For `ci_memories`: `gotcha`, `decision`, `discovery`, `bug_fix`, or `trade_off`. |
| `limit` | No | Max results (1–100). Default: 10. |
| `include_summary` | No | For `ci_sessions`: include session summaries. |
| `min_confidence` | No | `high`, `medium`, `low`, or `all`. Default: `medium`. |
| `purpose` | No | Documents why this query is needed. |
| `required` | No | Fail the task if no results. Default: `false`. |

#### `output_requirements`

| Field | Description |
|-------|-------------|
| `required_sections[]` | Sections the output must include. Each has `name`, `source` (`code`, `sessions`, `memories`), and `description`. |
| `format` | Output format: `keepachangelog`, `adr`, `readme-badges`, `api-reference`. |
| `link_sources` | Include links to CI data sources. |

#### `style`

| Field | Description |
|-------|-------------|
| `tone` | `technical`, `concise`, `welcoming`, or `formal`. |
| `include_examples` | Include code examples. |
| `link_code_files` | Link to referenced code files. |
| `code_link_format` | `relative` (path only) or `line` (path:line). |
| `link_sessions` | Link to sessions in the dashboard. |
| `conventions[]` | List of writing style rules (e.g., "Use imperative mood"). |

#### `schedule`

| Field | Required | Description |
|-------|----------|-------------|
| `cron` | Yes | Standard cron expression: `minute hour day month weekday`. |
| `description` | No | Human-readable schedule description. |

### Creating a Custom Task

1. Create a YAML file in `oak/agents/`:

```bash
ls oak/agents/   # Verify directory exists
```

2. Write your task definition following the schema above.

3. The daemon automatically discovers the new task — no restart needed.

:::tip
You can also create tasks from the dashboard. Click **Create Task** on the Agents page to start from a built-in template, then customize it.
:::

### Overriding Built-in Tasks

To customize a built-in task, create a file in `oak/agents/` with the same `name` as the built-in task. Your custom version takes precedence.

For example, to customize the README task:

```yaml
# oak/agents/readme.yaml
name: readme                            # Same name = overrides built-in
display_name: "Custom README Update"
agent_type: documentation
description: "README updater with project-specific instructions"

default_task: |
  Update README.md with focus on:
  1. Verify the installation section matches current dependencies
  2. Update the Quick Start with a working example
  3. Add an FAQ section based on recent gotchas

  Keep the existing badges and license section unchanged.

execution:
  timeout_seconds: 300
  max_turns: 50
  permission_mode: acceptEdits

maintained_files:
  - path: "{project_root}/README.md"
    purpose: "Project overview"

ci_queries:
  discovery:
    - tool: ci_sessions
      limit: 15
      include_summary: true
      purpose: "Recent changes"
    - tool: ci_project_stats
      purpose: "Project overview"
  context:
    - tool: ci_memories
      filter: gotcha
      limit: 5
      purpose: "Recent gotchas for FAQ"

schedule:
  cron: "0 9 * * MON"
  description: "Weekly Monday morning"

schema_version: 1
```

## Provider Configuration

The Documentation Agent uses the shared OAK Agents provider configured in **Agents page → Settings** (`/agents/settings`).

See [OAK Agents](/open-agent-kit/features/codebase-intelligence/agents/#provider-configuration) for supported providers and setup details.

## Security

The Documentation Agent operates within strict boundaries:

**Allowed file access:**
- `oak/docs/**`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/**`, and any `*.md` file

**Blocked file access:**
- `.env`, `*.pem`, `*.key`, `*.crt`, `**/credentials*`, `**/secrets*`

**Allowed tools:**
- `Read`, `Write`, `Edit`, `Glob`, `Grep` (filesystem)
- `ci_search`, `ci_memories`, `ci_sessions`, `ci_project_stats` (CI data)

**Blocked tools:**
- `Bash` (no shell access)
