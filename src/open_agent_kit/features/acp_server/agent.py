"""OAK ACP Agent implementation.

Implements the ACP Agent protocol as a thin bridge to the OAK daemon.
All session lifecycle, tool execution, and activity recording happen
in the daemon — this process only translates between ACP JSON-RPC
(over stdio) and daemon HTTP/NDJSON.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from acp import (
    PROTOCOL_VERSION,
    AuthenticateResponse,
    Client,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    text_block,
    update_agent_message,
)
from acp.schema import (
    ClientCapabilities,
    ForkSessionResponse,
    HttpMcpServer,
    Implementation,
    ListSessionsResponse,
    McpServerStdio,
    ResumeSessionResponse,
    SessionMode,
    SessionModeState,
    SetSessionConfigOptionResponse,
    SetSessionModelResponse,
    SetSessionModeResponse,
    SseMcpServer,
    TextContentBlock,
)

from open_agent_kit.features.acp_server.bridge import AcpBridge
from open_agent_kit.features.acp_server.constants import (
    ACP_AGENT_NAME,
    ACP_ERROR_DAEMON_PROMPT_FAILED,
    ACP_ERROR_DAEMON_SESSION_FAILED,
    ACP_LOG_PROMPT_RECEIVED,
    ACP_LOG_SESSION_CANCELLED,
    ACP_LOG_SESSION_CREATED,
    ACP_MODE_ACCEPT_EDITS,
    ACP_MODE_DEFAULT,
    ACP_MODE_PLAN,
    ACP_SESSION_MODE_ARCHITECT,
    ACP_SESSION_MODE_ASK,
    ACP_SESSION_MODE_CODE,
)
from open_agent_kit.features.acp_server.daemon_client import DaemonClient, discover_daemon
from open_agent_kit.features.codebase_intelligence.daemon.models_acp import (
    DoneEvent,
)

logger = logging.getLogger(__name__)

# Map editor-facing mode IDs to daemon permission modes
_MODE_MAP: dict[str, str] = {
    ACP_SESSION_MODE_CODE: ACP_MODE_ACCEPT_EDITS,
    ACP_SESSION_MODE_ARCHITECT: ACP_MODE_PLAN,
    ACP_SESSION_MODE_ASK: ACP_MODE_DEFAULT,
}


class OakAcpAgent:
    """ACP Agent that delegates all execution to the OAK daemon.

    This is a thin protocol bridge: the ACP stdio process translates
    between ACP JSON-RPC and daemon HTTP/NDJSON.  All session lifecycle,
    tool execution, and activity recording happen in the daemon.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._conn: Client | None = None
        self._daemon_client: DaemonClient | None = None
        # Track pending plan approvals per session
        self._pending_plans: dict[str, bool] = {}

    def _ensure_daemon_client(self) -> DaemonClient:
        """Lazily create daemon client."""
        if self._daemon_client is None:
            base_url, auth_token = discover_daemon(self._project_root)
            self._daemon_client = DaemonClient(base_url, auth_token)
        return self._daemon_client

    # -- ACP lifecycle --------------------------------------------------------

    def on_connect(self, conn: Client) -> None:  # noqa: D401
        """Called by the ACP transport when a client connects."""
        self._conn = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        """Return agent capabilities to the client."""
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_info=Implementation(name=ACP_AGENT_NAME, version="0.3.0"),
        )

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new interactive session via the daemon."""
        session_cwd = cwd if cwd else str(self._project_root)

        try:
            client = self._ensure_daemon_client()
            session_id = await client.create_session(session_cwd)
        except Exception as exc:
            logger.error(ACP_ERROR_DAEMON_SESSION_FAILED.format(error=exc))
            # Fall back to a local-only session ID so the client gets a response
            session_id = str(uuid4())

        logger.info(ACP_LOG_SESSION_CREATED.format(session_id=session_id, cwd=session_cwd))

        modes = SessionModeState(
            available_modes=[
                SessionMode(
                    id=ACP_SESSION_MODE_CODE,
                    name="Code",
                    description="Full tool access, auto-accept edits",
                ),
                SessionMode(
                    id=ACP_SESSION_MODE_ARCHITECT,
                    name="Architect",
                    description="Plan changes before executing",
                ),
                SessionMode(
                    id=ACP_SESSION_MODE_ASK,
                    name="Ask",
                    description="Ask permission for each action",
                ),
            ],
            current_mode_id=ACP_SESSION_MODE_CODE,
        )
        return NewSessionResponse(session_id=session_id, modes=modes)

    async def prompt(
        self,
        prompt: list[Any],
        session_id: str,
        **kwargs: Any,
    ) -> PromptResponse:
        """Handle a user prompt by delegating to the daemon."""
        logger.info(ACP_LOG_PROMPT_RECEIVED.format(session_id=session_id))

        # Extract text from prompt content blocks
        user_text_parts: list[str] = []
        for block in prompt:
            if isinstance(block, TextContentBlock):
                user_text_parts.append(block.text)
            elif isinstance(block, dict) and block.get("type") == "text":
                user_text_parts.append(block.get("text", ""))
        user_text = "\n".join(user_text_parts)

        try:
            client = self._ensure_daemon_client()

            # If there is a pending plan approval, approve it instead of sending text
            if self._pending_plans.pop(session_id, False):
                event_stream = client.approve_plan(session_id)
            else:
                event_stream = client.prompt(session_id, user_text)

            async for event in event_stream:
                updates = AcpBridge.map_event(event)
                if self._conn is not None:
                    for update in updates:
                        await self._conn.session_update(
                            session_id=session_id,
                            update=update,
                        )
                # Track if the daemon signals a pending plan approval
                if isinstance(event, DoneEvent) and event.needs_plan_approval:
                    self._pending_plans[session_id] = True

        except Exception as exc:
            error_msg = ACP_ERROR_DAEMON_PROMPT_FAILED.format(error=exc)
            logger.exception(error_msg)
            if self._conn is not None:
                await self._conn.session_update(
                    session_id=session_id,
                    update=update_agent_message(text_block(error_msg)),
                )

        return PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        """Cancel an in-progress prompt for the given session."""
        logger.info(ACP_LOG_SESSION_CANCELLED.format(session_id=session_id))
        try:
            client = self._ensure_daemon_client()
            await client.cancel(session_id)
        except Exception:
            logger.exception("Failed to cancel session %s on daemon", session_id)

    async def set_session_mode(
        self, mode_id: str, session_id: str, **kwargs: Any
    ) -> SetSessionModeResponse | None:
        """Set session mode by mapping editor mode to daemon permission mode."""
        daemon_mode = _MODE_MAP.get(mode_id)
        if daemon_mode is None:
            logger.warning("Unknown mode_id: %s", mode_id)
            return None

        try:
            client = self._ensure_daemon_client()
            await client.set_mode(session_id, daemon_mode)
        except Exception:
            logger.exception("Failed to set mode %s for session %s", mode_id, session_id)
        return None

    # -- Stubs for required Agent protocol methods ----------------------------

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Not yet implemented."""
        return None

    async def list_sessions(
        self,
        cursor: str | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> ListSessionsResponse:
        """Not yet implemented."""
        return ListSessionsResponse(sessions=[])

    async def set_session_model(
        self, model_id: str, session_id: str, **kwargs: Any
    ) -> SetSessionModelResponse | None:
        """Not yet implemented."""
        return None

    async def set_config_option(
        self, config_id: str, session_id: str, value: str, **kwargs: Any
    ) -> SetSessionConfigOptionResponse | None:
        """Not yet implemented."""
        return None

    async def authenticate(self, method_id: str, **kwargs: Any) -> AuthenticateResponse | None:
        """Not yet implemented."""
        return None

    async def fork_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> ForkSessionResponse:
        """Not yet implemented."""
        new_id = str(uuid4())
        return ForkSessionResponse(session_id=new_id)

    async def resume_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> ResumeSessionResponse:
        """Not yet implemented."""
        return ResumeSessionResponse()

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handle unknown extension methods."""
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Handle unknown extension notifications."""
        return None
