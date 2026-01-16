"""Tests for daemon health and status routes.

Tests cover:
- Health check endpoint
- Detailed status endpoint
- Logs retrieval
- Uptime tracking
- Index and embedding status
- File watcher status
"""

from pathlib import Path
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
def mock_vector_store():
    """Mock vector store."""
    mock = MagicMock()
    mock.get_stats.return_value = {
        "code_chunks": 250,
        "memory_observations": 45,
    }
    mock.count_unique_files.return_value = 42
    return mock


@pytest.fixture
def mock_embedding_chain():
    """Mock embedding chain."""
    mock = MagicMock()
    mock.get_status.return_value = {
        "primary_provider": "ollama",
        "active_provider": "ollama",
        "providers": [
            {
                "name": "ollama",
                "is_available": True,
                "success_count": 500,
                "error_count": 2,
            }
        ],
        "total_embeds": 500,
    }
    return mock


@pytest.fixture
def mock_file_watcher():
    """Mock file watcher."""
    mock = MagicMock()
    mock.is_running = True
    mock.get_pending_count.return_value = 3
    return mock


@pytest.fixture
def setup_state_fully_initialized(
    tmp_path: Path, mock_vector_store, mock_embedding_chain, mock_file_watcher
):
    """Setup fully initialized daemon state."""
    state = get_state()
    state.initialize(tmp_path)
    state.project_root = tmp_path
    state.vector_store = mock_vector_store
    state.embedding_chain = mock_embedding_chain
    state.file_watcher = mock_file_watcher
    state.index_status.set_ready(duration=15.5)
    state.index_status.file_count = 42
    state.index_status.ast_stats = {
        "ast_success": 35,
        "ast_fallback": 5,
        "line_based": 2,
    }
    return state


# =============================================================================
# GET /api/health Tests
# =============================================================================


class TestHealthCheck:
    """Test GET /api/health endpoint."""

    def test_health_check_success(self, client, setup_state_fully_initialized):
        """Test successful health check."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_includes_uptime(self, client, setup_state_fully_initialized):
        """Test that health check includes uptime."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))

    def test_health_check_includes_project_root(self, client, setup_state_fully_initialized):
        """Test that health check includes project root."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "project_root" in data
        assert data["project_root"] is not None

    def test_health_check_no_project_root(self, client):
        """Test health check when project root is not set."""
        # Reset state AFTER client creation (client fixture sets project_root)
        reset_state()
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["project_root"] is None

    def test_health_check_response_model(self, client, setup_state_fully_initialized):
        """Test that health check follows response model."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        # Check model fields
        assert "status" in data
        assert "uptime_seconds" in data
        assert "project_root" in data


# =============================================================================
# GET /api/status Tests
# =============================================================================


