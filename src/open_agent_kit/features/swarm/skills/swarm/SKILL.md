---
name: swarm
description: >-
  Search across multiple projects in your organization's swarm.
  Use when you need cross-project patterns, org-level conventions,
  shared decisions, or want to know how other projects solved a problem.
  Complements the oak (team) skill which covers single-project knowledge.
allowed-tools: Bash, Read
user-invocable: true
---

# Swarm

Use MCP tools (`swarm_search`, `swarm_fetch`, `swarm_nodes`, `swarm_call`,
`swarm_broadcast`, `swarm_status`) to access cross-project knowledge from
the swarm — a federation of team nodes across your organization.

## When to Use Swarm vs Team

| Question | Team (`oak-ci`) | Swarm (`oak-swarm`) |
|----------|-----------------|---------------------|
| How does auth work in *this* project? | `oak_search` | |
| How do we handle auth *across* projects? | | `swarm_search` |
| What patterns exist for error handling? | Local patterns | Org-wide conventions |
| What was decided about the API? | Local decisions | Cross-project decisions |
| What depends on this change? | Local impact | Cross-project impact |

**Rule of thumb:** Team = "this project", Swarm = "the organization".

## Quick Start

### Search then Fetch (primary workflow)

```
# 1. Broad search across all projects
swarm_search(query="retry with exponential backoff", search_type="memory")

# 2. Get full details for a specific result
swarm_fetch(ids=["chunk-id-from-search"], project_slug="project-name")
```

Search returns summaries with IDs. Fetch returns full content for the IDs
you care about. This two-step keeps responses focused.

### Discover connected projects

```
swarm_nodes()
```

### Check connectivity

```
swarm_status()
```

## Tool Reference

| MCP Tool | Purpose | Key Args |
|----------|---------|----------|
| `swarm_search` | Search observations, sessions, plans across all nodes | `query`, `search_type` (all/memory/sessions/plans), `limit` |
| `swarm_fetch` | Get full details for search result IDs | `ids` (list), `project_slug` |
| `swarm_nodes` | List connected teams and capabilities | (none) |
| `swarm_call` | Call a tool on a specific team node | `tool_name`, `arguments`, `target_project` |
| `swarm_broadcast` | Call a tool on all team nodes | `tool_name`, `arguments` |
| `swarm_status` | Check swarm connection status | (none) |

### Search Types

- `all` — everything (default)
- `memory` — observations, decisions, gotchas, discoveries
- `sessions` — session summaries
- `plans` — planning documents and decisions

Note: code search is NOT available via swarm. Use `oak_search` (team) for
code search within the current project.

## Common Patterns

### Find org-wide conventions

```
swarm_search(query="error handling conventions", search_type="memory")
```

### Check how other projects solved a problem

```
swarm_search(query="database migration strategy", search_type="all")
# then fetch details for the most relevant result
swarm_fetch(ids=["<id>"], project_slug="<project>")
```

### Discover cross-project dependencies

```
swarm_search(query="shared authentication service", search_type="memory")
```

### Run a tool on a specific project

```
swarm_call(
    tool_name="oak_search",
    arguments='{"query": "payment processing", "search_type": "code"}',
    target_project="billing-service"
)
```
