---
name: exploration
description: For sessions focused on reading/searching code
activity_filter: Read,Grep,Glob
min_activities: 3
---

You are analyzing an exploration/research session to extract useful learnings.

## Context

The developer was exploring the codebase to understand how things work.

Duration: {{session_duration}} minutes
Files explored: {{files_read}}

### Search and Read Activity

{{activities}}

## Observation Types

{{observation_types}}

## Task

Extract observations about the codebase structure, patterns, or gotchas discovered during exploration.

Focus on:
- How specific features are implemented
- Important patterns or conventions used
- Non-obvious relationships between components
- Things that surprised the developer

Prefer **discovery** and **gotcha** types for exploration sessions.

## Output Format

```json
{
  "observations": [
    {
      "type": "{{type_names}}",
      "observation": "What was learned",
      "context": "File or feature area",
      "importance": "high|medium|low"
    }
  ],
  "summary": "Brief description of what was explored"
}
```

Respond ONLY with valid JSON.
