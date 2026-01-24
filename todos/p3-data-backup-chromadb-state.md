# P3 NICE-TO-HAVE: Backup Does Not Include ChromaDB State

## Summary
The backup only exports SQLite tables. ChromaDB (vector embeddings) is not backed up. While rebuild is possible from SQLite, this has implications for search quality.

## Location
- `src/open_agent_kit/features/codebase_intelligence/activity/store.py:1440-1508`

## Evidence
```python
def export_to_sql(self, output_path: Path, include_activities: bool = False) -> int:
    tables = ["sessions", "prompt_batches", "memory_observations"]
    # ChromaDB not included!
```

## Implications
1. Re-embedding requires embedding provider to be available and configured identically
2. Different embedding models produce different vectors, making old observations less searchable
3. No validation that rebuild was successful after restore

## Recommended Fix
Add post-restore validation:

```python
def validate_restore(self) -> dict:
    """Verify ChromaDB matches SQLite after restore."""
    sqlite_obs_count = self.activity_store.count_observations()
    chromadb_obs_count = self.vector_store.count_memories()

    sqlite_session_summaries = self.activity_store.count_session_summaries()
    chromadb_session_summaries = self.vector_store.count_session_summaries()

    return {
        "sqlite_observations": sqlite_obs_count,
        "chromadb_observations": chromadb_obs_count,
        "observations_match": sqlite_obs_count == chromadb_obs_count,
        "needs_rebuild": sqlite_obs_count != chromadb_obs_count,
    }
```

Also consider:
- Adding a `--verify` flag to restore command
- Auto-triggering rebuild if counts don't match
- Documenting the limitation in user docs

## Review Agent
data-integrity-guardian

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
