---
title: Coding Agents
description: AI coding agents that OAK captures, enriches, and extends.
---

These are the AI coding agents your team uses to build software — Claude Code, Cursor, Gemini, and others. OAK integrates with each of them through hooks (to capture activity and inject context), MCP tools (for semantic search and memory), and skills (to extend what agents can do). No matter which agent your engineers prefer, OAK ensures every session contributes to and benefits from your project's shared intelligence.

:::note[Looking for OAK's built-in agents?]
OAK also runs its own autonomous agents that turn captured intelligence into action — documentation, analysis, and insights. See [OAK Agents](/team/agents/).
:::

## Supported Agents

| Agent | Directory | Hooks | MCP | Skills |
|-------|-----------|-------|-----|--------|
| **Claude Code** | `.claude/` | Yes | Yes | Yes |
| **Codex CLI** | `.codex/` | Yes (OTel) | Yes | Yes |
| **Cursor** | `.cursor/` | Yes | Yes | Yes |
| **Gemini CLI** | `.gemini/` | Yes | Yes | Yes |
| **OpenCode** | `.opencode/` | Yes (Plugin) | Yes | Yes |
| **VS Code Copilot** | `.github/` | Yes | Yes | Yes |
| **Windsurf** | `.windsurf/` | Yes | No | Yes |

For details on what each agent's hooks actually provide (context injection, activity capture, summarization), see the [Team overview](/team/).

## Skills & Commands

OAK deploys **[skills](/agents/skills/)** and commands into each agent's native directories. Skills are the primary way OAK extends your agent — invoke them with slash commands like `/project-governance` or `/oak`.

After `oak init`, **4 skills** are available:
- **OAK** — `/oak` (semantic search, impact analysis, memory, database queries)
- **Rules Management** — `/project-governance` (constitutions, agent files, RFCs)
- **Context Engineering** — `/context-engineering` (prompt design, context optimization, the four strategies)
- **Swarm** — `/swarm` (cross-project search for collective knowledge and patterns)

See the **[Skills](/agents/skills/)** page for full details on each skill.

## Agent Instruction Files

OAK creates and manages instruction files that reference your project constitution:

| Agent | Instruction File |
|-------|-----------------|
| Claude Code | `.claude/CLAUDE.md` |
| VS Code Copilot | `.github/copilot-instructions.md` |
| Codex / Cursor / OpenCode | `AGENTS.md` (root level, shared) |
| Gemini | `GEMINI.md` (root level) |
| Windsurf | `.windsurf/rules/rules.md` |

If your team already has these files with established conventions:
- OAK will **append** constitution references (not overwrite)
- Backups are created automatically (`.backup` extension) as a failsafe
- Existing team conventions are preserved

## ACP: OAK as a Coding Agent

In addition to enriching existing agents, OAK can act as the agent itself via the **[Agent Client Protocol (ACP)](/team/acp/)**. ACP-compatible editors like Zed connect to OAK directly, getting full team intelligence built into every response — no hooks or MCP required.

```bash
oak team start        # Start the daemon
oak acp serve       # Start the ACP agent server
```

The ACP integration supports **session modes** (Code, Architect, Ask) and **focus switching** between specialized agent templates (documentation, analysis, engineering, maintenance) — all within the editor's native UI.

See the [ACP documentation](/team/acp/) for setup instructions and details.

## Multi-Agent Workflows

OAK supports multiple agents in the same project — ideal for teams where engineers use different tools. Select agents during `oak init` or add them incrementally by re-running `oak init`.

**Benefits:**
- **Team flexibility**: Engineers can use their preferred AI tool
- **Consistent skills**: Same skills and commands across all agents
- **Zero conflicts**: Each agent's files live in separate directories
