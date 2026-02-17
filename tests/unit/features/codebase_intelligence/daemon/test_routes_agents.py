"""Tests for agent route models and prompt composition.

Tests cover:
- TaskRunRequest model validation
- additional_prompt composition into task prompt
"""

import pytest

from open_agent_kit.features.codebase_intelligence.daemon.routes.agents import TaskRunRequest


class TestTaskRunRequest:
    """Tests for TaskRunRequest model."""

    def test_default_additional_prompt_is_none(self) -> None:
        """TaskRunRequest should default additional_prompt to None."""
        request = TaskRunRequest()

        assert request.additional_prompt is None

    def test_additional_prompt_accepted(self) -> None:
        """TaskRunRequest should accept an additional_prompt string."""
        request = TaskRunRequest(additional_prompt="Focus on the backup system")

        assert request.additional_prompt == "Focus on the backup system"

    def test_additional_prompt_max_length(self) -> None:
        """TaskRunRequest should reject prompts exceeding max_length."""
        with pytest.raises(ValueError):
            TaskRunRequest(additional_prompt="x" * 10001)

    def test_additional_prompt_at_max_length(self) -> None:
        """TaskRunRequest should accept prompts at exactly max_length."""
        request = TaskRunRequest(additional_prompt="x" * 10000)

        assert len(request.additional_prompt) == 10000


class TestAdditionalPromptComposition:
    """Tests for additional_prompt composition into task prompt.

    Validates the prompt composition logic used in the run_task route:
    when additional_prompt is provided, it's prepended as an Assignment section.
    """

    @staticmethod
    def _compose_prompt(default_task: str, additional_prompt: str | None) -> str:
        """Mirror the composition logic from the run_task route."""
        task_prompt = default_task
        if additional_prompt:
            task_prompt = f"## Assignment\n{additional_prompt}\n\n---\n\n{default_task}"
        return task_prompt

    def test_no_additional_prompt_uses_default(self) -> None:
        """Without additional_prompt, default_task is used unchanged."""
        default_task = "Hunt for bugs and security issues."

        result = self._compose_prompt(default_task, None)

        assert result == default_task

    def test_additional_prompt_prepends_assignment(self) -> None:
        """With additional_prompt, Assignment section is prepended."""
        default_task = "Hunt for bugs and security issues."
        additional = "Focus on the backup/restore system."

        result = self._compose_prompt(default_task, additional)

        assert result.startswith("## Assignment\n")
        assert additional in result
        assert "---" in result
        assert result.endswith(default_task)

    def test_empty_additional_prompt_uses_default(self) -> None:
        """Empty string additional_prompt should use default_task unchanged."""
        default_task = "Review architecture."

        result = self._compose_prompt(default_task, "")

        assert result == default_task

    def test_assignment_section_structure(self) -> None:
        """Assignment section should have correct markdown structure."""
        default_task = "Implement the feature."
        additional = "Create a cloud MCP relay."

        result = self._compose_prompt(default_task, additional)

        lines = result.split("\n")
        assert lines[0] == "## Assignment"
        assert lines[1] == additional
        assert lines[2] == ""
        assert lines[3] == "---"
        assert lines[4] == ""
        assert lines[5] == default_task
