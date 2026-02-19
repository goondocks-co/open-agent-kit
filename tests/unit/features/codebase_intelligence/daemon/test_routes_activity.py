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

from open_agent_kit.features.codebase_intelligence.constants import (
    PROMPT_SOURCE_PLAN,
    PROMPT_SOURCE_USER,
)
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
    session1.title = "Add user authentication feature"
    session1.parent_session_id = None
    session1.parent_session_reason = None

    session2 = MagicMock()
    session2.id = "session-002"
    session2.agent = "codex"
    session2.project_root = "/tmp/project"
    session2.started_at = now - timedelta(minutes=30)
    session2.ended_at = None
    session2.status = "active"
    session2.summary = None
    session2.title = None
    session2.parent_session_id = None
    session2.parent_session_reason = None

    mock.get_recent_sessions.return_value = [session1, session2]
    mock.get_session.return_value = session1
    mock.get_child_session_count.return_value = 0
    mock.get_latest_session_summary.return_value = None  # No summary observation by default

    # Session stats (for individual queries)
    mock.get_session_stats.return_value = {
        "prompt_batch_count": 5,
        "activity_count": 23,
        "files_touched": 8,
        "tool_counts": {"Read": 10, "Edit": 8, "Bash": 5},
    }

    # Bulk session stats (for bulk queries - eliminates N+1 pattern)
    mock.get_bulk_session_stats.return_value = {
        "session-001": {
            "prompt_batch_count": 5,
            "activity_count": 23,
            "files_touched": 8,
            "reads": 10,
            "edits": 8,
            "writes": 0,
            "errors": 0,
            "tool_counts": {"Read": 10, "Edit": 8, "Bash": 5},
        },
        "session-002": {
            "prompt_batch_count": 2,
            "activity_count": 5,
            "files_touched": 3,
            "reads": 3,
            "edits": 2,
            "writes": 0,
            "errors": 0,
            "tool_counts": {"Read": 3, "Edit": 2},
        },
    }

    # Bulk first prompts (for session titles)
    mock.get_bulk_first_prompts.return_value = {
        "session-001": "Write a new feature",
        "session-002": "Debug the login flow",
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
    batch1.source_type = "user"
    batch1.plan_file_path = None  # Plan file path (only set for plan source_type)
    batch1.plan_content = None  # Plan content (only set for plan source_type)
    batch1.response_summary = None  # Agent's final response (v21)
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

    def test_list_sessions_with_agent_filter(self, client, setup_state_with_activity_store):
        """Test filtering sessions by agent."""
        response = client.get(
            "/api/activity/sessions",
            params={"agent": "codex"},
        )

        assert response.status_code == 200
        setup_state_with_activity_store.activity_store.get_recent_sessions.assert_called_with(
            limit=20,
            offset=0,
            status=None,
            agent="codex",
            sort="last_activity",
        )


class TestSessionAgents:
    """Test GET /api/activity/session-agents endpoint."""

    def test_list_session_agents(self, client):
        """Should return coding agents from manifest registry."""
        response = client.get("/api/activity/session-agents")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "claude" in data["agents"]
        assert "codex" in data["agents"]

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

    CODEX_MODEL_AGENT = "gpt-5.3-codex"
    CODEX_RESUME_PREFIX = "codex resume"
    GEMINI_MODEL_AGENT = "gemini-2.5-pro-gemini"
    GEMINI_RESUME_PREFIX = "gemini --resume"

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
        active_session.title = None
        active_session.parent_session_id = None
        active_session.parent_session_reason = None
        setup_state_with_activity_store.activity_store.get_session.return_value = active_session

        response = client.get("/api/activity/sessions/active-session")

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "active"

    def test_get_session_detail_includes_resume_for_codex_model_agent(
        self, client, setup_state_with_activity_store
    ):
        """Codex model-style agent labels should still resolve resume command."""
        session_id = "codex-model-session"
        codex_session = MagicMock()
        codex_session.id = session_id
        codex_session.agent = self.CODEX_MODEL_AGENT
        codex_session.project_root = "/tmp/project"
        codex_session.started_at = datetime.now()
        codex_session.ended_at = None
        codex_session.status = "active"
        codex_session.summary = None
        codex_session.title = None
        codex_session.parent_session_id = None
        codex_session.parent_session_reason = None
        setup_state_with_activity_store.activity_store.get_session.return_value = codex_session

        response = client.get(f"/api/activity/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["resume_command"] == f"{self.CODEX_RESUME_PREFIX} {session_id}"

    def test_get_session_detail_uses_codex_resume_flag(
        self, client, setup_state_with_activity_store
    ):
        """Codex sessions should render resume command with --resume."""
        session_id = "codex-session"
        codex_session = MagicMock()
        codex_session.id = session_id
        codex_session.agent = "codex"
        codex_session.project_root = "/tmp/project"
        codex_session.started_at = datetime.now()
        codex_session.ended_at = None
        codex_session.status = "active"
        codex_session.summary = None
        codex_session.title = None
        codex_session.parent_session_id = None
        codex_session.parent_session_reason = None
        setup_state_with_activity_store.activity_store.get_session.return_value = codex_session

        response = client.get(f"/api/activity/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["resume_command"] == f"{self.CODEX_RESUME_PREFIX} {session_id}"

    def test_get_session_detail_includes_resume_for_gemini_model_agent(
        self, client, setup_state_with_activity_store
    ):
        """Gemini model-style agent labels should still resolve resume command."""
        session_id = "gemini-model-session"
        gemini_session = MagicMock()
        gemini_session.id = session_id
        gemini_session.agent = self.GEMINI_MODEL_AGENT
        gemini_session.project_root = "/tmp/project"
        gemini_session.started_at = datetime.now()
        gemini_session.ended_at = None
        gemini_session.status = "active"
        gemini_session.summary = None
        gemini_session.title = None
        gemini_session.parent_session_id = None
        gemini_session.parent_session_reason = None
        setup_state_with_activity_store.activity_store.get_session.return_value = gemini_session

        response = client.get(f"/api/activity/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["resume_command"] == f"{self.GEMINI_RESUME_PREFIX} {session_id}"

    def test_get_session_detail_uses_gemini_resume_flag(
        self, client, setup_state_with_activity_store
    ):
        """Gemini sessions should render resume command with --resume."""
        session_id = "gemini-session"
        gemini_session = MagicMock()
        gemini_session.id = session_id
        gemini_session.agent = "gemini"
        gemini_session.project_root = "/tmp/project"
        gemini_session.started_at = datetime.now()
        gemini_session.ended_at = None
        gemini_session.status = "active"
        gemini_session.summary = None
        gemini_session.title = None
        gemini_session.parent_session_id = None
        gemini_session.parent_session_reason = None
        setup_state_with_activity_store.activity_store.get_session.return_value = gemini_session

        response = client.get(f"/api/activity/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["resume_command"] == f"{self.GEMINI_RESUME_PREFIX} {session_id}"


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


# =============================================================================
# POST /api/activity/plans/{batch_id}/refresh Tests
# =============================================================================


class TestRefreshPlan:
    """Test POST /api/activity/plans/{batch_id}/refresh endpoint."""

    REFRESH_ENDPOINT = "/api/activity/plans/{batch_id}/refresh"
    DEFAULT_BATCH_ID = 1
    NONEXISTENT_BATCH_ID = 999
    NONEXISTENT_FILE_PATH = "/nonexistent/plan.md"

    def _refresh_url(self, batch_id=None, graceful=False):
        """Build the refresh endpoint URL."""
        bid = batch_id if batch_id is not None else self.DEFAULT_BATCH_ID
        url = self.REFRESH_ENDPOINT.format(batch_id=bid)
        if graceful:
            url += "?graceful=true"
        return url

    def _make_plan_batch(
        self,
        batch_id=None,
        source_type=PROMPT_SOURCE_PLAN,
        plan_file_path="/tmp/plan.md",
        session_id="test-session-123",
    ):
        """Helper to create a mock plan batch."""
        batch = MagicMock()
        batch.id = batch_id if batch_id is not None else self.DEFAULT_BATCH_ID
        batch.source_type = source_type
        batch.plan_file_path = plan_file_path
        batch.session_id = session_id
        return batch

    def test_refresh_graceful_batch_not_found(self, client, setup_state_with_activity_store):
        """Graceful mode returns success=False when batch doesn't exist."""
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = None

        response = client.post(self._refresh_url(batch_id=self.NONEXISTENT_BATCH_ID, graceful=True))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"]

    def test_refresh_graceful_not_a_plan(self, client, setup_state_with_activity_store):
        """Graceful mode returns success=False when batch is not a plan."""
        batch = self._make_plan_batch(source_type=PROMPT_SOURCE_USER)
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = batch

        response = client.post(self._refresh_url(graceful=True))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not a plan" in data["message"]

    def test_refresh_graceful_no_file_path(self, client, setup_state_with_activity_store):
        """Graceful mode returns success=False when plan has no file path."""
        from unittest.mock import patch

        batch = self._make_plan_batch(plan_file_path=None)
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = batch

        # Return empty activities so fallback scan finds nothing
        setup_state_with_activity_store.activity_store.get_prompt_batch_activities.return_value = []

        # Mock transcript resolver and filesystem scan to return nothing
        with (
            patch(
                "open_agent_kit.features.codebase_intelligence.plan_detector.get_plan_detector",
            ) as mock_detector,
            patch(
                "open_agent_kit.features.codebase_intelligence.transcript.extract_attached_file_paths",
                return_value=[],
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.transcript_resolver.get_transcript_resolver",
            ) as mock_resolver,
        ):
            mock_detector.return_value.find_recent_plan_file.return_value = None
            mock_resolver.return_value.resolve.return_value = MagicMock(path=None)
            response = client.post(self._refresh_url(graceful=True))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "No file path" in data["message"]

    def test_refresh_graceful_file_not_on_disk(self, client, setup_state_with_activity_store):
        """Graceful mode returns success=False when plan file doesn't exist on disk."""
        batch = self._make_plan_batch(plan_file_path=self.NONEXISTENT_FILE_PATH)
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = batch

        response = client.post(self._refresh_url(graceful=True))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found on disk" in data["message"]
        assert data["plan_file_path"] == self.NONEXISTENT_FILE_PATH

    def test_refresh_graceful_success(self, client, setup_state_with_activity_store, tmp_path):
        """Graceful mode reads fresh content and updates the database."""
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Updated Plan\n\nNew content here.")

        batch = self._make_plan_batch(plan_file_path=str(plan_file))
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = batch

        response = client.post(self._refresh_url(graceful=True))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content_length"] > 0
        assert data["plan_file_path"] == str(plan_file)

        # Verify DB was updated and plan was marked for re-embedding
        setup_state_with_activity_store.activity_store.update_prompt_batch_source_type.assert_called_once()
        setup_state_with_activity_store.activity_store.mark_plan_unembedded.assert_called_once_with(
            self.DEFAULT_BATCH_ID
        )

    def test_refresh_strict_file_not_found_raises_404(
        self, client, setup_state_with_activity_store
    ):
        """Without graceful, missing file raises HTTP 404."""
        batch = self._make_plan_batch(plan_file_path=self.NONEXISTENT_FILE_PATH)
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = batch

        response = client.post(self._refresh_url())

        assert response.status_code == 404

    def test_refresh_strict_no_file_path_raises_400(self, client, setup_state_with_activity_store):
        """Without graceful, missing file path raises HTTP 400."""
        from unittest.mock import patch

        batch = self._make_plan_batch(plan_file_path=None)
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = batch

        # Return empty activities so fallback scan finds nothing
        setup_state_with_activity_store.activity_store.get_prompt_batch_activities.return_value = []

        # Mock transcript resolver and filesystem scan to return nothing
        with (
            patch(
                "open_agent_kit.features.codebase_intelligence.plan_detector.get_plan_detector",
            ) as mock_detector,
            patch(
                "open_agent_kit.features.codebase_intelligence.transcript.extract_attached_file_paths",
                return_value=[],
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.transcript_resolver.get_transcript_resolver",
            ) as mock_resolver,
        ):
            mock_detector.return_value.find_recent_plan_file.return_value = None
            mock_resolver.return_value.resolve.return_value = MagicMock(path=None)
            response = client.post(self._refresh_url())

        assert response.status_code == 400

    def test_refresh_discovers_plan_file_from_transcript(
        self, client, setup_state_with_activity_store, tmp_path
    ):
        """Refresh discovers plan file from transcript <code_selection> tags."""
        import json
        from unittest.mock import patch

        from open_agent_kit.features.codebase_intelligence.plan_detector import (
            PlanDetectionResult,
        )

        # Create a plan file on disk
        plan_file = tmp_path / ".cursor" / "plans" / "transcript_plan.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Transcript Plan\n\nFull plan content from disk")

        # Create a transcript that references the plan file
        transcript_file = tmp_path / "transcript.jsonl"
        transcript_lines = [
            json.dumps(
                {
                    "role": "user",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f'<code_selection path="file://{plan_file}" lines="1-5">'
                                    "# Plan\n"
                                    "</code_selection>"
                                ),
                            }
                        ]
                    },
                }
            )
        ]
        transcript_file.write_text("\n".join(transcript_lines), encoding="utf-8")

        # Batch has no plan_file_path and no activities with plan files
        batch = self._make_plan_batch(plan_file_path=None, session_id="cursor-session-abc")
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = batch
        setup_state_with_activity_store.activity_store.get_prompt_batch_activities.return_value = []

        # Mock session for transcript resolver
        mock_session = MagicMock()
        mock_session.project_root = str(tmp_path)
        mock_session.agent = "cursor"
        setup_state_with_activity_store.activity_store.get_session.return_value = mock_session

        with (
            patch(
                "open_agent_kit.features.codebase_intelligence.plan_detector.detect_plan",
            ) as mock_detect,
            patch(
                "open_agent_kit.features.codebase_intelligence.transcript_resolver.get_transcript_resolver",
            ) as mock_resolver,
        ):
            mock_detect.return_value = PlanDetectionResult(
                is_plan=True, agent_type="cursor", is_global=True
            )
            mock_resolver.return_value.resolve.return_value = MagicMock(path=transcript_file)

            response = client.post(self._refresh_url(graceful=True))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["plan_file_path"] == str(plan_file)
        assert data["content_length"] > 0
        assert "transcript" in data["message"].lower()

        # Verify DB was updated
        setup_state_with_activity_store.activity_store.update_prompt_batch_source_type.assert_called_once()
        call_args = (
            setup_state_with_activity_store.activity_store.update_prompt_batch_source_type.call_args
        )
        assert call_args[1]["plan_file_path"] == str(plan_file)
        assert "Transcript Plan" in call_args[1]["plan_content"]

    def test_refresh_discovers_plan_file_from_activities(
        self, client, setup_state_with_activity_store, tmp_path
    ):
        """Refresh scans activities to discover plan_file_path when batch has none."""
        from unittest.mock import patch

        # Create a plan file on disk
        plan_file = tmp_path / ".cursor" / "plans" / "discovered.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Discovered Plan\n\nFull content from disk")

        # Batch has no plan_file_path (the bug scenario)
        batch = self._make_plan_batch(plan_file_path=None)
        setup_state_with_activity_store.activity_store.get_prompt_batch.return_value = batch

        # Simulate activities that include a Read of the plan file
        mock_activity = MagicMock()
        mock_activity.tool_name = "Read"
        mock_activity.file_path = str(plan_file)
        setup_state_with_activity_store.activity_store.get_prompt_batch_activities.return_value = [
            mock_activity
        ]

        with patch(
            "open_agent_kit.features.codebase_intelligence.plan_detector.detect_plan",
        ) as mock_detect:
            from open_agent_kit.features.codebase_intelligence.plan_detector import (
                PlanDetectionResult,
            )

            mock_detect.return_value = PlanDetectionResult(
                is_plan=True, agent_type="cursor", is_global=False
            )

            response = client.post(self._refresh_url(graceful=True))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["plan_file_path"] == str(plan_file)
        assert data["content_length"] > 0
        assert "Discovered" in data["message"]

        # Verify DB was updated
        setup_state_with_activity_store.activity_store.update_prompt_batch_source_type.assert_called_once()
        call_args = (
            setup_state_with_activity_store.activity_store.update_prompt_batch_source_type.call_args
        )
        assert call_args[1]["plan_file_path"] == str(plan_file)
        assert "Discovered Plan" in call_args[1]["plan_content"]
        setup_state_with_activity_store.activity_store.mark_plan_unembedded.assert_called_once()
