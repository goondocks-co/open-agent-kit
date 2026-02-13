"""Tests for daemon version check functionality.

Tests cover:
- Detecting version mismatch from stamp file
- No mismatch when versions match
- Fallback to importlib.metadata
- No detection when both sources fail
- Stamp file takes priority over metadata
- Handling missing project_root
- State fields updated correctly
- Semantic version comparison (parse_base_release, is_meaningful_upgrade)
- Dogfooding scenario: dev version vs release version
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CLI_VERSION_FILE,
    CI_DATA_DIR,
    is_meaningful_upgrade,
    parse_base_release,
)
from open_agent_kit.features.codebase_intelligence.daemon.server import _check_version
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)

# Test version values (no magic strings)
# _OLD_VERSION simulates a *newer* installed version (stamp/metadata) vs running daemon
_OLD_VERSION = "0.9.0"
_CURRENT_VERSION = "0.8.0"
# _METADATA_VERSION must be higher than _CURRENT_VERSION to trigger update_available
_METADATA_VERSION = "0.8.1"


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
            patch("importlib.metadata.version", side_effect=ImportError("not found")),
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

    def test_dogfooding_dev_vs_release_no_false_positive(
        self, initialized_state, stamp_file: Path
    ) -> None:
        """Dev version running, release stamp with same base -> no update banner."""
        dev_version = "1.0.10.dev0+gb93e51d90.d20260211"
        release_version = "1.0.10"
        stamp_file.write_text(release_version)

        with patch("open_agent_kit.constants.VERSION", dev_version):
            _check_version(initialized_state)

        assert initialized_state.installed_version == release_version
        assert initialized_state.update_available is False

    def test_dogfooding_dev_with_real_upgrade(self, initialized_state, stamp_file: Path) -> None:
        """Dev version running, stamp has genuinely newer release -> update available."""
        dev_version = "1.0.10.dev0+gb93e51d90.d20260211"
        newer_release = "1.0.11"
        stamp_file.write_text(newer_release)

        with patch("open_agent_kit.constants.VERSION", dev_version):
            _check_version(initialized_state)

        assert initialized_state.installed_version == newer_release
        assert initialized_state.update_available is True


class TestParseBaseRelease:
    """Test parse_base_release() helper."""

    def test_simple_version(self) -> None:
        assert parse_base_release("1.0.10") == (1, 0, 10)

    def test_version_with_v_prefix(self) -> None:
        assert parse_base_release("v1.0.10") == (1, 0, 10)

    def test_dev_version_with_local(self) -> None:
        assert parse_base_release("1.0.10.dev0+gb93e51d90.d20260211") == (1, 0, 10)

    def test_dev_version_without_local(self) -> None:
        assert parse_base_release("1.0.10.dev9") == (1, 0, 10)

    def test_pre_release(self) -> None:
        assert parse_base_release("1.0.10a1") == (1, 0, 10)

    def test_two_part_version(self) -> None:
        assert parse_base_release("1.0") == (1, 0)

    def test_unparseable_returns_empty(self) -> None:
        assert parse_base_release("not-a-version") == ()

    def test_zero_dev(self) -> None:
        assert parse_base_release("0.0.0-dev") == (0, 0, 0)


class TestIsMeaningfulUpgrade:
    """Test is_meaningful_upgrade() helper."""

    def test_same_version_not_upgrade(self) -> None:
        assert is_meaningful_upgrade("1.0.10", "1.0.10") is False

    def test_higher_installed_is_upgrade(self) -> None:
        assert is_meaningful_upgrade("1.0.10", "1.0.11") is True

    def test_lower_installed_not_upgrade(self) -> None:
        assert is_meaningful_upgrade("1.0.11", "1.0.10") is False

    def test_dev_vs_same_base_release_not_upgrade(self) -> None:
        """Dogfooding scenario: dev version vs same-base release."""
        assert is_meaningful_upgrade("1.0.10.dev0+gb93e51d90", "1.0.10") is False

    def test_dev_vs_higher_release_is_upgrade(self) -> None:
        assert is_meaningful_upgrade("1.0.10.dev0+gb93e51d90", "1.0.11") is True

    def test_major_version_upgrade(self) -> None:
        assert is_meaningful_upgrade("1.0.10", "2.0.0") is True

    def test_unparseable_falls_back_to_string_compare(self) -> None:
        assert is_meaningful_upgrade("foo", "bar") is True
        assert is_meaningful_upgrade("foo", "foo") is False
