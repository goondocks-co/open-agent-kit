"""Tests for cloudflared tunnel provider."""

from unittest.mock import MagicMock, patch

from open_agent_kit.features.codebase_intelligence.constants import (
    TUNNEL_ERROR_CLOUDFLARED_EXITED_UNEXPECTED,
)
from open_agent_kit.features.codebase_intelligence.tunnel.cloudflared import (
    CloudflaredProvider,
)

from .fixtures import (
    TEST_CLOUDFLARED_CUSTOM_PATH,
    TEST_CLOUDFLARED_LOG_LINES,
    TEST_CLOUDFLARED_MISSING_PATH,
    TEST_CLOUDFLARED_PATH,
    TEST_ERROR_NOT_FOUND,
    TEST_ERROR_PERMISSION_DENIED,
    TEST_PORT,
    TEST_PROVIDER_CLOUDFLARED,
    TEST_RETURN_CODE,
    TEST_STARTED_AT,
    TEST_TIMEOUT_SECONDS,
    TEST_URL_CLOUDFLARE,
    TEST_URL_CLOUDFLARE_ABC,
    TEST_URL_CLOUDFLARE_EXISTING,
)


class TestCloudflaredProvider:
    """Tests for CloudflaredProvider."""

    def test_name(self) -> None:
        """Provider name is 'cloudflared'."""
        provider = CloudflaredProvider()
        assert provider.name == TEST_PROVIDER_CLOUDFLARED

    @patch("shutil.which", return_value=TEST_CLOUDFLARED_PATH)
    def test_is_available_found(self, mock_which: MagicMock) -> None:
        """is_available returns True when binary is found."""
        provider = CloudflaredProvider()
        assert provider.is_available is True
        mock_which.assert_called_with(TEST_PROVIDER_CLOUDFLARED)

    @patch("shutil.which", return_value=None)
    def test_is_available_not_found(self, mock_which: MagicMock) -> None:
        """is_available returns False when binary is not found."""
        provider = CloudflaredProvider()
        assert provider.is_available is False

    @patch("shutil.which", return_value=TEST_CLOUDFLARED_CUSTOM_PATH)
    def test_is_available_custom_path(self, mock_which: MagicMock) -> None:
        """Custom binary path is checked."""
        provider = CloudflaredProvider(binary_path=TEST_CLOUDFLARED_CUSTOM_PATH)
        assert provider.is_available is True
        mock_which.assert_called_with(TEST_CLOUDFLARED_CUSTOM_PATH)

    @patch("shutil.which", return_value=None)
    def test_start_binary_not_available(self, mock_which: MagicMock) -> None:
        """start() returns error when binary not available."""
        provider = CloudflaredProvider()
        status = provider.start(TEST_PORT)
        assert status.active is False
        assert status.error is not None
        assert TEST_ERROR_NOT_FOUND in status.error

    @patch("shutil.which", return_value=TEST_CLOUDFLARED_PATH)
    def test_start_file_not_found(self, mock_which: MagicMock) -> None:
        """start() handles FileNotFoundError."""
        provider = CloudflaredProvider(binary_path=TEST_CLOUDFLARED_MISSING_PATH)
        with patch("subprocess.Popen", side_effect=FileNotFoundError(TEST_ERROR_NOT_FOUND)):
            status = provider.start(TEST_PORT)
        assert status.active is False
        assert TEST_ERROR_NOT_FOUND in (status.error or "")

    @patch("shutil.which", return_value=TEST_CLOUDFLARED_PATH)
    def test_start_os_error(self, mock_which: MagicMock) -> None:
        """start() handles OSError."""
        provider = CloudflaredProvider()
        with patch("subprocess.Popen", side_effect=OSError(TEST_ERROR_PERMISSION_DENIED)):
            status = provider.start(TEST_PORT)
        assert status.active is False
        assert TEST_ERROR_PERMISSION_DENIED in (status.error or "")

    @patch("shutil.which", return_value=TEST_CLOUDFLARED_PATH)
    def test_start_success_parses_url(self, mock_which: MagicMock) -> None:
        """start() parses URL from stderr output."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        # Simulate stderr output with the URL
        mock_process.stderr = iter(TEST_CLOUDFLARED_LOG_LINES)

        provider = CloudflaredProvider()
        with patch("subprocess.Popen", return_value=mock_process):
            status = provider.start(TEST_PORT)

        assert status.active is True
        assert status.public_url == TEST_URL_CLOUDFLARE_ABC
        assert status.provider_name == TEST_PROVIDER_CLOUDFLARED
        assert status.started_at is not None

    @patch("shutil.which", return_value=TEST_CLOUDFLARED_PATH)
    def test_start_timeout(self, mock_which: MagicMock) -> None:
        """start() handles timeout waiting for URL."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        # Stderr that never produces a URL (empty iterator)
        mock_process.stderr = iter([])

        provider = CloudflaredProvider()
        with patch("subprocess.Popen", return_value=mock_process):
            with patch(
                "open_agent_kit.features.codebase_intelligence.tunnel.cloudflared.TUNNEL_URL_PARSE_TIMEOUT_SECONDS",
                TEST_TIMEOUT_SECONDS,
            ):
                status = provider.start(TEST_PORT)

        assert status.active is False
        assert status.error is not None

    def test_stop_no_process(self) -> None:
        """stop() is a no-op when no process is running."""
        provider = CloudflaredProvider()
        provider.stop()  # Should not raise

    def test_get_status_no_process(self) -> None:
        """get_status() returns inactive when no process."""
        provider = CloudflaredProvider()
        status = provider.get_status()
        assert status.active is False
        assert status.public_url is None

    def test_get_status_with_running_process(self) -> None:
        """get_status() returns active when process is running."""
        provider = CloudflaredProvider()
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Still running
        provider._process = mock_process
        provider._public_url = TEST_URL_CLOUDFLARE
        provider._started_at = TEST_STARTED_AT

        status = provider.get_status()
        assert status.active is True
        assert status.public_url == TEST_URL_CLOUDFLARE

    def test_get_status_process_died(self) -> None:
        """get_status() detects dead process."""
        provider = CloudflaredProvider()
        mock_process = MagicMock()
        mock_process.poll.return_value = TEST_RETURN_CODE  # Exited
        mock_process.returncode = TEST_RETURN_CODE
        provider._process = mock_process
        provider._public_url = TEST_URL_CLOUDFLARE

        status = provider.get_status()
        assert status.active is False
        assert status.error == TUNNEL_ERROR_CLOUDFLARED_EXITED_UNEXPECTED.format(
            code=TEST_RETURN_CODE
        )

    def test_start_returns_existing_if_running(self) -> None:
        """start() returns existing status if tunnel already running."""
        provider = CloudflaredProvider()
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        provider._process = mock_process
        provider._public_url = TEST_URL_CLOUDFLARE_EXISTING

        status = provider.start(TEST_PORT)
        assert status.public_url == TEST_URL_CLOUDFLARE_EXISTING
