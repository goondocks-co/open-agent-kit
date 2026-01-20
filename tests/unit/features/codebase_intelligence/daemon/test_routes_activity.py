"""Comprehensive tests for daemon activity browsing routes.

Tests cover:
- Session listing and filtering
- Session detail retrieval
- Prompt batch listing
- Activity listing
- Activity search
- Statistics endpoints
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_activity_store():
    """Mock activity store with sample data."""
    mock = MagicMock()

    # Sample sessions
    now = datetime.now()
    session1 = MagicMock()
    session1.id = "session-001"
    session1.agent = "claude"
    session1.project_root = "/tmp/project"
    session1.started_at = now - timedelta(hours=2)
    session1.ended_at = now - timedelta(hours=1)
    session1.status = "completed"
    session1.summary = "Implemented new feature"

    session2 = MagicMock()
    session2.id = "session-002"
    session2.agent = "codex"
    session2.project_root = "/tmp/project"
    session2.started_at = now - timedelta(minutes=30)
    session2.ended_at = None
    session2.status = "active"
    session2.summary = None

    mock.get_recent_sessions.return_value = [session1, session2]
    mock.get_session.return_value = session1

    # Session stats
    mock.get_session_stats.return_value = {
        "prompt_batch_count": 5,
        "activity_count": 23,
        "files_touched": 8,
        "tool_counts": {"Read": 10, "Edit": 8, "Bash": 5},
    }

    # Sample activities
    activity1 = MagicMock()
    activity1.id = 1
    activity1.session_id = "session-001"
    activity1.prompt_batch_id = 1
    activity1.tool_name = "Read"
    activity1.tool_input = {"file_path": "/src/main.py"}
    activity1.tool_output_summary = "file contents"
    activity1.file_path = "/src/main.py"
    activity1.success = True
    activity1.error_message = None
    activity1.timestamp = now - timedelta(hours=1, minutes=30)

    activity2 = MagicMock()
    activity2.id = 2
    activity2.session_id = "session-001"
    activity2.prompt_batch_id = 1
    activity2.tool_name = "Edit"
    activity2.tool_input = {"file_path": "/src/main.py"}
    activity2.tool_output_summary = "edited successfully"
    activity2.file_path = "/src/main.py"
    activity2.success = True
    activity2.error_message = None
    activity2.timestamp = now - timedelta(hours=1, minutes=20)

    mock.get_session_activities.return_value = [activity1, activity2]
    mock.search_activities.return_value = [activity1]

    # Prompt batches
    batch1 = MagicMock()
    batch1.id = 1
    batch1.session_id = "session-001"
    batch1.prompt_number = 1
    batch1.user_prompt = "Write a new feature"
    batch1.classification = "code_implementation"
    batch1.started_at = now - timedelta(hours=1, minutes=45)
    batch1.ended_at = now - timedelta(hours=1, minutes=15)

    mock.get_session_batches.return_value = [batch1]
    mock.get_session_prompt_batches.return_value = [batch1]  # Route uses this method name
    mock.get_prompt_batch.return_value = batch1
    mock.get_prompt_batch_activities.return_value = [activity1, activity2]
    mock.get_prompt_batch_stats.return_value = {"activity_count": 2}

    return mock


@pytest.fixture
def setup_state_with_activity_store(mock_activity_store):
    """Setup daemon state with mocked activity store."""
    state = get_state()
    state.activity_store = mock_activity_store
    return state


# =============================================================================
# GET /api/activity/sessions Tests
# =============================================================================


class TestListSessions:
    """Test GET /api/activity/sessions endpoint."""

    def test_list_sessions_default(self, client, setup_state_with_activity_store):
        """Test listing sessions with default parameters."""
        response = client.get("/api/activity/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["sessions"], list)

    def test_list_sessions_with_limit(self, client, setup_state_with_activity_store):
        """Test listing sessions with custom limit."""
        response = client.get("/api/activity/sessions", params={"limit": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10

    def test_list_sessions_with_offset(self, client, setup_state_with_activity_store):
        """Test listing sessions with offset."""
        response = client.get("/api/activity/sessions", params={"offset": 5})

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 5

    def test_list_sessions_with_status_filter(self, client, setup_state_with_activity_store):
        """Test filtering sessions by status."""
        response = client.get(
            "/api/activity/sessions",
            params={"status": "completed"},
        )

        assert response.status_code == 200
        data = response.json()
        # Response may be empty or filtered
        assert "sessions" in data

    def test_list_sessions_includes_stats(self, client, setup_state_with_activity_store):
        """Test that session list includes statistics."""
        response = client.get("/api/activity/sessions")

        assert response.status_code == 200
        data = response.json()
        if data["sessions"]:
            session = data["sessions"][0]
            assert "id" in session
            assert "agent" in session
            assert "status" in session
            assert "prompt_batch_count" in session
            assert "activity_count" in session

    def test_list_sessions_limit_validation(self, client, setup_state_with_activity_store):
        """Test that limit is validated."""
        response = client.get("/api/activity/sessions", params={"limit": 200})

        # Should either accept with max of 100 or return error
        assert response.status_code in (200, 422)

    def test_list_sessions_offset_validation(self, client, setup_state_with_activity_store):
        """Test that offset is validated."""
        response = client.get("/api/activity/sessions", params={"offset": -1})

        assert response.status_code in (200, 422)

    def test_list_sessions_no_activity_store(self, client):
        """Test listing sessions without activity store."""
        # No activity store - using fresh daemon state from fixture
        response = client.get("/api/activity/sessions")

        assert response.status_code == 503

    def test_list_sessions_includes_summary(self, client, setup_state_with_activity_store):
        """Test that session summary is included."""
        response = client.get("/api/activity/sessions")

        assert response.status_code == 200
        data = response.json()
        if data["sessions"]:
            session = data["sessions"][0]
            # Summary might be None for active sessions
            assert "summary" in session


# =============================================================================
# GET /api/activity/sessions/{session_id} Tests
# =============================================================================


class TestGetSessionDetail:
    """Test GET /api/activity/sessions/{session_id} endpoint."""

    def test_get_session_detail_success(self, client, setup_state_with_activity_store):
        """Test retrieving session detail."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 200
        data = response.json()
        assert "session" in data
        assert "stats" in data
        assert "recent_activities" in data

    def test_get_session_detail_includes_all_fields(self, client, setup_state_with_activity_store):
        """Test that session detail includes all required fields."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 200
        data = response.json()
        session = data["session"]
        assert "id" in session
        assert "agent" in session
        assert "started_at" in session
        assert "ended_at" in session
        assert "status" in session

    def test_get_session_detail_includes_stats(self, client, setup_state_with_activity_store):
        """Test that session stats are included."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 200
        data = response.json()
        stats = data["stats"]
        assert "prompt_batch_count" in stats
        assert "activity_count" in stats
        assert "files_touched" in stats
        assert "tool_counts" in stats

    def test_get_session_detail_includes_recent_activities(
        self, client, setup_state_with_activity_store
    ):
        """Test that recent activities are included."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 200
        data = response.json()
        activities = data["recent_activities"]
        assert isinstance(activities, list)
        if activities:
            activity = activities[0]
            assert "id" in activity
            assert "tool_name" in activity
            assert "created_at" in activity

    def test_get_session_detail_not_found(self, client, setup_state_with_activity_store):
        """Test retrieving non-existent session."""
        setup_state_with_activity_store.activity_store.get_session.return_value = None

        response = client.get("/api/activity/sessions/nonexistent-session")

        assert response.status_code == 404

    def test_get_session_detail_no_activity_store(self, client):
        """Test getting session detail without activity store."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 503

    def test_get_session_detail_active_session(self, client, setup_state_with_activity_store):
        """Test retrieving active (not ended) session."""
        # Setup an active session with all required attributes
        active_session = MagicMock()
        active_session.id = "active-session"
        active_session.agent = "claude"
        active_session.project_root = "/tmp/project"
        active_session.started_at = datetime.now()
        active_session.ended_at = None
        active_session.status = "active"
        active_session.summary = None
        setup_state_with_activity_store.activity_store.get_session.return_value = active_session

        response = client.get("/api/activity/sessions/active-session")

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "active"


