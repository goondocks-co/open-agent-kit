"""Tests for the PyPI update checker."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.features.team.daemon.lifecycle.update_checker import (
    check_for_update,
    should_check_now,
)
from open_agent_kit.utils.global_config import UpdateConfig


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


_PYPI_RESPONSE = json.dumps(
    {
        "releases": {
            "1.0.0": [],
            "1.1.0": [],
            "1.2.0": [],
            "1.3.0b1": [],
            "1.3.0b2": [],
        }
    }
).encode()


class TestCheckForUpdate:
    """Test the core version check logic."""

    @pytest.mark.anyio
    async def test_detects_newer_stable_version(self) -> None:
        config = UpdateConfig(channel="stable")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=_PYPI_RESPONSE,
        ):
            result = await check_for_update(running_version="1.1.0", config=config)
        assert result.update_available is True
        assert result.latest_version == "1.2.0"

    @pytest.mark.anyio
    async def test_no_update_when_current(self) -> None:
        config = UpdateConfig(channel="stable")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=_PYPI_RESPONSE,
        ):
            result = await check_for_update(running_version="1.2.0", config=config)
        assert result.update_available is False

    @pytest.mark.anyio
    async def test_beta_channel_considers_prereleases(self) -> None:
        config = UpdateConfig(channel="beta")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=_PYPI_RESPONSE,
        ):
            result = await check_for_update(running_version="1.2.0", config=config)
        assert result.update_available is True
        assert result.latest_version == "1.3.0b2"

    @pytest.mark.anyio
    async def test_beta_channel_prefers_stable_if_newer(self) -> None:
        """If latest stable > latest beta, offer stable even on beta channel."""
        pypi_data = json.dumps({"releases": {"2.0.0": [], "1.9.0b1": []}}).encode()
        config = UpdateConfig(channel="beta")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=pypi_data,
        ):
            result = await check_for_update(running_version="1.8.0", config=config)
        assert result.latest_version == "2.0.0"

    @pytest.mark.anyio
    async def test_no_downgrade(self) -> None:
        config = UpdateConfig(channel="stable")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            return_value=_PYPI_RESPONSE,
        ):
            result = await check_for_update(running_version="5.0.0", config=config)
        assert result.update_available is False

    @pytest.mark.anyio
    async def test_handles_pypi_failure(self) -> None:
        config = UpdateConfig(channel="stable")
        with patch(
            "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
            side_effect=Exception("Network error"),
        ):
            result = await check_for_update(running_version="1.0.0", config=config)
        assert result.update_available is False
        assert result.error is not None


class TestShouldCheckNow:
    """Test check interval logic."""

    def test_true_when_no_last_check(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        assert should_check_now(check_interval_hours=6) is True

    def test_false_when_recently_checked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        from open_agent_kit.utils.global_config import ensure_global_dir, write_last_check

        ensure_global_dir()
        write_last_check({"timestamp": time.time(), "version": "1.0.0"})
        assert should_check_now(check_interval_hours=6) is False

    def test_true_when_interval_expired(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        from open_agent_kit.utils.global_config import ensure_global_dir, write_last_check

        ensure_global_dir()
        write_last_check({"timestamp": time.time() - 7 * 3600, "version": "1.0.0"})
        assert should_check_now(check_interval_hours=6) is True
