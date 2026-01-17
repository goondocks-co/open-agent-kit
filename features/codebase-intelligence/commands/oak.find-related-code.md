---
description: Find semantically related code across the codebase using vector search. Use when you need to find similar implementations, patterns, or code that serves the same purpose but may use different names.
---

## Request

```text
$ARGUMENTS
```

## Action

Find code that's semantically related to what you're working on, even if it uses different names or patterns.

### When to Use This

Use this command when:
- Looking for similar implementations elsewhere in the codebase
- Finding all code related to a concept (not just by name)
- Discovering patterns you should follow
- Finding code to learn from or reference

**Why this over grep**: Grep finds literal text. This finds code that *does the same thing* or *solves the same problem*, regardless of naming.

### Commands

```bash
# Find code related to a concept
oak ci search "form validation logic" --type code

# Find similar patterns
oak ci search "retry with exponential backoff" --type code

# More results for broader exploration
oak ci search "error handling and logging" --type code -n 20

# Find code related to files you're editing
oak ci context "similar implementations" -f src/services/user.py

# Find related code for a specific task
oak ci context "validation patterns" -f src/api/handlers.py
```

### Example: Finding Similar Implementations

**Task**: Implementing a new API endpoint, want to follow existing patterns

```bash
# 1. Find existing endpoint implementations
oak ci search "REST API endpoint handler" --type code

# 2. Find validation patterns
oak ci search "input validation for API requests" --type code

# 3. Find error handling patterns
oak ci search "API error response formatting" --type code
```

**What you'll find**: Consistent patterns used elsewhere, even if the endpoints are in different modules or use different naming conventions.

### Example: Finding All Code for a Concept

**Task**: Understanding all authentication-related code

```bash
# Grep would miss these:
# - "verify_credentials" (doesn't say "auth")
# - "session_handler" (related concept)
# - "token_refresh" (authentication adjacent)

# Semantic search finds them all:
oak ci search "user authentication and authorization" --type code -n 20
```

### Tips

- Search for **what code does**, not **what it's called**
- Use natural language: "sending email notifications" not "email_sender"
- Increase `-n` limit when exploring broadly
- Use `--type code` to focus on implementation (exclude memories)
- Combine multiple searches to build complete picture

### Output

Results include:
- File path and line numbers
- Relevance score (higher = more related)
- Code snippet showing the match

```bash
# JSON output (default) - good for parsing
oak ci search "database transactions" -f json

# Text output - good for reading
oak ci search "database transactions" -f text
```
