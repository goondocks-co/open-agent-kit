"""Tests for daemon backup and restore routes.

Tests cover:
- Backup status endpoint
- Backup creation endpoint
- Backup restore endpoint
- Error handling for missing database/backup files
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.activity.store import (
    ActivityStore,
    StoredObservation,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    get_backup_filename,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_BACKUP_PATH_INVALID_ERROR,
    CI_DATA_DIR,
    CI_HISTORY_BACKUP_DIR,
    CI_HISTORY_BACKUP_FILE_SUFFIX,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes import backup as backup_routes
from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)

TEST_BACKUP_FILENAME_PREFIX = "test_backup"
TEST_BACKUP_FILENAME = f"{TEST_BACKUP_FILENAME_PREFIX}{CI_HISTORY_BACKUP_FILE_SUFFIX}"
TEST_OUTSIDE_DIR_NAME = "outside"


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
def temp_project(tmp_path: Path):
    """Create a temporary project directory with CI data."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Create .oak/ci directory structure
    ci_dir = project_root / OAK_DIR / CI_DATA_DIR
    ci_dir.mkdir(parents=True)

    # Create backup directory
    backup_dir = project_root / CI_HISTORY_BACKUP_DIR
    backup_dir.mkdir(parents=True)

    return project_root


@pytest.fixture
def setup_state_with_activity_store(temp_project: Path):
    """Set up daemon state with a real activity store."""
    import uuid

    state = get_state()
    state.project_root = temp_project

    # Create a real activity store
    db_path = temp_project / OAK_DIR / CI_DATA_DIR / CI_ACTIVITIES_DB_FILENAME
    state.activity_store = ActivityStore(db_path)

    # Add some test data
    state.activity_store.create_session(
        session_id="test-session-1",
        agent="claude",
        project_root=str(temp_project),
    )
    obs = StoredObservation(
        id=str(uuid.uuid4()),
        session_id="test-session-1",
        observation="Test observation for backup",
        memory_type="discovery",
    )
    state.activity_store.store_observation(obs)

    yield state

    if state.activity_store:
        state.activity_store.close()


# =============================================================================
# Backup Status Tests
# =============================================================================


class TestBackupStatus:
    """Test backup status endpoint."""

    def test_backup_status_no_backup_exists(self, client, temp_project: Path):
        """Test status when no backup file exists."""
        state = get_state()
        state.project_root = temp_project
        state.activity_store = MagicMock()

        response = client.get("/api/backup/status")

        assert response.status_code == 200
        data = response.json()
        assert data["backup_exists"] is False
        assert data["backup_path"].endswith(CI_HISTORY_BACKUP_FILE_SUFFIX)
        assert "machine_id" in data
        assert "all_backups" in data

    def test_backup_status_backup_exists(self, client, temp_project: Path):
        """Test status when backup file exists."""
        state = get_state()
        state.project_root = temp_project
        state.activity_store = MagicMock()

        # Create a backup file with machine-specific filename
        backup_filename = get_backup_filename()
        backup_path = temp_project / CI_HISTORY_BACKUP_DIR / backup_filename
        backup_path.write_text("-- Test backup\nINSERT INTO sessions VALUES (1);")

        response = client.get("/api/backup/status")

        assert response.status_code == 200
        data = response.json()
        assert data["backup_exists"] is True
        assert data["backup_size_bytes"] > 0
        assert data["last_modified"] is not None
        assert "machine_id" in data
        assert len(data["all_backups"]) >= 1

    def test_backup_status_uses_header_reader(self, client, temp_project: Path, monkeypatch):
        """Test that status uses the header reader helper."""
        state = get_state()
        state.project_root = temp_project
        state.activity_store = MagicMock()

        backup_filename = get_backup_filename()
        backup_path = temp_project / CI_HISTORY_BACKUP_DIR / backup_filename
        backup_path.write_text("-- Test backup")

        called = {"value": False}

        def fake_reader(path: Path, max_lines: int) -> list[str]:
            called["value"] = True
            return []

        monkeypatch.setattr(backup_routes, "_read_backup_header_lines", fake_reader)

        response = client.get("/api/backup/status")

        assert response.status_code == 200
        assert called["value"] is True

    def test_backup_status_project_not_initialized(self, client):
        """Test status when project root is not set."""
        state = get_state()
        state.project_root = None

        response = client.get("/api/backup/status")

        assert response.status_code == 503


# =============================================================================
# Backup Create Tests
# =============================================================================


