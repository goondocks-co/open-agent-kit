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

## Examples

**Good observation** (specific root cause and fix — extract this):
```json
{
  "type": "bug_fix",
  "observation": "ChromaDB dimension mismatch error when switching embedding models. Old collection had 384-dim vectors but new model produces 768-dim. Fix: delete and recreate the collection when embedding model changes, detected via stored metadata.",
  "context": "memory/store/chroma.py",
  "importance": "high"
}
```

**Bad observation** (too vague — skip this):
```json
{
  "type": "bug_fix",
  "observation": "Fixed a database error",
  "context": "memory/store",
  "importance": "medium"
}
```

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
