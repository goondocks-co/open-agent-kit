"""Tests for backup directory configuration functions."""

import os
from pathlib import Path
from unittest import mock

import pytest


class TestGetBackupDir:
    """Tests for get_backup_dir function."""

    def test_default_when_no_user_config(self, tmp_path: Path) -> None:
        """Should return default path when no user config is set."""
        from open_agent_kit.features.team.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.team.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        with mock.patch(
            "open_agent_kit.features.team.config.user_store.read_user_value",
            return_value=None,
        ):
            result = get_backup_dir(tmp_path)

        assert result == tmp_path / CI_HISTORY_BACKUP_DIR

    def test_uses_cwd_when_no_project_root(self) -> None:
        """Should use cwd when project_root is None."""
        from open_agent_kit.features.team.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.team.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        with mock.patch(
            "open_agent_kit.features.team.config.user_store.read_user_value",
            return_value=None,
        ):
            result = get_backup_dir(None)

            assert result == Path.cwd() / CI_HISTORY_BACKUP_DIR


class TestUserConfigSupport:
    """Tests for user config reading in get_backup_dir."""

    def test_user_config_absolute_path(self, tmp_path: Path) -> None:
        """Should read backup dir from user config."""
        from open_agent_kit.features.team.activity.store.backup import (
            get_backup_dir,
        )

        custom_dir = tmp_path / "shared-backups"

        with mock.patch(
            "open_agent_kit.features.team.config.user_store.read_user_value",
            return_value=str(custom_dir),
        ):
            result = get_backup_dir(tmp_path)

        assert result == custom_dir

    def test_user_config_relative_path(self, tmp_path: Path) -> None:
        """Should resolve relative user config paths against project root."""
        from open_agent_kit.features.team.activity.store.backup import (
            get_backup_dir,
        )

        with mock.patch(
            "open_agent_kit.features.team.config.user_store.read_user_value",
            return_value="backups/shared",
        ):
            result = get_backup_dir(tmp_path)

        assert result == (tmp_path / "backups/shared").resolve()

    def test_no_user_config_uses_default(self, tmp_path: Path) -> None:
        """Should use default when user config has no value."""
        from open_agent_kit.features.team.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.team.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        with mock.patch(
            "open_agent_kit.features.team.config.user_store.read_user_value",
            return_value=None,
        ):
            result = get_backup_dir(tmp_path)

        assert result == tmp_path / CI_HISTORY_BACKUP_DIR


class TestGetBackupDirSource:
    """Tests for get_backup_dir_source function."""

    def test_returns_default_when_no_config(self, tmp_path: Path) -> None:
        """Should return 'default' when no user config is set."""
        from open_agent_kit.features.team.activity.store.backup import (
            get_backup_dir_source,
        )

        with mock.patch(
            "open_agent_kit.features.team.config.user_store.read_user_value",
            return_value=None,
        ):
            result = get_backup_dir_source(tmp_path)

        assert result == "default"

    def test_returns_user_config_source(self, tmp_path: Path) -> None:
        """Should return 'user config' when set via user override config."""
        from open_agent_kit.features.team.activity.store.backup import (
            get_backup_dir_source,
        )

        with mock.patch(
            "open_agent_kit.features.team.config.user_store.read_user_value",
            return_value="/shared/backups",
        ):
            result = get_backup_dir_source(tmp_path)

        assert result == "user config"


class TestValidateBackupDir:
    """Tests for validate_backup_dir function."""

    def test_valid_existing_writable_directory(self, tmp_path: Path) -> None:
        """Should return valid for existing writable directory."""
        from open_agent_kit.features.team.activity.store.backup import (
            validate_backup_dir,
        )

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        is_valid, error_msg = validate_backup_dir(backup_dir, create=False)

        assert is_valid is True
        assert error_msg is None

    def test_creates_directory_when_missing(self, tmp_path: Path) -> None:
        """Should create directory when missing and create=True."""
        from open_agent_kit.features.team.activity.store.backup import (
            validate_backup_dir,
        )

        backup_dir = tmp_path / "new-backups" / "nested"

        is_valid, error_msg = validate_backup_dir(backup_dir, create=True)

        assert is_valid is True
        assert error_msg is None
        assert backup_dir.exists()

    def test_fails_when_missing_and_create_false(self, tmp_path: Path) -> None:
        """Should fail when directory missing and create=False."""
        from open_agent_kit.features.team.activity.store.backup import (
            validate_backup_dir,
        )

        backup_dir = tmp_path / "nonexistent"

        is_valid, error_msg = validate_backup_dir(backup_dir, create=False)

        assert is_valid is False
        assert error_msg is not None
        assert "does not exist" in error_msg

    def test_fails_when_path_is_file(self, tmp_path: Path) -> None:
        """Should fail when path points to a file, not directory."""
        from open_agent_kit.features.team.activity.store.backup import (
            validate_backup_dir,
        )

        file_path = tmp_path / "not-a-dir"
        file_path.write_text("I am a file")

        is_valid, error_msg = validate_backup_dir(file_path, create=False)

        assert is_valid is False
        assert error_msg is not None
        assert "not a directory" in error_msg

    @pytest.mark.skipif(os.name == "nt", reason="Permission tests unreliable on Windows")
    def test_checks_writability(self, tmp_path: Path) -> None:
        """Should check if directory is writable."""
        from open_agent_kit.features.team.activity.store.backup import (
            validate_backup_dir,
        )

        backup_dir = tmp_path / "readonly"
        backup_dir.mkdir()

        # Make directory read-only
        original_mode = backup_dir.stat().st_mode
        try:
            os.chmod(backup_dir, 0o444)

            is_valid, error_msg = validate_backup_dir(backup_dir, create=False)

            # On some systems, root can still write to read-only dirs
            # so we just check it doesn't crash
            if os.geteuid() != 0:  # Not root
                assert is_valid is False
                assert error_msg is not None
                assert "not writable" in error_msg
        finally:
            os.chmod(backup_dir, original_mode)
