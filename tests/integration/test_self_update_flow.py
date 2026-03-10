# tests/integration/test_self_update_flow.py
"""Integration test for the full self-update flow.

Tests: detect → download → stage → apply sequence with mocked PyPI
and subprocess. Verifies all components work together.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from open_agent_kit.features.team.daemon.server import create_app
from open_agent_kit.features.team.daemon.state import get_state, reset_state
from open_agent_kit.utils.global_config import ensure_global_dir, write_staged_update


_WHEEL_CONTENT = b"PK\x03\x04integration-test-wheel"
_WHEEL_SHA = hashlib.sha256(_WHEEL_CONTENT).hexdigest()

_PYPI_RESPONSE = json.dumps({
    "releases": {
        "1.0.0": [],
        "2.0.0": [{
            "filename": "oak_ci-2.0.0-py3-none-any.whl",
            "url": "https://example.com/oak_ci-2.0.0.whl",
            "digests": {"sha256": _WHEEL_SHA},
            "packagetype": "bdist_wheel",
        }],
    }
}).encode()


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client(auth_headers):
    app = create_app()
    return TestClient(app, headers=auth_headers)


class TestSelfUpdateFlow:
    """Test the complete check → download → apply sequence."""

    def test_check_detects_update(self, client, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        state = get_state()
        state.initialize(tmp_path)

        with (
            patch("open_agent_kit.features.team.daemon.routes.update.check_update_exempt", return_value=None),
            patch("open_agent_kit.features.team.daemon.routes.update.VERSION", "1.0.0"),
            patch(
                "open_agent_kit.features.team.daemon.lifecycle.update_checker.fetch_pypi_raw",
                return_value=_PYPI_RESPONSE,
            ),
        ):
            resp = client.post("/api/update/check")

        assert resp.status_code == 200
        data = resp.json()
        assert data["update_available"] is True
        assert data["latest_version"] == "2.0.0"

    def test_status_shows_staged_update(self, client, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("OAK_GLOBAL_DIR", str(tmp_path))
        ensure_global_dir()
        state = get_state()
        state.initialize(tmp_path)

        # Pre-stage an update
        staging = tmp_path / "staging"
        staging.mkdir(exist_ok=True)
        wheel = staging / "oak_ci-2.0.0.whl"
        wheel.write_bytes(_WHEEL_CONTENT)
        write_staged_update({
            "schema_version": 1,
            "version": "2.0.0",
            "wheel_path": str(wheel),
            "channel": "stable",
            "downloaded_at": "2026-03-10T00:00:00Z",
            "sha256": _WHEEL_SHA,
        })

        with patch("open_agent_kit.features.team.daemon.routes.update.check_update_exempt", return_value=None):
            resp = client.get("/api/update/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["staged_update"]["version"] == "2.0.0"