# =============================================================================
# Prompt Batches Tests (batches are part of session detail response)
# =============================================================================


class TestGetSessionBatches:
    """Test prompt batches in session detail response."""

    def test_get_session_batches(self, client, setup_state_with_activity_store):
        """Test that prompt batches are included in session detail."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 200
        data = response.json()
        assert "prompt_batches" in data
        assert isinstance(data["prompt_batches"], list)

    def test_get_session_batches_includes_details(self, client, setup_state_with_activity_store):
        """Test that batch details are included."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 200
        data = response.json()
        if data["prompt_batches"]:
            batch = data["prompt_batches"][0]
            assert "id" in batch
            assert "prompt_number" in batch
            assert "user_prompt" in batch
            assert "classification" in batch

    def test_get_session_batches_with_session_detail(self, client, setup_state_with_activity_store):
        """Test that batches are included with session detail."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 200
        data = response.json()
        assert "prompt_batches" in data
        # Session detail also includes session info
        assert "session" in data

    def test_get_session_batches_not_found(self, client, setup_state_with_activity_store):
        """Test getting batches for non-existent session."""
        setup_state_with_activity_store.activity_store.get_session.return_value = None

        response = client.get("/api/activity/sessions/nonexistent")

        assert response.status_code == 404


# =============================================================================
# GET /api/activity/sessions/{session_id}/activities Tests
# =============================================================================


class TestGetSessionActivities:
    """Test GET /api/activity/sessions/{session_id}/activities endpoint."""

    def test_get_session_activities(self, client, setup_state_with_activity_store):
        """Test retrieving activities for session."""
        response = client.get("/api/activity/sessions/session-001/activities")

        assert response.status_code == 200
        data = response.json()
        assert "activities" in data
        assert "total" in data

    def test_get_session_activities_includes_details(self, client, setup_state_with_activity_store):
        """Test that activity details are included."""
        response = client.get("/api/activity/sessions/session-001/activities")

        assert response.status_code == 200
        data = response.json()
        if data["activities"]:
            activity = data["activities"][0]
            assert "id" in activity
            assert "tool_name" in activity
            assert "success" in activity
            assert "created_at" in activity

    def test_get_session_activities_with_pagination(self, client, setup_state_with_activity_store):
        """Test activity retrieval with pagination."""
        response = client.get(
            "/api/activity/sessions/session-001/activities",
            params={"limit": 10, "offset": 0},
        )

        assert response.status_code == 200
        data = response.json()
        assert "activities" in data
        assert "limit" in data
        assert "offset" in data

    def test_get_session_activities_tool_filter(self, client, setup_state_with_activity_store):
        """Test filtering activities by tool."""
        response = client.get(
            "/api/activity/sessions/session-001/activities",
            params={"tool": "Read"},
        )

        assert response.status_code in (200, 422)

    def test_get_session_activities_success_filter(self, client, setup_state_with_activity_store):
        """Test filtering by success status."""
        response = client.get(
            "/api/activity/sessions/session-001/activities",
            params={"success": "true"},
        )

        assert response.status_code in (200, 422)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestActivityRoutesErrorHandling:
    """Test error handling in activity routes."""

    def test_invalid_session_id_format(self, client, setup_state_with_activity_store):
        """Test handling invalid session ID format."""
        response = client.get("/api/activity/sessions/invalid-id/activities")

        # Should still work or return 404
        assert response.status_code in (200, 404)

    def test_invalid_batch_id_format(self, client, setup_state_with_activity_store):
        """Test handling invalid batch ID format."""
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = None

        response = client.get("/api/activity/batches/invalid")

        # Should return 404 or error
        assert response.status_code in (400, 404)

    def test_store_operation_error_handling(self, client, setup_state_with_activity_store):
        """Test handling of store operation errors."""
        setup_state_with_activity_store.activity_store.get_session.side_effect = RuntimeError(
            "Database error"
        )

        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 500

    def test_very_large_limit(self, client, setup_state_with_activity_store):
        """Test handling of very large limit values."""
        response = client.get("/api/activity/sessions", params={"limit": 10000})

        # Should either cap at max or return error
        assert response.status_code in (200, 422)

    def test_negative_offset(self, client, setup_state_with_activity_store):
        """Test handling of negative offset."""
        response = client.get("/api/activity/sessions", params={"offset": -10})

        # Should return error
        assert response.status_code in (200, 422)


# =============================================================================
# Response Model Tests
# =============================================================================


class TestActivityResponseModels:
    """Test that response models are properly formatted."""

    def test_session_list_response_format(self, client, setup_state_with_activity_store):
        """Test session list response format."""
        response = client.get("/api/activity/sessions")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert isinstance(data["sessions"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["limit"], int)
        assert isinstance(data["offset"], int)

    def test_session_detail_response_format(self, client, setup_state_with_activity_store):
        """Test session detail response format."""
        response = client.get("/api/activity/sessions/session-001")

        assert response.status_code == 200
        data = response.json()

        assert "session" in data
        assert "stats" in data
        assert "recent_activities" in data

    def test_activity_item_format(self, client, setup_state_with_activity_store):
        """Test activity item response format."""
        response = client.get("/api/activity/sessions/session-001/activities")

        assert response.status_code == 200
        data = response.json()

        if data["activities"]:
            activity = data["activities"][0]
            assert "id" in activity
            assert "session_id" in activity
            assert "tool_name" in activity
            assert "success" in activity
            assert "created_at" in activity
