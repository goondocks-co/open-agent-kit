"""Tests for DaemonState version detection fields.

Tests cover:
- Default installed_version is None
- Default update_available is False
- reset() clears version fields
- Fields are mutable
"""

import pytest

from open_agent_kit.features.codebase_intelligence.daemon.state import (
    DaemonState,
    reset_state,
)

# Test version value (no magic strings)
_TEST_VERSION = "1.2.3"


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


class TestDaemonStateVersionFields:
    """Test new version detection fields on DaemonState."""

    def test_default_installed_version_is_none(self) -> None:
        """installed_version defaults to None on fresh state."""
        state = DaemonState()
        assert state.installed_version is None

    def test_default_update_available_is_false(self) -> None:
        """update_available defaults to False on fresh state."""
        state = DaemonState()
        assert state.update_available is False

    def test_reset_clears_version_fields(self) -> None:
        """reset() returns version fields to defaults."""
        state = DaemonState()
        state.installed_version = _TEST_VERSION
        state.update_available = True

        state.reset()

        assert state.installed_version is None
        assert state.update_available is False

    def test_fields_are_mutable(self) -> None:
        """Version fields can be set and read back."""
        state = DaemonState()

        state.installed_version = _TEST_VERSION
        state.update_available = True

        assert state.installed_version == _TEST_VERSION
        assert state.update_available is True

        # Can be set to different values
        state.installed_version = None
        state.update_available = False

        assert state.installed_version is None
        assert state.update_available is False
