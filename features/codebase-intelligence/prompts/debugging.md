---
name: debugging
description: For debugging sessions with errors
activity_filter: Read,Edit,Bash
min_activities: 2
---

You are analyzing a debugging session to capture the root cause and fix.

## Context

The developer was debugging an issue.

Duration: {{session_duration}} minutes
Files investigated: {{files_read}}
Files modified: {{files_modified}}
Errors: {{errors}}

### Debugging Activity

{{activities}}

## Observation Types

{{observation_types}}

## Task

Extract the debugging journey: what was the symptom, what was investigated, what was the root cause, and how was it fixed.

Focus on:
- The initial error or symptom
- Wrong assumptions or dead ends
- The actual root cause
- The fix and why it works
- How to avoid this in the future

Prefer **bug_fix** and **gotcha** types for debugging sessions.

## Output Format

```json
{
  "observations": [
    {
      "type": "{{type_names}}",
      "observation": "Root cause and fix description",
      "context": "File where bug was",
      "importance": "high|medium|low"
    }
  ],
  "summary": "Brief description of bug and fix"
}
```

Respond ONLY with valid JSON.
