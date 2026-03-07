---
title: OAK Agents
description: OAK as an active participant — autonomous background agents and an interactive editor agent, all powered by team intelligence.
---

OAK doesn't just capture your development story — it acts on it. This section covers the two ways OAK becomes an active participant in your workflow:

- **Autonomous agents** — Background agents that run tasks on demand or on a schedule: writing documentation, generating insights, reviewing code, and maintaining the memory store. They work from the *full development record* — decisions, gotchas, session history, and semantic code search — not just the code.
- **Interactive editor agent (ACP)** — OAK as a first-class coding agent inside editors like Zed. Every prompt gets full team intelligence built in — no hooks, no MCP configuration required.

The same agent templates power both modes. When you run the Documentation Agent as a background task, it uses the same system prompt and CI access profile as the Documentation *focus* in an ACP session.

They are distinct from external coding agents (Claude Code, Cursor, Codex, etc.) — those are documented in [Coding Agents](/agents/).

## Autonomous Agents

Each autonomous agent has:

- **Built-in tasks** — Pre-configured work items that ship inside the OAK package (not copied into your project)
- **Custom task support** — Create your own tasks in `oak/agents/` (git-tracked, shareable with your team)
- **Scheduling** — Run tasks automatically on a cron schedule
- **Run history** — Every run is logged with status, output, files modified, and token usage

![Agents page showing templates and task list](../../../assets/images/agents-page.png)

| Agent | Purpose | Built-in Tasks |
|-------|---------|---------------|
| **[Documentation Agent](/team/documentation-agent/)** | Maintains project documentation using the full CI knowledge base | Root Documentation, Feature Docs, Changelog, Architecture Docs |
| **[Analysis Agent](/team/analysis-agent/)** | Turns CI data into actionable insights about productivity, costs, and codebase health | Usage & Cost Report, Productivity Analysis, Codebase Activity, Prompt Quality |
| **[Engineering Agent](/team/engineering-agent/)** | An engineering team with role-based tasks for code review, implementation, and issue triage | Senior Engineer, Product Manager |
| **[Maintenance Agent](/team/maintenance-agent/)** | Keeps OAK's memory store healthy — consolidates duplicates, resolves stale observations, and maintains data hygiene | Memory Consolidation, Data Hygiene |

## Interactive Editor Agent (ACP)

The **[Agent Client Protocol (ACP)](./acp)** integration lets ACP-compatible editors like Zed connect to OAK directly, turning it into your interactive coding agent with team intelligence built into every response.

Each agent template above is available as a **focus** you can switch to mid-session — the focus determines which system prompt, tools, and CI access the agent uses, while preserving your conversation history.

| Focus | Agent Template |
|-------|---------------|
| **Oak** (default) | Interactive coding with full CI context |
| **Documentation** | Documentation Agent |
| **Analysis** | Analysis Agent |
| **Engineering** | Engineering Agent |
| **Maintenance** | Maintenance Agent |

See **[Agent Client Protocol (ACP)](./acp)** for editor setup, session modes, and how to switch focus.

## Provider Configuration

OAK Agents use the LLM provider configured in the **Agents page → Settings** tab (`/agents/settings`). This is separate from the summarization model — you may want a more capable model for agent tasks.

Supported providers:

| Provider | Type | Notes |
|----------|------|-------|
| **Claude Code (Default)** | Cloud | Uses your logged-in Claude Code subscription on this machine (no API key needed). |
| **Ollama** | Local | Experimental for agent execution. Requires v0.14.0+ and a capable local model. |
| **LM Studio** | Local | Experimental for agent execution via local OpenAI-compatible endpoint. |

Test the connection from the Agents Settings tab before running agents.
