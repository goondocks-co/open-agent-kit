---
title: DevTools
description: Power-user tools for managing the CI backend.
sidebar:
  order: 7
---

The **DevTools** page in the dashboard provides power-user capabilities for managing the Codebase Intelligence backend. Open it from the sidebar in the [Dashboard](/open-agent-kit/features/codebase-intelligence/dashboard/).

These tools are useful when:
- The index feels stale or out of sync
- You want to re-process past sessions with a new LLM
- You changed embedding models and need to re-vectorize memories

## Available Actions

### Rebuild Index

Triggers a full wipe and rebuild of the codebase index (vector store). This **does not delete memories** — only the code chunks are re-indexed.

Use this when:
- Files have been renamed or moved and search results feel stale
- You changed the AST parser configuration
- The index was corrupted

### Reset Processing

Resets the "processed" flags for sessions, prompt batches, and activities. This allows the background workers to pick them up again — useful if you've improved the summarization prompts and want to re-summarize past work.

Options:
- **Delete memories** — Also removes generated memory observations, allowing them to be regenerated from the raw session logs

### Trigger Processing

Manually kicks the background worker loop. Useful for immediate processing without waiting for the scheduled interval.

### Rebuild Memories

Re-embeds existing memory text from SQLite into ChromaDB. Use this when:
1. You switched embedding providers (to match the vector space of the new model)
2. The vector store was corrupted or deleted, but the SQLite data is intact

## CLI Shortcuts

A few DevTools actions are also available from the terminal:

```bash
oak ci index --force   # Rebuild the entire code index
oak ci reset           # Reset the entire system (data + index)
```

## Monitoring

Watch the effect of DevTools actions in real time from the dashboard's **Logs** page, or from the terminal:

```bash
oak ci logs -f
```
