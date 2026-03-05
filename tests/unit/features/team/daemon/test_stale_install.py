"""Tests for stale-install detection and version check (no auto-restart).

Tests cover:
- _is_install_stale() returns False when files exist (healthy install)
- _is_install_stale() returns True when sys.executable is missing
- _is_install_stale() returns True when static/index.html is missing
- periodic_version_check() logs warning on stale install (no restart)
- periodic_version_check() logs warning on version mismatch (no restart)
- periodic_version_check() continues silently when healthy
- Dashboard returns fallback HTML when static files are missing
- Logo/favicon return 404 when static files are missing

Note: ``asyncio.create_task`` must NOT be mocked globally (breaks ASGI
TestClient).  We mock ``os.kill`` instead, matching the pattern in
``test_routes_restart.py``.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.team.daemon.lifecycle.version_check import (
    _is_install_stale,
)
from open_agent_kit.features.team.daemon.lifecycle.version_check import (
    periodic_version_check as _periodic_version_check,
)
from open_agent_kit.features.team.daemon.server import (
    create_app,
)
from open_agent_kit.features.team.daemon.state import (
    get_state,
    reset_state,
)

# Module paths for patching
_VERSION_MODULE = "open_agent_kit.features.team.daemon.lifecycle.version_check"
_UI_MODULE = "open_agent_kit.features.team.daemon.routes.ui"

# Non-existent path for stale-executable test
_NONEXISTENT_EXECUTABLE = "/nonexistent/python3.13"


@pytest.fixture
def anyio_backend():
    """Restrict anyio tests to asyncio backend (trio doesn't support asyncio.sleep patching)."""
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def setup_state_with_project(tmp_path: Path):
    """Setup daemon state with a project root."""
    state = get_state()
    state.initialize(tmp_path)
    state.project_root = tmp_path
    return state


# =========================================================================
# _is_install_stale() tests
# =========================================================================


class TestIsInstallStale:
    """Test _is_install_stale() helper."""

    def test_returns_false_when_healthy(self) -> None:
        """No mocking needed — sys.executable and static/index.html exist in dev."""
        assert _is_install_stale() is False

    def test_detects_missing_executable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns True when sys.executable points to a deleted path."""
        monkeypatch.setattr("sys.executable", _NONEXISTENT_EXECUTABLE)
        assert _is_install_stale() is True

    def test_detects_missing_static(self, tmp_path: Path) -> None:
        """Returns True when static/index.html does not exist."""
        # Point __file__ resolution to a directory without static/index.html
        fake_parent = tmp_path / "daemon"
        fake_parent.mkdir()
        with patch(f"{_VERSION_MODULE}.Path") as mock_path_cls:
            # First call: Path(sys.executable).exists() -> True (executable OK)
            exec_path = MagicMock()
            exec_path.exists.return_value = True

            # Second call: Path(__file__).parent.parent / "static" / "index.html"
            # (parent.parent because version_check.py is in lifecycle/ subdir)
            file_path = MagicMock()
            static_index = MagicMock()
            static_index.exists.return_value = False
            # Chain: .parent.parent / "static" / "index.html"
            daemon_dir = MagicMock()
            daemon_dir.__truediv__ = MagicMock(return_value=MagicMock())
            daemon_dir.__truediv__.return_value.__truediv__ = MagicMock(return_value=static_index)
            file_path.parent.parent = daemon_dir

            mock_path_cls.side_effect = [exec_path, file_path]
            assert _is_install_stale() is True


# =========================================================================
# periodic_version_check() tests — no auto-restart
# =========================================================================


class TestPeriodicVersionCheck:
    """Test periodic_version_check() logs warnings but does NOT auto-restart."""

    @pytest.mark.anyio
    async def test_logs_warning_on_stale_no_restart(self) -> None:
        """Version check loop detects stale install and logs warning, no restart."""
        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise asyncio.CancelledError

        with (
            patch(f"{_VERSION_MODULE}._is_install_stale", return_value=True),
            patch(f"{_VERSION_MODULE}.check_version"),
            patch(f"{_VERSION_MODULE}.check_upgrade_needed"),
            patch(f"{_VERSION_MODULE}.logger") as mock_logger,
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(asyncio.CancelledError):
                await _periodic_version_check()

        # Should log a warning about stale install
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "Stale install" in warning_msg

    @pytest.mark.anyio
    async def test_logs_warning_on_version_mismatch_no_restart(self) -> None:
        """Version check loop detects version mismatch and logs, no restart."""
        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise asyncio.CancelledError

        def fake_check_version(s):
            # Simulate a meaningful upgrade detected
            s.installed_version = "99.0.0"
            s.update_available = True

        with (
            patch(f"{_VERSION_MODULE}._is_install_stale", return_value=False),
            patch(f"{_VERSION_MODULE}.check_version", side_effect=fake_check_version),
            patch(f"{_VERSION_MODULE}.check_upgrade_needed"),
            patch(f"{_VERSION_MODULE}.logger") as mock_logger,
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(asyncio.CancelledError):
                await _periodic_version_check()

        # Should log about version mismatch
        mock_logger.info.assert_called()
        info_calls = [c[0][0] for c in mock_logger.info.call_args_list]
        assert any("Package update available" in msg for msg in info_calls)

    @pytest.mark.anyio
    async def test_no_warning_when_version_matches(self) -> None:
        """Version check loop does NOT log warnings when versions match."""
        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise asyncio.CancelledError

        def fake_check_version(s):
            s.update_available = False

        with (
            patch(f"{_VERSION_MODULE}._is_install_stale", return_value=False),
            patch(f"{_VERSION_MODULE}.check_version", side_effect=fake_check_version),
            patch(f"{_VERSION_MODULE}.check_upgrade_needed"),
            patch(f"{_VERSION_MODULE}.logger") as mock_logger,
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(asyncio.CancelledError):
                await _periodic_version_check()

        mock_logger.warning.assert_not_called()

    @pytest.mark.anyio
    async def test_stale_warning_logged_only_once(self) -> None:
        """Stale install warning is logged only once, not on every iteration."""
        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                raise asyncio.CancelledError

        with (
            patch(f"{_VERSION_MODULE}._is_install_stale", return_value=True),
            patch(f"{_VERSION_MODULE}.check_version"),
            patch(f"{_VERSION_MODULE}.check_upgrade_needed"),
            patch(f"{_VERSION_MODULE}.logger") as mock_logger,
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(asyncio.CancelledError):
                await _periodic_version_check()

        # Warning should be logged exactly once despite multiple iterations
        stale_warnings = [
            c for c in mock_logger.warning.call_args_list if "Stale install" in c[0][0]
        ]
        assert len(stale_warnings) == 1


# =========================================================================
# UI fallback tests
# =========================================================================


class TestDashboardFallback:
    """Test dashboard returns fallback HTML when static files are missing."""

    def test_returns_fallback_on_missing_static(self, client, setup_state_with_project) -> None:
        """Dashboard returns helpful HTML when index.html is gone."""
        original_read_text = Path.read_text

        def patched_read_text(self, *args, **kwargs):
            if "index.html" in str(self):
                raise FileNotFoundError("Stale install")
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", patched_read_text):
            response = client.get("/")

        assert response.status_code == 200
        assert "Restarting" in response.text
        assert "oak team restart" in response.text

    def test_logo_returns_404_on_missing_file(self, client) -> None:
        """Logo returns 404 when the file doesn't exist."""
        original_exists = Path.exists

        def patched_exists(self, *args, **kwargs):
            if "logo.png" in str(self):
                return False
            return original_exists(self, *args, **kwargs)

        with patch.object(Path, "exists", patched_exists):
            response = client.get("/logo.png")

        assert response.status_code == 404

    def test_favicon_returns_404_on_missing_file(self, client) -> None:
        """Favicon returns 404 when the file doesn't exist."""
        original_exists = Path.exists

        def patched_exists(self, *args, **kwargs):
            if "favicon.png" in str(self):
                return False
            return original_exists(self, *args, **kwargs)

        with patch.object(Path, "exists", patched_exists):
            response = client.get("/favicon.png")

        assert response.status_code == 404
