"""Tests for POST /api/self-restart route.

Tests cover:
- Returns restarting status
- Spawns subprocess
- Uses configured cli_command
- Uses default cli_command when not set
- Passes project_root as cwd
- Schedules SIGTERM shutdown
- Error when no project_root
- Uses detach kwargs
"""

from pathlib import Path
from unittest.mock import patch

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


@pytest.fixture(autouse=True)
def mock_subprocess():
    """Mock subprocess.Popen to prevent spawning real processes."""
    with patch(f"{_RESTART_MODULE}.subprocess.Popen") as mock_popen:
        yield mock_popen


@pytest.fixture(autouse=True)
def mock_os_kill():
    """Mock os.kill to prevent sending real signals."""
    with patch(f"{_RESTART_MODULE}.os.kill") as mock_kill:
        yield mock_kill


@pytest.fixture(autouse=True)
def mock_asyncio_create_task():
    """Mock asyncio.create_task to prevent scheduling real tasks."""
    with patch(f"{_RESTART_MODULE}.asyncio.create_task") as mock_task:
        yield mock_task


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
        response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == CI_RESTART_STATUS_RESTARTING

    def test_spawns_subprocess(self, client, setup_state_with_project, mock_subprocess) -> None:
        """subprocess.Popen is called to spawn the restarter."""
        response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        mock_subprocess.assert_called_once()

    def test_uses_configured_cli_command(
        self, client, setup_state_with_project, mock_subprocess
    ) -> None:
        """When cli_command is configured, uses that command in subprocess."""
        custom_command = "oak-dev"
        with patch(
            f"{_RESTART_MODULE}.resolve_ci_cli_command",
            return_value=custom_command,
        ):
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        # The custom command should appear in the Popen args (restarter code)
        call_args = mock_subprocess.call_args
        popen_args = call_args[0][0]  # First positional arg is the command list
        restarter_code = popen_args[2]  # Third element is the -c code string
        assert custom_command in restarter_code

    def test_uses_default_cli_command_when_not_set(
        self, client, setup_state_with_project, mock_subprocess
    ) -> None:
        """When no cli_command configured, uses default 'oak' command."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_CLI_COMMAND_DEFAULT,
        )

        with patch(
            f"{_RESTART_MODULE}.resolve_ci_cli_command",
            return_value=CI_CLI_COMMAND_DEFAULT,
        ):
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        call_args = mock_subprocess.call_args
        popen_args = call_args[0][0]
        restarter_code = popen_args[2]
        assert CI_CLI_COMMAND_DEFAULT in restarter_code

    def test_passes_project_root_as_cwd(
        self, client, setup_state_with_project, mock_subprocess, tmp_path: Path
    ) -> None:
        """Popen cwd is set to project_root."""
        response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        call_kwargs = mock_subprocess.call_args[1]  # keyword args
        assert call_kwargs["cwd"] == str(tmp_path)

    def test_schedules_sigterm(
        self, client, setup_state_with_project, mock_asyncio_create_task
    ) -> None:
        """asyncio.create_task is called to schedule delayed shutdown."""
        response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        mock_asyncio_create_task.assert_called_once()
        # Verify the task name
        call_kwargs = mock_asyncio_create_task.call_args[1]
        assert call_kwargs.get("name") == "self_restart_shutdown"

    def test_error_when_no_project_root(self, client) -> None:
        """Returns error when state.project_root is None."""
        state = get_state()
        state.project_root = None

        response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 500
        data = response.json()
        assert CI_RESTART_ERROR_NO_PROJECT_ROOT in data["detail"]

    def test_uses_detach_kwargs(self, client, setup_state_with_project, mock_subprocess) -> None:
        """get_process_detach_kwargs() result is passed to Popen."""
        detach_kwargs = {"start_new_session": True}
        with patch(
            f"{_RESTART_MODULE}.get_process_detach_kwargs",
            return_value=detach_kwargs,
        ):
            response = client.post(CI_RESTART_API_PATH)

        assert response.status_code == 200
        call_kwargs = mock_subprocess.call_args[1]
        assert call_kwargs.get("start_new_session") is True
