"""Tests for PromptClassifier - dynamic prompt classification across agents.

Tests cover:
- Detection of plan execution prompts (auto-injected by plan mode)
- Detection of internal messages (task-notification, system)
- Classification of user prompts (default)
- Pattern loading from agent manifests
"""

from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.constants import (
    PROMPT_SOURCE_AGENT,
    PROMPT_SOURCE_PLAN,
    PROMPT_SOURCE_SYSTEM,
    PROMPT_SOURCE_USER,
)
from open_agent_kit.features.codebase_intelligence.prompt_classifier import (
    PromptClassificationResult,
    PromptClassifier,
    classify_prompt,
    get_prompt_classifier,
    is_internal_message,
    is_plan_execution,
    reset_prompt_classifier,
)


@pytest.fixture(autouse=True)
def reset_classifier():
    """Reset the global classifier before and after each test."""
    reset_prompt_classifier()
    yield
    reset_prompt_classifier()


@pytest.fixture
def mock_agent_service():
    """Mock AgentService that returns plan execution prefixes."""
    mock = MagicMock()
    mock.get_all_plan_execution_prefixes.return_value = {
        "claude": "Implement the following plan:",
        "cursor": "Execute this plan:",
    }
    return mock


@pytest.fixture
def classifier_with_mock(mock_agent_service, tmp_path):
    """Create a PromptClassifier with mocked AgentService."""
    with patch(
        "open_agent_kit.features.codebase_intelligence.prompt_classifier.PromptClassifier._get_agent_service"
    ) as mock_get:
        mock_get.return_value = mock_agent_service
        classifier = PromptClassifier(project_root=tmp_path)
        yield classifier


class TestPromptClassificationResult:
    """Test PromptClassificationResult dataclass."""

    def test_default_values(self):
        """Test default values for user result."""
        result = PromptClassificationResult(source_type=PROMPT_SOURCE_USER)
        assert result.source_type == PROMPT_SOURCE_USER
        assert result.agent_type is None
        assert result.matched_prefix is None

    def test_plan_result(self):
        """Test result for plan execution."""
        result = PromptClassificationResult(
            source_type=PROMPT_SOURCE_PLAN,
            agent_type="claude",
            matched_prefix="Implement the following plan:",
        )
        assert result.source_type == PROMPT_SOURCE_PLAN
        assert result.agent_type == "claude"
        assert result.matched_prefix == "Implement the following plan:"


class TestPromptClassifierPlanExecution:
    """Test detection of plan execution prompts."""

    def test_detect_claude_plan_execution(self, classifier_with_mock):
        """Test detecting Claude plan execution prompt."""
        prompt = "Implement the following plan:\n\n# Feature X\n\n1. Do thing"
        result = classifier_with_mock.classify(prompt)

        assert result.source_type == PROMPT_SOURCE_PLAN
        assert result.agent_type == "claude"
        assert result.matched_prefix == "Implement the following plan:"

    def test_detect_cursor_plan_execution(self, classifier_with_mock):
        """Test detecting Cursor plan execution prompt."""
        prompt = "Execute this plan:\n\nBuild the feature"
        result = classifier_with_mock.classify(prompt)

        assert result.source_type == PROMPT_SOURCE_PLAN
        assert result.agent_type == "cursor"
        assert result.matched_prefix == "Execute this plan:"

    def test_is_plan_execution_convenience(self, classifier_with_mock):
        """Test convenience method is_plan_execution."""
        plan_prompt = "Implement the following plan:\n\n# Feature"
        assert classifier_with_mock.is_plan_execution(plan_prompt) is True

        user_prompt = "Help me fix this bug"
        assert classifier_with_mock.is_plan_execution(user_prompt) is False

    def test_plan_execution_with_whitespace(self, classifier_with_mock):
        """Test plan execution detection with leading whitespace."""
        prompt = "  Implement the following plan:\n\n# Feature"
        result = classifier_with_mock.classify(prompt)

        assert result.source_type == PROMPT_SOURCE_PLAN
        assert result.agent_type == "claude"


class TestPromptClassifierInternalMessages:
    """Test detection of internal messages."""

    def test_detect_task_notification(self, classifier_with_mock):
        """Test detecting task-notification messages."""
        prompt = "<task-notification>Agent completed task</task-notification>"
        result = classifier_with_mock.classify(prompt)

        assert result.source_type == PROMPT_SOURCE_AGENT
        assert result.matched_prefix == "<task-notification>"

    def test_detect_system_message(self, classifier_with_mock):
        """Test detecting system messages."""
        prompt = "<system-reminder>Important info</system-reminder>"
        result = classifier_with_mock.classify(prompt)

        assert result.source_type == PROMPT_SOURCE_SYSTEM
        assert result.matched_prefix == "<system-"

    def test_is_internal_message_convenience(self, classifier_with_mock):
        """Test convenience method is_internal_message."""
        task_prompt = "<task-notification>Done</task-notification>"
        assert classifier_with_mock.is_internal_message(task_prompt) is True

        user_prompt = "Help me fix this bug"
        assert classifier_with_mock.is_internal_message(user_prompt) is False


class TestPromptClassifierUserPrompts:
    """Test classification of user prompts (default)."""

    def test_classify_user_prompt(self, classifier_with_mock):
        """Test that regular prompts are classified as user."""
        prompt = "Help me implement a login feature"
        result = classifier_with_mock.classify(prompt)

        assert result.source_type == PROMPT_SOURCE_USER
        assert result.agent_type is None
        assert result.matched_prefix is None

    def test_classify_none_prompt(self, classifier_with_mock):
        """Test that None prompt returns user source type."""
        result = classifier_with_mock.classify(None)

        assert result.source_type == PROMPT_SOURCE_USER

    def test_classify_empty_prompt(self, classifier_with_mock):
        """Test that empty prompt returns user source type."""
        result = classifier_with_mock.classify("")

        assert result.source_type == PROMPT_SOURCE_USER

    def test_classify_whitespace_only(self, classifier_with_mock):
        """Test that whitespace-only prompt returns user source type."""
        result = classifier_with_mock.classify("   \n\t  ")

        assert result.source_type == PROMPT_SOURCE_USER


