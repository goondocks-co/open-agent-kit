# P2 IMPORTANT: O(n) Full Table Scan in list_memories

## Summary
The `list_memories` function fetches ALL matching records from ChromaDB into memory, then sorts and slices in Python. This becomes O(n) for every pagination request.

## Location
- `src/open_agent_kit/features/codebase_intelligence/memory/store.py:822-859`

## Impact
- **1,000 memories**: ~50ms
- **10,000 memories**: ~500ms
- **100,000 memories**: ~5s (unacceptable)

## Evidence
```python
# ChromaDB get() doesn't support offset/limit with where, so we fetch all
results = self._memory_collection.get(
    where=where,
    include=["documents", "metadatas"],
)
# Then Python-side sorting and slicing
sorted_indices.sort(key=lambda i: results["metadatas"][i].get("created_at", ""), reverse=True)
paginated_indices = sorted_indices[offset : offset + limit]
```

## Recommended Fix
Use SQLite as the pagination source (it already stores observations with proper indexes), then fetch only the needed IDs from ChromaDB for content.

```python
def list_memories(self, limit: int, offset: int, ...):
    # 1. Query SQLite for IDs with pagination (fast, indexed)
    ids = self.activity_store.list_observation_ids(limit, offset, filters)

    # 2. Fetch only those IDs from ChromaDB
    results = self._memory_collection.get(ids=ids, ...)
    return results
```

## Review Agent
performance-oracle

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
