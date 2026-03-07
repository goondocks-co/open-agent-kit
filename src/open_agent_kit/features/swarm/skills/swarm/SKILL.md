---
name: swarm
description: >-
  Search across multiple projects in your organization's swarm. Use when you
  need cross-project patterns, org-level conventions, shared decisions, or want
  to know how other projects solved a problem. Complements the oak (team) skill
  which covers single-project knowledge. Also use when the user mentions
  swarm_search, swarm_fetch, swarm_nodes, swarm_status, or asks about what
  other teams/projects have done, cross-project dependencies, org-wide patterns,
  or collective knowledge across the organization.
allowed-tools: Bash, Read
user-invocable: true
---

# Swarm

The swarm is a federation of teams across your organization. Each team is a
project with its own machine and developer nodes — its own memories, sessions,
plans, and codebase knowledge. The swarm connects these teams so you can search
and retrieve knowledge from all of them at once.

Use MCP tools (`swarm_search`, `swarm_fetch`, `swarm_nodes`, `swarm_status`)
to access collective knowledge. If MCP tools are not available, fall back to
the CLI commands shown below.

## Architecture at a Glance

```
Organization Swarm
├── Team A (this project)
│   ├── Node: developer laptop
│   └── Node: CI server
├── Team B (api-service)
│   └── Node: developer laptop
└── Team C (mobile-app)
    ├── Node: developer laptop
    └── Node: staging server
```

- **Swarm** = organization-level federation of teams
- **Team** = a single project (has its own `.oak/ci/activities.db`)
- **Node** = a machine running the team daemon within a project

The swarm aggregates knowledge across teams. The team federates tool calls
across nodes within one project. This skill is for the swarm layer.

## When to Use Swarm vs Team

| Question | Use Team (`oak`) | Use Swarm |
|----------|------------------|-----------|
| How does auth work in *this* project? | `oak_search` | |
| How do we handle auth *across* projects? | | `swarm_search` |
| What patterns exist org-wide for error handling? | | `swarm_search` |
| What was decided about *our* API design? | `oak_search` | |
| What API conventions do other teams follow? | | `swarm_search` |
| What depends on this module locally? | `oak_context` | |
| Which other projects depend on our shared library? | | `swarm_search` |

**Rule of thumb:** Team = "this project", Swarm = "the organization".

## Quick Start

### Search then Fetch (primary workflow)

The two-step pattern keeps responses focused — search returns summaries with
IDs, fetch returns full content for the items you care about.

```
# 1. Search across all connected teams
swarm_search(query="retry with exponential backoff", search_type="memory")

# 2. Get full details for specific results
swarm_fetch(ids=["chunk-id-from-search"], project_slug="api-service")
```

### Discover connected teams

```
swarm_nodes()
```

Returns each team's project slug, connection status, and capabilities.

### Check connectivity

```
swarm_status()
```

Returns whether this node is connected to the swarm, the swarm ID, and
peer count.

## Tool Reference

| MCP Tool | Purpose | Key Args |
|----------|---------|----------|
| `swarm_search` | Search memories, sessions, plans across all teams | `query`, `search_type` (`all`/`memory`/`sessions`/`plans`), `limit` |
| `swarm_fetch` | Get full details for search result IDs | `ids` (list of chunk IDs), `project_slug` |
| `swarm_nodes` | List connected teams and their capabilities | (none) |
| `swarm_status` | Check swarm connection health | (none) |

### Search Types

- `all` — everything (default, good starting point)
- `memory` — observations, decisions, gotchas, discoveries across teams
- `sessions` — session summaries from other projects
- `plans` — planning documents and architectural decisions

Code search is NOT available via swarm. Use `oak_search` (team skill) for
code search within the current project.

### CLI Fallback

If MCP tools are unavailable, use the CLI:

```bash
# Search across the swarm
{oak-cli-command} swarm search "retry with exponential backoff" --type memory

# List connected teams
{oak-cli-command} swarm nodes

# Check connectivity
{oak-cli-command} swarm status
```

## Common Patterns

### Find how other teams solved a problem

```
swarm_search(query="database migration strategy", search_type="all")
# Review results, then fetch the most relevant
swarm_fetch(ids=["<id>"], project_slug="<project>")
```

### Discover org-wide conventions

```
swarm_search(query="error handling conventions", search_type="memory")
```

### Check cross-project impact before a breaking change

```
swarm_search(query="shared authentication service", search_type="memory")
```

### Find decisions made by other teams

```
swarm_search(query="chose PostgreSQL over MongoDB", search_type="memory")
```

### Understand what a team has been working on

```
swarm_search(query="recent refactoring", search_type="sessions")
```

## Tips

- **Start broad, narrow down.** Use `search_type="all"` first. If results
  are noisy, switch to `memory` or `sessions`.
- **Use project_slug from results.** Search results include the originating
  project — pass it to `swarm_fetch` to get full details.
- **Check nodes first if search returns nothing.** Run `swarm_nodes()` to
  verify teams are connected. If the list is empty, the swarm may not be
  configured or the daemon may be offline.
- **Combine with team skill.** Use swarm to find cross-project patterns, then
  use `oak_search` to find the local implementation of that pattern.
