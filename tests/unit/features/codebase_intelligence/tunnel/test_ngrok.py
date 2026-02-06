"""Tests for ngrok tunnel provider (CLI-based)."""

import json
from unittest.mock import MagicMock, patch

from open_agent_kit.features.codebase_intelligence.constants import (
    NGROK_LOG_KEY_MSG,
    NGROK_LOG_KEY_URL,
    NGROK_LOG_MSG_STARTED,
    TUNNEL_ERROR_NGROK_EXITED,
    TUNNEL_ERROR_NGROK_EXITED_UNEXPECTED,
)
from open_agent_kit.features.codebase_intelligence.tunnel.ngrok_provider import (
    NgrokProvider,
)

from .fixtures import (
    TEST_ERROR_NOT_FOUND,
    TEST_ERROR_PERMISSION_DENIED,
    TEST_NGROK_ADDR_KEY,
    TEST_NGROK_ADDR_VALUE,
    TEST_NGROK_CUSTOM_PATH,
    TEST_NGROK_INVALID_LINE,
    TEST_NGROK_MISSING_PATH,
    TEST_NGROK_PATH,
    TEST_NGROK_START_LINE,
    TEST_PORT,
    TEST_PROVIDER_NGROK,
    TEST_RETURN_CODE,
    TEST_STARTED_AT,
    TEST_TIMEOUT_SECONDS,
    TEST_URL_NGROK,
    TEST_URL_NGROK_ABC,
    TEST_URL_NGROK_EXISTING,
    TEST_URL_NGROK_TEST,
)