class TestBackupCreate:
    """Test backup creation endpoint."""

    def test_create_backup_success(self, client, setup_state_with_activity_store):
        """Test successful backup creation."""
        response = client.post(
            "/api/backup/create",
            json={"include_activities": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["record_count"] >= 2  # session + observation
        assert data["backup_path"].endswith(CI_HISTORY_BACKUP_FILE_SUFFIX)
        assert "machine_id" in data

        # Verify file was created
        state = get_state()
        backup_filename = get_backup_filename()
        backup_path = state.project_root / CI_HISTORY_BACKUP_DIR / backup_filename
        assert backup_path.exists()

    def test_create_backup_with_activities(self, client, setup_state_with_activity_store):
        """Test backup creation with activities included."""
        state = get_state()

        # Add an activity
        from open_agent_kit.features.codebase_intelligence.activity.store import Activity

        activity = Activity(
            session_id="test-session-1",
            tool_name="Read",
            tool_input={"path": "/test.py"},
            file_path="/test.py",
            duration_ms=100,
            success=True,
        )
        state.activity_store.add_activity(activity)

        response = client.post(
            "/api/backup/create",
            json={"include_activities": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

        # Verify activities are in the backup
        backup_filename = get_backup_filename()
        backup_path = state.project_root / CI_HISTORY_BACKUP_DIR / backup_filename
        content = backup_path.read_text()
        assert "INSERT INTO activities" in content

    def test_create_backup_rejects_outside_path(self, client, setup_state_with_activity_store):
        """Test backup creation rejects paths outside backup dir."""
        state = get_state()
        backup_dir = state.project_root / CI_HISTORY_BACKUP_DIR
        outside_path = state.project_root / TEST_OUTSIDE_DIR_NAME / TEST_BACKUP_FILENAME

        response = client.post(
            "/api/backup/create",
            json={"output_path": str(outside_path)},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == CI_BACKUP_PATH_INVALID_ERROR.format(
            backup_dir=backup_dir
        )

    def test_create_backup_no_database(self, client, temp_project: Path):
        """Test backup creation when database doesn't exist."""
        state = get_state()
        state.project_root = temp_project
        state.activity_store = MagicMock()

        # Don't create the database file

        response = client.post(
            "/api/backup/create",
            json={"include_activities": False},
        )

        assert response.status_code == 404

    def test_create_backup_activity_store_not_initialized(self, client, temp_project: Path):
        """Test backup creation when activity store is not initialized."""
        state = get_state()
        state.project_root = temp_project
        state.activity_store = None

        response = client.post(
            "/api/backup/create",
            json={},
        )

        assert response.status_code == 503


# =============================================================================
# Backup Restore Tests
# =============================================================================


class TestBackupRestore:
    """Test backup restore endpoint."""

    def test_restore_backup_success(self, client, setup_state_with_activity_store):
        """Test successful backup restore."""
        # First create a backup
        client.post("/api/backup/create", json={})

        # Clear the session (simulate starting fresh after reinstall)
        # Note: We can't truly clear without recreating the store,
        # so we'll just verify the restore endpoint works
        response = client.post("/api/backup/restore", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # New response format includes deduplication stats
        assert "Restored" in data["message"] or "skipped" in data["message"]
        assert "sessions_imported" in data
        assert "sessions_skipped" in data
        assert "observations_imported" in data
        assert "observations_skipped" in data

    def test_restore_backup_file_not_found(self, client, setup_state_with_activity_store):
        """Test restore when backup file doesn't exist."""
        # Don't create a backup file

        response = client.post("/api/backup/restore", json={})

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_restore_backup_rejects_outside_path(self, client, setup_state_with_activity_store):
        """Test backup restore rejects paths outside backup dir."""
        state = get_state()
        backup_dir = state.project_root / CI_HISTORY_BACKUP_DIR
        outside_path = state.project_root / TEST_OUTSIDE_DIR_NAME / TEST_BACKUP_FILENAME

        response = client.post(
            "/api/backup/restore",
            json={"input_path": str(outside_path)},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == CI_BACKUP_PATH_INVALID_ERROR.format(
            backup_dir=backup_dir
        )

    def test_restore_backup_no_database(self, client, temp_project: Path):
        """Test restore when database doesn't exist."""
        state = get_state()
        state.project_root = temp_project
        state.activity_store = MagicMock()

        # Create backup file but no database
        backup_dir = temp_project / CI_HISTORY_BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_filename = get_backup_filename()
        backup_path = backup_dir / backup_filename
        backup_path.write_text("-- Test backup")

        response = client.post("/api/backup/restore", json={})

        assert response.status_code == 404

    def test_restore_backup_activity_store_not_initialized(self, client, temp_project: Path):
        """Test restore when activity store is not initialized."""
        state = get_state()
        state.project_root = temp_project
        state.activity_store = None

        response = client.post("/api/backup/restore", json={})

        assert response.status_code == 503


# =============================================================================
# Integration Tests
# =============================================================================


class TestBackupIntegration:
    """Integration tests for backup/restore workflow."""

    def test_full_backup_restore_cycle(self, client, temp_project: Path):
        """Test complete backup and restore cycle."""
        import os
        import uuid

        state = get_state()
        state.project_root = temp_project

        # Create activity store with test data
        db_path = temp_project / OAK_DIR / CI_DATA_DIR / CI_ACTIVITIES_DB_FILENAME
        state.activity_store = ActivityStore(db_path)

        # Add comprehensive test data
        state.activity_store.create_session(
            session_id="cycle-test-1",
            agent="claude",
            project_root=str(temp_project),
        )
        state.activity_store.create_prompt_batch(
            session_id="cycle-test-1",
            user_prompt="Test prompt for cycle",
        )
        obs = StoredObservation(
            id=str(uuid.uuid4()),
            session_id="cycle-test-1",
            observation="Important observation",
            memory_type="gotcha",
            context="test_context",
        )
        state.activity_store.store_observation(obs)

        # Get original counts
        orig_obs_count = state.activity_store.count_observations()
        assert orig_obs_count > 0

        # Create backup
        backup_response = client.post("/api/backup/create", json={})
        assert backup_response.status_code == 200

        # Close store and delete database (simulate reinstall)
        state.activity_store.close()
        os.remove(db_path)

        # Create a fresh database at the same path
        state.activity_store = ActivityStore(db_path)

        # Verify it's empty
        assert state.activity_store.count_observations() == 0

        # Restore from backup
        restore_response = client.post("/api/backup/restore", json={})
        assert restore_response.status_code == 200

        # Verify data was restored
        restored_count = state.activity_store.count_observations()
        assert restored_count == orig_obs_count

        # Verify session was restored
        session = state.activity_store.get_session("cycle-test-1")
        assert session is not None
        assert session.agent == "claude"

        state.activity_store.close()
