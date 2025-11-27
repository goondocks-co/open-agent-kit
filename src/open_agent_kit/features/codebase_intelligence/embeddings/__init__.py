"""Embedding providers for Codebase Intelligence."""

from open_agent_kit.features.codebase_intelligence.embeddings.base import EmbeddingProvider
from open_agent_kit.features.codebase_intelligence.embeddings.provider_chain import (
    EmbeddingProviderChain,
)

__all__ = ["EmbeddingProvider", "EmbeddingProviderChain"]