class TestNgrokProvider:
    """Tests for NgrokProvider."""

    def test_name(self) -> None:
        """Provider name is 'ngrok'."""
        provider = NgrokProvider()
        assert provider.name == TEST_PROVIDER_NGROK

    @patch("shutil.which", return_value=TEST_NGROK_PATH)
    def test_is_available_found(self, mock_which: MagicMock) -> None:
        """is_available returns True when binary is found."""
        provider = NgrokProvider()
        assert provider.is_available is True
        mock_which.assert_called_with(TEST_PROVIDER_NGROK)

    @patch("shutil.which", return_value=None)
    def test_is_available_not_found(self, mock_which: MagicMock) -> None:
        """is_available returns False when binary is not found."""
        provider = NgrokProvider()
        assert provider.is_available is False

    @patch("shutil.which", return_value=TEST_NGROK_CUSTOM_PATH)
    def test_is_available_custom_path(self, mock_which: MagicMock) -> None:
        """Custom binary path is checked."""
        provider = NgrokProvider(binary_path=TEST_NGROK_CUSTOM_PATH)
        assert provider.is_available is True
        mock_which.assert_called_with(TEST_NGROK_CUSTOM_PATH)

    @patch("shutil.which", return_value=None)
    def test_start_binary_not_available(self, mock_which: MagicMock) -> None:
        """start() returns error when binary not available."""
        provider = NgrokProvider()
        status = provider.start(TEST_PORT)
        assert status.active is False
        assert status.error is not None
        assert TEST_ERROR_NOT_FOUND in status.error

    @patch("shutil.which", return_value=TEST_NGROK_PATH)
    def test_start_file_not_found(self, mock_which: MagicMock) -> None:
        """start() handles FileNotFoundError."""
        provider = NgrokProvider(binary_path=TEST_NGROK_MISSING_PATH)
        with patch("subprocess.Popen", side_effect=FileNotFoundError(TEST_ERROR_NOT_FOUND)):
            status = provider.start(TEST_PORT)
        assert status.active is False
        assert TEST_ERROR_NOT_FOUND in (status.error or "")

    @patch("shutil.which", return_value=TEST_NGROK_PATH)
    def test_start_os_error(self, mock_which: MagicMock) -> None:
        """start() handles OSError."""
        provider = NgrokProvider()
        with patch("subprocess.Popen", side_effect=OSError(TEST_ERROR_PERMISSION_DENIED)):
            status = provider.start(TEST_PORT)
        assert status.active is False
        assert TEST_ERROR_PERMISSION_DENIED in (status.error or "")

    @patch("shutil.which", return_value=TEST_NGROK_PATH)
    def test_start_success_parses_url(self, mock_which: MagicMock) -> None:
        """start() parses URL from JSON log output."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        # Simulate JSON log output with the tunnel URL
        log_line = json.dumps(
            {
                NGROK_LOG_KEY_MSG: NGROK_LOG_MSG_STARTED,
                NGROK_LOG_KEY_URL: TEST_URL_NGROK_ABC,
                TEST_NGROK_ADDR_KEY: TEST_NGROK_ADDR_VALUE,
            }
        )
        stdout_lines = [
            TEST_NGROK_START_LINE,
            (log_line + "\n").encode("utf-8"),
        ]
        mock_process.stdout = iter(stdout_lines)

        provider = NgrokProvider()
        with patch("subprocess.Popen", return_value=mock_process):
            status = provider.start(TEST_PORT)

        assert status.active is True
        assert status.public_url == TEST_URL_NGROK_ABC
        assert status.provider_name == TEST_PROVIDER_NGROK
        assert status.started_at is not None

    @patch("shutil.which", return_value=TEST_NGROK_PATH)
    def test_start_timeout(self, mock_which: MagicMock) -> None:
        """start() handles timeout waiting for URL."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        # Stdout that never produces a URL (empty iterator)
        mock_process.stdout = iter([])

        provider = NgrokProvider()
        with patch("subprocess.Popen", return_value=mock_process):
            with patch(
                "open_agent_kit.features.codebase_intelligence.tunnel.ngrok_provider.TUNNEL_URL_PARSE_TIMEOUT_SECONDS",
                TEST_TIMEOUT_SECONDS,
            ):
                status = provider.start(TEST_PORT)

        assert status.active is False
        assert status.error is not None

    def test_stop_no_process(self) -> None:
        """stop() is a no-op when no process is running."""
        provider = NgrokProvider()
        provider.stop()  # Should not raise

    def test_get_status_no_process(self) -> None:
        """get_status() returns inactive when no process."""
        provider = NgrokProvider()
        status = provider.get_status()
        assert status.active is False
        assert status.public_url is None

    def test_get_status_with_running_process(self) -> None:
        """get_status() returns active when process is running."""
        provider = NgrokProvider()
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Still running
        provider._process = mock_process
        provider._public_url = TEST_URL_NGROK
        provider._started_at = TEST_STARTED_AT

        status = provider.get_status()
        assert status.active is True
        assert status.public_url == TEST_URL_NGROK

    def test_get_status_process_died(self) -> None:
        """get_status() detects dead process."""
        provider = NgrokProvider()
        mock_process = MagicMock()
        mock_process.poll.return_value = TEST_RETURN_CODE  # Exited
        mock_process.returncode = TEST_RETURN_CODE
        provider._process = mock_process
        provider._public_url = TEST_URL_NGROK

        status = provider.get_status()
        assert status.active is False
        assert status.error == TUNNEL_ERROR_NGROK_EXITED_UNEXPECTED.format(code=TEST_RETURN_CODE)

    def test_start_returns_existing_if_running(self) -> None:
        """start() returns existing status if tunnel already running."""
        provider = NgrokProvider()
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        provider._process = mock_process
        provider._public_url = TEST_URL_NGROK_EXISTING

        status = provider.start(TEST_PORT)
        assert status.public_url == TEST_URL_NGROK_EXISTING

    @patch("shutil.which", return_value=TEST_NGROK_PATH)
    def test_start_ignores_non_json_lines(self, mock_which: MagicMock) -> None:
        """start() gracefully handles non-JSON output lines."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        log_line = json.dumps(
            {
                NGROK_LOG_KEY_MSG: NGROK_LOG_MSG_STARTED,
                NGROK_LOG_KEY_URL: TEST_URL_NGROK_TEST,
            }
        )
        stdout_lines = [
            TEST_NGROK_INVALID_LINE,
            b"",
            (log_line + "\n").encode("utf-8"),
        ]
        mock_process.stdout = iter(stdout_lines)

        provider = NgrokProvider()
        with patch("subprocess.Popen", return_value=mock_process):
            status = provider.start(TEST_PORT)

        assert status.active is True
        assert status.public_url == TEST_URL_NGROK_TEST

    @patch("shutil.which", return_value=TEST_NGROK_PATH)
    def test_start_process_died_early(self, mock_which: MagicMock) -> None:
        """start() reports error when ngrok process exits before producing URL."""
        mock_process = MagicMock()
        mock_process.poll.return_value = TEST_RETURN_CODE  # Already exited
        mock_process.returncode = TEST_RETURN_CODE
        mock_process.stdout = iter([])

        provider = NgrokProvider()
        with patch("subprocess.Popen", return_value=mock_process):
            with patch(
                "open_agent_kit.features.codebase_intelligence.tunnel.ngrok_provider.TUNNEL_URL_PARSE_TIMEOUT_SECONDS",
                TEST_TIMEOUT_SECONDS,
            ):
                status = provider.start(TEST_PORT)

        assert status.active is False
        assert status.error == TUNNEL_ERROR_NGROK_EXITED.format(code=TEST_RETURN_CODE)
