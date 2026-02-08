---
title: Coding Agents
description: AI coding agents that OAK captures, enriches, and extends.
---

These are the AI coding agents your team uses to build software — Claude Code, Cursor, Gemini, and others. OAK integrates with each of them through hooks (to capture activity and inject context), MCP tools (for semantic search and memory), and skills (to extend what agents can do). No matter which agent your engineers prefer, OAK ensures every session contributes to and benefits from your project's shared intelligence.

:::note[Looking for OAK's built-in agents?]
OAK also runs its own autonomous agents that turn captured intelligence into action — documentation, analysis, and insights. See [OAK Agents](/open-agent-kit/features/codebase-intelligence/agents/).
:::

## Supported Agents

| Agent | Directory | Hooks | MCP | Skills |
|-------|-----------|-------|-----|--------|
| **Claude Code** | `.claude/` | Yes | Yes | Yes |
| **Codex CLI** | `.codex/` | Yes (OTel) | Yes | Yes |
| **Cursor** | `.cursor/` | Yes | Yes | Yes |
| **Gemini CLI** | `.gemini/` | Yes | Yes | Yes |
| **OpenCode** | `.opencode/` | Yes (Plugin) | Yes | Yes |
| **Windsurf** | `.windsurf/` | Yes | No | Yes |
| **GitHub Copilot** | `.github/` | Limited | No | Yes |

For details on what each agent's hooks actually provide (context injection, activity capture, summarization), see the [Codebase Intelligence overview](/open-agent-kit/features/codebase-intelligence/).

## Skills & Commands

OAK deploys **[skills](/open-agent-kit/agents/skills/)** and commands into each agent's native directories. Skills are the primary way OAK extends your agent — invoke them with slash commands like `/project-governance` or `/codebase-intelligence`.

After `oak init`, **2 skills** are available across two domains:
- **Rules Management** — `/project-governance` (constitutions, agent files, RFCs)
- **Codebase Intelligence** — `/codebase-intelligence` (semantic search, impact analysis, database queries)

See the **[Skills](/open-agent-kit/agents/skills/)** page for full details on each skill.

## Commands

OAK also deploys expert commands into each agent's commands directory. These act as specialized sub-agents with deep domain knowledge:

- **`/oak.backend-python-expert`** — A senior Python backend expert covering modern Python 3.12+ patterns, type hints, async programming, FastAPI, Pydantic V2, SQLAlchemy 2.0, and testing with pytest.

More expert commands may be added in future releases.

## Agent Instruction Files

OAK creates and manages instruction files that reference your project constitution:

| Agent | Instruction File |
|-------|-----------------|
| Claude Code | `.claude/CLAUDE.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Codex / Cursor / OpenCode | `AGENTS.md` (root level, shared) |
| Gemini | `GEMINI.md` (root level) |
| Windsurf | `.windsurf/rules/rules.md` |

If your team already has these files with established conventions:
- OAK will **append** constitution references (not overwrite)
- Backups are created automatically (`.backup` extension) as a failsafe
- Existing team conventions are preserved

## Multi-Agent Workflows

OAK supports multiple agents in the same project — ideal for teams where engineers use different tools. Select agents during `oak init` or add them incrementally by re-running `oak init`.

**Benefits:**
- **Team flexibility**: Engineers can use their preferred AI tool
- **Consistent skills**: Same skills and commands across all agents
- **Zero conflicts**: Each agent's files live in separate directories
