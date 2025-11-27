---
name: classify
description: Classify activity type for a single user request
---

Classify the type of work done in response to a single user request.

## Activity Summary

- Duration: {{session_duration}} minutes
- Tools used: {{tool_summary}}
- Files read: {{files_read_count}}
- Files modified: {{files_modified_count}}
- Files created: {{files_created_count}}
- Errors encountered: {{has_errors}}

## Activity Log

{{activities}}

## Classification Types

{{classification_types}}

## Task

Based on the activities above, determine what the agent was primarily doing.
Respond with ONLY the classification word (e.g., exploration, debugging, implementation, refactoring), nothing else.
