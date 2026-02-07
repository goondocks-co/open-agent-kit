---
title: Agent Overview
description: Supported AI agents and their integration capabilities.
---

Open Agent Kit integrates with AI coding assistants by installing command prompts in their native directories.

## Supported Agents

| Agent | Commands Directory | Command Format | Hooks | MCP |
|-------|-------------------|----------------|-------|-----|
| **Claude Code** | `.claude/commands/` | `oak.rfc-create.md` | Full | Yes |
| **Codex CLI** | `.codex/prompts/` | `oak.rfc-create.md` | Full (OTel) | Yes |
| **Cursor** | `.cursor/commands/` | `oak.rfc-create.md` | Full | Yes |
| **Gemini CLI** | `.gemini/commands/` | `oak.rfc-create.md` | Full | Yes |
| **OpenCode** | `.opencode/commands/` | `oak.rfc-create.md` | Full (Plugin) | Yes |
| **Windsurf** | `.windsurf/commands/` | `oak.rfc-create.md` | No | No |
| **GitHub Copilot** | `.github/agents/` | `oak.rfc-create.prompt.md` | Limited | No |

## Available Commands

After running `oak init --agent <agent-name>`, you can use:

- `/oak.constitution-create` — Create engineering constitutions from codebase analysis
- `/oak.constitution-validate` — Validate constitution structure
- `/oak.constitution-amend` — Add amendments to constitutions
- `/oak.rfc-create` — Create RFC documents for technical decisions
- `/oak.rfc-list` — List existing RFCs
- `/oak.rfc-validate` — Validate RFC structure

**No API keys required!** Commands are invoked through your agent's interface, which handles authentication.

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

OAK supports multiple agents in the same project — ideal for teams where engineers use different tools:

```bash
# Initialize with multiple agents
oak init --agent claude --agent copilot --agent cursor

# Or add agents incrementally
oak init --agent claude
oak init --agent copilot   # Adds to existing setup
```

**Benefits:**
- **Team flexibility**: Engineers can use their preferred AI tool
- **Consistent workflow**: Same commands (`/oak.rfc-create`, etc.) across all agents
- **Zero conflicts**: Each agent's commands live in separate directories
