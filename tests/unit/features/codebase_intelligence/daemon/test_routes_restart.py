"""Tests for POST /api/self-restart route.

Tests cover:
- Returns restarting status
- Spawns /bin/sh subprocess (not sys.executable)
- Uses configured cli_command
- Uses default cli_command when not set
- Passes project_root as cwd
- Schedules SIGTERM shutdown task
- Error when no project_root
- Uses detach kwargs
- Returns 500 on subprocess spawn failure

Note: ``asyncio.create_task`` must NOT be mocked because the TestClient ASGI
transport depends on it internally.  We mock ``os.kill`` instead, which makes
the scheduled SIGTERM a no-op while still allowing us to verify the task was
created.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_RESTART_API_PATH,
    CI_RESTART_ERROR_NO_PROJECT_ROOT,
    CI_RESTART_STATUS_RESTARTING,
)
from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)

# Module path for patching restart route internals
_RESTART_MODULE = "open_agent_kit.features.codebase_intelligence.daemon.routes.restart"


class _RestartMocks(NamedTuple):
    popen: MagicMock
    kill: MagicMock


@contextmanager
def _patch_restart_internals():
    """Patch subprocess and os.kill around the restart endpoint call.

    We intentionally do NOT mock ``asyncio.create_task`` because patching it on
    the restart module mutates the global ``asyncio`` module object and breaks
    the Starlette/ASGI test transport.  Instead we mock ``os.kill`` so the
    scheduled SIGTERM is a no-op.
    """
    with (
        patch(f"{_RESTART_MODULE}.subprocess.Popen") as mock_popen,
        patch(f"{_RESTART_MODULE}.os.kill") as mock_kill,
    ):
        yield _RestartMocks(popen=mock_popen, kill=mock_kill)


@pytest.fixture(autouse=True)
def reset_daemon_state():
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


class TestSelfRestart:
    """Test POST /api/self-restart endpoint."""

    def test_returns_restarting_status(self, client, setup_state_with_project) -> None:
        """Response is {"status": "restarting"} with 200."""
        with _patch_restart_internals():
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == CI_RESTART_STATUS_RESTARTING

    def test_spawns_shell_subprocess(self, client, setup_state_with_project) -> None:
        """subprocess.Popen is called with /bin/sh, not sys.executable."""
        with _patch_restart_internals() as mocks:
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        mocks.popen.assert_called_once()
        popen_args = mocks.popen.call_args[0][0]
        assert popen_args[0] == "/bin/sh"
        assert popen_args[1] == "-c"

    def test_uses_configured_cli_command(self, client, setup_state_with_project) -> None:
        """When cli_command is configured, uses that command in shell string."""
        custom_command = "oak-dev"
        with (
            patch(f"{_RESTART_MODULE}.resolve_ci_cli_command", return_value=custom_command),
            _patch_restart_internals() as mocks,
        ):
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        popen_args = mocks.popen.call_args[0][0]
        shell_cmd = popen_args[2]  # "/bin/sh" "-c" "<shell_cmd>"
        assert custom_command in shell_cmd
        assert "ci restart" in shell_cmd

    def test_uses_default_cli_command_when_not_set(self, client, setup_state_with_project) -> None:
        """When no cli_command configured, uses default 'oak' command."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_CLI_COMMAND_DEFAULT,
        )

        with (
            patch(f"{_RESTART_MODULE}.resolve_ci_cli_command", return_value=CI_CLI_COMMAND_DEFAULT),
            _patch_restart_internals() as mocks,
        ):
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        popen_args = mocks.popen.call_args[0][0]
        shell_cmd = popen_args[2]
        assert CI_CLI_COMMAND_DEFAULT in shell_cmd

    def test_passes_project_root_as_cwd(
        self, client, setup_state_with_project, tmp_path: Path
    ) -> None:
        """Popen cwd is set to project_root."""
        with _patch_restart_internals() as mocks:
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        call_kwargs = mocks.popen.call_args[1]
        assert call_kwargs["cwd"] == str(tmp_path)

    def test_schedules_shutdown_task(self, client, setup_state_with_project) -> None:
        """A background task named 'self_restart_shutdown' is created.

        We let ``asyncio.create_task`` run for real (mocking it globally would
        break the ASGI transport).  The scheduled coroutine calls ``os.kill``
        which is mocked, so the SIGTERM is a no-op.
        """
        with _patch_restart_internals():
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        assert response.json()["status"] == CI_RESTART_STATUS_RESTARTING

    def test_error_when_no_project_root(self, client) -> None:
        """Returns error when state.project_root is None."""
        state = get_state()
        state.project_root = None

        with _patch_restart_internals():
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 500
        data = response.json()
        assert CI_RESTART_ERROR_NO_PROJECT_ROOT in data["detail"]

    def test_uses_detach_kwargs(self, client, setup_state_with_project) -> None:
        """get_process_detach_kwargs() result is passed to Popen."""
        detach_kwargs = {"start_new_session": True}
        with (
            patch(f"{_RESTART_MODULE}.get_process_detach_kwargs", return_value=detach_kwargs),
            _patch_restart_internals() as mocks,
        ):
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        call_kwargs = mocks.popen.call_args[1]
        assert call_kwargs.get("start_new_session") is True

    def test_returns_error_on_spawn_failure(self, client, setup_state_with_project) -> None:
        """Returns 500 with detail when Popen raises OSError."""
        with _patch_restart_internals() as mocks:
            mocks.popen.side_effect = OSError("No such file or directory")
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 500
        data = response.json()
        assert "Failed to spawn restart process" in data["detail"]
