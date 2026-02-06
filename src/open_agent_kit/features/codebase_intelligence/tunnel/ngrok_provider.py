"""ngrok tunnel provider.

Uses the ngrok CLI to create tunnels via the ngrok service.
Requires the ngrok binary to be installed and configured (auth token set via
``ngrok config add-authtoken``).
"""

import json
import logging
import os
import shutil
import signal
import subprocess
import threading
from datetime import UTC, datetime

from open_agent_kit.features.codebase_intelligence.constants import (
    NGROK_LOG_KEY_MSG,
    NGROK_LOG_KEY_URL,
    NGROK_LOG_MSG_STARTED,
    TUNNEL_ENCODING_ERROR_REPLACE,
    TUNNEL_ENCODING_UTF8,
    TUNNEL_ERROR_NGROK_BINARY_MISSING,
    TUNNEL_ERROR_NGROK_BINARY_NOT_FOUND,
    TUNNEL_ERROR_NGROK_EXITED,
    TUNNEL_ERROR_NGROK_EXITED_UNEXPECTED,
    TUNNEL_ERROR_NGROK_STOP,
    TUNNEL_ERROR_START_NGROK,
    TUNNEL_ERROR_TIMEOUT_URL,
    TUNNEL_LOG_NGROK_PREFIX,
    TUNNEL_LOG_START_NGROK,
    TUNNEL_LOG_STOP_NGROK,
    TUNNEL_LOG_STOP_NGROK_DONE,
    TUNNEL_LOG_STOP_NGROK_KILL,
    TUNNEL_LOG_TUNNEL_URL,
    TUNNEL_NGROK_FLAG_LOG,
    TUNNEL_NGROK_FLAG_LOG_FORMAT,
    TUNNEL_NGROK_LOG_FORMAT_JSON,
    TUNNEL_NGROK_LOG_TARGET_STDOUT,
    TUNNEL_NGROK_SUBCOMMAND_HTTP,
    TUNNEL_PROVIDER_NGROK,
    TUNNEL_SHUTDOWN_TIMEOUT_SECONDS,
    TUNNEL_THREAD_NGROK_STDOUT,
    TUNNEL_URL_PARSE_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.tunnel.base import (
    TunnelProvider,
    TunnelStatus,
)
from open_agent_kit.utils.platform import IS_WINDOWS

logger = logging.getLogger(__name__)


class NgrokProvider(TunnelProvider):
    """Tunnel provider using the ngrok CLI.

    Starts ``ngrok http <port> --log stdout --log-format json`` as a subprocess
    and parses the generated public URL from the JSON log output.

    Args:
        binary_path: Custom path to the ngrok binary. If None, uses PATH.
    """

    def __init__(self, binary_path: str | None = None) -> None:
        self._binary_path = binary_path
        self._process: subprocess.Popen | None = None  # type: ignore[type-arg]
        self._public_url: str | None = None
        self._started_at: str | None = None
        self._error: str | None = None
        self._stdout_thread: threading.Thread | None = None

    @property
    def name(self) -> str:
        return TUNNEL_PROVIDER_NGROK

    @property
    def is_available(self) -> bool:
        """Check if ngrok binary is available."""
        path = self._binary_path or TUNNEL_PROVIDER_NGROK
        return shutil.which(path) is not None

    def _get_binary(self) -> str:
        """Get the ngrok binary path."""
        return self._binary_path or TUNNEL_PROVIDER_NGROK

    def start(self, local_port: int) -> TunnelStatus:
        """Start an ngrok tunnel.

        Args:
            local_port: Local port the daemon is listening on.

        Returns:
            TunnelStatus with the public URL on success.
        """
        if self._process is not None and self._process.poll() is None:
            return self.get_status()

        if not self.is_available:
            self._error = TUNNEL_ERROR_NGROK_BINARY_MISSING
            return TunnelStatus(
                active=False,
                provider_name=self.name,
                error=self._error,
            )

        self._error = None
        self._public_url = None

        # Use an event to signal when the URL has been parsed
        url_ready = threading.Event()

        cmd = [
            self._get_binary(),
            TUNNEL_NGROK_SUBCOMMAND_HTTP,
            str(local_port),
            TUNNEL_NGROK_FLAG_LOG,
            TUNNEL_NGROK_LOG_TARGET_STDOUT,
            TUNNEL_NGROK_FLAG_LOG_FORMAT,
            TUNNEL_NGROK_LOG_FORMAT_JSON,
        ]

        logger.info(TUNNEL_LOG_START_NGROK.format(command=" ".join(cmd)))

        try:
            # Cross-platform subprocess creation
            kwargs: dict = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.DEVNULL,
            }
            # On POSIX, start in a new process group so we can signal cleanly
            if not IS_WINDOWS:
                kwargs["preexec_fn"] = os.setsid

            self._process = subprocess.Popen(cmd, **kwargs)  # noqa: S603

            # Read stdout in a background thread to find the URL from JSON logs
            def _read_stdout() -> None:
                assert self._process is not None
                assert self._process.stdout is not None
                for raw_line in self._process.stdout:
                    line = raw_line.decode(
                        TUNNEL_ENCODING_UTF8, errors=TUNNEL_ENCODING_ERROR_REPLACE
                    ).strip()
                    if not line:
                        continue
                    logger.debug(TUNNEL_LOG_NGROK_PREFIX.format(line=line))
                    try:
                        log_entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # ngrok emits {"msg":"started tunnel","url":"https://..."}
                    if (
                        log_entry.get(NGROK_LOG_KEY_MSG) == NGROK_LOG_MSG_STARTED
                        and NGROK_LOG_KEY_URL in log_entry
                        and self._public_url is None
                    ):
                        self._public_url = log_entry[NGROK_LOG_KEY_URL]
                        logger.info(TUNNEL_LOG_TUNNEL_URL.format(public_url=self._public_url))
                        url_ready.set()

            self._stdout_thread = threading.Thread(
                target=_read_stdout, daemon=True, name=TUNNEL_THREAD_NGROK_STDOUT
            )
            self._stdout_thread.start()

            # Wait for URL with timeout
            if url_ready.wait(timeout=TUNNEL_URL_PARSE_TIMEOUT_SECONDS):
                self._started_at = datetime.now(UTC).isoformat()
                return TunnelStatus(
                    active=True,
                    public_url=self._public_url,
                    provider_name=self.name,
                    started_at=self._started_at,
                )
            else:
                # Timeout - check if process died
                if self._process.poll() is not None:
                    error = TUNNEL_ERROR_NGROK_EXITED.format(code=self._process.returncode)
                else:
                    error = TUNNEL_ERROR_TIMEOUT_URL.format(
                        timeout=TUNNEL_URL_PARSE_TIMEOUT_SECONDS
                    )
                # Capture error before stop() clears instance state
                self.stop()
                return TunnelStatus(
                    active=False,
                    provider_name=self.name,
                    error=error,
                )

        except FileNotFoundError:
            self._error = TUNNEL_ERROR_NGROK_BINARY_NOT_FOUND.format(path=self._get_binary())
            logger.error(self._error)
            return TunnelStatus(
                active=False,
                provider_name=self.name,
                error=self._error,
            )
        except OSError as e:
            self._error = TUNNEL_ERROR_START_NGROK.format(error=e)
            logger.error(self._error)
            return TunnelStatus(
                active=False,
                provider_name=self.name,
                error=self._error,
            )

    def stop(self) -> None:
        """Stop the ngrok tunnel."""
        if self._process is None:
            return

        logger.info(TUNNEL_LOG_STOP_NGROK)

        try:
            if self._process.poll() is None:
                # Cross-platform termination
                if not IS_WINDOWS:
                    # Send SIGTERM to the process group
                    try:
                        os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):
                        self._process.terminate()
                else:
                    self._process.terminate()

                try:
                    self._process.wait(timeout=TUNNEL_SHUTDOWN_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    logger.warning(TUNNEL_LOG_STOP_NGROK_KILL)
                    self._process.kill()
                    self._process.wait(timeout=TUNNEL_SHUTDOWN_TIMEOUT_SECONDS)
        except (OSError, ProcessLookupError) as e:
            logger.warning(TUNNEL_ERROR_NGROK_STOP.format(error=e))
        finally:
            self._process = None
            self._public_url = None
            self._started_at = None
            self._error = None
            logger.info(TUNNEL_LOG_STOP_NGROK_DONE)

    def get_status(self) -> TunnelStatus:
        """Get current tunnel status."""
        if self._process is not None and self._process.poll() is None:
            return TunnelStatus(
                active=True,
                public_url=self._public_url,
                provider_name=self.name,
                started_at=self._started_at,
            )

        # Process died unexpectedly
        if self._process is not None:
            self._error = TUNNEL_ERROR_NGROK_EXITED_UNEXPECTED.format(code=self._process.returncode)
            self._process = None
            self._public_url = None
            self._started_at = None

        return TunnelStatus(
            active=False,
            public_url=None,
            provider_name=self.name,
            error=self._error,
        )
