"""Tests for /api/update/* routes.

Tests cover:
- GET /api/update/status (exempt case, normal case)
- POST /api/update/check (triggers PyPI check)
- POST /api/update/apply (no staged update error, success case)
- PUT /api/update/channel (valid switch, invalid channel)

Note: ``delayed_shutdown`` is replaced with a no-op coroutine so that the
scheduled SIGTERM never fires during tests.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.team.daemon.lifecycle.update_checker import UpdateCheckResult
from open_agent_kit.features.team.daemon.server import create_app
from open_agent_kit.features.team.daemon.state import get_state, reset_state
from open_agent_kit.utils.global_config import UpdateConfig
from open_agent_kit.utils.update_exempt import UpdateExemption

# Module path under test
_UPDATE_MODULE = "open_agent_kit.features.team.daemon.routes.update"

# Stable test values — no magic strings
_RUNNING_VERSION = "1.0.0"
_LATEST_VERSION = "1.1.0"
_VALID_CHANNEL_BETA = "beta"
_VALID_CHANNEL_STABLE = "stable"
_INVALID_CHANNEL = "nightly"
_STAGED_VERSION = "1.1.0"
_STAGED_WHEEL = "/tmp/oak-1.1.0.whl"

_EDITABLE_EXEMPTION = UpdateExemption(
    reason="editable_install",
    message="Self-update is disabled for editable (development) installs.",
)


async def _noop_shutdown(delay_seconds: float, *, log_message: str | None = None) -> None:
    """No-op replacement for delayed_shutdown during tests."""


@contextmanager
def _no_exemption():
    """Patch check_update_exempt to return None (update allowed)."""
    with patch(f"{_UPDATE_MODULE}.check_update_exempt", return_value=None):
        yield


@contextmanager
def _with_exemption(exemption: UpdateExemption = _EDITABLE_EXEMPTION):
    """Patch check_update_exempt to return an exemption."""
    with patch(f"{_UPDATE_MODULE}.check_update_exempt", return_value=exemption):
        yield


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client(auth_headers):
    """FastAPI test client with auth."""
    app = create_app()
    return TestClient(app, headers=auth_headers)


@pytest.fixture
def setup_state_with_project(tmp_path: Path):
    """Setup daemon state with a project root."""
    state = get_state()
    state.initialize(tmp_path)
    state.project_root = tmp_path
    return state


# =============================================================================
# GET /api/update/status
# =============================================================================


class TestUpdateStatus:
    """Test GET /api/update/status endpoint."""

    def test_status_returns_exempt_when_editable(self, client) -> None:
        """Returns exempt=True with reason when update is not allowed."""
        with _with_exemption():
            response = client.get("/api/update/status")

        assert response.status_code == 200
        data = response.json()
        assert data["exempt"] is True
        assert data["reason"] == _EDITABLE_EXEMPTION.reason
        assert data["message"] == _EDITABLE_EXEMPTION.message

    def test_status_returns_full_state_when_not_exempt(self, client) -> None:
        """Returns version/channel/staged info when update is allowed."""
        fake_config = UpdateConfig(channel=_VALID_CHANNEL_STABLE, auto_download=True, check_interval_hours=6)

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.load_update_config", return_value=fake_config),
            patch(f"{_UPDATE_MODULE}.read_staged_update", return_value=None),
            patch(f"{_UPDATE_MODULE}.read_last_check", return_value=None),
            patch(f"{_UPDATE_MODULE}.read_update_error", return_value=None),
            patch(f"{_UPDATE_MODULE}.VERSION", _RUNNING_VERSION),
        ):
            response = client.get("/api/update/status")

        assert response.status_code == 200
        data = response.json()
        assert data["exempt"] is False
        assert data["running_version"] == _RUNNING_VERSION
        assert data["channel"] == _VALID_CHANNEL_STABLE
        assert data["auto_download"] is True
        assert data["check_interval_hours"] == 6
        assert data["staged_update"] is None
        assert data["last_check"] is None
        assert data["error"] is None

    def test_status_includes_staged_update_when_present(self, client) -> None:
        """staged_update field populated when a staged update exists."""
        staged = {"version": _STAGED_VERSION, "wheel_path": _STAGED_WHEEL}
        fake_config = UpdateConfig()

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.load_update_config", return_value=fake_config),
            patch(f"{_UPDATE_MODULE}.read_staged_update", return_value=staged),
            patch(f"{_UPDATE_MODULE}.read_last_check", return_value=None),
            patch(f"{_UPDATE_MODULE}.read_update_error", return_value=None),
        ):
            response = client.get("/api/update/status")

        assert response.status_code == 200
        data = response.json()
        assert data["staged_update"]["version"] == _STAGED_VERSION

    def test_status_includes_error_when_present(self, client) -> None:
        """error field populated when an update error file exists."""
        fake_config = UpdateConfig()

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.load_update_config", return_value=fake_config),
            patch(f"{_UPDATE_MODULE}.read_staged_update", return_value=None),
            patch(f"{_UPDATE_MODULE}.read_last_check", return_value=None),
            patch(f"{_UPDATE_MODULE}.read_update_error", return_value="Package install failed"),
        ):
            response = client.get("/api/update/status")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] == "Package install failed"


# =============================================================================
# POST /api/update/check
# =============================================================================


class TestUpdateCheck:
    """Test POST /api/update/check endpoint."""

    def test_check_returns_400_when_exempt(self, client) -> None:
        """Returns 400 when self-update is not allowed."""
        with _with_exemption():
            response = client.post("/api/update/check")

        assert response.status_code == 400
        assert _EDITABLE_EXEMPTION.message in response.json()["detail"]

    def test_check_returns_update_available(self, client) -> None:
        """Returns update_available=True when newer version found."""
        fake_config = UpdateConfig(channel=_VALID_CHANNEL_STABLE)
        check_result = UpdateCheckResult(
            update_available=True,
            latest_version=_LATEST_VERSION,
            channel=_VALID_CHANNEL_STABLE,
        )

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.load_update_config", return_value=fake_config),
            patch(
                f"{_UPDATE_MODULE}.check_for_update",
                new=AsyncMock(return_value=check_result),
            ),
        ):
            response = client.post("/api/update/check")

        assert response.status_code == 200
        data = response.json()
        assert data["update_available"] is True
        assert data["latest_version"] == _LATEST_VERSION
        assert data["channel"] == _VALID_CHANNEL_STABLE
        assert data["error"] is None

    def test_check_returns_no_update_when_current(self, client) -> None:
        """Returns update_available=False when already up to date."""
        fake_config = UpdateConfig(channel=_VALID_CHANNEL_STABLE)
        check_result = UpdateCheckResult(
            update_available=False,
            latest_version=None,
            channel=_VALID_CHANNEL_STABLE,
        )

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.load_update_config", return_value=fake_config),
            patch(
                f"{_UPDATE_MODULE}.check_for_update",
                new=AsyncMock(return_value=check_result),
            ),
        ):
            response = client.post("/api/update/check")

        assert response.status_code == 200
        data = response.json()
        assert data["update_available"] is False
        assert data["latest_version"] is None

    def test_check_propagates_error_from_checker(self, client) -> None:
        """Error field is returned when PyPI check fails."""
        fake_config = UpdateConfig()
        check_result = UpdateCheckResult(
            update_available=False,
            error="Network timeout",
            channel=_VALID_CHANNEL_STABLE,
        )

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.load_update_config", return_value=fake_config),
            patch(
                f"{_UPDATE_MODULE}.check_for_update",
                new=AsyncMock(return_value=check_result),
            ),
        ):
            response = client.post("/api/update/check")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] == "Network timeout"


# =============================================================================
# POST /api/update/apply
# =============================================================================


class TestUpdateApply:
    """Test POST /api/update/apply endpoint."""

    def test_apply_returns_400_when_exempt(self, client) -> None:
        """Returns 400 when self-update is not allowed."""
        with _with_exemption():
            response = client.post("/api/update/apply")

        assert response.status_code == 400
        assert _EDITABLE_EXEMPTION.message in response.json()["detail"]

    def test_apply_returns_400_when_no_staged_update(self, client) -> None:
        """Returns 400 when no staged update is available."""
        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.read_staged_update", return_value=None),
        ):
            response = client.post("/api/update/apply")

        assert response.status_code == 400
        assert "No staged update available" in response.json()["detail"]

    def test_apply_returns_500_when_no_project_root(self, client) -> None:
        """Returns 500 when state.project_root is None."""
        staged = {"version": _STAGED_VERSION, "wheel_path": _STAGED_WHEEL}
        state = get_state()
        state.project_root = None

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.read_staged_update", return_value=staged),
        ):
            response = client.post("/api/update/apply")

        assert response.status_code == 500
        assert "No project root configured" in response.json()["detail"]

    def test_apply_returns_500_when_installer_fails(
        self, client, setup_state_with_project
    ) -> None:
        """Returns 500 when apply_staged_update returns False."""
        staged = {"version": _STAGED_VERSION, "wheel_path": _STAGED_WHEEL}

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.read_staged_update", return_value=staged),
            patch(f"{_UPDATE_MODULE}.apply_staged_update", return_value=False),
        ):
            response = client.post("/api/update/apply")

        assert response.status_code == 500
        assert "Failed to spawn update script" in response.json()["detail"]

    def test_apply_succeeds_and_schedules_shutdown(
        self, client, setup_state_with_project
    ) -> None:
        """Returns 200 with applying status and schedules delayed shutdown."""
        staged = {"version": _STAGED_VERSION, "wheel_path": _STAGED_WHEEL}

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.read_staged_update", return_value=staged),
            patch(f"{_UPDATE_MODULE}.apply_staged_update", return_value=True),
            patch(
                f"{_UPDATE_MODULE}.delayed_shutdown",
                side_effect=_noop_shutdown,
            ),
        ):
            response = client.post("/api/update/apply")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "applying"
        assert data["version"] == _STAGED_VERSION


# =============================================================================
# PUT /api/update/channel
# =============================================================================


class TestUpdateChannel:
    """Test PUT /api/update/channel endpoint."""

    def test_channel_returns_400_when_exempt(self, client) -> None:
        """Returns 400 when self-update is not allowed."""
        with _with_exemption():
            response = client.put("/api/update/channel", json={"channel": _VALID_CHANNEL_BETA})

        assert response.status_code == 400
        assert _EDITABLE_EXEMPTION.message in response.json()["detail"]

    def test_channel_rejects_invalid_channel(self, client) -> None:
        """Returns 400 for unrecognised channel names."""
        with _no_exemption():
            response = client.put("/api/update/channel", json={"channel": _INVALID_CHANNEL})

        assert response.status_code == 400
        assert _INVALID_CHANNEL in response.json()["detail"]

    def test_channel_switches_to_beta(self, client) -> None:
        """Successfully switches to beta channel and persists config."""
        fake_config = UpdateConfig(channel=_VALID_CHANNEL_STABLE)

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.ensure_global_dir"),
            patch(f"{_UPDATE_MODULE}.load_update_config", return_value=fake_config),
            patch(f"{_UPDATE_MODULE}.save_update_config") as mock_save,
        ):
            response = client.put("/api/update/channel", json={"channel": _VALID_CHANNEL_BETA})

        assert response.status_code == 200
        data = response.json()
        assert data["channel"] == _VALID_CHANNEL_BETA
        assert _VALID_CHANNEL_BETA in data["message"]
        mock_save.assert_called_once()

    def test_channel_switches_to_stable(self, client) -> None:
        """Successfully switches to stable channel."""
        fake_config = UpdateConfig(channel=_VALID_CHANNEL_BETA)

        with (
            _no_exemption(),
            patch(f"{_UPDATE_MODULE}.ensure_global_dir"),
            patch(f"{_UPDATE_MODULE}.load_update_config", return_value=fake_config),
            patch(f"{_UPDATE_MODULE}.save_update_config"),
        ):
            response = client.put("/api/update/channel", json={"channel": _VALID_CHANNEL_STABLE})

        assert response.status_code == 200
        data = response.json()
        assert data["channel"] == _VALID_CHANNEL_STABLE

    def test_channel_rejects_missing_body(self, client) -> None:
        """Returns 422 when request body is missing."""
        with _no_exemption():
            response = client.put("/api/update/channel", json={})

        assert response.status_code == 422
