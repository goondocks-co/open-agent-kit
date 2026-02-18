"""Tests for cloud relay deploy module (wrangler subprocess automation).

All subprocess calls are mocked — no real npm/wrangler is invoked.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from open_agent_kit.features.codebase_intelligence.cloud_relay.deploy import (
    check_wrangler_auth,
    check_wrangler_available,
    run_npm_install,
    run_wrangler_deploy,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_DEPLOY_NPM_INSTALL_TIMEOUT,
    CLOUD_RELAY_DEPLOY_WRANGLER_TIMEOUT,
    CLOUD_RELAY_DEPLOY_WRANGLER_WHOAMI_TIMEOUT,
)

_PATCH_SUBPROCESS_RUN = (
    "open_agent_kit.features.codebase_intelligence.cloud_relay.deploy.subprocess.run"
)

FAKE_SCAFFOLD_DIR = Path("/tmp/fake-scaffold")

# Realistic wrangler whoami output (account table with Unicode box-drawing chars)
WRANGLER_WHOAMI_SUCCESS_OUTPUT = """\
 ⛅️ wrangler 3.99.0
--------------------

Getting User settings...
You are logged in with an API Token.

┌──────────────────┬──────────────────────────────────┐
│ Account Name     │ Account ID                       │
├──────────────────┼──────────────────────────────────┤
│ My CF Account    │ abcdef0123456789abcdef0123456789 │
└──────────────────┴──────────────────────────────────┘
"""

WRANGLER_WHOAMI_NOT_LOGGED_IN = """\
 ⛅️ wrangler 3.99.0
--------------------

You are not authenticated. Please run `wrangler login`.
"""

WRANGLER_DEPLOY_SUCCESS_OUTPUT = """\
 ⛅️ wrangler 3.99.0
--------------------

Total Upload: 12.34 KiB / gzip: 4.56 KiB
Worker Startup Time: 5 ms
Published oak-mcp-relay (1.2 sec)
  https://oak-mcp-relay.my-account.workers.dev
Current Version ID: abc-123
"""

WRANGLER_DEPLOY_NO_URL_OUTPUT = """\
 ⛅️ wrangler 3.99.0
--------------------