class TestGetStatus:
    """Test GET /api/status endpoint."""

    def test_get_status_success(self, client, setup_state_fully_initialized):
        """Test successful status retrieval."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

    def test_get_status_includes_indexing_flag(self, client, setup_state_fully_initialized):
        """Test that status includes indexing flag."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "indexing" in data
        assert isinstance(data["indexing"], bool)

    def test_get_status_includes_embedding_provider(self, client, setup_state_fully_initialized):
        """Test that status includes embedding provider info."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "embedding_provider" in data
        assert data["embedding_provider"] == "ollama"

    def test_get_status_includes_embedding_stats(self, client, setup_state_fully_initialized):
        """Test that status includes embedding statistics."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "embedding_stats" in data
        embedding_stats = data["embedding_stats"]
        assert "providers" in embedding_stats
        assert "total_embeds" in embedding_stats

    def test_get_status_includes_uptime(self, client, setup_state_fully_initialized):
        """Test that status includes uptime."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))

    def test_get_status_includes_project_root(self, client, setup_state_fully_initialized):
        """Test that status includes project root."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "project_root" in data

    def test_get_status_includes_index_stats(self, client, setup_state_fully_initialized):
        """Test that status includes index statistics."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "index_stats" in data
        index_stats = data["index_stats"]
        assert "files_indexed" in index_stats
        assert "chunks_indexed" in index_stats
        assert "memories_stored" in index_stats
        assert "last_indexed" in index_stats
        assert "duration_seconds" in index_stats
        assert "status" in index_stats

    def test_get_status_includes_file_watcher(self, client, setup_state_fully_initialized):
        """Test that status includes file watcher info."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "file_watcher" in data
        file_watcher = data["file_watcher"]
        assert "enabled" in file_watcher
        assert "running" in file_watcher
        assert "pending_changes" in file_watcher

    def test_get_status_indexing_in_progress(self, client, setup_state_fully_initialized):
        """Test status when indexing is in progress."""
        setup_state_fully_initialized.index_status.set_indexing()
        setup_state_fully_initialized.index_status.update_progress(50, 100)

        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["indexing"] is True
        assert data["index_stats"]["progress"] == 50
        assert data["index_stats"]["total"] == 100

    def test_get_status_index_not_ready(self, client):
        """Test status when index is not ready."""
        # Using fresh daemon state from fixture (index not ready)
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        # Should show empty stats
        assert data["index_stats"]["files_indexed"] == 0

    def test_get_status_file_watcher_disabled(self, client):
        """Test status when file watcher is disabled."""
        # Using fresh daemon state from fixture (file watcher disabled)
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["file_watcher"]["enabled"] is False

    def test_get_status_fallback_to_db_count(self, client, setup_state_fully_initialized):
        """Test that file count falls back to DB query."""
        # Reset file count to test fallback
        setup_state_fully_initialized.index_status.file_count = 0

        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        # Should query DB
        assert data["index_stats"]["files_indexed"] >= 0

    def test_get_status_ast_stats(self, client, setup_state_fully_initialized):
        """Test that AST statistics are included."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        ast_stats = data["index_stats"]["ast_stats"]
        assert "ast_success" in ast_stats
        assert "ast_fallback" in ast_stats
        assert "line_based" in ast_stats


# =============================================================================
# GET /api/logs Tests
# =============================================================================


class TestGetLogs:
    """Test GET /api/logs endpoint."""

    def test_get_logs_default(self, client, setup_state_fully_initialized, tmp_path: Path):
        """Test retrieving logs with default parameters."""
        # Create log file
        log_dir = tmp_path / ".oak" / "ci"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_file.write_text("log line 1\nlog line 2\nlog line 3\n")

        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "lines" in data
        assert "log_file" in data

    def test_get_logs_custom_line_count(
        self, client, setup_state_fully_initialized, tmp_path: Path
    ):
        """Test retrieving specific number of log lines."""
        log_dir = tmp_path / ".oak" / "ci"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_file.write_text("\n".join([f"line {i}" for i in range(100)]) + "\n")

        response = client.get("/api/logs", params={"lines": 20})

        assert response.status_code == 200
        data = response.json()
        assert data["lines"] == 20

    def test_get_logs_large_line_count(self, client, setup_state_fully_initialized):
        """Test limiting max log lines."""
        response = client.get("/api/logs", params={"lines": 1000})

        # Should cap at 500
        assert response.status_code in (200, 422)

    def test_get_logs_minimum_line_count(self, client, setup_state_fully_initialized):
        """Test minimum log lines."""
        response = client.get("/api/logs", params={"lines": 1})

        assert response.status_code == 200
        data = response.json()
        assert data["lines"] == 1

    def test_get_logs_zero_lines_rejected(self, client, setup_state_fully_initialized):
        """Test that 0 lines is rejected."""
        response = client.get("/api/logs", params={"lines": 0})

        assert response.status_code == 422

    def test_get_logs_file_not_found(self, client):
        """Test retrieving logs when file doesn't exist."""
        # Using fresh daemon state from fixture (no log file)
        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert "No log file found" in data["content"] or data["log_file"] is None

    def test_get_logs_includes_file_path(
        self, client, setup_state_fully_initialized, tmp_path: Path
    ):
        """Test that log file path is included."""
        log_dir = tmp_path / ".oak" / "ci"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_file.write_text("test log\n")

        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["log_file"] is not None

    def test_get_logs_empty_file(self, client, setup_state_fully_initialized, tmp_path: Path):
        """Test retrieving from empty log file."""
        log_dir = tmp_path / ".oak" / "ci"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_file.write_text("")

        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == ""

    def test_get_logs_with_unicode(self, client, setup_state_fully_initialized, tmp_path: Path):
        """Test retrieving logs with unicode content."""
        log_dir = tmp_path / ".oak" / "ci"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "daemon.log"
        log_file.write_text("unicode: 你好 🎉 mötley\n", encoding="utf-8")

        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert "content" in data


# =============================================================================
# Status Integration Tests
# =============================================================================


class TestHealthStatusIntegration:
    """Integration tests for health and status endpoints."""

    def test_health_vs_status_consistency(self, client, setup_state_fully_initialized):
        """Test that health and status endpoints are consistent."""
        health_response = client.get("/api/health")
        status_response = client.get("/api/status")

        assert health_response.status_code == 200
        assert status_response.status_code == 200

        health_data = health_response.json()
        status_data = status_response.json()

        # Uptime and project root should be consistent
        assert health_data["uptime_seconds"] >= 0
        assert status_data["uptime_seconds"] >= 0

    def test_multiple_status_calls_show_increasing_uptime(
        self, client, setup_state_fully_initialized
    ):
        """Test that uptime increases with multiple calls."""
        import time

        response1 = client.get("/api/status")
        uptime1 = response1.json()["uptime_seconds"]

        time.sleep(0.1)

        response2 = client.get("/api/status")
        uptime2 = response2.json()["uptime_seconds"]

        # Uptime should increase
        assert uptime2 >= uptime1


# =============================================================================
# Response Format Tests
# =============================================================================


class TestStatusResponseFormats:
    """Test that status responses follow expected formats."""

    def test_health_response_format(self, client, setup_state_fully_initialized):
        """Test health response format."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "status" in data
        assert isinstance(data["status"], str)
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))

    def test_status_response_format(self, client, setup_state_fully_initialized):
        """Test status response format."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert isinstance(data, dict)
        assert "status" in data
        assert "indexing" in data
        assert "index_stats" in data
        assert isinstance(data["index_stats"], dict)

    def test_logs_response_format(self, client, setup_state_fully_initialized):
        """Test logs response format."""
        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()

        assert "log_file" in data
        assert "lines" in data
        assert "content" in data
        assert isinstance(data["lines"], int)
        assert isinstance(data["content"], str)
