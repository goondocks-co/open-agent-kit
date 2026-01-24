# P3 NICE-TO-HAVE: Embedding Provider Abstraction Over-Engineered

## Summary
The embedding provider system has 6 files for what could be 2-3. The LMStudio provider duplicates OpenAI-compat logic, and the provider chain has unused usage tracking.

## Location
- `src/open_agent_kit/features/codebase_intelligence/embeddings/`

## Current Structure (6 files)
- `base.py` (91 lines) - Abstract base class
- `provider_chain.py` (273 lines) - Fallback chain with tracking
- `fastembed.py` - FastEmbed provider
- `ollama.py` - Ollama provider
- `openai_compat.py` - OpenAI-compatible provider
- `lmstudio.py` - LM Studio provider (duplicates openai_compat)

## Issues
1. `lmstudio.py` is nearly identical to `openai_compat.py`
2. `EmbeddingProviderChain` has complex fallback tracking (~80 lines) that's rarely used
3. `_usage_stats`, `_tried_providers` are never displayed in UI

## Recommended Simplification
1. Merge `lmstudio.py` into `openai_compat.py` (factory function)
2. Remove unused usage tracking from chain
3. **Estimated LOC reduction**: ~100 lines

## Review Agent
code-simplicity-reviewer

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
