"""Summarization services for Codebase Intelligence.

This module provides LLM-based summarization of session activity,
inspired by claude-mem's approach to extracting meaningful observations
from tool executions.

All providers use the OpenAI-compatible API:
- Ollama: Local LLM via /v1 endpoints (auto-converted from base URL)
- LM Studio: Local LLM server with OpenAI-compatible API
- vLLM: High-performance serving with OpenAI-compatible API
- OpenAI: Direct OpenAI API access
- Any other OpenAI-compatible server
"""

from open_agent_kit.features.codebase_intelligence.summarization.base import (
    BaseSummarizer,
    SummarizationResult,
)
from open_agent_kit.features.codebase_intelligence.summarization.providers import (
    ModelInfo,
    OllamaSummarizer,
    OpenAICompatSummarizer,
    OpenAISummarizer,
    create_summarizer,
    create_summarizer_from_config,
    discover_model_context,
    ensure_v1_url,
    list_available_models,
)

__all__ = [
    "BaseSummarizer",
    "ModelInfo",
    "OllamaSummarizer",
    "OpenAICompatSummarizer",
    "OpenAISummarizer",
    "SummarizationResult",
    "create_summarizer",
    "create_summarizer_from_config",
    "discover_model_context",
    "ensure_v1_url",
    "list_available_models",
]
