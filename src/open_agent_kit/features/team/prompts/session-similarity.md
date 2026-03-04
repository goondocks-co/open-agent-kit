---
name: session-similarity
description: Rate how related two coding sessions are for parent session suggestions
---

Rate how related these two coding sessions are on a scale of 0.0 to 1.0.

## Session A (Current)

{{session_a_summary}}

## Session B (Candidate Parent)

{{session_b_summary}}

## Scoring Guidelines

Consider these factors:

1. **Same feature/bug** (high weight)
   - Are both sessions working on the same feature, bug fix, or component?
   - Do they mention the same file names or modules?

2. **Continuation pattern** (high weight)
   - Does Session A appear to be a continuation of Session B?
   - Does Session A reference decisions, plans, or outcomes from Session B?

3. **Related work** (medium weight)
   - Are they working on related but distinct features?
   - Do they touch the same area of the codebase?

4. **Unrelated** (low score)
   - Different features, different parts of the codebase
   - No logical connection between the sessions

## Score Ranges

- **0.9 - 1.0**: Direct continuation (Session A picks up exactly where B left off)
- **0.7 - 0.9**: Same feature/bug (clearly related work on the same thing)
- **0.5 - 0.7**: Related work (same area of codebase, related features)
- **0.3 - 0.5**: Loosely related (some overlap but different focus)
- **0.0 - 0.3**: Unrelated (different work entirely)

## Output

Respond with ONLY a single number between 0.0 and 1.0. No explanation, no text, just the number.
