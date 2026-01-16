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
