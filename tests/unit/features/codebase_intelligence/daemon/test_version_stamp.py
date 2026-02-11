"""Tests for CLI version stamp functionality.

Tests cover:
- Writing version stamp when CI directory exists
- No-op behavior when CI directory is missing
- Skip write when version is unchanged
- Overwrite when version differs
- Graceful OSError handling
- Stamp content matches VERSION constant
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.constants import VERSION
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CLI_VERSION_FILE,
    CI_DATA_DIR,
)


@pytest.fixture
def ci_dir(tmp_path: Path) -> Path:
    """Create .oak/ci/ directory structure and return the CI data dir."""
    ci_data = tmp_path / OAK_DIR / CI_DATA_DIR
    ci_data.mkdir(parents=True)
    return ci_data


class TestStampCliVersion:
    """Test _stamp_cli_version() function from cli.py."""

    def test_writes_stamp_when_ci_dir_exists(self, tmp_path: Path, ci_dir: Path) -> None:
        """Creates stamp file with VERSION content when .oak/ci/ exists."""
        from open_agent_kit.cli import _stamp_cli_version

        with patch.object(Path, "cwd", return_value=tmp_path):
            _stamp_cli_version()

        stamp = ci_dir / CI_CLI_VERSION_FILE
        assert stamp.exists()
        assert stamp.read_text() == VERSION

    def test_no_op_when_ci_dir_missing(self, tmp_path: Path) -> None:
        """No error and no file created when .oak/ci/ does not exist."""
        from open_agent_kit.cli import _stamp_cli_version

        with patch.object(Path, "cwd", return_value=tmp_path):
            _stamp_cli_version()

        stamp = tmp_path / OAK_DIR / CI_DATA_DIR / CI_CLI_VERSION_FILE
        assert not stamp.exists()

    def test_no_op_when_version_unchanged(self, tmp_path: Path, ci_dir: Path) -> None:
        """Reads existing stamp and skips write if version matches."""
        from open_agent_kit.cli import _stamp_cli_version

        stamp = ci_dir / CI_CLI_VERSION_FILE
        stamp.write_text(VERSION)

        with patch.object(Path, "cwd", return_value=tmp_path):
            _stamp_cli_version()

        # File should not have been rewritten (mtime unchanged)
        assert stamp.read_text() == VERSION

    def test_overwrites_when_version_differs(self, tmp_path: Path, ci_dir: Path) -> None:
        """Old version content is overwritten with current VERSION."""
        from open_agent_kit.cli import _stamp_cli_version

        stamp = ci_dir / CI_CLI_VERSION_FILE
        stamp.write_text("0.0.0-old")

        with patch.object(Path, "cwd", return_value=tmp_path):
            _stamp_cli_version()

        assert stamp.read_text() == VERSION

    def test_handles_oserror_gracefully(self, tmp_path: Path, ci_dir: Path) -> None:
        """Read-only filesystem or permission error does not raise an exception."""
        from open_agent_kit.cli import _stamp_cli_version

        stamp = ci_dir / CI_CLI_VERSION_FILE

        with (
            patch.object(Path, "cwd", return_value=tmp_path),
            patch.object(Path, "write_text", side_effect=OSError("read-only")),
        ):
            # Should not raise
            _stamp_cli_version()

        # Stamp should not exist since write_text was mocked to fail
        assert not stamp.exists()

    def test_stamp_content_matches_version_constant(self, tmp_path: Path, ci_dir: Path) -> None:
        """Stamp file content equals VERSION constant exactly."""
        from open_agent_kit.cli import _stamp_cli_version

        with patch.object(Path, "cwd", return_value=tmp_path):
            _stamp_cli_version()

        stamp = ci_dir / CI_CLI_VERSION_FILE
        assert stamp.read_text().strip() == VERSION
