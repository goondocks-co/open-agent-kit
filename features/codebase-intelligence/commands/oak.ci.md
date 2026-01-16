---
description: Semantic code search and project memory using Codebase Intelligence.
---

## Request

```text
$ARGUMENTS
```

## Action

**FIRST**, run `oak ci context` or `oak ci search` to get relevant code and memories:

```bash
# Get context for a task (recommended first step)
oak ci context "the request above"

# Or search for specific code/patterns
oak ci search "query based on request"
```

Then complete the request using the insights returned.

## Commands Reference

| Command | Use For |
|---------|---------|
| `oak ci context "<task>"` | Starting work - gets relevant code + memories |
| `oak ci search "<query>"` | Finding code by meaning (semantic search) |
| `oak ci search "<query>" --type memory` | Finding past decisions, gotchas |
| `oak ci remember "<observation>" -t <type>` | Storing learnings for future |

## Remember Types

When you discover something important, store it:

```bash
oak ci remember "description" -t gotcha -c file.py    # Tricky behaviors
oak ci remember "description" -t decision             # Design choices
oak ci remember "description" -t bug_fix -c file.py   # Bug solutions
```

## Key Principles

1. **Context first** - Always run `oak ci context` before modifying unfamiliar code
2. **Trust memories** - Stored gotchas and decisions exist for good reason
3. **Store immediately** - When you discover something non-obvious, `oak ci remember` it
