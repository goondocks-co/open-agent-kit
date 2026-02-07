---
title: Skills
description: Skills that OAK deploys into your AI coding agents.
---

Skills are the primary way OAK extends your AI agent's capabilities. They are deployed into each agent's skills directory during `oak init` and can be invoked directly from your agent's interface using slash commands (e.g., `/project-rules`).

Skills use CI's semantic search and memory under the hood — no additional API keys required beyond what your agent already uses.

## Codebase Intelligence

### `/finding-related-code`

Find semantically related code and discover relationships between components using vector search. Useful for finding similar implementations, understanding how code connects, or exploring patterns that grep would miss.

**When to use:**
- Finding similar implementations across the codebase
- Understanding how components connect to each other
- Exploring patterns that keyword search would miss

**Example:**
```
/finding-related-code how does the authentication middleware work?
```

### `/analyzing-code-change-impacts`

Analyze the potential impact of code changes using semantic search. Use before refactoring or modifying code to find all conceptually related code that might be affected.

**When to use:**
- Before refactoring a function or module
- Checking what might break if you change an interface
- Finding all consumers of an API before modifying it

**Example:**
```
/analyzing-code-change-impacts I'm about to change the session model schema
```

### `/querying-oak-databases`

Query the OAK CI SQLite database with ready-to-use queries and an up-to-date schema reference. Provides the database location, current schema, and common query templates so agents can query directly without discovering the schema first.

**When to use:**
- Inspecting session history or activity logs
- Looking up past memories or observations
- Checking agent run data
- Debugging CI behavior

**Example:**
```
/querying-oak-databases show me recent sessions and their statuses
```

:::tip
The schema evolves between releases. This skill always provides the current schema, making it more reliable than hand-written SQL queries.
:::

## Rules Management

### `/project-rules`

Create and maintain project constitutions and agent instruction files. A constitution (`oak/constitution.md`) codifies your team's engineering standards, architecture patterns, and conventions so that AI agents follow them consistently.

**When to use:**
- Creating a new constitution for a project
- Adding or updating coding standards
- Syncing agent instruction files after constitution changes
- Creating `CLAUDE.md`, `AGENTS.md`, or `.cursorrules` for a new project

**What a constitution defines:**
- **Hard rules** — invariants that must never be violated
- **Golden paths** — standard ways to implement common changes
- **Anchor files** — canonical reference implementations to copy from
- **Quality gates** — what must pass before work is complete

**Example:**
```
/project-rules We need to establish coding standards for this Python project
```

After creating or updating a constitution, sync it to all agent instruction files:
```bash
oak rules sync-agents
```

## Strategic Planning

### `/creating-rfcs`

Create RFC (Request for Comments) or ADR (Architecture Decision Record) documents for formal technical planning. RFCs live in `oak/rfc/` and serve as a persistent record of technical decisions.

**When to use:**
- Planning a significant architectural change
- Proposing a new feature that needs team review
- Documenting a technical decision (ADR-style)
- Changes that affect multiple teams or systems

**Available templates:**

| Template | Use for |
|----------|---------|
| `feature` | New features, capabilities |
| `architecture` | System architecture changes |
| `engineering` | Development practices, tooling |
| `process` | Team processes, workflows |

**Example:**
```
/creating-rfcs Create an RFC for adding a caching layer to the API
```

:::note
This is for formal RFC/ADR workflows. For quick implementation planning, use your agent's native plan mode instead.
:::

### `/reviewing-rfcs`

Review existing RFC documents for completeness, clarity, and technical soundness. Provides structured feedback using a standard review checklist.

**When to use:**
- Preparing an RFC for team review
- Providing feedback on someone else's RFC
- Checking if an RFC is ready for adoption

**What it checks:**
- Structure — required sections present, proper formatting
- Context — problem clearly stated, scope well-defined
- Decision — proposed solution is clear, technical approach explained
- Consequences — risks acknowledged, mitigations proposed
- Alternatives — other options considered, trade-offs documented

**Example:**
```
/reviewing-rfcs Review oak/rfc/RFC-001-add-caching-layer.md
```

## Refreshing Skills

After upgrading OAK, refresh skills to get the latest content:

```bash
oak skill refresh
```

This re-copies all skill files from the package into each agent's skills directory without changing your configuration.
