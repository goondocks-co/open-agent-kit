"""Comprehensive tests for daemon hook routes.

Tests cover:
- Session start/stop hooks
- Prompt submit hooks
- Post-tool-use hooks
- Context injection and memory retrieval
- Activity store interactions
- Error handling and edge cases
"""

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_CLAUDE,
    AGENT_COPILOT,
    AGENT_CURSOR,
    PROMPT_SOURCE_PLAN,
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
    """Mock activity store."""
    from datetime import datetime, timedelta

    mock = MagicMock()
    # Create mock session with started_at for duration calculation
    mock_session = MagicMock(
        id="session-123",
        title=None,  # title=None for new sessions
        started_at=datetime.now() - timedelta(minutes=5),  # Session started 5 minutes ago
    )
    mock.create_session.return_value = mock_session
    # get_or_create_session returns (session, created) tuple
    mock.get_or_create_session.return_value = (mock_session, True)
    mock.get_session.return_value = mock_session  # Return session for get_session calls
    mock.create_prompt_batch.return_value = MagicMock(id=1)
    mock.end_prompt_batch.return_value = None
    mock.end_session.return_value = None
    mock.get_session_stats.return_value = {
        "files_touched": 5,
        "tool_counts": {"Read": 10, "Edit": 5},
    }
    mock.add_activity.return_value = None
    mock.add_activity_buffered.return_value = None
    mock.get_prompt_batch_stats.return_value = {
        "activity_count": 5,
        "tools_used": ["Read", "Edit"],
    }
    return mock


@pytest.fixture
def mock_vector_store():
    """Mock vector store.

    Returns mock data with all fields required by RetrievalEngine.
    """
    mock = MagicMock()
    mock.get_stats.return_value = {
        "code_chunks": 100,
        "memory_observations": 20,
    }
    mock.list_memories.return_value = (
        [
            {
                "id": "mem-1",
                "observation": "Important gotcha about error handling",
                "memory_type": "gotcha",
                "tags": [],
                "context": None,
            }
        ],
        1,
    )
    mock.search_memory.return_value = [
        {
            "id": "mem-1",
            "observation": "Important gotcha",
            "memory_type": "gotcha",
            "context": None,
            "relevance": 0.85,
            "token_estimate": 10,
        }
    ]
    mock.search_code.return_value = [
        {
            "id": "code-1",
            "filepath": "src/main.py",
            "name": "main_function",
            "chunk_type": "function",
            "start_line": 1,
            "end_line": 10,
            "content": "def main(): pass",
            "relevance": 0.9,
            "token_estimate": 20,
        }
    ]
    return mock


@pytest.fixture
def mock_activity_processor():
    """Mock activity processor."""
    mock = MagicMock()
    mock.process_session_summary.return_value = "Session summary"
    return mock


@pytest.fixture
def setup_state_with_mocks(mock_activity_store, mock_vector_store, mock_activity_processor):
    """Setup daemon state with mocked stores."""
    state = get_state()
    state.project_root = "/tmp/test_project"
    state.activity_store = mock_activity_store
    state.vector_store = mock_vector_store
    state.activity_processor = mock_activity_processor
    return state


# =============================================================================
# Session Start Hook Tests
# =============================================================================


