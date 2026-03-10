"""Tests for self-update exemption checks."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from open_agent_kit.utils.update_exempt import (
    FORCE_SELF_UPDATE_ENV_VAR,
    check_update_exempt,
)


@pytest.fixture(autouse=True)
def _clear_force_env(monkeypatch):
    """Ensure the force-bypass env var is never set during exemption tests."""
    monkeypatch.delenv(FORCE_SELF_UPDATE_ENV_VAR, raising=False)
    check_update_exempt.cache_clear()


class TestCheckUpdateExempt:
    """Test exemption detection."""

    def test_not_exempt_on_normal_install(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.update_exempt.get_install_source", return_value=(None, False)
            ),
            patch("open_agent_kit.utils.update_exempt.sys") as mock_sys,
        ):
            mock_sys.platform = "darwin"
            result = check_update_exempt()
        assert result is None

    def test_exempt_on_editable_install(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.update_exempt.get_install_source",
                return_value=("/path", True),
            ),
            patch("open_agent_kit.utils.update_exempt.sys") as mock_sys,
        ):
            mock_sys.platform = "darwin"
            result = check_update_exempt()
        assert result is not None
        assert result.reason == "editable_install"

    def test_exempt_on_windows(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.update_exempt.get_install_source", return_value=(None, False)
            ),
            patch("open_agent_kit.utils.update_exempt.sys") as mock_sys,
        ):
            mock_sys.platform = "win32"
            result = check_update_exempt()
        assert result is not None
        assert result.reason == "windows_unsupported"

    def test_editable_takes_priority_over_windows(self) -> None:
        with (
            patch(
                "open_agent_kit.utils.update_exempt.get_install_source",
                return_value=("/path", True),
            ),
            patch("open_agent_kit.utils.update_exempt.sys") as mock_sys,
        ):
            mock_sys.platform = "win32"
            result = check_update_exempt()
        assert result is not None
        assert result.reason == "editable_install"
