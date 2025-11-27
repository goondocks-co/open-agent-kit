"""Tests for backup directory configuration functions."""

import os
from pathlib import Path
from unittest import mock

import pytest


class TestGetBackupDir:
    """Tests for get_backup_dir function."""

    def test_default_when_no_env_var(self, tmp_path: Path) -> None:
        """Should return default path when no env var is set."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            # Remove OAK_CI_BACKUP_DIR if it exists
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(tmp_path)

            assert result == tmp_path / CI_HISTORY_BACKUP_DIR

    def test_env_var_absolute_path(self, tmp_path: Path) -> None:
        """Should use absolute path from env var."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )

        custom_dir = tmp_path / "custom-backups"
        custom_dir.mkdir(parents=True)

        with mock.patch.dict(os.environ, {"OAK_CI_BACKUP_DIR": str(custom_dir)}):
            result = get_backup_dir(tmp_path)

            assert result == custom_dir

    def test_env_var_relative_path(self, tmp_path: Path) -> None:
        """Should resolve relative path against project root."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )

        with mock.patch.dict(os.environ, {"OAK_CI_BACKUP_DIR": "relative/backup/dir"}):
            result = get_backup_dir(tmp_path)

            expected = (tmp_path / "relative/backup/dir").resolve()
            assert result == expected

    def test_env_var_empty_uses_default(self, tmp_path: Path) -> None:
        """Should use default path when env var is empty string."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        with mock.patch.dict(os.environ, {"OAK_CI_BACKUP_DIR": ""}):
            result = get_backup_dir(tmp_path)

            assert result == tmp_path / CI_HISTORY_BACKUP_DIR

    def test_env_var_whitespace_only_uses_default(self, tmp_path: Path) -> None:
        """Should use default path when env var is whitespace only."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        with mock.patch.dict(os.environ, {"OAK_CI_BACKUP_DIR": "   "}):
            result = get_backup_dir(tmp_path)

            assert result == tmp_path / CI_HISTORY_BACKUP_DIR

    def test_uses_cwd_when_no_project_root(self) -> None:
        """Should use cwd when project_root is None."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(None)

            assert result == Path.cwd() / CI_HISTORY_BACKUP_DIR


class TestDotenvSupport:
    """Tests for .env file reading in get_backup_dir."""

    def test_dotenv_absolute_path(self, tmp_path: Path) -> None:
        """Should read backup dir from .env file."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )

        custom_dir = tmp_path / "shared-backups"
        dotenv = tmp_path / ".env"
        dotenv.write_text(f"OAK_CI_BACKUP_DIR={custom_dir}\n")

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(tmp_path)

            assert result == custom_dir

    def test_dotenv_relative_path(self, tmp_path: Path) -> None:
        """Should resolve relative .env paths against project root."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )

        dotenv = tmp_path / ".env"
        dotenv.write_text("OAK_CI_BACKUP_DIR=backups/shared\n")

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(tmp_path)

            assert result == (tmp_path / "backups/shared").resolve()

    def test_env_var_overrides_dotenv(self, tmp_path: Path) -> None:
        """Shell env var should take priority over .env file."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )

        dotenv_dir = tmp_path / "from-dotenv"
        env_dir = tmp_path / "from-env"

        dotenv = tmp_path / ".env"
        dotenv.write_text(f"OAK_CI_BACKUP_DIR={dotenv_dir}\n")

        with mock.patch.dict(os.environ, {"OAK_CI_BACKUP_DIR": str(env_dir)}):
            result = get_backup_dir(tmp_path)

            assert result == env_dir

    def test_dotenv_quoted_value(self, tmp_path: Path) -> None:
        """Should handle quoted values in .env file."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )

        custom_dir = tmp_path / "quoted-path"
        dotenv = tmp_path / ".env"
        dotenv.write_text(f'OAK_CI_BACKUP_DIR="{custom_dir}"\n')

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(tmp_path)

            assert result == custom_dir

    def test_dotenv_with_comments(self, tmp_path: Path) -> None:
        """Should skip comments in .env file."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )

        custom_dir = tmp_path / "backups"
        dotenv = tmp_path / ".env"
        dotenv.write_text(f"# This is a comment\nOTHER_VAR=foo\nOAK_CI_BACKUP_DIR={custom_dir}\n")

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(tmp_path)

            assert result == custom_dir

    def test_dotenv_with_inline_comment(self, tmp_path: Path) -> None:
        """Should handle inline comments for unquoted values."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )

        custom_dir = tmp_path / "backups"
        dotenv = tmp_path / ".env"
        dotenv.write_text(f"OAK_CI_BACKUP_DIR={custom_dir} # team shared dir\n")

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(tmp_path)

            assert result == custom_dir

    def test_no_dotenv_uses_default(self, tmp_path: Path) -> None:
        """Should use default when no .env file exists."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(tmp_path)

            assert result == tmp_path / CI_HISTORY_BACKUP_DIR

    def test_dotenv_empty_value_uses_default(self, tmp_path: Path) -> None:
        """Should use default when .env has empty value."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
        )
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_HISTORY_BACKUP_DIR,
        )

        dotenv = tmp_path / ".env"
        dotenv.write_text("OAK_CI_BACKUP_DIR=\n")

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir(tmp_path)

            assert result == tmp_path / CI_HISTORY_BACKUP_DIR


