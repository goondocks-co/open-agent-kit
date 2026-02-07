---
title: Analysis Agent
description: An autonomous agent that turns CI data into actionable insights about productivity, costs, and codebase health.
---

The Analysis Agent is an autonomous AI agent that queries your CI database directly to produce actionable reports about how your team uses AI coding agents. It analyzes session quality, tool usage, costs, prompt effectiveness, and codebase activity patterns — turning the development record into insights you can act on.

Where the [Documentation Agent](/open-agent-kit/features/codebase-intelligence/documentation-agent/) works with your filesystem and semantic search to maintain docs, the Analysis Agent works with **direct SQL access** to your CI database. It reads the raw data — every session, prompt, tool execution, memory, and agent run — and surfaces patterns that would be invisible otherwise.

## How It Works

The agent uses `ci_query` to execute read-only SQL against your `activities.db` database, then writes markdown reports to `oak/insights/`.

| CI Tool | What the agent uses it for |
|---------|---------------------------|
| `ci_query` | Execute read-only SQL against activities.db — the primary tool |
| `ci_memories` | Filter memories by type for context about decisions and gotchas |
| `ci_sessions` | Quick session overview with summaries |
| `ci_project_stats` | High-level codebase metrics |

For every task, the agent follows a consistent workflow:

1. **Run exploratory queries** — Start broad, understand the shape of the data
2. **Refine and aggregate** — Build specific queries for trends, distributions, and correlations
3. **Interpret results** — Turn raw numbers into insights with context
4. **Write the report** — Key findings first, data tables, trend analysis, and actionable recommendations
5. **Cite data** — Every claim is backed by actual query results, never fabricated

### Database Access

The Analysis Agent has access to these tables:

| Table | What it contains |
|-------|-----------------|
| `sessions` | Every coding session — agent type, status, summary, timestamps |
| `prompt_batches` | User prompts with classifications and response summaries |
| `activities` | Raw tool executions — file paths, success/failure, error messages |
| `memory_observations` | Extracted memories — gotchas, decisions, discoveries, trade-offs |
| `agent_runs` | CI agent executions with cost, token usage, and status |
| `agent_schedules` | Cron scheduling state for automated tasks |

All queries are **read-only** — INSERT, UPDATE, DELETE, and DROP are rejected. The agent cannot modify your data.

## Built-in Tasks

OAK ships four built-in analysis tasks. Run them from the Agents page in the dashboard, or trigger them via the API. All reports are written to `oak/insights/`.

### Usage & Cost Report

Tracks CI spend and activity volume by aggregating agent run costs, token usage, and session counts.

**What it analyzes:**
- Total cost by agent, with 30-day and all-time breakdowns
- Weekly cost trends (last 8 weeks)
- Average cost per run by agent type
- Input vs output token usage and ratios
- Session volume by agent and by week

**Output:** `oak/insights/usage-report.md`

**When to run:** Weekly or monthly to track spend and catch cost anomalies early.

### Productivity Analysis

Identifies productivity patterns by analyzing session quality, activity classifications, error rates, and time-of-day patterns.

**What it analyzes:**
- Session completion rates and quality tiers (high vs low activity)
- Prompt classification distribution — how time splits between exploration, implementation, debugging, and refactoring
- Classification trends over time (is the team spending more time debugging?)
- Error rates by tool, with trend analysis
- Productive time periods — activity by hour and day of week

**Output:** `oak/insights/productivity-report.md`

**When to run:** Weekly to track session quality trends and identify workflow improvements.

### Codebase Activity Report

Maps where work is happening across your codebase — file hotspots, tool usage patterns, and how project knowledge accumulates over time.

**What it analyzes:**
- Top 20 files by edit count and read count (hotspot detection)
- Files with the highest error rates
- Directory-level activity grouping (which areas of the codebase are most active)
- Tool usage frequency and trends
- Memory accumulation by type over time — are new gotchas still being discovered?
- Activity density (activities per unique file)

**Output:** `oak/insights/codebase-activity-report.md`

**When to run:** Monthly to understand codebase health and identify areas needing attention.

### Prompt Quality Analysis

Analyzes your prompting patterns to help you get better results from AI coding agents. Correlates prompt characteristics with session outcomes and provides educational, data-backed recommendations.

**What it analyzes:**
- Prompt length distribution and its correlation with activity count
- Prompts with file references vs without — which lead to better outcomes
- Common anti-patterns: vague instructions (< 20 chars), missing context, repeated rework
- Exemplary prompts — high activity count with low error rate, with truncated previews
- Context engineering recommendations based on what actually worked in your history
- Prompt quality trends over time — are you improving?

**Output:** `oak/insights/prompt-analysis.md`

