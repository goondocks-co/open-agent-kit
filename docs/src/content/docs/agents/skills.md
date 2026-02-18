---
title: Skills
description: Skills that OAK deploys into your AI coding agents.
---

Skills are the primary way OAK extends your AI agent's capabilities. They are deployed into each agent's skills directory during `oak init` and can be invoked directly from your agent's interface using slash commands (e.g., `/project-governance`), or they activate automatically when your request matches their description.

You don't need to memorize commands — just describe what you need:

```
"We need coding standards for this Python project"     → /project-governance
"What did we discuss about auth last week?"             → /codebase-intelligence
"I'm about to refactor the payment module — what breaks?" → /codebase-intelligence
"Propose an RFC for switching to PostgreSQL"            → /project-governance
```

Skills use CI's semantic search and memory under the hood — no additional API keys required beyond what your agent already uses.

## Codebase Intelligence

### `/codebase-intelligence`

Search, analyze, and query your codebase using semantic vector search, impact analysis, and direct SQL queries against the Oak CI database. Finds conceptually related code that grep would miss, assesses refactoring risk, and provides direct database access for session history, activity logs, and agent run data.

**When to use:**
- Finding similar implementations across the codebase
- Understanding how components connect to each other
- Assessing the impact of code changes before refactoring
- Recalling what was discussed or decided in previous sessions
- Looking up past conversations, outcomes, or decisions
- Querying session history or activity logs
- Looking up past memories or observations
- Checking agent run costs and performance

**Examples:**
```
# Find code by concept, not just text
/codebase-intelligence how does the authentication middleware work?

# Assess risk before refactoring
/codebase-intelligence I'm about to change the session model schema — what might be affected?

# Recall past conversations and decisions
/codebase-intelligence what did we discuss about the auth refactor last week?

# Look up what happened in previous sessions
/codebase-intelligence show me recent sessions and what was accomplished

# Search past learnings and gotchas
/codebase-intelligence are there any known gotchas with the payment module?

# Query raw data when you need specifics
/codebase-intelligence how many sessions have we had this week and what was the total cost?
```

:::tip
The database schema evolves between releases. This skill always provides the current schema, making it more reliable than hand-written SQL queries.
:::

**Reference docs included:** semantic search guide, impact analysis workflow, database querying guide, full schema reference (auto-generated), advanced query cookbook, analysis playbooks.

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
# Establish standards for a new project
/project-governance We need to establish our constitution for this Python project

# Add a specific rule
/project-governance Add a new rule No-Magic-Literals (Zero Tolerance)

# Keep agent instruction files in sync
/project-governance Sync all agent files after we updated the constitution

# Propose a change formally
/project-governance Create an RFC for adding a caching layer to the API

# Review an RFC
/project-governance Review oak/rfc/RFC-001-add-caching-layer.md
```

After creating or updating a constitution, sync it to all agent instruction files:
```bash
oak rules sync-agents
```

**Reference docs included:** constitution creation guide, good/bad constitution examples, agent file guide, good/bad agent file examples, RFC creation workflow, RFC review checklist.

## Context Engineering

### `/context-engineering`

Design effective prompts and optimize the full context window for AI models and agents. Covers prompt engineering foundations (clarity, examples, chain of thought, XML structure), the four context engineering strategies (Write, Select, Compress, Isolate), agent memory and session patterns, and before/after examples showing measurable improvement.

**When to use:**
- Writing or improving system prompts
- Designing agent workflows with optimal context
- Optimizing context windows for better output
- Building prompt templates with clear structure
- Structuring few-shot examples effectively
- Reducing context rot in long conversations
- Improving AI output quality with better prompting

**The Four Strategies:**

| Strategy | Action | Example |
|----------|--------|---------|
| **Write** | Craft persistent instructions | System prompt with altitude-appropriate rules |
| **Select** | Choose what enters context | Use `oak_search` to retrieve only relevant code |
| **Compress** | Reduce tokens, preserve signal | Summarize prior conversation turns |
| **Isolate** | Move information out of context | Store reference docs externally, load just-in-time |

**Examples:**
```
# Improve a vague prompt
/context-engineering Help me improve this prompt: "Review this code and give feedback"

# Design a system prompt
/context-engineering I need to write a system prompt for a code review agent

# Understand context rot
/context-engineering My agent is losing track of instructions — how do I fix this?

# Optimize context usage
/context-engineering The context window is filling up too fast — what strategies help?
```

**Key concepts:**
- **Altitude concept** — Write instructions at the right level of abstraction (not too high like "be helpful", not too low like "always use 4 spaces")
- **Context rot** — Output quality degradation as conversations grow longer; mitigate with Compress and Isolate strategies
- **Memory-as-a-tool** — Store information externally with `oak_remember`, retrieve just-in-time with `oak_search`

**Reference docs included:** prompt foundations, context engineering framework, agent context patterns, system prompt design templates, memory and sessions guide, before/after examples gallery.

## Refreshing Skills

After upgrading OAK, refresh skills to get the latest content:

```bash
oak skill refresh
```

This re-copies all skill files from the package into each agent's skills directory without changing your configuration.
