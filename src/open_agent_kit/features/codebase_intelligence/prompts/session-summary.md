---
name: session-summary
description: Generate a high-level summary of what was accomplished in the session
---

You are summarizing a coding session to help future sessions understand what was done.

## Session Statistics

- Duration: {{session_duration}} minutes
- Prompt batches: {{prompt_batch_count}}
- Files read: {{files_read_count}}
- Files modified: {{files_modified_count}}
- Files created: {{files_created_count}}
- Total tool calls: {{tool_calls}}

## Prompt Batches

{{prompt_batches}}

## Task

Write a concise summary of this session. You have access to both the user's prompts and the agent's actions, so capture the full picture:

- **User intent**: What was the user trying to accomplish? What was their approach or priority?
- **Key actions**: What did the agent do? Which files were modified and why?
- **Outcomes**: What was achieved? Any decisions made or problems solved?
- **Context**: Any constraints, trade-offs, or discoveries worth noting?

Be specific - include file names, feature names, and technical details when relevant.

## Output Format

Respond with ONLY the summary text. No JSON, no code blocks, just plain text. A bulleted list is acceptable if it improves clarity.

## Examples

Good (captures intent + actions + outcome):
- "User wanted to add dark mode support. Implemented theme toggle in settings/ThemeProvider.tsx using CSS variables, added useTheme hook, and updated 12 components to use theme tokens instead of hardcoded colors. Chose CSS variables over styled-components for better performance."

Good (captures debugging journey):
- "User reported intermittent test failures in CI. Investigated flaky tests in tests/api/, discovered race condition in database cleanup. Fixed by adding proper test isolation with transaction rollbacks. Also identified that TestClient was sharing state across tests."

Good (captures exploration with learnings):
- "User needed to understand the payment processing flow before adding refund support. Traced code from PaymentController through StripeService to webhook handlers. Key finding: payments use idempotency keys stored in Redis, refunds will need similar pattern."

Bad (too vague):
- "Fixed some bugs and added a feature"
- "Worked on authentication"
- "Made improvements to the codebase"
