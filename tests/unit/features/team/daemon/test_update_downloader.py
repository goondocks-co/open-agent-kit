"""Tests for wheel download and staging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent_kit.features.team.daemon.lifecycle.update_downloader import (
    _find_wheel_url,
    clean_staging,
    download_and_stage,
)
from open_agent_kit.utils.global_config import ensure_global_dir, read_staged_update

_FAKE_WHEEL_CONTENT = b"PK\x03\x04fake-wheel-content-for-testing"
_FAKE_SHA256 = hashlib.sha256(_FAKE_WHEEL_CONTENT).hexdigest()

_PYPI_JSON = {
    "releases": {
        "1.3.0": [
            {
                "filename": "oak_ci-1.3.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/packages/oak_ci-1.3.0-py3-none-any.whl",
                "digests": {"sha256": _FAKE_SHA256},
                "packagetype": "bdist_wheel",
            },
            {
                "filename": "oak_ci-1.3.0.tar.gz",
                "url": "https://files.pythonhosted.org/packages/oak_ci-1.3.0.tar.gz",
                "digests": {"sha256": "ignored"},
                "packagetype": "sdist",
            },
        ]
    }
}


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


class TestFindWheelUrl:
    """Test wheel URL extraction from PyPI metadata."""

    def test_finds_wheel_not_sdist(self) -> None:
        url, sha, filename = _find_wheel_url(_PYPI_JSON, "1.3.0")
        assert "whl" in url
        assert sha == _FAKE_SHA256
        assert filename == "oak_ci-1.3.0-py3-none-any.whl"

    def test_raises_when_version_missing(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            _find_wheel_url(_PYPI_JSON, "9.9.9")

    def test_raises_when_no_wheel(self) -> None:
        data = {
            "releases": {
                "1.0.0": [
                    {
                        "packagetype": "sdist",
                        "filename": "x.tar.gz",
                        "url": "x",
                        "digests": {"sha256": "x"},
                    }
                ]
            }
        }
        with pytest.raises(ValueError, match="No wheel"):
            _find_wheel_url(data, "1.0.0")


class TestCleanStaging:
    """Test staging directory cleanup."""

    def test_removes_existing_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        (tmp_path / "staging" / "old_wheel.whl").write_bytes(b"old")
        clean_staging()
        assert list((tmp_path / "staging").iterdir()) == []


class TestDownloadAndStage:
    """Test full download + verify + stage flow."""

    @pytest.mark.anyio
    async def test_successful_download(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()

        with (
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader.fetch_pypi_raw",
                return_value=json.dumps(_PYPI_JSON).encode(),
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader._download_file",
                new_callable=AsyncMock,
                return_value=_FAKE_WHEEL_CONTENT,
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader._try_acquire_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=True), __exit__=MagicMock(return_value=False)
                ),
            ),
        ):
            result = await download_and_stage("1.3.0", channel="stable")

        assert result is True
        staged = read_staged_update()
        assert staged is not None
        assert staged["version"] == "1.3.0"
        assert staged["channel"] == "stable"
        assert staged["schema_version"] == 1
        # Wheel file exists
        wheel_path = Path(staged["wheel_path"])
        assert wheel_path.exists()

    @pytest.mark.anyio
    async def test_checksum_mismatch_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()

        with (
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader.fetch_pypi_raw",
                return_value=json.dumps(_PYPI_JSON).encode(),
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader._download_file",
                new_callable=AsyncMock,
                return_value=b"corrupted-content",
            ),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_downloader._try_acquire_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=True), __exit__=MagicMock(return_value=False)
                ),
            ),
        ):
            result = await download_and_stage("1.3.0")

        assert result is False
        assert read_staged_update() is None
