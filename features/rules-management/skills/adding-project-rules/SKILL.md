---
name: adding-project-rules
description: Add a rule to the project's constitution and sync it across all configured AI agents. Use when you identify a pattern, practice, or standard that should be preserved as a project rule.
allowed-tools: Bash, Read, Edit
user-invocable: true
---

# Adding Project Rules

Add a rule to the project constitution (`oak/constitution.md`) and sync it to all configured agent instruction files.

## When to Use

Use this skill when you:
- Identify a pattern that should be followed across the project
- Discover a practice the team wants to standardize
- Need to document a decision that affects how code should be written
- Want to ensure all AI agents follow the same standards

## How It Works

1. **You decide** what rule to add and which section it belongs in
2. **Edit** the constitution file to add the rule
3. **Sync** to all agent instruction files using the CLI

## Steps

### 1. Read the current constitution

```bash
oak rules get-content
```

Or read the file directly:

```bash
cat oak/constitution.md
```

### 2. Add your rule to the appropriate section

Edit `oak/constitution.md` and add your rule to the relevant section. Use RFC 2119 language:

| Keyword | Meaning |
|---------|---------|
| **MUST** | Absolute requirement |
| **SHOULD** | Strong recommendation (exceptions need justification) |
| **MAY** | Optional, team discretion |

Example rule formats:
```markdown
- All API endpoints MUST include input validation
- Database queries SHOULD use parameterized statements
- Teams MAY use dependency injection frameworks
```

### 3. Sync to all agents

After editing the constitution, sync to all agent instruction files:

```bash
oak rules sync-agents
```

This ensures CLAUDE.md, AGENTS.md, .cursorrules, and other agent files reference the updated constitution.

## Example

User says: "We should always use TypeScript strict mode"

1. Read constitution: `oak rules get-content`
2. Find the appropriate section (likely "Code Style" or "TypeScript")
3. Add: `- All TypeScript projects MUST enable strict mode in tsconfig.json`
4. Sync: `oak rules sync-agents`

## Notes

- Rules should be **achievable**, not aspirational
- Include rationale when the "why" isn't obvious
- The constitution is in `oak/constitution.md`
- Agent files are synced automatically via `oak rules sync-agents`
