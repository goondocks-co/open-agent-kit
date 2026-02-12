"""Tests for ActivityProcessor config accessor pattern.

Verifies that the processor reads summarizer, context_budget, and
session_quality from live config via config_accessor, so UI changes
take effect without a daemon restart.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.processor.core import (
    ActivityProcessor,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.models import (
    ContextBudget,
)
from open_agent_kit.features.codebase_intelligence.config import (
    CIConfig,
    SessionQualityConfig,
    SummarizationConfig,
)


@pytest.fixture()
def _stores(tmp_path: Path) -> tuple[MagicMock, MagicMock]:
    """Minimal mock stores for processor construction."""
    return MagicMock(), MagicMock()


class TestProcessorConfigAccessor:
    """Tests for live config accessor pattern on ActivityProcessor."""

    def test_context_budget_reads_live_config(self, _stores: tuple) -> None:
        """context_budget should reflect config changes without restart."""
        activity_store, vector_store = _stores
        live_config = CIConfig()
        live_config.summarization = SummarizationConfig(context_tokens=4096)

        processor = ActivityProcessor(
            activity_store=activity_store,
            vector_store=vector_store,
            config_accessor=lambda: live_config,
        )

        initial_budget = processor.context_budget
        assert initial_budget == ContextBudget.from_context_tokens(4096)

        # Simulate user changing context_tokens via UI
        live_config.summarization = SummarizationConfig(context_tokens=8192)

        updated_budget = processor.context_budget
        assert updated_budget == ContextBudget.from_context_tokens(8192)
        assert updated_budget != initial_budget

    def test_session_quality_reads_live_config(self, _stores: tuple) -> None:
        """session_quality thresholds should reflect config changes."""
        activity_store, vector_store = _stores
        live_config = CIConfig()
        live_config.session_quality = SessionQualityConfig(
            min_activities=3,
            stale_timeout_seconds=300,
        )

        processor = ActivityProcessor(
            activity_store=activity_store,
            vector_store=vector_store,
            config_accessor=lambda: live_config,
        )

        assert processor.min_session_activities == 3
        assert processor.stale_timeout_seconds == 300

        # Simulate user changing thresholds via UI
        live_config.session_quality = SessionQualityConfig(
            min_activities=10,
            stale_timeout_seconds=600,
        )

        assert processor.min_session_activities == 10
        assert processor.stale_timeout_seconds == 600

    def test_summarizer_cache_invalidated_on_model_change(self, _stores: tuple) -> None:
        """Summarizer cache key should change when provider/model/base_url changes."""
        activity_store, vector_store = _stores
        live_config = CIConfig()
        live_config.summarization = SummarizationConfig(
            enabled=True,
            provider="ollama",
            model="model-a",
            base_url="http://localhost:11434",
        )

        processor = ActivityProcessor(
            activity_store=activity_store,
            vector_store=vector_store,
            config_accessor=lambda: live_config,
        )

        # Access summarizer to populate cache key
        _ = processor.summarizer
        first_key = processor._summarizer_config_key
        assert first_key == ("ollama", "model-a", "http://localhost:11434", None, 180.0, True)

        # Same config — cache key unchanged
        _ = processor.summarizer
        assert processor._summarizer_config_key == first_key

        # Change model — cache key should update
        live_config.summarization = SummarizationConfig(
            enabled=True,
            provider="ollama",
            model="model-b",
            base_url="http://localhost:11434",
        )

        _ = processor.summarizer
        second_key = processor._summarizer_config_key
        assert second_key == ("ollama", "model-b", "http://localhost:11434", None, 180.0, True)
        assert second_key != first_key

    def test_summarizer_none_when_disabled(self, _stores: tuple) -> None:
        """Summarizer should be None when summarization is disabled in config."""
        activity_store, vector_store = _stores
        live_config = CIConfig()
        live_config.summarization = SummarizationConfig(enabled=False)

        processor = ActivityProcessor(
            activity_store=activity_store,
            vector_store=vector_store,
            config_accessor=lambda: live_config,
        )

        assert processor.summarizer is None

    def test_fallback_used_when_no_accessor(self, _stores: tuple) -> None:
        """Without config_accessor, processor uses static fallbacks (test path)."""
        activity_store, vector_store = _stores
        mock_summarizer = MagicMock()

        processor = ActivityProcessor(
            activity_store=activity_store,
            vector_store=vector_store,
            summarizer=mock_summarizer,
            context_tokens=2048,
            session_quality_config=SessionQualityConfig(min_activities=5),
        )

        assert processor.summarizer is mock_summarizer
        assert processor.context_budget == ContextBudget.from_context_tokens(2048)
        assert processor.min_session_activities == 5

    def test_accessor_none_return_uses_fallback(self, _stores: tuple) -> None:
        """If accessor returns None, processor uses static fallbacks."""
        activity_store, vector_store = _stores
        mock_summarizer = MagicMock()

        processor = ActivityProcessor(
            activity_store=activity_store,
            vector_store=vector_store,
            summarizer=mock_summarizer,
            context_tokens=2048,
            config_accessor=lambda: None,
        )

        assert processor.summarizer is mock_summarizer
        assert processor.context_budget == ContextBudget.from_context_tokens(2048)
