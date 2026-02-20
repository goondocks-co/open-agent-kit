---
name: extraction
description: General observation extraction from session activities
min_activities: 1
---

You are analyzing a coding session to extract important observations for future reference.

## Session Activity

Duration: {{session_duration}} minutes
Files read: {{files_read}}
Files modified: {{files_modified}}
Errors encountered: {{errors}}

### Tool Executions

{{activities}}

## Observation Types

Extract observations using these types:

{{observation_types}}

## Importance Levels

Rate each observation's importance based on its value for future sessions:

- **high**: Non-obvious insight that would cause bugs, confusion, or wasted time if forgotten. Cannot be easily rediscovered from code alone. Examples: hidden gotchas, security considerations, subtle dependencies, counterintuitive behavior.
- **medium**: Useful context that saves time but could be rediscovered with investigation. Examples: design patterns, conventions, integration points, configuration quirks.
- **low**: Nice-to-know information that is easily found from code or already documented elsewhere. Skip if already captured in project rules/docs.

Prefer fewer high-quality observations over many low-importance ones.

## Session Context Awareness

Consider the session's activity pattern when rating observation importance:

- **Planning/investigation sessions** (many reads, few edits): Prefer lower importance
  ratings for observations that describe current problems or temporary state rather
  than permanent learnings. These observations describe what *is*, not what *should be*.
- **Implementation sessions** (significant edits): Observations about decisions made,
  patterns established, or gotchas encountered are more likely to be permanent learnings
  and may warrant higher importance.

When in doubt, prefer a conservative (lower) importance rating — observations can be
promoted later but high-importance noise is harder to filter.

## Examples

**Good observation** (specific, actionable — extract this):
```json
{
  "type": "gotcha",
  "observation": "SQLite WAL mode must be enabled before concurrent reads work. Without WAL, readers block writers and vice versa. Enabled via PRAGMA journal_mode=WAL at connection time.",
  "context": "activity/store/database.py",
  "importance": "high"
}
```

**Bad observation** (too generic — skip this):
```json
{
  "type": "discovery",
  "observation": "The project uses SQLite for storage",
  "context": "activity/store",
  "importance": "low"
}
```

## Output Format

Respond with a JSON object:

```json
{
  "observations": [
    {
      "type": "{{type_names}}",
      "observation": "Concise description of what was learned",
      "context": "Relevant file or feature name",
      "importance": "high|medium|low"
    }
  ],
  "summary": "One sentence describing what the session accomplished"
}
```

Guidelines:
- Only include genuinely useful observations that would help in future sessions
- Be specific - mention file names, function names, actual values
- If the session was just exploration without meaningful learnings, return empty observations
- Focus on things that aren't obvious from the code itself

Respond ONLY with valid JSON.
