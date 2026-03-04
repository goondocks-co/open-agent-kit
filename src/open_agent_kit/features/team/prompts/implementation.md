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

## Importance Levels

Rate each observation's importance based on its value for future sessions:

- **high**: Non-obvious insight that would cause bugs, confusion, or wasted time if forgotten. Cannot be easily rediscovered from code alone. Examples: hidden gotchas, security considerations, subtle dependencies, counterintuitive behavior.
- **medium**: Useful context that saves time but could be rediscovered with investigation. Examples: design patterns, conventions, integration points, configuration quirks.
- **low**: Nice-to-know information that is easily found from code or already documented elsewhere. Skip if already captured in project rules/docs.

Prefer fewer high-quality observations over many low-importance ones.

## Task

Extract design decisions, architectural choices, and implementation gotchas.

Focus on:
- Why specific approaches were chosen
- Trade-offs considered
- Patterns followed or established
- Edge cases handled
- Integration points with existing code

Prefer **decision**, **trade_off**, and **gotcha** types for implementation sessions.

## Examples

**Good observation** (clear rationale — extract this):
```json
{
  "type": "decision",
  "observation": "Chose Pydantic over dataclasses for agent config models because agent YAML definitions need runtime validation (type coercion, range checks, defaults). Pydantic's validator decorators handle this; dataclasses would need manual __post_init__ validation.",
  "context": "agents/models.py",
  "importance": "medium"
}
```

**Bad observation** (no rationale — skip this):
```json
{
  "type": "decision",
  "observation": "Used Pydantic for the config model",
  "context": "agents/models.py",
  "importance": "low"
}
```

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

Guidelines:
- Extract at most 5 observations per session. Prefer fewer, higher-quality observations over many low-value ones.

Respond ONLY with valid JSON.
