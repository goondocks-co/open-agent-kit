# DevTools & Debugging

The **DevTools** suite provides power-user capabilities for managing the Codebase Intelligence backend. These tools are accessible via the `oak ci` CLI or the `/api/devtools` endpoints.

These tools are critical when:
-   The index feels stale or out of sync.
-   You want to re-process past sessions with a new LLM.
-   You changed embedding models and need to re-vectorize memories.

## CLI Access

Currently, DevTools functions are primarily exposed via specific `oak ci` commands or the [Web Dashboard](dashboard.md).

```bash
# Rebuild the entire code index
oak ci index --force

# Reset the entire system (Data + Index)
oak ci reset
```

## API Access

The full power of DevTools is available via the REST API. You can `curl` these endpoints locally.

### Rebuild Index
`POST /api/devtools/rebuild-index`

Triggers a manual flush and rebuild of the codebase index (vector store). Unlike `oak ci reset`, this **does not delete memories**, only the code chunks.

```json
{
  "full_rebuild": true
}
```

### Reset Processing
`POST /api/devtools/reset-processing`

Resets the 'processed' flags for sessions, prompt batches, and activities in the SQLite store. This allows the background workers to pick them up again—useful if you've improved the summarization prompts and want to re-summarize past work.

```json
{
  "delete_memories": true
}
```
*`delete_memories: true` will remove the generated memory observations, allowing them to be regenerated from the raw session logs.*

### Trigger Processing
`POST /api/devtools/trigger-processing`

Manually kicks the background worker loop. Useful for immediate debugging without waiting for the scheduled interval.

### Rebuild Memories
`POST /api/devtools/rebuild-memories`

Re-embeds existing memory text from SQLite into ChromaDB. Use this when:
1.  You switched embedding providers (e.g., matching the vector space of a new model).
2.  The vector store was corrupted or deleted, but the SQLite logs are intact.

```json
{
  "full_rebuild": true
}
```

## Monitoring

You can monitor the effect of these tools via the logs:

```bash
oak ci logs -f
```
