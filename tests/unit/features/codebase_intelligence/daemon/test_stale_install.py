"""Tests for stale-install detection and self-restart.

Tests cover:
- _is_install_stale() returns False when files exist (healthy install)
- _is_install_stale() returns True when sys.executable is missing
- _is_install_stale() returns True when static/index.html is missing
- _trigger_stale_restart() spawns /bin/sh subprocess and sends SIGTERM
- _periodic_version_check() triggers restart on stale install
- Dashboard returns fallback HTML when static files are missing
- Logo/favicon return 404 when static files are missing

Note: ``asyncio.create_task`` must NOT be mocked globally (breaks ASGI
TestClient).  We mock ``os.kill`` instead, matching the pattern in
``test_routes_restart.py``.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.daemon.server import (
    _is_install_stale,
    _periodic_version_check,
    _trigger_stale_restart,
    create_app,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)

# Module paths for patching
_SERVER_MODULE = "open_agent_kit.features.codebase_intelligence.daemon.server"
_UI_MODULE = "open_agent_kit.features.codebase_intelligence.daemon.routes.ui"

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
        with patch(f"{_SERVER_MODULE}.Path") as mock_path_cls:
            # First call: Path(sys.executable).exists() -> True (executable OK)
            exec_path = MagicMock()
            exec_path.exists.return_value = True

            # Second call: Path(__file__).parent / "static" / "index.html"
            # Path(__file__) -> mock with .parent that chains / "static" / "index.html"
            file_path = MagicMock()
            static_index = MagicMock()
            static_index.exists.return_value = False
            file_path.parent.__truediv__ = MagicMock(return_value=MagicMock())
            file_path.parent.__truediv__.return_value.__truediv__ = MagicMock(
                return_value=static_index
            )

            mock_path_cls.side_effect = [exec_path, file_path]
            assert _is_install_stale() is True


# =========================================================================
# _trigger_stale_restart() tests
# =========================================================================


class TestTriggerStaleRestart:
    """Test _trigger_stale_restart() helper."""

    @pytest.mark.anyio
    async def test_spawns_shell_subprocess(self, setup_state_with_project) -> None:
        """subprocess.Popen is called with /bin/sh and 'ci restart'."""
        with (
            patch(f"{_SERVER_MODULE}.subprocess.Popen") as mock_popen,
            patch(f"{_SERVER_MODULE}.os.kill") as mock_kill,
            patch(f"{_SERVER_MODULE}.asyncio.sleep", new_callable=AsyncMock),
        ):
            await _trigger_stale_restart()

        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "/bin/sh"
        assert args[1] == "-c"
        assert "ci restart" in args[2]
        mock_kill.assert_called_once()

    @pytest.mark.anyio
    async def test_noop_without_project_root(self) -> None:
        """Does nothing when state.project_root is None."""
        state = get_state()
        state.project_root = None

        with (
            patch(f"{_SERVER_MODULE}.subprocess.Popen") as mock_popen,
            patch(f"{_SERVER_MODULE}.os.kill") as mock_kill,
        ):
            await _trigger_stale_restart()

        mock_popen.assert_not_called()
        mock_kill.assert_not_called()


# =========================================================================
# _periodic_version_check() integration test
# =========================================================================


class TestPeriodicVersionCheck:
    """Test _periodic_version_check() calls restart on stale install."""

    @pytest.mark.anyio
    async def test_triggers_restart_on_stale(self) -> None:
        """Version check loop detects stale install and triggers restart."""
        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise asyncio.CancelledError

        with (
            patch(f"{_SERVER_MODULE}._is_install_stale", return_value=True),
            patch(
                f"{_SERVER_MODULE}._trigger_stale_restart", new_callable=AsyncMock
            ) as mock_restart,
            patch(f"{_SERVER_MODULE}._check_version"),
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            await _periodic_version_check()

        mock_restart.assert_called_once()

    @pytest.mark.anyio
    async def test_continues_when_not_stale(self) -> None:
        """Version check loop continues normally when install is healthy."""
        call_count = 0

        async def mock_sleep(seconds: float) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise asyncio.CancelledError

        with (
            patch(f"{_SERVER_MODULE}._is_install_stale", return_value=False),
            patch(
                f"{_SERVER_MODULE}._trigger_stale_restart", new_callable=AsyncMock
            ) as mock_restart,
            patch(f"{_SERVER_MODULE}._check_version"),
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(asyncio.CancelledError):
                await _periodic_version_check()

        mock_restart.assert_not_called()


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
        assert "Restart Required" in response.text
        assert "oak ci restart" in response.text

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