class TestPromptClassifierPatternLoading:
    """Test pattern loading from agent manifests."""

    def test_patterns_loaded_from_manifests(self, classifier_with_mock):
        """Test that patterns are loaded from AgentService."""
        patterns = classifier_with_mock._get_plan_execution_patterns()

        assert len(patterns) == 2
        assert "Implement the following plan:" in patterns
        assert patterns["Implement the following plan:"] == "claude"
        assert "Execute this plan:" in patterns
        assert patterns["Execute this plan:"] == "cursor"

    def test_patterns_cached(self, mock_agent_service, tmp_path):
        """Test that patterns are cached after first load."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.prompt_classifier.PromptClassifier._get_agent_service"
        ) as mock_get:
            mock_get.return_value = mock_agent_service
            classifier = PromptClassifier(project_root=tmp_path)

            # First access
            classifier._get_plan_execution_patterns()
            # Second access
            classifier._get_plan_execution_patterns()

            # AgentService should only be called once
            assert mock_agent_service.get_all_plan_execution_prefixes.call_count == 1

    def test_get_supported_agents(self, classifier_with_mock):
        """Test getting list of supported agents."""
        agents = classifier_with_mock.get_supported_agents()

        assert "claude" in agents
        assert "cursor" in agents
        assert len(agents) == 2


class TestPromptClassifierPriority:
    """Test classification priority (internal > plan > user)."""

    def test_internal_takes_priority_over_plan(self, classifier_with_mock):
        """Test that internal message detection takes priority."""
        # A prompt that starts with task-notification but contains plan prefix
        prompt = "<task-notification>Implement the following plan:</task-notification>"
        result = classifier_with_mock.classify(prompt)

        # Should be classified as agent_notification, not plan
        assert result.source_type == PROMPT_SOURCE_AGENT

    def test_user_asking_about_task_notification(self, classifier_with_mock):
        """Test that user asking about <task-notification> is classified correctly."""
        # A prompt where user mentions task-notification but doesn't start with it
        prompt = "What is a <task-notification> message?"
        result = classifier_with_mock.classify(prompt)

        # Should be classified as user (doesn't start with the prefix)
        assert result.source_type == PROMPT_SOURCE_USER


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_classify_prompt_function(self, mock_agent_service, tmp_path):
        """Test module-level classify_prompt function."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.prompt_classifier.PromptClassifier._get_agent_service"
        ) as mock_get:
            mock_get.return_value = mock_agent_service
            reset_prompt_classifier()

            result = classify_prompt("Help me with code")
            assert isinstance(result, PromptClassificationResult)
            assert result.source_type == PROMPT_SOURCE_USER

    def test_is_plan_execution_function(self, mock_agent_service, tmp_path):
        """Test module-level is_plan_execution function."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.prompt_classifier.PromptClassifier._get_agent_service"
        ) as mock_get:
            mock_get.return_value = mock_agent_service
            reset_prompt_classifier()

            result = is_plan_execution("Help me with code")
            assert isinstance(result, bool)

    def test_is_internal_message_function(self, mock_agent_service, tmp_path):
        """Test module-level is_internal_message function."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.prompt_classifier.PromptClassifier._get_agent_service"
        ) as mock_get:
            mock_get.return_value = mock_agent_service
            reset_prompt_classifier()

            result = is_internal_message("<task-notification>test</task-notification>")
            assert result is True

    def test_get_prompt_classifier_singleton(self, tmp_path):
        """Test that get_prompt_classifier returns singleton."""
        reset_prompt_classifier()

        classifier1 = get_prompt_classifier(tmp_path)
        classifier2 = get_prompt_classifier()

        assert classifier1 is classifier2

    def test_reset_prompt_classifier(self, tmp_path):
        """Test that reset creates new instance."""
        classifier1 = get_prompt_classifier(tmp_path)
        reset_prompt_classifier()
        classifier2 = get_prompt_classifier(tmp_path)

        assert classifier1 is not classifier2


class TestPromptClassifierErrorHandling:
    """Test error handling in PromptClassifier."""

    def test_handles_agent_service_error(self, tmp_path):
        """Test graceful handling when AgentService fails."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.prompt_classifier.PromptClassifier._get_agent_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.get_all_plan_execution_prefixes.side_effect = Exception("Service error")
            mock_get.return_value = mock_service

            classifier = PromptClassifier(project_root=tmp_path)

            # Should not raise, returns empty patterns
            patterns = classifier._get_plan_execution_patterns()
            assert patterns == {}

            # Classification should fall back to user
            result = classifier.classify("Implement the following plan:\n\nFeature")
            assert result.source_type == PROMPT_SOURCE_USER

    def test_internal_messages_work_without_agent_service(self, tmp_path):
        """Test that internal message detection works even if AgentService fails."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.prompt_classifier.PromptClassifier._get_agent_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.get_all_plan_execution_prefixes.side_effect = Exception("Service error")
            mock_get.return_value = mock_service

            classifier = PromptClassifier(project_root=tmp_path)

            # Internal message detection should still work
            result = classifier.classify("<task-notification>test</task-notification>")
            assert result.source_type == PROMPT_SOURCE_AGENT
