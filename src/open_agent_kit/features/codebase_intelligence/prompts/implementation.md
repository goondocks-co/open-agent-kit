---
name: implementation
description: For implementation sessions with writes/edits
activity_filter: Write,Edit
min_activities: 2
---

You are analyzing an implementation session to capture design decisions.

## Context

The developer was implementing a new feature or making significant changes.

Duration: {{session_duration}} minutes
Files created: {{files_created}}
Files modified: {{files_modified}}

### Implementation Activity

{{activities}}

## Observation Types

{{observation_types}}

## Task

Extract design decisions, architectural choices, and implementation gotchas.

Focus on:
- Why specific approaches were chosen
- Trade-offs considered
- Patterns followed or established
- Edge cases handled
- Integration points with existing code

Prefer **decision**, **trade_off**, and **gotcha** types for implementation sessions.

## Output Format

```json
{
  "observations": [
    {
      "type": "{{type_names}}",
      "observation": "Design choice and rationale",
      "context": "Feature or component name",
      "importance": "high|medium|low"
    }
  ],
  "summary": "Brief description of what was implemented"
}
```

Respond ONLY with valid JSON.
