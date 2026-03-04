"""ACP server CLI command.

Starts the OAK ACP agent over stdio so that editors can connect to it.
"""

import asyncio
import logging
import sys
import threading
from pathlib import Path
from typing import cast

import typer

from open_agent_kit.config.messages import ERROR_MESSAGES
from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.acp_server.constants import (
    ACP_LOG_FILE,
    ACP_LOG_SERVER_STARTING,
)
from open_agent_kit.utils import get_project_root, print_error

logger = logging.getLogger(__name__)

acp_app = typer.Typer(
    name="acp",
    help="Agent Client Protocol (ACP) server commands",
    no_args_is_help=True,
)

# Default to 50 MB to match the ACP SDK's default for multimodal payloads.
_STDIO_BUFFER_LIMIT_BYTES = 50 * 1024 * 1024


@acp_app.command("serve")
def serve() -> None:
    """Start the ACP agent server over stdio.

    Editors like Zed connect to this process via stdin/stdout using the
    Agent Client Protocol.  All logging is redirected to ``.oak/ci/acp.log``
    so it does not corrupt the JSON-RPC stream.

    Example:
        oak acp serve
    """
    project_root = get_project_root()
    if not project_root:
        print_error(ERROR_MESSAGES["no_oak_dir"])
        raise typer.Exit(code=1)

    # Redirect logging to a file so stdout stays clean for JSON-RPC
    _configure_file_logging(project_root)

    # Validate daemon is running before starting the ACP bridge
    from open_agent_kit.features.acp_server.constants import (
        ACP_DAEMON_PORT_FILE,
        ACP_DAEMON_PORT_FILE_LOCAL,
        ACP_ERROR_DAEMON_UNREACHABLE,
    )

    local_port = project_root / ACP_DAEMON_PORT_FILE_LOCAL
    shared_port = project_root / ACP_DAEMON_PORT_FILE
    if not local_port.exists() and not shared_port.exists():
        print_error(ACP_ERROR_DAEMON_UNREACHABLE)
        raise typer.Exit(code=1)

    logger.info(ACP_LOG_SERVER_STARTING)

    from acp import run_agent

    from open_agent_kit.features.acp_server.agent import OakAcpAgent

    agent = OakAcpAgent(project_root=project_root)

    try:
        asyncio.run(_run_agent_with_safe_stdio(run_agent, agent))
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("ACP server exited with error")
        raise typer.Exit(code=1) from None


async def _run_agent_with_safe_stdio(run_agent_fn, agent) -> None:  # type: ignore[no-untyped-def]
    """Start the agent with thread-based stdio to avoid kqueue issues on macOS.

    The ACP SDK's default POSIX transport uses ``loop.connect_read_pipe()``
    which relies on kqueue on macOS.  kqueue cannot monitor certain fd types
    (e.g. ``/dev/null``, or pipes that the selector rejects) and raises
    ``OSError: [Errno 22] Invalid argument``.

    This helper mirrors the SDK's own Windows workaround: a daemon thread
    reads stdin synchronously and feeds data into an ``asyncio.StreamReader``,
    while stdout writes go through a thin synchronous transport.
    """
    loop = asyncio.get_running_loop()

    # --- stdin reader (thread-fed) ---
    reader = asyncio.StreamReader(limit=_STDIO_BUFFER_LIMIT_BYTES)

    def _blocking_stdin_read() -> None:
        try:
            while True:
                data = sys.stdin.buffer.readline()
                if not data:
                    break
                loop.call_soon_threadsafe(reader.feed_data, data)
        except Exception:
            logger.exception("stdin reader thread error")
        finally:
            loop.call_soon_threadsafe(reader.feed_eof)

    threading.Thread(target=_blocking_stdin_read, daemon=True).start()

    # --- stdout writer (synchronous) ---
    write_protocol = _WritePipeProtocol()
    transport = _StdoutTransport()
    writer = asyncio.StreamWriter(
        cast(asyncio.transports.WriteTransport, transport),
        write_protocol,
        None,
        loop,
    )

    await run_agent_fn(agent, input_stream=writer, output_stream=reader)


class _WritePipeProtocol(asyncio.BaseProtocol):
    """Flow-control protocol for the stdout writer."""

    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._paused = False
        self._drain_waiter: asyncio.Future[None] | None = None

    def pause_writing(self) -> None:  # type: ignore[override]
        self._paused = True
        if self._drain_waiter is None:
            self._drain_waiter = self._loop.create_future()

    def resume_writing(self) -> None:  # type: ignore[override]
        self._paused = False
        if self._drain_waiter is not None and not self._drain_waiter.done():
            self._drain_waiter.set_result(None)
        self._drain_waiter = None

    async def _drain_helper(self) -> None:
        if self._paused and self._drain_waiter is not None:
            await self._drain_waiter


class _StdoutTransport(asyncio.BaseTransport):
    """Thin synchronous transport that writes directly to stdout."""

    def __init__(self) -> None:
        self._is_closing = False

    def write(self, data: bytes) -> None:  # type: ignore[override]
        if self._is_closing:
            return
        try:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        except Exception:
            logger.exception("Error writing to stdout")

    def can_write_eof(self) -> bool:  # type: ignore[override]
        return False

    def is_closing(self) -> bool:  # type: ignore[override]
        return self._is_closing

    def close(self) -> None:  # type: ignore[override]
        self._is_closing = True
        try:
            sys.stdout.flush()
        except Exception:
            pass

    def abort(self) -> None:  # type: ignore[override]
        self.close()

    def get_extra_info(self, name: str, default: object = None) -> object:  # type: ignore[override]
        return default


def _configure_file_logging(project_root: Path) -> None:
    """Route all log output to .oak/ci/acp.log (stdout is JSON-RPC)."""
    from open_agent_kit.features.team.constants import CI_DATA_DIR

    log_dir = project_root / OAK_DIR / CI_DATA_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / ACP_LOG_FILE

    # Remove all existing handlers and add a file handler
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)