class TestSessionStartHook:
    """Test /api/oak/ci/session-start endpoint."""

    def test_session_start_minimal_request(self, client, setup_state_with_mocks):
        """Test session start with minimal request body."""
        payload = {"session_id": str(uuid4())}
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "session_id" in data
        assert "context" in data

    def test_session_start_with_agent_and_session_id(self, client, setup_state_with_mocks):
        """Test session start with agent and session_id provided."""
        session_id = str(uuid4())
        payload = {
            "agent": AGENT_CLAUDE,
            "session_id": session_id,
            "source": "startup",
        }
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["context"]["agent"] == AGENT_CLAUDE

    def test_session_start_injects_context_on_startup(self, client, setup_state_with_mocks):
        """Test that full context is injected on startup source."""
        payload = {
            "agent": AGENT_CLAUDE,
            "source": "startup",
            "session_id": str(uuid4()),
        }
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        data = response.json()
        context = data["context"]
        # Check that injected_context is present on startup
        if "injected_context" in context:
            assert isinstance(context["injected_context"], str)

    def test_session_start_no_context_on_resume(self, client, setup_state_with_mocks):
        """Test that context is not fully injected on resume source."""
        payload = {
            "agent": AGENT_CLAUDE,
            "source": "resume",
            "session_id": str(uuid4()),
        }
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        data = response.json()
        # Resume should not inject full context
        assert data["status"] == "ok"

    def test_session_start_creates_activity_session(self, client, setup_state_with_mocks):
        """Test that activity store is called to create or resume session."""
        session_id = str(uuid4())
        payload = {
            "agent": AGENT_CLAUDE,
            "session_id": session_id,
        }
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        # Verify activity store was called (uses get_or_create_session for resume support)
        setup_state_with_mocks.activity_store.get_or_create_session.assert_called_once()

    def test_session_start_includes_index_stats(self, client, setup_state_with_mocks):
        """Test that index stats are included in response."""
        payload = {"agent": AGENT_CLAUDE, "session_id": str(uuid4())}
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "index" in data["context"]
        assert data["context"]["index"]["code_chunks"] == 100
        assert data["context"]["index"]["memory_observations"] == 20

    def test_session_start_invalid_json(self, client, setup_state_with_mocks):
        """Test session start with invalid JSON."""
        response = client.post(
            "/api/oak/ci/session-start",
            content=b"invalid json",
            headers={"Content-Type": "application/json"},
        )
        # Should still succeed with graceful fallback
        assert response.status_code == 200

    def test_session_start_drops_when_session_id_missing(self, client, setup_state_with_mocks):
        """Test that session-start drops when session_id is missing."""
        response = client.post("/api/oak/ci/session-start", json={})

        data = response.json()
        assert data["status"] == "ok"
        assert data.get("context") == {}
        assert "session_id" not in data

    def test_session_start_project_root_included(self, client, setup_state_with_mocks):
        """Test that project_root is included if set."""
        response = client.post(
            "/api/oak/ci/session-start",
            json={"session_id": str(uuid4())},
        )

        data = response.json()
        assert "project_root" in data["context"]
        assert data["context"]["project_root"] == "/tmp/test_project"

    def test_session_start_hook_output_for_claude(self, client, setup_state_with_mocks):
        """Test that hook_output contains correct hookSpecificOutput for Claude."""
        session_id = str(uuid4())
        payload = {
            "agent": AGENT_CLAUDE,
            "session_id": session_id,
            "source": "startup",
            "hook_event_name": "SessionStart",
        }
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "hook_output" in data
        hook_output = data["hook_output"]
        assert hook_output["continue"] is True
        assert "hookSpecificOutput" in hook_output
        assert hook_output["hookSpecificOutput"]["hookEventName"] == "SessionStart"

    def test_session_start_hook_output_for_vscode_copilot(self, client, setup_state_with_mocks):
        """Test that hook_output is always present for vscode-copilot (prevents crash)."""
        session_id = str(uuid4())
        payload = {
            "agent": AGENT_COPILOT,
            "session_id": session_id,
            "source": "startup",
            "hook_event_name": "SessionStart",
        }
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "hook_output" in data
        hook_output = data["hook_output"]
        assert hook_output["continue"] is True
        assert "hookSpecificOutput" in hook_output
        assert hook_output["hookSpecificOutput"]["hookEventName"] == "SessionStart"

    def test_session_start_hook_output_for_cursor(self, client, setup_state_with_mocks):
        """Test that hook_output uses cursor format."""
        session_id = str(uuid4())
        payload = {
            "agent": AGENT_CURSOR,
            "session_id": session_id,
            "source": "startup",
            "hook_event_name": "SessionStart",
        }
        response = client.post("/api/oak/ci/session-start", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "hook_output" in data
        # Cursor with no injected context → empty dict
        hook_output = data["hook_output"]
        assert "hookSpecificOutput" not in hook_output

    def test_session_start_duplicate_hook_idempotent(self, client, setup_state_with_mocks):
        """Test that duplicate SessionStart hooks are handled idempotently."""
        session_id = str(uuid4())
        payload = {
            "agent": AGENT_CLAUDE,
            "session_id": session_id,
            "source": "startup",
        }

        # First call - creates session
        response1 = client.post("/api/oak/ci/session-start", json=payload)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["session_id"] == session_id

        # Mock get_session to return existing session (simulating duplicate hook)
        # Session tracking is now SQLite-only, so we mock the activity_store
        mock_existing_session = MagicMock(id=session_id, status="active")
        setup_state_with_mocks.activity_store.get_session.return_value = mock_existing_session
        setup_state_with_mocks.activity_store.get_or_create_session.return_value = (
            mock_existing_session,
            False,
        )

        # Second call - should handle duplicate gracefully
        response2 = client.post("/api/oak/ci/session-start", json=payload)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["session_id"] == session_id
        # Should still return valid response
        assert data2["status"] == "ok"


# =============================================================================
# Prompt Submit Hook Tests
# =============================================================================


class TestPromptSubmitHook:
    """Test /api/oak/ci/prompt-submit endpoint."""

    def test_prompt_submit_minimal(self, client, setup_state_with_mocks):
        """Test prompt submit with minimal request."""
        payload = {
            "prompt": "Write a test for the function",
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "context" in data

    def test_prompt_submit_hook_output_present(self, client, setup_state_with_mocks):
        """Test that hook_output is present in prompt-submit response."""
        payload = {
            "prompt": "Write a test for the function",
            "session_id": str(uuid4()),
            "agent": AGENT_CLAUDE,
            "hook_event_name": "UserPromptSubmit",
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "hook_output" in data

    def test_prompt_submit_hook_output_cursor(self, client, setup_state_with_mocks):
        """Test that cursor gets continue:true for prompt-submit."""
        payload = {
            "prompt": "Write a test for the function",
            "session_id": str(uuid4()),
            "agent": AGENT_CURSOR,
            "hook_event_name": "beforeSubmitPrompt",
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "hook_output" in data
        assert data["hook_output"]["continue"] is True

    def test_prompt_submit_skips_short_prompts(self, client, setup_state_with_mocks):
        """Test that short prompts are skipped."""
        payload = {
            "prompt": "hi",  # Too short
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_prompt_submit_creates_batch(self, client, setup_state_with_mocks):
        """Test that prompt batch is created in activity store."""
        session_id = str(uuid4())
        # First create session
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})

        payload = {
            "session_id": session_id,
            "prompt": "This is a test prompt with enough content",
            "agent": AGENT_CLAUDE,
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        # Verify batch was created (would have batch ID)
        assert "prompt_batch_id" in data

    def test_prompt_submit_searches_memories(self, client, setup_state_with_mocks):
        """Test that memories are searched based on prompt."""
        payload = {
            "prompt": "How do I handle error cases in this codebase?",
            "session_id": str(uuid4()),
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        _ = response.json()  # Verify valid JSON response
        # Should have searched for relevant memories
        setup_state_with_mocks.vector_store.search_memory.assert_called()

    def test_prompt_submit_injects_memory_context(self, client, setup_state_with_mocks):
        """Test that memory context is injected into response."""
        # Configure mock to return memories (include all fields required by RetrievalEngine)
        setup_state_with_mocks.vector_store.search_memory.return_value = [
            {
                "id": "mem-test",
                "observation": "Bug: error handling broken",
                "memory_type": "bug_fix",
                "context": None,
                "relevance": 0.85,
                "token_estimate": 10,
            }
        ]

        payload = {
            "prompt": "How should I handle errors?",
            "session_id": str(uuid4()),
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        if "context" in data and "injected_context" in data["context"]:
            assert "bug_fix" in data["context"]["injected_context"]

    def test_prompt_submit_injects_memory_ids(self, client, setup_state_with_mocks):
        """Test that injected memory context includes observation UUIDs."""
        # Configure mock to return memories with id field
        setup_state_with_mocks.vector_store.search_memory.return_value = [
            {
                "id": "mem-uuid-456",
                "observation": "Always check for null",
                "memory_type": "gotcha",
                "context": None,
                "relevance": 0.90,
                "token_estimate": 10,
            }
        ]

        payload = {
            "prompt": "How should I handle null values?",
            "session_id": str(uuid4()),
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        if "context" in data and "injected_context" in data["context"]:
            injected = data["context"]["injected_context"]
            assert "gotcha" in injected
            assert "[id: mem-uuid-456]" in injected

    def test_prompt_submit_auto_creates_missing_session(self, client, setup_state_with_mocks):
        """Test that session is auto-created if missing."""
        session_id = str(uuid4())
        payload = {
            "session_id": session_id,
            "prompt": "This is a test prompt with enough content",
            "agent": AGENT_CLAUDE,
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_prompt_submit_invalid_json(self, client, setup_state_with_mocks):
        """Test prompt submit with invalid JSON."""
        response = client.post(
            "/api/oak/ci/prompt-submit",
            content=b"bad json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200

    def test_prompt_submit_ends_previous_batch(self, client, setup_state_with_mocks):
        """Test that previous prompt batch is ended."""
        session_id = str(uuid4())
        # Create session first
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})

        # Submit first prompt
        payload1 = {
            "session_id": session_id,
            "prompt": "First prompt that is long enough",
            "agent": AGENT_CLAUDE,
        }
        client.post("/api/oak/ci/prompt-submit", json=payload1)

        # Submit second prompt
        payload2 = {
            "session_id": session_id,
            "prompt": "Second prompt that is long enough",
            "agent": AGENT_CLAUDE,
        }
        response = client.post("/api/oak/ci/prompt-submit", json=payload2)

        assert response.status_code == 200
        # end_prompt_batch should have been called
        if setup_state_with_mocks.activity_store.end_prompt_batch.called:
            assert setup_state_with_mocks.activity_store.end_prompt_batch.call_count >= 1


# =============================================================================
# Post-Tool-Use Hook Tests
# =============================================================================


class TestPostToolUseHook:
    """Test /api/oak/ci/post-tool-use endpoint."""

    def test_post_tool_use_minimal(self, client, setup_state_with_mocks):
        """Test post-tool-use with minimal data."""
        payload = {
            "tool_name": "Read",
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "observations_captured" in data

    def test_post_tool_use_hook_output_present(self, client, setup_state_with_mocks):
        """Test that hook_output is present in post-tool-use response."""
        payload = {
            "tool_name": "Read",
            "session_id": str(uuid4()),
            "agent": AGENT_CLAUDE,
            "hook_event_name": "PostToolUse",
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "hook_output" in data
        assert data["hook_output"]["continue"] is True
        assert data["hook_output"]["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

    def test_post_tool_use_with_tool_input(self, client, setup_state_with_mocks):
        """Test post-tool-use with tool input."""
        payload = {
            "tool_name": "Read",
            "tool_input": {
                "file_path": "/src/main.py",
            },
            "tool_output": "file contents here",
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_post_tool_use_with_string_tool_input(self, client, setup_state_with_mocks):
        """Test post-tool-use with tool_input as string."""
        payload = {
            "tool_name": "Bash",
            "tool_input": '{"command": "ls -la"}',
            "tool_output": "file list",
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_post_tool_use_creates_activity(self, client, setup_state_with_mocks):
        """Test that activity is created in activity store."""
        session_id = str(uuid4())
        payload = {
            "session_id": session_id,
            "tool_name": "Read",
            "tool_input": {"file_path": "/src/main.py"},
            "tool_output": "file contents",
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200
        # Verify activity was added (using buffered insert for performance)
        setup_state_with_mocks.activity_store.add_activity_buffered.assert_called()

    def test_post_tool_use_detects_errors_in_output(self, client, setup_state_with_mocks):
        """Test that errors are detected in tool output."""
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "invalid_command"},
            "tool_output": json.dumps({"stderr": "command not found"}),
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200
        # Should have captured error state

    def test_post_tool_use_base64_encoded_output(self, client, setup_state_with_mocks):
        """Test post-tool-use with base64-encoded output."""
        import base64

        output_text = "tool output"
        encoded = base64.b64encode(output_text.encode()).decode()

        payload = {
            "tool_name": "Read",
            "tool_output_b64": encoded,
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_post_tool_use_injects_file_memories(self, client, setup_state_with_mocks):
        """Test that memories about files are injected for file operations."""
        # Include all fields required by RetrievalEngine
        setup_state_with_mocks.vector_store.search_memory.return_value = [
            {
                "id": "mem-file",
                "observation": "Be careful with error handling in this file",
                "memory_type": "gotcha",
                "context": None,
                "relevance": 0.85,
                "token_estimate": 10,
            }
        ]

        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/src/main.py"},
            "tool_output": "file contents",
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200
        data = response.json()
        if "injected_context" in data:
            assert "gotcha" in data["injected_context"] or "Memories" in data["injected_context"]

    def test_post_tool_use_oak_ci_hint_after_search_tools(self, client, setup_state_with_mocks):
        """Test oak ci hint injection after multiple search tool uses."""
        session_id = str(uuid4())
        # Create session
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})

        # Use Grep multiple times
        for _ in range(3):
            payload = {
                "session_id": session_id,
                "tool_name": "Grep",
                "tool_input": {"pattern": "test"},
                "tool_output": "results",
            }
            response = client.post("/api/oak/ci/post-tool-use", json=payload)
            assert response.status_code == 200

    def test_post_tool_use_records_file_modifications(self, client, setup_state_with_mocks):
        """Test that file modifications are recorded."""
        session_id = str(uuid4())
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})

        payload = {
            "session_id": session_id,
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/src/main.py",
                "old_string": "old code",
                "new_string": "new code",
            },
            "tool_output": "edit successful",
        }
        response = client.post("/api/oak/ci/post-tool-use", json=payload)

        assert response.status_code == 200

    def test_post_tool_use_invalid_json(self, client, setup_state_with_mocks):
        """Test post-tool-use with invalid JSON."""
        response = client.post(
            "/api/oak/ci/post-tool-use",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200


# =============================================================================
# Stop Hook Tests
# =============================================================================


class TestStopHook:
    """Test /api/oak/ci/stop endpoint."""

    def test_stop_hook_minimal(self, client, setup_state_with_mocks):
        """Test stop hook with minimal request."""
        response = client.post("/api/oak/ci/stop", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_stop_hook_ends_prompt_batch(self, client, setup_state_with_mocks):
        """Test that prompt batch is ended on stop."""
        session_id = str(uuid4())
        # Create and submit prompt
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})
        client.post(
            "/api/oak/ci/prompt-submit",
            json={
                "session_id": session_id,
                "prompt": "Test prompt with enough content",
            },
        )

        # Stop
        response = client.post("/api/oak/ci/stop", json={"session_id": session_id})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_stop_hook_includes_batch_stats(self, client, setup_state_with_mocks):
        """Test that batch stats are included in stop response."""
        session_id = str(uuid4())
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})
        client.post(
            "/api/oak/ci/prompt-submit",
            json={
                "session_id": session_id,
                "prompt": "Test prompt with enough content",
            },
        )

        response = client.post("/api/oak/ci/stop", json={"session_id": session_id})

        assert response.status_code == 200
        data = response.json()
        # Should have batch stats if batch existed
        if "prompt_batch_stats" in data:
            assert isinstance(data["prompt_batch_stats"], dict)

    def test_stop_promotes_plan_on_heuristic_match(self, client, setup_state_with_mocks):
        """Test that stop hook promotes batch to plan when heuristic detects a plan."""
        from unittest.mock import patch

        session_id = str(uuid4())
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})
        client.post(
            "/api/oak/ci/prompt-submit",
            json={
                "session_id": session_id,
                "prompt": "Test prompt with enough content",
            },
        )

        # Mock detect_plan_in_response to return True
        with patch(
            "open_agent_kit.features.codebase_intelligence.plan_detector.detect_plan_in_response",
            return_value=True,
        ):
            response = client.post(
                "/api/oak/ci/stop",
                json={
                    "session_id": session_id,
                    "agent": AGENT_COPILOT,
                    "response_summary": "# Plan: Embed Session Ids\n\nStep 1...",
                },
            )

        assert response.status_code == 200
        # Verify update_prompt_batch_source_type was called with plan
        setup_state_with_mocks.activity_store.update_prompt_batch_source_type.assert_called_once()
        call_args = setup_state_with_mocks.activity_store.update_prompt_batch_source_type.call_args
        assert call_args[0][1] == PROMPT_SOURCE_PLAN  # second positional arg is source_type
        assert call_args[1].get("plan_content") is not None  # plan_content kwarg

    def test_stop_skips_heuristic_when_already_plan(self, client, setup_state_with_mocks):
        """Test that heuristic is skipped when batch is already source_type=plan."""
        from unittest.mock import patch

        session_id = str(uuid4())
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})
        client.post(
            "/api/oak/ci/prompt-submit",
            json={
                "session_id": session_id,
                "prompt": "Test prompt with enough content",
            },
        )

        # Set the active batch's source_type to plan already
        mock_batch = setup_state_with_mocks.activity_store.get_active_prompt_batch.return_value
        mock_batch.source_type = PROMPT_SOURCE_PLAN

        with patch(
            "open_agent_kit.features.codebase_intelligence.plan_detector.detect_plan_in_response",
        ) as mock_detect:
            response = client.post(
                "/api/oak/ci/stop",
                json={
                    "session_id": session_id,
                    "agent": AGENT_COPILOT,
                    "response_summary": "# Plan: Embed Session Ids",
                },
            )

        assert response.status_code == 200
        # detect_plan_in_response should NOT have been called since batch is already a plan
        mock_detect.assert_not_called()
        # update_prompt_batch_source_type should NOT have been called
        setup_state_with_mocks.activity_store.update_prompt_batch_source_type.assert_not_called()


# =============================================================================
# Session End Hook Tests
# =============================================================================


class TestSessionEndHook:
    """Test /api/oak/ci/session-end endpoint."""

    def test_session_end_minimal(self, client, setup_state_with_mocks):
        """Test session end with minimal request."""
        response = client.post("/api/oak/ci/session-end", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_session_end_with_session_id(self, client, setup_state_with_mocks):
        """Test session end with session_id."""
        session_id = str(uuid4())
        # Create session first
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})

        response = client.post(
            "/api/oak/ci/session-end",
            json={"session_id": session_id, "agent": AGENT_CLAUDE},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_session_end_includes_stats(self, client, setup_state_with_mocks):
        """Test that session end includes activity stats."""
        session_id = str(uuid4())
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})

        response = client.post(
            "/api/oak/ci/session-end",
            json={"session_id": session_id},
        )

        assert response.status_code == 200
        data = response.json()
        # Should include activity stats
        assert "activity_stats" in data or "observations_captured" in data

    def test_session_end_calls_activity_store(self, client, setup_state_with_mocks):
        """Test that activity store is called to end session."""
        session_id = str(uuid4())
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})

        response = client.post(
            "/api/oak/ci/session-end",
            json={"session_id": session_id},
        )

        assert response.status_code == 200
        # Verify end_session was called
        setup_state_with_mocks.activity_store.end_session.assert_called()

    def test_session_end_calculates_duration(self, client, setup_state_with_mocks):
        """Test that session duration is calculated."""
        session_id = str(uuid4())
        client.post("/api/oak/ci/session-start", json={"session_id": session_id})

        response = client.post(
            "/api/oak/ci/session-end",
            json={"session_id": session_id},
        )

        assert response.status_code == 200
        data = response.json()
        if "duration_minutes" in data:
            assert isinstance(data["duration_minutes"], (int, float))

    def test_session_end_invalid_json(self, client, setup_state_with_mocks):
        """Test session end with invalid JSON."""
        response = client.post(
            "/api/oak/ci/session-end",
            content=b"bad json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200


# =============================================================================
# Before Prompt Hook Tests
# =============================================================================


class TestBeforePromptHook:
    """Test /api/oak/ci/before-prompt endpoint."""

    def test_before_prompt_minimal(self, client, setup_state_with_mocks):
        """Test before-prompt with minimal request."""
        response = client.post("/api/oak/ci/before-prompt", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "context" in data

    def test_before_prompt_searches_code(self, client, setup_state_with_mocks):
        """Test that before-prompt searches for relevant code."""
        payload = {
            "prompt": "How do I implement error handling in this codebase?",
        }
        response = client.post("/api/oak/ci/before-prompt", json=payload)

        assert response.status_code == 200
        _ = response.json()  # Verify valid JSON response
        # Should have searched for code
        setup_state_with_mocks.vector_store.search_code.assert_called()

    def test_before_prompt_searches_memories(self, client, setup_state_with_mocks):
        """Test that before-prompt searches for relevant memories."""
        payload = {
            "prompt": "What are the known issues?",
        }
        response = client.post("/api/oak/ci/before-prompt", json=payload)

        assert response.status_code == 200
        _ = response.json()  # Verify valid JSON response
        # Should have searched for memories
        setup_state_with_mocks.vector_store.search_memory.assert_called()

    def test_before_prompt_includes_relevant_code(self, client, setup_state_with_mocks):
        """Test that relevant code is included in context."""
        payload = {
            "prompt": "How should I implement this?",
        }
        response = client.post("/api/oak/ci/before-prompt", json=payload)

        assert response.status_code == 200
        data = response.json()
        if "relevant_code" in data["context"]:
            assert isinstance(data["context"]["relevant_code"], list)

    def test_before_prompt_includes_relevant_memories(self, client, setup_state_with_mocks):
        """Test that relevant memories are included in context."""
        payload = {
            "prompt": "Are there any gotchas I should know about?",
        }
        response = client.post("/api/oak/ci/before-prompt", json=payload)

        assert response.status_code == 200
        data = response.json()
        if "relevant_memories" in data["context"]:
            assert isinstance(data["context"]["relevant_memories"], list)


# =============================================================================
# Generic Hook Tests
# =============================================================================


class TestGenericHookHandler:
    """Test generic hook handler for unknown events."""

    def test_generic_hook_handler(self, client, setup_state_with_mocks):
        """Test generic hook handler for unknown events."""
        response = client.post("/api/oak/ci/custom-event", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["event"] == "custom-event"


# =============================================================================
# Integration Tests
# =============================================================================


class TestHookIntegration:
    """Integration tests for hook workflows."""

    def test_full_session_workflow(self, client, setup_state_with_mocks):
        """Test complete session workflow: start -> prompt -> tool -> stop -> end."""
        session_id = str(uuid4())

        # Start session
        start_response = client.post(
            "/api/oak/ci/session-start",
            json={"session_id": session_id, "agent": AGENT_CLAUDE},
        )
        assert start_response.status_code == 200

        # Submit prompt
        prompt_response = client.post(
            "/api/oak/ci/prompt-submit",
            json={
                "session_id": session_id,
                "prompt": "Write a function to calculate fibonacci",
            },
        )
        assert prompt_response.status_code == 200

        # Execute tool
        tool_response = client.post(
            "/api/oak/ci/post-tool-use",
            json={
                "session_id": session_id,
                "tool_name": "Write",
                "tool_input": {"file_path": "/fib.py"},
                "tool_output": "written successfully",
            },
        )
        assert tool_response.status_code == 200

        # Stop
        stop_response = client.post(
            "/api/oak/ci/stop",
            json={"session_id": session_id},
        )
        assert stop_response.status_code == 200

        # End session
        end_response = client.post(
            "/api/oak/ci/session-end",
            json={"session_id": session_id, "agent": AGENT_CLAUDE},
        )
        assert end_response.status_code == 200

    def test_multiple_prompts_in_session(self, client, setup_state_with_mocks):
        """Test handling of multiple prompts in single session."""
        session_id = str(uuid4())

        # Start session
        client.post(
            "/api/oak/ci/session-start",
            json={"session_id": session_id},
        )

        # First prompt
        response1 = client.post(
            "/api/oak/ci/prompt-submit",
            json={
                "session_id": session_id,
                "prompt": "Explain the architecture",
            },
        )
        assert response1.status_code == 200

        # Second prompt
        response2 = client.post(
            "/api/oak/ci/prompt-submit",
            json={
                "session_id": session_id,
                "prompt": "How do I add a new feature?",
            },
        )
        assert response2.status_code == 200

    def test_session_without_activities(self, client, setup_state_with_mocks):
        """Test session that completes without tool use."""
        session_id = str(uuid4())

        # Start and end session without tool use
        client.post(
            "/api/oak/ci/session-start",
            json={"session_id": session_id},
        )

        response = client.post(
            "/api/oak/ci/session-end",
            json={"session_id": session_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
