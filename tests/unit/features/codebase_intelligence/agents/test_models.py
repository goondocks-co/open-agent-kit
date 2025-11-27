"""Tests for agent Pydantic models."""

from datetime import datetime, timedelta

import pytest

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentListItem,
    AgentListResponse,
    AgentRun,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunStatus,
)


class TestAgentRunStatus:
    """Tests for AgentRunStatus enum."""

    def test_all_status_values(self) -> None:
        """All expected status values should be defined."""
        assert AgentRunStatus.PENDING.value == "pending"
        assert AgentRunStatus.RUNNING.value == "running"
        assert AgentRunStatus.COMPLETED.value == "completed"
        assert AgentRunStatus.FAILED.value == "failed"
        assert AgentRunStatus.CANCELLED.value == "cancelled"
        assert AgentRunStatus.TIMEOUT.value == "timeout"


class TestAgentRun:
    """Tests for AgentRun model."""

    def test_default_values(self) -> None:
        """AgentRun should have sensible defaults."""
        run = AgentRun(
            id="test-123",
            agent_name="documentation",
            task="Update README",
        )

        assert run.id == "test-123"
        assert run.agent_name == "documentation"
        assert run.task == "Update README"
        assert run.status == AgentRunStatus.PENDING
        assert run.result is None
        assert run.error is None
        assert run.turns_used == 0
        assert run.cost_usd is None
        assert run.files_created == []
        assert run.files_modified == []
        assert run.files_deleted == []

    def test_is_terminal_pending(self) -> None:
        """Pending status should not be terminal."""
        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
            status=AgentRunStatus.PENDING,
        )
        assert not run.is_terminal()

    def test_is_terminal_running(self) -> None:
        """Running status should not be terminal."""
        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
            status=AgentRunStatus.RUNNING,
        )
        assert not run.is_terminal()

    def test_is_terminal_completed(self) -> None:
        """Completed status should be terminal."""
        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
            status=AgentRunStatus.COMPLETED,
        )
        assert run.is_terminal()

    def test_is_terminal_failed(self) -> None:
        """Failed status should be terminal."""
        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
            status=AgentRunStatus.FAILED,
        )
        assert run.is_terminal()

    def test_is_terminal_cancelled(self) -> None:
        """Cancelled status should be terminal."""
        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
            status=AgentRunStatus.CANCELLED,
        )
        assert run.is_terminal()

    def test_is_terminal_timeout(self) -> None:
        """Timeout status should be terminal."""
        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
            status=AgentRunStatus.TIMEOUT,
        )
        assert run.is_terminal()

    def test_duration_seconds_none_when_not_started(self) -> None:
        """Duration should be None when not started."""
        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
        )
        assert run.duration_seconds is None

    def test_duration_seconds_none_when_not_completed(self) -> None:
        """Duration should be None when not completed."""
        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
            started_at=datetime.now(),
        )
        assert run.duration_seconds is None

    def test_duration_seconds_calculated(self) -> None:
        """Duration should be calculated when both times are set."""
        started = datetime.now()
        completed = started + timedelta(seconds=30)

        run = AgentRun(
            id="test",
            agent_name="test",
            task="test",
            started_at=started,
            completed_at=completed,
        )

        assert run.duration_seconds is not None
        assert abs(run.duration_seconds - 30.0) < 0.01


class TestAgentRunRequest:
    """Tests for AgentRunRequest model."""

    def test_minimal_request(self) -> None:
        """Request should work with just task."""
        request = AgentRunRequest(task="Update the README")

        assert request.task == "Update the README"
        assert request.context is None

    def test_request_with_context(self) -> None:
        """Request should accept context."""
        request = AgentRunRequest(
            task="Update docs",
            context={"focus_area": "authentication"},
        )

        assert request.task == "Update docs"
        assert request.context == {"focus_area": "authentication"}

    def test_task_validation_min_length(self) -> None:
        """Task should have minimum length."""
        with pytest.raises(ValueError):
            AgentRunRequest(task="")


class TestAgentRunResponse:
    """Tests for AgentRunResponse model."""

    def test_response_fields(self) -> None:
        """Response should include run_id and status."""
        response = AgentRunResponse(
            run_id="abc-123",
            status=AgentRunStatus.PENDING,
            message="Started",
        )

        assert response.run_id == "abc-123"
        assert response.status == AgentRunStatus.PENDING
        assert response.message == "Started"


class TestAgentListModels:
    """Tests for agent list models."""

    def test_agent_list_item(self) -> None:
        """AgentListItem should have expected fields."""
        item = AgentListItem(
            name="documentation",
            display_name="Documentation Agent",
            description="Maintains docs",
            max_turns=100,
            timeout_seconds=600,
        )

        assert item.name == "documentation"
        assert item.display_name == "Documentation Agent"
        assert item.max_turns == 100

    def test_agent_list_response(self) -> None:
        """AgentListResponse should wrap items with total."""
        response = AgentListResponse(
            agents=[
                AgentListItem(
                    name="doc",
                    display_name="Doc",
                    description="Docs",
                    max_turns=50,
                    timeout_seconds=300,
                )
            ],
            total=1,
        )

        assert len(response.agents) == 1
        assert response.total == 1
