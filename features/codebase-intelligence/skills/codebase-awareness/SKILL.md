---
name: codebase-awareness
description: Search codebase semantically, find similar code, retrieve past decisions and gotchas. Use when starting tasks, implementing features, debugging, exploring unfamiliar code, or needing context about project patterns.
version: 1.2.0
allowed-tools: Bash, Read, Grep, Glob
user-invocable: false
---

# Codebase Awareness

**ALWAYS** retrieve context before working. This project has indexed code and stored memories from past sessions.

## When You MUST Call Context

| Scenario | Action |
|----------|--------|
| **Session start** | `oak ci context "user's request"` |
| **Before any code changes** | `oak ci context "what you're about to do"` |
| **Exploring unfamiliar code** | `oak ci search "area you're investigating"` |
| **Debugging an issue** | `oak ci search "error or symptom" --type memory` |
| **Making design decisions** | `oak ci search "topic" --type memory` |

## Commands

```bash
# Get context for a task (code patterns + past decisions + gotchas)
oak ci context "implement user authentication"

# Search code semantically
oak ci search "database connection handling" --type code

# Search past decisions, gotchas, bug fixes
oak ci search "why we chose Redis" --type memory

# Search everything
oak ci search "error handling patterns"
```

## Non-Negotiable Rules

1. **Context first** - Run `oak ci context` before writing or modifying code
2. **Search before creating** - Similar code or past solutions may exist
3. **Trust stored memories** - Gotchas and decisions exist for good reason
4. **Match existing patterns** - Follow conventions found in search results
