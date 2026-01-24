# P3 NICE-TO-HAVE: Progressive Disclosure API Duplication

## Summary
The RetrievalEngine has two parallel APIs that duplicate most logic: primary methods and "Layer 1-2-3" progressive disclosure methods.

## Location
- `src/open_agent_kit/features/codebase_intelligence/retrieval/engine.py`

## Duplicated APIs
**Primary methods (used by daemon routes):**
- `search()`
- `fetch()`
- `get_task_context()`

**Progressive disclosure methods (Layer 1-3):**
- `search_index()` - 90% duplicates `search()`
- `get_chunk_context()` - Similar to `fetch()` with extras
- `fetch_full()` - Duplicates `fetch()`

## Evidence
`search_index()` and `search()` have nearly identical code paths:
- Both call `store.search_code()` and `store.search_memory()`
- Both apply confidence scoring
- Both build result dictionaries

## Recommended Fix
Unify into single methods with configuration flags:

```python
def search(
    self,
    query: str,
    search_type: str = "all",
    limit: int = None,
    include_content: bool = False,  # False = index-level, True = full
) -> SearchResult:
    ...

# Remove search_index(), fetch_full() - they become:
# search(query, include_content=False)  # was search_index()
# fetch(ids)  # was fetch_full()
```

**Estimated LOC reduction**: ~100 lines

## Review Agent
code-simplicity-reviewer

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
