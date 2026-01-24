# P2 IMPORTANT: O(n) Full Scan in count_unique_files

## Summary
The `count_unique_files` function fetches ALL code chunk metadata into memory to count unique files. This is called on every file watcher update.

## Location
- `src/open_agent_kit/features/codebase_intelligence/memory/store.py:943-963`

## Impact
- **5,000 chunks**: ~200ms
- **50,000 chunks**: ~2s
- **500,000 chunks**: Memory exhaustion possible

## Evidence
```python
def count_unique_files(self) -> int:
    # ChromaDB doesn't have distinct count, so fetch all metadata
    results = self._code_collection.get(include=["metadatas"])
    unique_files = {m.get("filepath") for m in results["metadatas"] if m.get("filepath")}
    return len(unique_files)
```

## Recommended Fix
Maintain a separate file count in SQLite or state, updated incrementally:

```python
class IndexStatus:
    _file_count: int = 0
    _known_files: set[str] = field(default_factory=set)

    def add_file(self, filepath: str):
        if filepath not in self._known_files:
            self._known_files.add(filepath)
            self._file_count += 1

    def remove_file(self, filepath: str):
        if filepath in self._known_files:
            self._known_files.discard(filepath)
            self._file_count -= 1

    @property
    def file_count(self) -> int:
        return self._file_count
```

## Review Agent
performance-oracle

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
