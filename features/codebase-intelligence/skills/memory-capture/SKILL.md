---
name: memory-capture
description: Store observations, gotchas, decisions, bug fixes for future sessions. Use when discovering non-obvious behaviors, making architectural decisions, fixing bugs, or learning something important about the codebase.
version: 1.2.0
allowed-tools: Bash
user-invocable: false
---

# Memory Capture

**IMMEDIATELY** store observations when you discover something important. Future sessions depend on these memories.

## When You MUST Capture

| Scenario | Type | Example |
|----------|------|---------|
| **Found unexpected behavior** | `gotcha` | Silent failures, edge cases, quirks |
| **Fixed a bug** | `bug_fix` | Root cause and solution |
| **Made a design choice** | `decision` | Architecture decisions with WHY |
| **Learned how something works** | `discovery` | Non-obvious system behavior |
| **Chose between trade-offs** | `trade_off` | What was sacrificed and why |

## Command

```bash
oak ci remember "observation" -t <type> [-c filepath]
```

## Examples

```bash
# Gotcha - prevent future confusion
oak ci remember "JWT tokens expire silently when Redis is down" -t gotcha -c src/auth/middleware.py

# Bug fix - help the next person
oak ci remember "Fixed race condition with distributed lock via Redis SETNX" -t bug_fix -c src/orders/processor.py

# Decision - capture the WHY
oak ci remember "Using PostgreSQL JSONB for flexible schema evolution" -t decision

# Discovery - document learned behavior
oak ci remember "The API rate limits reset at UTC midnight, not rolling 24h" -t discovery
```

## Non-Negotiable Rules

1. **Capture immediately** - Don't wait until later; store when you discover
2. **Capture the WHY** - Not just what, but why it matters
3. **Include file paths** - Use `-c filepath` when the observation relates to specific code
4. **Be concise but complete** - Future you (or someone else) needs to understand
