"""ACP interactive session routes for the CI daemon.

Provides API endpoints for creating, prompting, and managing interactive
ACP sessions that support multi-turn conversations via NDJSON streaming.

These routes delegate to the InteractiveSessionManager which manages
long-lived Claude SDK sessions.
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from open_agent_kit.features.acp_server.constants import ACP_ERROR_SESSION_NOT_FOUND
from open_agent_kit.features.team.daemon.state import get_state

if TYPE_CHECKING:
    from open_agent_kit.features.agent_runtime.interactive import (
        InteractiveSessionManager,
    )

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/acp/sessions", tags=["acp-sessions"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    """Request body for creating a new ACP session."""

    cwd: str | None = Field(
        default=None,
        description="Working directory for the session (defaults to project root)",
    )


class PromptRequest(BaseModel):
    """Request body for sending a prompt to a session."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="User message text",
    )


class SetModeRequest(BaseModel):
    """Request body for setting session permission mode."""

    mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"] = Field(
        ...,
        description="Permission mode for file operations",
    )


class SetFocusRequest(BaseModel):
    """Request body for setting session agent focus."""

    focus: str = Field(
        ...,
        min_length=1,
        description="Agent template name to focus on",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_manager() -> "InteractiveSessionManager":
    """Get the interactive session manager or raise HTTP 503."""
    state = get_state()
    manager = state.interactive_session_manager
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Interactive session manager not initialized. "
            "The Claude Agent SDK may not be installed.",
        )
    return manager


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("")
async def create_session(request: CreateSessionRequest) -> dict:
    """Create a new interactive ACP session.

    Returns:
        Dictionary with the new session_id.
    """
    manager = _get_session_manager()

    cwd = Path(request.cwd) if request.cwd else None
    result = manager.create_session(cwd=cwd)
    return result


@router.post("/{session_id}/prompt")
async def prompt_session(session_id: str, request: PromptRequest) -> StreamingResponse:
    """Send a prompt to a session and stream execution events as NDJSON.

    Each line in the response is a JSON-serialized ExecutionEvent.

    Args:
        session_id: Session identifier.
        request: Prompt request with text.

    Returns:
        NDJSON streaming response.
    """
    manager = _get_session_manager()

    async def _stream_events() -> AsyncIterator[str]:
        async for event in manager.prompt(session_id, request.text):
            yield event.model_dump_json() + "\n"

    return StreamingResponse(
        _stream_events(),
        media_type="application/x-ndjson",
    )


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: str) -> dict:
    """Cancel an in-progress prompt for a session.

    Args:
        session_id: Session identifier.

    Returns:
        Confirmation of cancellation.
    """
    manager = _get_session_manager()

    try:
        manager.cancel(session_id)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=ACP_ERROR_SESSION_NOT_FOUND.format(session_id=session_id)
        ) from None

    return {"success": True, "session_id": session_id}


@router.put("/{session_id}/mode")
async def set_session_mode(session_id: str, request: SetModeRequest) -> dict:
    """Set the permission mode for a session.

    Args:
        session_id: Session identifier.
        request: Mode request.

    Returns:
        Confirmation with new mode.
    """
    manager = _get_session_manager()

    try:
        manager.set_mode(session_id, request.mode)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=ACP_ERROR_SESSION_NOT_FOUND.format(session_id=session_id)
        ) from None

    return {"success": True, "session_id": session_id, "mode": request.mode}


@router.put("/{session_id}/focus")
async def set_session_focus(session_id: str, request: SetFocusRequest) -> dict:
    """Set the agent focus for a session.

    Switches the agent template used for subsequent prompts. Conversation
    history is preserved across focus changes.

    Args:
        session_id: Session identifier.
        request: Focus request.

    Returns:
        Confirmation with new focus.
    """
    manager = _get_session_manager()

    try:
        manager.set_focus(session_id, request.focus)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=ACP_ERROR_SESSION_NOT_FOUND.format(session_id=session_id)
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    return {"success": True, "session_id": session_id, "focus": request.focus}


@router.post("/{session_id}/approve-plan")
async def approve_plan(session_id: str) -> StreamingResponse:
    """Approve a pending plan and stream execution events as NDJSON.

    Args:
        session_id: Session identifier with a pending plan.

    Returns:
        NDJSON streaming response.
    """
    manager = _get_session_manager()

    async def _stream_events() -> AsyncIterator[str]:
        async for event in manager.approve_plan(session_id):
            yield event.model_dump_json() + "\n"

    return StreamingResponse(
        _stream_events(),
        media_type="application/x-ndjson",
    )


@router.delete("/{session_id}")
async def close_session(session_id: str) -> dict:
    """Close a session and release resources.

    Args:
        session_id: Session identifier.

    Returns:
        Confirmation of closure.
    """
    manager = _get_session_manager()
    await manager.close_session(session_id)
    return {"success": True, "session_id": session_id}
