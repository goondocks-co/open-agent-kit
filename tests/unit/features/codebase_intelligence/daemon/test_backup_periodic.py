"""Tests for periodic auto-backup behavior.

Tests cover:
- Auto backup trigger calls create_backup()
- DaemonState.last_auto_backup is updated on success
- Periodic backup loop removal (replaced by transition backups)
- Transition backup store reuse
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    BackupResult,
    create_backup,
)
from open_agent_kit.features.codebase_intelligence.daemon.server import (
    _run_auto_backup,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    DaemonState,
    reset_state,
)


@pytest.fixture
def anyio_backend():
    """Restrict anyio tests to asyncio backend (trio doesn't support asyncio.sleep patching)."""
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


class TestRunAutoBackup:
    """Tests for _run_auto_backup sync function."""

    def test_skips_when_no_project_root(self):
        """Auto-backup is a no-op when project_root is None."""
        state = DaemonState()
        state.project_root = None

        _run_auto_backup(state)

        assert state.last_auto_backup is None

    def test_skips_when_db_missing(self, tmp_path: Path):
        """Auto-backup is a no-op when the database file does not exist."""
        state = DaemonState()
        state.project_root = tmp_path

        _run_auto_backup(state)

        assert state.last_auto_backup is None

    def test_calls_create_backup_on_success(self, tmp_path: Path):
        """Auto-backup calls create_backup and updates last_auto_backup on success."""
        from open_agent_kit.config.paths import OAK_DIR
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_ACTIVITIES_DB_FILENAME,
            CI_DATA_DIR,
        )

        state = DaemonState()
        state.project_root = tmp_path

        # Create the database file so the check passes
        db_dir = tmp_path / OAK_DIR / CI_DATA_DIR
        db_dir.mkdir(parents=True)
        db_path = db_dir / CI_ACTIVITIES_DB_FILENAME
        db_path.write_text("placeholder")

        mock_result = BackupResult(
            success=True,
            backup_path=tmp_path / "backup.sql",
            record_count=42,
            machine_id="test_machine",
        )

        with patch(
            "open_agent_kit.features.codebase_intelligence.activity.store.backup.create_backup",
            return_value=mock_result,
        ) as mock_create:
            _run_auto_backup(state)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            assert call_kwargs[1]["project_root"] == tmp_path

        assert state.last_auto_backup is not None
        assert state.last_auto_backup > 0

    def test_does_not_update_timestamp_on_failure(self, tmp_path: Path):
        """Auto-backup does not update last_auto_backup when create_backup fails."""
        from open_agent_kit.config.paths import OAK_DIR
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_ACTIVITIES_DB_FILENAME,
            CI_DATA_DIR,
        )

        state = DaemonState()
        state.project_root = tmp_path

        db_dir = tmp_path / OAK_DIR / CI_DATA_DIR
        db_dir.mkdir(parents=True)
        (db_dir / CI_ACTIVITIES_DB_FILENAME).write_text("placeholder")

        mock_result = BackupResult(
            success=False,
            error="disk full",
        )

        with patch(
            "open_agent_kit.features.codebase_intelligence.activity.store.backup.create_backup",
            return_value=mock_result,
        ):
            _run_auto_backup(state)

        assert state.last_auto_backup is None


class TestDaemonStateLastAutoBackup:
    """Tests for last_auto_backup field on DaemonState."""

    def test_default_is_none(self):
        """last_auto_backup defaults to None."""
        state = DaemonState()
        assert state.last_auto_backup is None

    def test_reset_clears_last_auto_backup(self):
        """reset() clears last_auto_backup."""
        state = DaemonState()
        state.last_auto_backup = 1234567890.0
        state.reset()
        assert state.last_auto_backup is None

    def test_can_set_and_read(self):
        """last_auto_backup can be set and read."""
        import time

        state = DaemonState()
        now = time.time()
        state.last_auto_backup = now
        assert state.last_auto_backup == now


# =============================================================================
# Periodic Backup Loop Removal (replaced by transition backups)
# =============================================================================


class TestPeriodicBackupLoopRemoved:
    """Verify _periodic_backup_loop is no longer used in lifespan."""

    def test_periodic_backup_loop_removed(self):
        """Verify _periodic_backup_loop is no longer called in lifespan.

        The periodic backup loop was replaced by transition-triggered backups
        in the power state lifecycle. The lifespan function should no longer
        create a 'periodic_backup' background task.
        """
        import ast
        import inspect

        from open_agent_kit.features.codebase_intelligence.daemon import server

        source = inspect.getsource(server.lifespan)
        tree = ast.parse(source)

        # Walk the AST looking for references to _periodic_backup_loop
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "_periodic_backup_loop":
                pytest.fail(
                    "lifespan() still references _periodic_backup_loop; "
                    "it should use transition backups instead"
                )


# =============================================================================
# Transition Backup Store Reuse
# =============================================================================


class TestTransitionBackupStoreReuse:
    """Tests for create_backup activity_store parameter."""

    def test_transition_backup_reuses_existing_store(self, tmp_path: Path):
        """Call create_backup(activity_store=mock_store) -> assert no new ActivityStore created."""
        from open_agent_kit.config.paths import OAK_DIR
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_ACTIVITIES_DB_FILENAME,
            CI_DATA_DIR,
        )

        # Create the database file so the check passes
        db_dir = tmp_path / OAK_DIR / CI_DATA_DIR
        db_dir.mkdir(parents=True)
        db_path = db_dir / CI_ACTIVITIES_DB_FILENAME
        db_path.write_text("placeholder")

        mock_store = MagicMock()
        mock_store.machine_id = "test_machine"

        with (
            patch(
                "open_agent_kit.features.codebase_intelligence.activity.store.backup.export_to_sql",
                return_value=10,
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.activity.store.backup.get_machine_identifier",
                return_value="test_machine",
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore"
            ) as MockActivityStore,
        ):
            result = create_backup(
                project_root=tmp_path,
                db_path=db_path,
                activity_store=mock_store,
            )

        assert result.success is True
        # No new ActivityStore should have been constructed
        MockActivityStore.assert_not_called()

    def test_transition_backup_creates_store_when_none(self, tmp_path: Path):
        """Call create_backup(activity_store=None) -> assert ActivityStore constructor called."""
        from open_agent_kit.config.paths import OAK_DIR
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_ACTIVITIES_DB_FILENAME,
            CI_DATA_DIR,
        )

        # Create the database file so the check passes
        db_dir = tmp_path / OAK_DIR / CI_DATA_DIR
        db_dir.mkdir(parents=True)
        db_path = db_dir / CI_ACTIVITIES_DB_FILENAME
        db_path.write_text("placeholder")

        mock_store_instance = MagicMock()
        mock_store_instance.machine_id = "test_machine"

        with (
            patch(
                "open_agent_kit.features.codebase_intelligence.activity.store.backup.export_to_sql",
                return_value=10,
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.activity.store.backup.get_machine_identifier",
                return_value="test_machine",
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore",
                return_value=mock_store_instance,
            ) as MockActivityStore,
        ):
            result = create_backup(
                project_root=tmp_path,
                db_path=db_path,
            )

        assert result.success is True
        # A new ActivityStore should have been constructed
        MockActivityStore.assert_called_once()
