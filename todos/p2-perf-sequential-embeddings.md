# P2 IMPORTANT: Sequential Embedding Generation (N HTTP Requests)

## Summary
Embeddings are generated one-at-a-time via HTTP to Ollama. For N texts, this makes N HTTP round-trips, significantly slowing indexing.

## Location
- `src/open_agent_kit/features/codebase_intelligence/embeddings/ollama.py:181-210`

## Impact
- **100 chunks**: 100 HTTP round-trips (~30s with 300ms per request)
- **1,000 chunks**: ~5 minutes for full indexing

## Evidence
```python
for text in truncated_texts:
    response = self._client.post(
        f"{self._base_url}/api/embeddings",
        json={"model": model_name, "prompt": text},
    )
    embeddings.append(embedding)
```

## Recommended Fix
Use Ollama's batch endpoint or implement request pipelining:

```python
def embed(self, texts: list[str]) -> EmbeddingResult:
    # Option 1: Use batch endpoint if available
    response = self._client.post(
        f"{self._base_url}/api/embed",
        json={"model": model_name, "input": texts},  # Batch input
    )

    # Option 2: Use asyncio for concurrent requests
    async def embed_concurrent(texts):
        tasks = [self._embed_single(t) for t in texts]
        return await asyncio.gather(*tasks)
```

## Review Agent
performance-oracle

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
