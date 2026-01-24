# P3 NICE-TO-HAVE: Duplicate Dimension Mismatch Handling

## Summary
VectorStore has 3 methods handling dimension mismatches plus the same try/except pattern copied 3 times (~60 lines duplicated).

## Location
- `src/open_agent_kit/features/codebase_intelligence/memory/store.py`

## Duplicated Code
**3 methods for dimension handling:**
- `_get_or_recreate_collection()` (lines 331-379)
- `_handle_dimension_mismatch()` (lines 381-414)
- `_recreate_collection()` (lines 416-437)

**Same try/except block in 3 places:**
- `add_code_chunks()` (lines 518-537)
- `add_code_chunks_batched()` (lines 607-630)
- `add_memory()` (lines 664-681)

## Recommended Fix
Create a single `_upsert_with_dimension_recovery()` method:

```python
def _upsert_with_dimension_recovery(
    self,
    collection: Collection,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    try:
        collection.upsert(ids=ids, embeddings=embeddings, ...)
    except InvalidDimensionException as e:
        # Handle dimension mismatch
        self._recreate_collection(collection.name, len(embeddings[0]))
        collection.upsert(ids=ids, embeddings=embeddings, ...)
```

**Estimated LOC reduction**: ~80 lines

## Review Agent
code-simplicity-reviewer

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
