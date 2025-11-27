"""Tests for periodic auto-backup behavior.

Tests cover:
- Periodic loop behavior when enabled/disabled
- Auto backup trigger calls create_backup()
- DaemonState.last_auto_backup is updated on success
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    BackupResult,
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


class TestPeriodicBackupLoop:
    """Tests for _periodic_backup_loop async coroutine."""

    @pytest.mark.anyio
    async def test_sleeps_when_disabled(self):
        """Loop sleeps 60s when auto_enabled is False."""
        from open_agent_kit.features.codebase_intelligence.daemon.server import (
            _periodic_backup_loop,
        )

        state = DaemonState()
        state.project_root = Path("/tmp/test")

        # Create a mock config with auto_enabled=False
        mock_config = MagicMock()
        mock_config.backup.auto_enabled = False
        state._ci_config = mock_config

        sleep_calls: list[float] = []
        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            sleep_calls.append(seconds)
            call_count += 1
            if call_count >= 1:
                raise asyncio.CancelledError

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(asyncio.CancelledError):
                await _periodic_backup_loop(state)

        assert len(sleep_calls) >= 1
        assert sleep_calls[0] == 60

    @pytest.mark.anyio
    async def test_sleeps_interval_when_enabled(self):
        """Loop sleeps for config interval when auto_enabled is True."""
        from open_agent_kit.features.codebase_intelligence.daemon.server import (
            _periodic_backup_loop,
        )

        state = DaemonState()
        state.project_root = Path("/tmp/test")

        mock_config = MagicMock()
        mock_config.backup.auto_enabled = True
        mock_config.backup.interval_minutes = 15
        state._ci_config = mock_config

        sleep_calls: list[float] = []
        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            sleep_calls.append(seconds)
            call_count += 1
            if call_count >= 1:
                raise asyncio.CancelledError

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(asyncio.CancelledError):
                await _periodic_backup_loop(state)

        # Should sleep for interval_minutes * 60 = 15 * 60 = 900
        assert len(sleep_calls) >= 1
        assert sleep_calls[0] == 900


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
