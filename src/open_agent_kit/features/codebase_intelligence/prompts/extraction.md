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