Total Upload: 12.34 KiB
Published oak-mcp-relay (1.2 sec)
Current Version ID: abc-123
"""


class TestCheckWranglerAvailable:
    """Tests for check_wrangler_available()."""

    def test_success(self) -> None:
        mock_result = MagicMock(returncode=0)
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result) as mock_run:
            assert check_wrangler_available(FAKE_SCAFFOLD_DIR) is True
            mock_run.assert_called_once_with(
                ["npx", "wrangler", "--version"],
                capture_output=True,
                text=True,
                cwd=None,  # FAKE_SCAFFOLD_DIR doesn't exist, falls back to None
                timeout=CLOUD_RELAY_DEPLOY_WRANGLER_WHOAMI_TIMEOUT,
            )

    def test_not_found(self) -> None:
        with patch(_PATCH_SUBPROCESS_RUN, side_effect=FileNotFoundError):
            assert check_wrangler_available(FAKE_SCAFFOLD_DIR) is False

    def test_nonzero_exit(self) -> None:
        mock_result = MagicMock(returncode=1)
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result):
            assert check_wrangler_available(FAKE_SCAFFOLD_DIR) is False

    def test_timeout(self) -> None:
        with patch(
            _PATCH_SUBPROCESS_RUN,
            side_effect=subprocess.TimeoutExpired(cmd="npx", timeout=15),
        ):
            assert check_wrangler_available(FAKE_SCAFFOLD_DIR) is False


class TestCheckWranglerAuth:
    """Tests for check_wrangler_auth()."""

    def test_success(self) -> None:
        mock_result = MagicMock(
            returncode=0,
            stdout=WRANGLER_WHOAMI_SUCCESS_OUTPUT,
            stderr="",
        )
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result):
            info = check_wrangler_auth(FAKE_SCAFFOLD_DIR)

        assert info is not None
        assert info.authenticated is True
        assert info.account_name == "My CF Account"
        assert info.account_id == "abcdef0123456789abcdef0123456789"

    def test_not_authenticated(self) -> None:
        mock_result = MagicMock(
            returncode=0,
            stdout=WRANGLER_WHOAMI_NOT_LOGGED_IN,
            stderr="",
        )
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result):
            info = check_wrangler_auth(FAKE_SCAFFOLD_DIR)

        assert info is not None
        assert info.authenticated is False
        assert info.account_name is None
        assert info.account_id is None

    def test_command_fails(self) -> None:
        mock_result = MagicMock(returncode=1, stdout="", stderr="error")
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result):
            info = check_wrangler_auth(FAKE_SCAFFOLD_DIR)

        assert info is not None
        assert info.authenticated is False

    def test_command_not_found(self) -> None:
        with patch(_PATCH_SUBPROCESS_RUN, side_effect=FileNotFoundError):
            assert check_wrangler_auth(FAKE_SCAFFOLD_DIR) is None

    def test_timeout(self) -> None:
        with patch(
            _PATCH_SUBPROCESS_RUN,
            side_effect=subprocess.TimeoutExpired(cmd="npx", timeout=15),
        ):
            assert check_wrangler_auth(FAKE_SCAFFOLD_DIR) is None


class TestRunNpmInstall:
    """Tests for run_npm_install()."""

    def test_success(self) -> None:
        mock_result = MagicMock(returncode=0, stdout="added 50 packages", stderr="")
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result) as mock_run:
            success, output = run_npm_install(FAKE_SCAFFOLD_DIR)

        assert success is True
        assert "added 50 packages" in output
        mock_run.assert_called_once_with(
            ["npm", "install"],
            capture_output=True,
            text=True,
            cwd=FAKE_SCAFFOLD_DIR,
            timeout=CLOUD_RELAY_DEPLOY_NPM_INSTALL_TIMEOUT,
        )

    def test_failure(self) -> None:
        mock_result = MagicMock(returncode=1, stdout="", stderr="ERR! code ENOENT")
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result):
            success, output = run_npm_install(FAKE_SCAFFOLD_DIR)

        assert success is False
        assert "ENOENT" in output

    def test_npm_not_found(self) -> None:
        with patch(_PATCH_SUBPROCESS_RUN, side_effect=FileNotFoundError):
            success, output = run_npm_install(FAKE_SCAFFOLD_DIR)

        assert success is False
        assert "npm not found" in output

    def test_timeout(self) -> None:
        with patch(
            _PATCH_SUBPROCESS_RUN,
            side_effect=subprocess.TimeoutExpired(cmd="npm", timeout=120),
        ):
            success, output = run_npm_install(FAKE_SCAFFOLD_DIR)

        assert success is False
        assert "timed out" in output


class TestRunWranglerDeploy:
    """Tests for run_wrangler_deploy()."""

    def test_success(self) -> None:
        mock_result = MagicMock(
            returncode=0,
            stdout=WRANGLER_DEPLOY_SUCCESS_OUTPUT,
            stderr="",
        )
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result) as mock_run:
            success, url, output = run_wrangler_deploy(FAKE_SCAFFOLD_DIR)

        assert success is True
        assert url == "https://oak-mcp-relay.my-account.workers.dev"
        assert "Published" in output
        mock_run.assert_called_once_with(
            ["npx", "wrangler", "deploy"],
            capture_output=True,
            text=True,
            cwd=FAKE_SCAFFOLD_DIR,
            timeout=CLOUD_RELAY_DEPLOY_WRANGLER_TIMEOUT,
        )

    def test_success_no_url_in_output(self) -> None:
        mock_result = MagicMock(
            returncode=0,
            stdout=WRANGLER_DEPLOY_NO_URL_OUTPUT,
            stderr="",
        )
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result):
            success, url, output = run_wrangler_deploy(FAKE_SCAFFOLD_DIR)

        assert success is True
        assert url is None

    def test_failure(self) -> None:
        mock_result = MagicMock(returncode=1, stdout="", stderr="Error: deploy failed")
        with patch(_PATCH_SUBPROCESS_RUN, return_value=mock_result):
            success, url, output = run_wrangler_deploy(FAKE_SCAFFOLD_DIR)

        assert success is False
        assert url is None
        assert "deploy failed" in output

    def test_not_found(self) -> None:
        with patch(_PATCH_SUBPROCESS_RUN, side_effect=FileNotFoundError):
            success, url, output = run_wrangler_deploy(FAKE_SCAFFOLD_DIR)

        assert success is False
        assert url is None
        assert "not found" in output

    def test_timeout(self) -> None:
        with patch(
            _PATCH_SUBPROCESS_RUN,
            side_effect=subprocess.TimeoutExpired(cmd="npx", timeout=60),
        ):
            success, url, output = run_wrangler_deploy(FAKE_SCAFFOLD_DIR)

        assert success is False
        assert url is None
        assert "timed out" in output
