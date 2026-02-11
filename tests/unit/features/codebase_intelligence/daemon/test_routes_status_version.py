"""Tests for version block in /api/status response.

Tests cover:
- Status includes version block
- version.running matches VERSION constant
- version.installed reflects state
- version.update_available when True
- version.update_available defaults to False
- version.installed is null when unknown
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.constants import VERSION
from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)

# Test version values (no magic strings)
_INSTALLED_VERSION = "0.11.0"


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


class TestStatusVersionBlock:
    """Test version block in GET /api/status response."""

    def test_status_includes_version_block(self, client, setup_state_fully_initialized) -> None:
        """Response has a 'version' key with expected sub-keys."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        version_block = data["version"]
        assert "running" in version_block
        assert "installed" in version_block
        assert "update_available" in version_block

    def test_version_running_matches_constant(self, client, setup_state_fully_initialized) -> None:
        """version.running equals the VERSION constant."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["version"]["running"] == VERSION

    def test_version_installed_from_state(self, client, setup_state_fully_initialized) -> None:
        """version.installed reflects the value set on state."""
        setup_state_fully_initialized.installed_version = _INSTALLED_VERSION

        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["version"]["installed"] == _INSTALLED_VERSION

    def test_version_update_available_true(self, client, setup_state_fully_initialized) -> None:
        """version.update_available is True when state.update_available=True."""
        setup_state_fully_initialized.update_available = True

        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["version"]["update_available"] is True

    def test_version_update_available_false_default(
        self, client, setup_state_fully_initialized
    ) -> None:
        """version.update_available defaults to False on fresh state."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["version"]["update_available"] is False

    def test_version_installed_null_when_unknown(
        self, client, setup_state_fully_initialized
    ) -> None:
        """version.installed is null when state.installed_version is None."""
        assert setup_state_fully_initialized.installed_version is None

        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["version"]["installed"] is None
