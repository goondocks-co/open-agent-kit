"""HTTP client for communicating with the OAK daemon.

Handles session lifecycle, prompt streaming, and plan approval
via the daemon's ACP session API.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from open_agent_kit.features.acp_server.constants import (
    ACP_DAEMON_APPROVE_PLAN_ENDPOINT,
    ACP_DAEMON_CANCEL_ENDPOINT,
    ACP_DAEMON_CLOSE_ENDPOINT,
    ACP_DAEMON_FOCUS_ENDPOINT,
    ACP_DAEMON_MODE_ENDPOINT,
    ACP_DAEMON_PORT_FILE,
    ACP_DAEMON_PORT_FILE_LOCAL,
    ACP_DAEMON_PROMPT_ENDPOINT,
    ACP_DAEMON_SESSION_ENDPOINT,
    ACP_ERROR_DAEMON_UNREACHABLE,
    ACP_LOG_DAEMON_CONNECTING,
    ACP_LOG_DAEMON_SESSION_CREATED,
)
from open_agent_kit.features.codebase_intelligence.constants import CI_AUTH_ENV_VAR
from open_agent_kit.features.codebase_intelligence.daemon.models_acp import (
    AnyExecutionEvent,
    parse_execution_event,
)

logger = logging.getLogger(__name__)


def discover_daemon(project_root: Path) -> tuple[str, str]:
    """Discover daemon URL and auth token.

    Reads port from the local override (.oak/ci/daemon.port) first,
    then falls back to the team-shared file (oak/daemon.port).
    Auth token is read from the OAK_CI_TOKEN environment variable.

    Args:
        project_root: Root directory of the OAK project.

    Returns:
        Tuple of (base_url, auth_token).

    Raises:
        RuntimeError: If daemon port file is not found.
    """
    port: int | None = None

    # Priority: local override first, then team-shared
    for rel_path in (ACP_DAEMON_PORT_FILE_LOCAL, ACP_DAEMON_PORT_FILE):
        port_file = project_root / rel_path
        if port_file.exists():
            try:
                port = int(port_file.read_text().strip())
                break
            except (ValueError, OSError):
                continue

    if port is None:
        raise RuntimeError(ACP_ERROR_DAEMON_UNREACHABLE)

    base_url = f"http://127.0.0.1:{port}"
    auth_token = os.environ.get(CI_AUTH_ENV_VAR, "")

    # Also try reading from the token file if env var is not set
    if not auth_token:
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_DATA_DIR,
            CI_TOKEN_FILE,
        )

        token_file = project_root / ".oak" / CI_DATA_DIR / CI_TOKEN_FILE
        if token_file.exists():
            try:
                auth_token = token_file.read_text().strip()
            except OSError:
                logger.debug("Could not read daemon token file: %s", token_file)

    logger.info(ACP_LOG_DAEMON_CONNECTING.format(url=base_url))
    return base_url, auth_token


class DaemonClient:
    """HTTP client for communicating with the OAK daemon.

    Handles session lifecycle, prompt streaming, and plan approval
    via the daemon's ACP session API.
    """

    def __init__(self, base_url: str, auth_token: str) -> None:
        self._base_url = base_url
        self._auth_token = auth_token

    def _headers(self) -> dict[str, str]:
        """Build request headers with optional auth."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    async def create_session(self, cwd: str) -> str:
        """Create a new daemon session.

        Args:
            cwd: Working directory for the session.

        Returns:
            The session_id assigned by the daemon.

        Raises:
            httpx.HTTPStatusError: If the daemon rejects the request.
        """
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.post(
                ACP_DAEMON_SESSION_ENDPOINT,
                headers=self._headers(),
                json={"cwd": cwd},
            )
            response.raise_for_status()
            data = response.json()
            session_id: str = data["session_id"]
            logger.info(ACP_LOG_DAEMON_SESSION_CREATED.format(session_id=session_id))
            return session_id

    async def prompt(self, session_id: str, text: str) -> AsyncIterator[AnyExecutionEvent]:
        """Stream prompt execution events from the daemon.

        Sends the prompt text and reads back NDJSON events line by line.

        Args:
            session_id: Active daemon session ID.
            text: User prompt text.

        Yields:
            Parsed ExecutionEvent instances.
        """
        url = ACP_DAEMON_PROMPT_ENDPOINT.format(session_id=session_id)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=None) as client:
            async with client.stream(
                "POST",
                url,
                headers=self._headers(),
                json={"text": text},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        yield parse_execution_event(data)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning("Skipping unparseable NDJSON line: %s", line[:200])

    async def cancel(self, session_id: str) -> None:
        """Cancel an in-progress prompt.

        Args:
            session_id: Active daemon session ID.
        """
        url = ACP_DAEMON_CANCEL_ENDPOINT.format(session_id=session_id)
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.post(url, headers=self._headers())
            response.raise_for_status()

    async def set_mode(self, session_id: str, mode: str) -> None:
        """Set the session mode (permission mode) on the daemon.

        Args:
            session_id: Active daemon session ID.
            mode: Permission mode identifier.
        """
        url = ACP_DAEMON_MODE_ENDPOINT.format(session_id=session_id)
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.put(
                url,
                headers=self._headers(),
                json={"mode": mode},
            )
            response.raise_for_status()

    async def set_focus(self, session_id: str, focus: str) -> None:
        """Set the session's agent focus on the daemon.

        Args:
            session_id: Active daemon session ID.
            focus: Agent template name to focus on.
        """
        url = ACP_DAEMON_FOCUS_ENDPOINT.format(session_id=session_id)
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.put(
                url,
                headers=self._headers(),
                json={"focus": focus},
            )
            response.raise_for_status()

    async def approve_plan(self, session_id: str) -> AsyncIterator[AnyExecutionEvent]:
        """Approve a pending plan and stream execution events.

        Args:
            session_id: Active daemon session ID.

        Yields:
            Parsed ExecutionEvent instances from plan execution.
        """
        url = ACP_DAEMON_APPROVE_PLAN_ENDPOINT.format(session_id=session_id)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=None) as client:
            async with client.stream(
                "POST",
                url,
                headers=self._headers(),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        yield parse_execution_event(data)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning("Skipping unparseable NDJSON line: %s", line[:200])

    async def close_session(self, session_id: str) -> None:
        """Close and cleanup a daemon session.

        Args:
            session_id: Active daemon session ID.
        """
        url = ACP_DAEMON_CLOSE_ENDPOINT.format(session_id=session_id)
        async with httpx.AsyncClient(base_url=self._base_url) as client:
            response = await client.delete(url, headers=self._headers())
            response.raise_for_status()
