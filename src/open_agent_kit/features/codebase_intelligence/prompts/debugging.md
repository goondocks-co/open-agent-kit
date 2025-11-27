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

## Importance Levels

Rate each observation's importance based on its value for future sessions:

- **high**: Non-obvious insight that would cause bugs, confusion, or wasted time if forgotten. Cannot be easily rediscovered from code alone. Examples: hidden gotchas, security considerations, subtle dependencies, counterintuitive behavior.
- **medium**: Useful context that saves time but could be rediscovered with investigation. Examples: design patterns, conventions, integration points, configuration quirks.
- **low**: Nice-to-know information that is easily found from code or already documented elsewhere. Skip if already captured in project rules/docs.

Prefer fewer high-quality observations over many low-importance ones.

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
