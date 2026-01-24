# P2 IMPORTANT: ChromaDB Operations Not Thread-Safe

## Summary
ChromaDB collection operations (clear, rebuild, delete/recreate) are not thread-safe. Concurrent access during index operations can cause errors or data loss.

## Location
- `src/open_agent_kit/features/codebase_intelligence/memory/store.py:999-1020`

## Evidence
```python
def clear_code_index(self) -> None:
    self._ensure_initialized()
    self._client.delete_collection(CODE_COLLECTION)  # Not atomic
    self._code_collection = self._client.create_collection(...)  # Race window
```

## Risk
- Another thread querying during delete/recreate window gets errors
- `_code_collection` reference becomes stale for concurrent readers
- Dimension mismatch recreation destroys data without locking

## Recommended Fix
Add a read-write lock for collection operations:

```python
from threading import RLock

class VectorStore:
    def __init__(self, ...):
        self._collection_lock = RLock()

    def clear_code_index(self) -> None:
        with self._collection_lock:
            self._ensure_initialized()
            self._client.delete_collection(CODE_COLLECTION)
            self._code_collection = self._client.create_collection(...)

    def search_code(self, query: str, ...) -> list[dict]:
        with self._collection_lock:
            return self._code_collection.query(...)
```

## Review Agent
data-integrity-guardian

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
