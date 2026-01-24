# P2 IMPORTANT: Missing Query Result Caching

## Summary
Every search request generates fresh embeddings and queries ChromaDB. There's no caching layer for repeated queries, causing unnecessary latency and compute.

## Location
- `src/open_agent_kit/features/codebase_intelligence/retrieval/engine.py:285-311`

## Evidence
```python
def search(self, query: str, ...) -> SearchResult:
    query_embedding = self.embedding_provider.embed_query(query)  # Always new
    results = self._code_collection.query(...)  # Always hits ChromaDB
```

## Impact
- Same query repeated within seconds still generates embedding (~100-300ms)
- Same search results fetched repeatedly
- Expected 10-100x improvement for repeated searches with caching

## Recommended Fix
Implement an LRU cache for query embeddings and search results:

```python
from functools import lru_cache
import hashlib

class RetrievalEngine:
    def __init__(self, ...):
        self._embedding_cache = {}  # TTL cache
        self._search_cache = {}

    def _get_query_embedding(self, query: str) -> list[float]:
        cache_key = hashlib.sha256(query.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            entry = self._embedding_cache[cache_key]
            if time.time() - entry["timestamp"] < 300:  # 5 min TTL
                return entry["embedding"]

        embedding = self.embedding_provider.embed_query(query)
        self._embedding_cache[cache_key] = {
            "embedding": embedding,
            "timestamp": time.time(),
        }
        return embedding
```

## Review Agent
performance-oracle

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
