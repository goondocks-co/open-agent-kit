"""Tests for daemon version check functionality.

Tests cover:
- Detecting version mismatch from stamp file
- No mismatch when versions match
- Fallback to importlib.metadata
- No detection when both sources fail
- Stamp file takes priority over metadata
- Handling missing project_root
- State fields updated correctly
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CLI_VERSION_FILE,
    CI_DATA_DIR,
)
from open_agent_kit.features.codebase_intelligence.daemon.server import _check_version
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)

# Test version values (no magic strings)
_OLD_VERSION = "0.9.0"
_CURRENT_VERSION = "0.8.0"
_METADATA_VERSION = "0.7.5"


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def initialized_state(tmp_path: Path):
    """Create and return a daemon state initialized with tmp_path."""
    state = get_state()
    state.initialize(tmp_path)
    return state


@pytest.fixture
def stamp_file(tmp_path: Path) -> Path:
    """Create the stamp file parent directory and return the stamp path."""
    ci_dir = tmp_path / OAK_DIR / CI_DATA_DIR
    ci_dir.mkdir(parents=True)
    return ci_dir / CI_CLI_VERSION_FILE


class TestVersionCheck:
    """Test _check_version() sync helper from server.py."""

    def test_detects_mismatch_from_stamp_file(self, initialized_state, stamp_file: Path) -> None:
        """Stamp has different version than running VERSION -> mismatch detected."""
        stamp_file.write_text(_OLD_VERSION)

        with patch("open_agent_kit.constants.VERSION", _CURRENT_VERSION):
            _check_version(initialized_state)

        assert initialized_state.installed_version == _OLD_VERSION
        assert initialized_state.update_available is True

    def test_no_mismatch_when_versions_equal(self, initialized_state, stamp_file: Path) -> None:
        """Stamp matches VERSION -> no mismatch."""
        stamp_file.write_text(_CURRENT_VERSION)

        with patch("open_agent_kit.constants.VERSION", _CURRENT_VERSION):
            _check_version(initialized_state)

        assert initialized_state.installed_version == _CURRENT_VERSION
        assert initialized_state.update_available is False

    def test_falls_back_to_importlib_metadata(self, initialized_state, tmp_path: Path) -> None:
        """No stamp file -> falls back to importlib.metadata.version()."""
        # Ensure CI dir exists but no stamp file
        ci_dir = tmp_path / OAK_DIR / CI_DATA_DIR
        ci_dir.mkdir(parents=True)

        with (
            patch("open_agent_kit.constants.VERSION", _CURRENT_VERSION),
            patch("importlib.metadata.version", return_value=_METADATA_VERSION),
        ):
            _check_version(initialized_state)

        assert initialized_state.installed_version == _METADATA_VERSION
        assert initialized_state.update_available is True

    def test_no_detection_when_both_fail(self, initialized_state, tmp_path: Path) -> None:
        """No stamp file and importlib.metadata raises -> installed_version is None."""
        # No CI dir at all
        with (
            patch("open_agent_kit.constants.VERSION", _CURRENT_VERSION),
            patch("importlib.metadata.version", side_effect=Exception("not found")),
        ):
            _check_version(initialized_state)

        assert initialized_state.installed_version is None
        assert initialized_state.update_available is False

    def test_stamp_takes_priority_over_metadata(self, initialized_state, stamp_file: Path) -> None:
        """When both stamp and importlib are available, stamp wins."""
        stamp_file.write_text(_OLD_VERSION)

        with (
            patch("open_agent_kit.constants.VERSION", _CURRENT_VERSION),
            patch("importlib.metadata.version", return_value=_METADATA_VERSION),
        ):
            _check_version(initialized_state)

        # Stamp value should be used, not metadata
        assert initialized_state.installed_version == _OLD_VERSION

    def test_handles_missing_project_root(self) -> None:
        """state.project_root=None -> no-op, no exception."""
        state = get_state()
        assert state.project_root is None

        # Should return without error and not modify state
        _check_version(state)

        assert state.installed_version is None
        assert state.update_available is False

    def test_state_fields_updated_correctly(self, initialized_state, stamp_file: Path) -> None:
        """Verifies installed_version and update_available are set on state."""
        stamp_file.write_text(_OLD_VERSION)

        with patch("open_agent_kit.constants.VERSION", _CURRENT_VERSION):
            _check_version(initialized_state)

        # Both fields should be set
        assert isinstance(initialized_state.installed_version, str)
        assert isinstance(initialized_state.update_available, bool)
        assert initialized_state.installed_version == _OLD_VERSION
        assert initialized_state.update_available is True
