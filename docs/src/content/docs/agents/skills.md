---
title: Skills
description: Skills that OAK deploys into your AI coding agents.
---

Skills are the primary way OAK extends your AI agent's capabilities. They are deployed into each agent's skills directory during `oak init` and can be invoked directly from your agent's interface using slash commands (e.g., `/project-governance`).

Skills use CI's semantic search and memory under the hood — no additional API keys required beyond what your agent already uses.

## Rules Management

### `/project-governance`

Create and maintain project constitutions, agent instruction files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`), and RFC/ADR documents. A constitution (`oak/constitution.md`) codifies your team's engineering standards, architecture patterns, and conventions so that AI agents follow them consistently.

**When to use:**
- Creating a new constitution for a project
- Adding or updating coding standards
- Syncing agent instruction files after constitution changes
- Creating `CLAUDE.md`, `AGENTS.md`, or `.cursorrules` for a new project
- Proposing a new feature via RFC
- Reviewing an RFC for completeness and technical soundness

**What a constitution defines:**
- **Hard rules** — invariants that must never be violated
- **Golden paths** — standard ways to implement common changes
- **Anchor files** — canonical reference implementations to copy from
- **Quality gates** — what must pass before work is complete

**Examples:**
```
/project-governance We need to establish our constitution for this Python project
/project-governance Add a new rule No-Magic-Literals (Zero Tolerance)
/project-governance Create an RFC for adding a caching layer to the API
/project-governance Review oak/rfc/RFC-001-add-caching-layer.md
```

After creating or updating a constitution, sync it to all agent instruction files:
```bash
oak rules sync-agents
```

**Reference docs included:** constitution creation guide, good/bad constitution examples, agent file guide, good/bad agent file examples, RFC creation workflow, RFC review checklist.

## Codebase Intelligence

### `/codebase-intelligence`

Search, analyze, and query your codebase using semantic vector search, impact analysis, and direct SQL queries against the Oak CI database. Finds conceptually related code that grep would miss, assesses refactoring risk, and provides direct database access for session history, activity logs, and agent run data.

**When to use:**
- Finding similar implementations across the codebase
- Understanding how components connect to each other
- Assessing the impact of code changes before refactoring
- Querying session history or activity logs
- Looking up past memories or observations
- Checking agent run costs and performance

**Examples:**
```
/codebase-intelligence how does the authentication middleware work?
/codebase-intelligence I'm about to change the session model schema — what might be affected?
/codebase-intelligence show me recent sessions and their statuses
```

:::tip
The database schema evolves between releases. This skill always provides the current schema, making it more reliable than hand-written SQL queries.
:::

**Reference docs included:** semantic search guide, impact analysis workflow, database querying guide, full schema reference (auto-generated), advanced query cookbook, analysis playbooks.

## Refreshing Skills

After upgrading OAK, refresh skills to get the latest content:

```bash
oak skill refresh
```

This re-copies all skill files from the package into each agent's skills directory without changing your configuration.
