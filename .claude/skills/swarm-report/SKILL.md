---
name: swarm-report
description: >-
  Generate a cross-project comparative report from your organization's swarm.
  Use when you need an overview of all connected projects, want to compare
  activity levels, find shared patterns, or identify collaboration opportunities
  across teams. Also use when the user asks for a "swarm report",
  "cross-project analysis", "org overview", or wants to understand how projects
  relate to each other. Requires an active swarm connection.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
user-invocable: true
---

# Swarm Report

Generate a structured cross-project report from connected swarm nodes. The
report compares projects, surfaces shared patterns, and recommends collaboration
opportunities.

## Workflow

### 1. Verify Connectivity

```
swarm_status()
```

If disconnected, inform the user and stop. The swarm must be online to generate
a meaningful report.

### 2. Inventory Nodes

```
swarm_nodes()
```

Record each team's project slug, connection status, and capabilities. This
becomes the Node Inventory section of the report.

### 3. Gather Cross-Project Data

Run multiple searches to build a picture of the organization:

```
# Activity and recent work
swarm_search(query="recent changes and refactoring", search_type="all", limit=20)

# Shared dependencies and libraries
swarm_search(query="shared dependencies and common libraries", search_type="memory", limit=20)

# Coding conventions and patterns
swarm_search(query="coding conventions and architectural patterns", search_type="memory", limit=20)

# Decisions and trade-offs
swarm_search(query="architectural decisions and trade-offs", search_type="memory", limit=15)
```

Adapt queries based on what comes back — if a topic yields interesting results,
drill deeper with `swarm_fetch`:

```
swarm_fetch(ids=["<chunk-id>"], project_slug="<project>")
```

### 4. Write the Report

Write the report to `oak/insights/cross-project-report.md` using this structure:

```markdown
# Cross-Project Report

> Generated: YYYY-MM-DD | Nodes: N connected

## Executive Summary

2-3 paragraph overview of the organization's current state — what's active,
what themes emerge, and the top recommendations.

## Node Inventory

| Project | Status | Capabilities | Notable Activity |
|---------|--------|--------------|------------------|
| ...     | ...    | ...          | ...              |

## Activity Comparison

Compare what each project has been working on recently. Highlight:
- Projects with high activity vs quiet ones
- Overlapping work across teams
- Blocked or stalled efforts

## Shared Patterns

Patterns that appear across multiple projects:
- Common dependencies (same libraries, frameworks, versions)
- Similar architectural approaches (service layers, error handling)
- Shared conventions (naming, testing, deployment)

## Divergences

Where projects have made different choices:
- Conflicting dependency versions
- Different approaches to the same problem
- Inconsistent conventions that could cause friction

## Recommendations

Concrete, actionable suggestions:
- Opportunities for code sharing or extraction into shared libraries
- Projects that should coordinate on version alignment
- Teams that would benefit from knowledge sharing on specific topics
```

### CLI Fallback

If MCP tools are unavailable:

```bash
oak-dev swarm status
oak-dev swarm nodes
oak-dev swarm search "recent changes" --type all -n 20
oak-dev swarm search "shared dependencies" --type memory -n 20
oak-dev swarm search "coding conventions" --type memory -n 20
```

## Tips

- **Quality depends on node count.** With only 1-2 nodes connected, the report
  will be thin. Let the user know if coverage is limited.
- **Search broadly first.** The initial queries cast a wide net. Narrow down
  based on what comes back rather than starting too specific.
- **Fetch selectively.** Only use `swarm_fetch` for results that look
  particularly relevant — fetching everything is slow and noisy.
- **Be honest about gaps.** If a section has insufficient data, say so rather
  than speculating. A short honest report is more useful than a padded one.

## Deep Dives

Consult these reference documents for deeper guidance:

- **`references/report-examples.md`** — Good and bad report examples with detailed analysis of what makes a report useful vs useless. Read this before writing the report.
- **`references/search-strategies.md`** — How to write effective swarm queries, when to use each search type, and how to correlate results across projects.