class TestGetBackupDirSource:
    """Tests for get_backup_dir_source function."""

    def test_returns_environment_variable_when_set(self, tmp_path: Path) -> None:
        """Should return 'environment variable' when env var is set."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir_source,
        )

        with mock.patch.dict(os.environ, {"OAK_CI_BACKUP_DIR": "/some/path"}):
            result = get_backup_dir_source(tmp_path)

            assert result == "environment variable"

    def test_returns_default_when_not_set(self, tmp_path: Path) -> None:
        """Should return 'default' when env var is not set."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir_source,
        )

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir_source(tmp_path)

            assert result == "default"

    def test_returns_default_when_empty(self, tmp_path: Path) -> None:
        """Should return 'default' when env var is empty."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir_source,
        )

        with mock.patch.dict(os.environ, {"OAK_CI_BACKUP_DIR": ""}):
            result = get_backup_dir_source(tmp_path)

            assert result == "default"

    def test_returns_dotenv_source(self, tmp_path: Path) -> None:
        """Should return 'dotenv file (.env)' when set via .env."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir_source,
        )

        dotenv = tmp_path / ".env"
        dotenv.write_text("OAK_CI_BACKUP_DIR=/shared/backups\n")

        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OAK_CI_BACKUP_DIR", None)

            result = get_backup_dir_source(tmp_path)

            assert result == "dotenv file (.env)"

    def test_env_var_source_overrides_dotenv_source(self, tmp_path: Path) -> None:
        """Should report 'environment variable' even when .env also exists."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir_source,
        )

        dotenv = tmp_path / ".env"
        dotenv.write_text("OAK_CI_BACKUP_DIR=/from-dotenv\n")

        with mock.patch.dict(os.environ, {"OAK_CI_BACKUP_DIR": "/from-env"}):
            result = get_backup_dir_source(tmp_path)

            assert result == "environment variable"


class TestValidateBackupDir:
    """Tests for validate_backup_dir function."""

    def test_valid_existing_writable_directory(self, tmp_path: Path) -> None:
        """Should return valid for existing writable directory."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            validate_backup_dir,
        )

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        is_valid, error_msg = validate_backup_dir(backup_dir, create=False)

        assert is_valid is True
        assert error_msg is None

    def test_creates_directory_when_missing(self, tmp_path: Path) -> None:
        """Should create directory when missing and create=True."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            validate_backup_dir,
        )

        backup_dir = tmp_path / "new-backups" / "nested"

        is_valid, error_msg = validate_backup_dir(backup_dir, create=True)

        assert is_valid is True
        assert error_msg is None
        assert backup_dir.exists()

    def test_fails_when_missing_and_create_false(self, tmp_path: Path) -> None:
        """Should fail when directory missing and create=False."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            validate_backup_dir,
        )

        backup_dir = tmp_path / "nonexistent"

        is_valid, error_msg = validate_backup_dir(backup_dir, create=False)

        assert is_valid is False
        assert error_msg is not None
        assert "does not exist" in error_msg

    def test_fails_when_path_is_file(self, tmp_path: Path) -> None:
        """Should fail when path points to a file, not directory."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
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
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
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
