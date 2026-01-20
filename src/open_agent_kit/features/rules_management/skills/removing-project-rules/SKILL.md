---
name: removing-project-rules
description: Remove a rule from the project's constitution and sync the change across all configured AI agents. Use when a rule is no longer relevant, was added in error, or needs to be deprecated.
allowed-tools: Bash, Read, Edit
user-invocable: true
---

# Removing Project Rules

Remove a rule from the project constitution (`oak/constitution.md`) and sync the change to all configured agent instruction files.

## When to Use

Use this skill when:
- A rule is no longer relevant to the project
- A rule was added in error
- Team practices have changed
- A rule is being replaced with a different approach

## How It Works

1. **You decide** which rule to remove and why
2. **Edit** the constitution file to remove the rule
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

### 2. Remove the rule

Edit `oak/constitution.md` and remove the rule from the relevant section.

**Consider**: If this is a significant change (removing a MUST requirement), you may want to add an amendment note explaining why.

### 3. Sync to all agents

After editing the constitution, sync to all agent instruction files:

```bash
oak rules sync-agents
```

## Adding an Amendment (Optional)

For significant rule removals, document the change:

```bash
oak rules add-amendment \
  --summary "Remove strict TDD requirement" \
  --type major \
  --author "Your Name" \
  --rationale "Team moved to balanced testing approach"
```

Amendment types:
- **major**: Removing MUST requirements, significant policy changes
- **minor**: Removing SHOULD/MAY rules, small scope changes
- **patch**: Clarifications, typo fixes

## Example

User says: "We no longer require 100% code coverage"

1. Read constitution: `oak rules get-content`
2. Find the testing section
3. Remove or relax: `- All code MUST have 100% test coverage`
4. Optionally replace with: `- Critical paths SHOULD have comprehensive test coverage`
5. Sync: `oak rules sync-agents`

## Notes

- Consider **why** the rule is being removed
- For major changes, use `oak rules add-amendment` to document the change
- The constitution is in `oak/constitution.md`
- Agent files are synced automatically via `oak rules sync-agents`
