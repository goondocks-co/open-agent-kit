"""Cloudflared tunnel provider.

Uses Cloudflare's `cloudflared` CLI to create quick tunnels via trycloudflare.com.
No account or configuration required - just install cloudflared.
"""

import logging
import os
import re
import shutil
import signal
import subprocess
import threading
from datetime import UTC, datetime

from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUDFLARED_URL_PATTERN,
    TUNNEL_CLOUDFLARED_FLAG_URL,
    TUNNEL_CLOUDFLARED_SUBCOMMAND,
    TUNNEL_ENCODING_ERROR_REPLACE,
    TUNNEL_ENCODING_UTF8,
    TUNNEL_ERROR_CLOUDFLARED_BINARY_MISSING,
    TUNNEL_ERROR_CLOUDFLARED_BINARY_NOT_FOUND,
    TUNNEL_ERROR_CLOUDFLARED_EXITED,
    TUNNEL_ERROR_CLOUDFLARED_EXITED_UNEXPECTED,
    TUNNEL_ERROR_CLOUDFLARED_STOP,
    TUNNEL_ERROR_START_CLOUDFLARED,
    TUNNEL_ERROR_TIMEOUT_URL,
    TUNNEL_LOCALHOST_URL_TEMPLATE,
    TUNNEL_LOG_CLOUDFLARED_PREFIX,
    TUNNEL_LOG_START_CLOUDFLARED,
    TUNNEL_LOG_STOP_CLOUDFLARED,
    TUNNEL_LOG_STOP_CLOUDFLARED_DONE,
    TUNNEL_LOG_STOP_CLOUDFLARED_KILL,
    TUNNEL_LOG_TUNNEL_URL,
    TUNNEL_PROVIDER_CLOUDFLARED,
    TUNNEL_SHUTDOWN_TIMEOUT_SECONDS,
    TUNNEL_THREAD_CLOUDFLARED_STDERR,
    TUNNEL_URL_PARSE_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.tunnel.base import (
    TunnelProvider,
    TunnelStatus,
)
from open_agent_kit.utils.platform import IS_WINDOWS

logger = logging.getLogger(__name__)


class CloudflaredProvider(TunnelProvider):
    """Tunnel provider using cloudflared quick tunnels.

    Starts `cloudflared tunnel --url http://127.0.0.1:{port}` as a subprocess
    and parses the generated public URL from stderr output.

    Args:
        binary_path: Custom path to the cloudflared binary. If None, uses PATH.
    """

    def __init__(self, binary_path: str | None = None) -> None:
        self._binary_path = binary_path
        self._process: subprocess.Popen | None = None  # type: ignore[type-arg]
        self._public_url: str | None = None
        self._started_at: str | None = None
        self._error: str | None = None
        self._stderr_thread: threading.Thread | None = None

    @property
    def name(self) -> str:
        return TUNNEL_PROVIDER_CLOUDFLARED

    @property
    def is_available(self) -> bool:
        """Check if cloudflared binary is available."""
        path = self._binary_path or TUNNEL_PROVIDER_CLOUDFLARED
        return shutil.which(path) is not None

    def _get_binary(self) -> str:
        """Get the cloudflared binary path."""
        return self._binary_path or TUNNEL_PROVIDER_CLOUDFLARED

    def start(self, local_port: int) -> TunnelStatus:
        """Start a cloudflared quick tunnel.

        Args:
            local_port: Local port the daemon is listening on.

        Returns:
            TunnelStatus with the public URL on success.
        """
        if self._process is not None and self._process.poll() is None:
            return self.get_status()

        if not self.is_available:
            self._error = TUNNEL_ERROR_CLOUDFLARED_BINARY_MISSING
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
            TUNNEL_CLOUDFLARED_SUBCOMMAND,
            TUNNEL_CLOUDFLARED_FLAG_URL,
            TUNNEL_LOCALHOST_URL_TEMPLATE.format(port=local_port),
        ]

        logger.info(TUNNEL_LOG_START_CLOUDFLARED.format(command=" ".join(cmd)))

        try:
            # Cross-platform subprocess creation
            kwargs: dict = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.PIPE,
            }
            # On POSIX, start in a new process group so we can signal cleanly
            if not IS_WINDOWS:
                kwargs["preexec_fn"] = os.setsid

            self._process = subprocess.Popen(cmd, **kwargs)  # noqa: S603

            # Read stderr in a background thread to find the URL
            def _read_stderr() -> None:
                assert self._process is not None
                assert self._process.stderr is not None
                url_pattern = re.compile(CLOUDFLARED_URL_PATTERN)
                for raw_line in self._process.stderr:
                    line = raw_line.decode(
                        TUNNEL_ENCODING_UTF8, errors=TUNNEL_ENCODING_ERROR_REPLACE
                    ).strip()
                    logger.debug(TUNNEL_LOG_CLOUDFLARED_PREFIX.format(line=line))
                    match = url_pattern.search(line)
                    if match and self._public_url is None:
                        self._public_url = match.group(0)
                        logger.info(TUNNEL_LOG_TUNNEL_URL.format(public_url=self._public_url))
                        url_ready.set()

            self._stderr_thread = threading.Thread(
                target=_read_stderr, daemon=True, name=TUNNEL_THREAD_CLOUDFLARED_STDERR
            )
            self._stderr_thread.start()

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
                    error = TUNNEL_ERROR_CLOUDFLARED_EXITED.format(code=self._process.returncode)
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
            self._error = TUNNEL_ERROR_CLOUDFLARED_BINARY_NOT_FOUND.format(path=self._get_binary())
            logger.error(self._error)
            return TunnelStatus(
                active=False,
                provider_name=self.name,
                error=self._error,
            )
        except OSError as e:
            self._error = TUNNEL_ERROR_START_CLOUDFLARED.format(error=e)
            logger.error(self._error)
            return TunnelStatus(
                active=False,
                provider_name=self.name,
                error=self._error,
            )

    def stop(self) -> None:
        """Stop the cloudflared tunnel."""
        if self._process is None:
            return

        logger.info(TUNNEL_LOG_STOP_CLOUDFLARED)

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
                    logger.warning(TUNNEL_LOG_STOP_CLOUDFLARED_KILL)
                    self._process.kill()
                    self._process.wait(timeout=TUNNEL_SHUTDOWN_TIMEOUT_SECONDS)
        except (OSError, ProcessLookupError) as e:
            logger.warning(TUNNEL_ERROR_CLOUDFLARED_STOP.format(error=e))
        finally:
            self._process = None
            self._public_url = None
            self._started_at = None
            self._error = None
            logger.info(TUNNEL_LOG_STOP_CLOUDFLARED_DONE)

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
            self._error = TUNNEL_ERROR_CLOUDFLARED_EXITED_UNEXPECTED.format(
                code=self._process.returncode
            )
            self._process = None
            self._public_url = None
            self._started_at = None

        return TunnelStatus(
            active=False,
            public_url=None,
            provider_name=self.name,
            error=self._error,
        )
