# P1 CRITICAL: Dual-Write Without Atomicity

## Summary
The dual-write pattern (SQLite + ChromaDB) lacks atomicity. If the daemon crashes between writing to ChromaDB and marking the record as embedded in SQLite, duplicates can occur.

## Location
- `src/open_agent_kit/features/codebase_intelligence/activity/processor.py:1050-1091`

## Risk
- **Severity**: CRITICAL
- **Impact**: Duplicate entries in ChromaDB, data inconsistency
- **Scenario**:
  1. SQLite write succeeds (embedded=FALSE)
  2. ChromaDB write succeeds
  3. Daemon crashes before `mark_observation_embedded()`
  4. On restart, rebuild finds "unembedded" records
  5. ChromaDB now has duplicates

## Evidence
```python
def _store_observation(...):
    # Step 1: SQLite write
    self.activity_store.store_observation(stored_obs)

    # Step 2: ChromaDB write
    self.vector_store.add_memory(memory)

    # Step 3: Mark as embedded - CRASH WINDOW HERE
    self.activity_store.mark_observation_embedded(obs_id)
```

## Recommended Fix
1. Add idempotency key to ChromaDB upserts
2. Check if ID exists in ChromaDB before insert during rebuild
3. Or use ChromaDB's upsert semantics to prevent duplicates

```python
def add_memory(self, memory: MemoryObservation) -> str:
    # Use upsert instead of add to handle duplicates
    self._memory_collection.upsert(
        ids=[memory.id],
        documents=[memory.observation],
        metadatas=[...],
        embeddings=[embedding],
    )
```

## Review Agent
data-integrity-guardian

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
