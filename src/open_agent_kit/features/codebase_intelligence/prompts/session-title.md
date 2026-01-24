---
name: session-title
description: Generate a short title for the session based on prompts
---

Generate a short, descriptive title (5-10 words) for this coding session based on the user's prompts.

## Prompts

{{prompt_batches}}

## Task

Create a brief title that captures what this session was about. The title should:
- Be 5-10 words maximum
- Start with an action verb when appropriate (Add, Fix, Implement, Refactor, Debug, etc.)
- Mention the main feature, component, or file being worked on
- Be specific enough to distinguish from other sessions

## Output Format

Respond with ONLY the title text as plain text.
- No JSON
- No quotes
- No markdown
- No punctuation at the end
- No explanation or preamble

Just the title itself, nothing else.

## Examples

Good titles:
- Add dark mode theme support
- Fix authentication token refresh bug
- Implement user profile settings page
- Refactor payment processing service
- Debug CI test failures
- Update database migration scripts

Bad titles (too vague):
- Working on code
- Bug fix
- Feature implementation
- Updates
