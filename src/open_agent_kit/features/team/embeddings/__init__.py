"""Embedding providers for Team."""

from open_agent_kit.features.team.embeddings.base import EmbeddingProvider
from open_agent_kit.features.team.embeddings.provider_chain import (
    EmbeddingProviderChain,
)

__all__ = ["EmbeddingProvider", "EmbeddingProviderChain"]