**When to run:** Monthly to refine your prompting skills with data from your own sessions.

## Running Tasks

1. Navigate to the **Agents** page in the dashboard
2. Select an analysis task from the task list
3. Click **Run** to start the agent
4. Watch progress in real time — output streams as the agent queries and writes
5. View the generated report in `oak/insights/`

### Run History

Every agent run is recorded with:
- **Status** — Running, completed, failed, or cancelled
- **Output** — Full agent output including generated reports
- **Cost** — Token usage and cost for the run
- **Cancellation** — Cancel a running agent at any time

## Scheduling

Analysis tasks can be scheduled to run automatically using cron expressions. Manage schedules from the Agents page in the dashboard.

**Suggested schedules:**

| Task | Cron | Frequency |
|------|------|-----------|
| Usage & Cost Report | `0 9 * * MON` | Weekly on Monday |
| Productivity Analysis | `0 9 * * MON` | Weekly on Monday |
| Codebase Activity Report | `0 0 1 * *` | Monthly on the 1st |
| Prompt Quality Analysis | `0 0 1 * *` | Monthly on the 1st |

## Custom Tasks

You can create custom analysis tasks that the Analysis Agent will automatically pick up. Custom tasks live in `oak/agents/` (git-tracked) and use the same YAML format as built-in tasks.

### Example: Weekly Error Deep-Dive

```yaml
# oak/agents/error-analysis.yaml
name: error-analysis
display_name: "Error Deep-Dive"
agent_type: analysis
description: "Weekly analysis of tool execution errors and failure patterns"

default_task: |
  Analyze tool execution errors from the past 7 days.

  ## 1. Error Summary
  Query activities where success = 0. Break down by:
  - Tool name and error rate
  - Most common error messages
  - Files that trigger the most errors

  ## 2. Error Patterns
  Identify recurring patterns:
  - Same file failing repeatedly (flaky?)
  - Errors that cluster in time (environment issue?)
  - Error rate changes compared to previous week

  ## 3. Recommendations
  Suggest fixes for the top 3 most impactful error patterns.

execution:
  timeout_seconds: 180
  max_turns: 50
  permission_mode: acceptEdits

maintained_files:
  - path: "{project_root}/oak/insights/error-analysis.md"
    purpose: "Weekly error analysis report"
    auto_create: true

schedule:
  cron: "0 10 * * FRI"
  description: "Weekly Friday morning"

schema_version: 1
```

### Key Differences from Documentation Tasks

When creating custom analysis tasks, note these differences from documentation agent tasks:

| Aspect | Documentation Agent | Analysis Agent |
|--------|-------------------|---------------|
| `agent_type` | `documentation` | `analysis` |
| Primary tool | `ci_search` (semantic) | `ci_query` (SQL) |
| Output location | `oak/docs/`, `README.md`, `CHANGELOG.md` | `oak/insights/` only |
| Data access | Code search, memories, sessions | Direct SQL against all CI tables |
| Shell access | No | No |

:::tip
Include example SQL queries in your `default_task` prompt. The agent uses them as starting points and refines based on actual results. See the built-in tasks for good patterns.
:::

## Provider Configuration

The Analysis Agent uses the LLM provider configured in the **Agents** section of the [Configuration](/open-agent-kit/features/codebase-intelligence/configuration/) page. This is the same provider used by the Documentation Agent.

Supported providers:

| Provider | Type | Notes |
|----------|------|-------|
| **Anthropic** | Cloud | Default. Requires `ANTHROPIC_API_KEY`. |
| **Ollama** | Local | Requires v0.14.0+ and 64K+ context model. |
| **LM Studio** | Local | OpenAI-compatible endpoint. |
| **AWS Bedrock** | Cloud | Uses AWS credentials. |
| **OpenRouter** | Cloud | Proxy for multiple providers. |

Test the connection from the Configuration page before running agents.

## Security

The Analysis Agent operates within strict boundaries:

**Allowed file access:**
- `oak/insights/**` only — reports cannot be written anywhere else

**Blocked file access:**
- `.env`, `*.pem`, `*.key` — sensitive files are never accessible

**Allowed tools:**
- `Read`, `Write`, `Edit`, `Glob`, `Grep` (filesystem, restricted to insights directory)
- `ci_query`, `ci_memories`, `ci_sessions`, `ci_project_stats` (CI data, read-only)

**Blocked tools:**
- `Bash` (no shell access)
- `Task` (no sub-agent spawning)

**Data safety:**
- All SQL queries are read-only — mutations are rejected
- Prompt previews in reports are truncated to protect privacy
- Cost figures are rounded to 4 decimal places
- No data is fabricated — if a query returns no results, the agent notes it rather than inventing numbers
