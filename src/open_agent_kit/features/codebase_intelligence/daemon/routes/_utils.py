"""Shared utilities for daemon route handlers.

Provides common error-handling patterns and shared converters used across
activity route modules.
"""

from __future__ import annotations

import functools
import logging
import sqlite3
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from fastapi import HTTPException

from open_agent_kit.features.codebase_intelligence.daemon.models import (
    ActivityItem,
    PromptBatchItem,
    SessionItem,
    SessionLineageItem,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        Activity,
        PromptBatch,
        Session,
    )

logger = logging.getLogger(__name__)

# Hostnames accepted by ``validate_localhost_url``.
_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "::1"}


def validate_localhost_url(url: str) -> bool:
    """Validate that a URL is localhost-only to prevent SSRF attacks.

    Only ``http`` / ``https`` schemes and hostnames in ``_LOCALHOST_HOSTS``
    are accepted.

    Args:
        url: URL to validate.

    Returns:
        True if URL is safe, False otherwise.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False

        if hostname.lower() not in _LOCALHOST_HOSTS:
            logger.warning(f"Blocked non-localhost URL for security: {url}")
            return False

        if parsed.scheme not in {"http", "https"}:
            logger.warning(f"Blocked non-http(s) URL for security: {url}")
            return False

        return True
    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid URL format: {url} - {e}")
        return False


# Standard exception tuple caught by all activity route handlers.
# These cover the realistic failure modes of store operations:
# - OSError: filesystem / SQLite I/O errors
# - ValueError: invalid data or parameters
# - RuntimeError: ChromaDB or processing errors
# - AttributeError: store not fully initialized
ROUTE_EXCEPTION_TYPES = (OSError, ValueError, RuntimeError, AttributeError, sqlite3.Error)


def session_to_lineage_item(
    session: Session,
    first_prompt_preview: str | None = None,
    prompt_batch_count: int = 0,
) -> SessionLineageItem:
    """Convert Session dataclass to SessionLineageItem for lineage display."""
    return SessionLineageItem(
        id=session.id,
        title=session.title,
        first_prompt_preview=first_prompt_preview,
        started_at=session.started_at,
        ended_at=session.ended_at,
        status=session.status,
        parent_session_reason=session.parent_session_reason,
        prompt_batch_count=prompt_batch_count,
    )


def resolve_resume_agent(agent: str) -> str:
    """Resolve captured agent label to manifest key for resume commands."""
    normalized_agent = agent.strip().lower()
    try:
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService()
        known_agents = sorted(agent_service.list_available_agents(), key=len, reverse=True)
        for known_agent in known_agents:
            if known_agent in normalized_agent:
                return known_agent
    except (OSError, ValueError, KeyError, AttributeError):
        logger.debug("Failed to resolve normalized agent label", exc_info=True)
    return normalized_agent


def get_resume_command(agent: str, session_id: str) -> str | None:
    """Get the resolved resume command for a session.

    Looks up the agent manifest to get the resume_command template,
    then substitutes the session_id placeholder.
    """
    try:
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService()
        manifest = agent_service.get_agent_manifest(resolve_resume_agent(agent))
        if manifest and manifest.ci and manifest.ci.resume_command:
            return manifest.ci.resume_command.replace("{session_id}", session_id)
    except (OSError, ValueError, KeyError, AttributeError) as e:
        logger.debug(f"Failed to get resume command for agent {agent}: {e}")

    return None


def activity_to_item(activity: Activity) -> ActivityItem:
    """Convert Activity dataclass to ActivityItem Pydantic model."""
    return ActivityItem(
        id=str(activity.id) if activity.id is not None else "",
        session_id=activity.session_id,
        prompt_batch_id=str(activity.prompt_batch_id) if activity.prompt_batch_id else None,
        tool_name=activity.tool_name,
        tool_input=activity.tool_input,
        tool_output_summary=activity.tool_output_summary,
        file_path=activity.file_path,
        success=activity.success,
        error_message=activity.error_message,
        created_at=activity.timestamp,
    )


def session_to_item(
    session: Session,
    stats: dict | None = None,
    first_prompt_preview: str | None = None,
    child_session_count: int = 0,
    summary_text: str | None = None,
    resume_command: str | None = None,
    plan_count: int = 0,
) -> SessionItem:
    """Convert Session dataclass to SessionItem Pydantic model."""
    summary = summary_text if summary_text is not None else session.summary
    return SessionItem(
        id=session.id,
        agent=session.agent,
        project_root=session.project_root,
        started_at=session.started_at,
        ended_at=session.ended_at,
        status=session.status,
        summary=summary,
        title=session.title,
        title_manually_edited=session.title_manually_edited,
        first_prompt_preview=first_prompt_preview,
        prompt_batch_count=stats.get("prompt_batch_count", 0) if stats else 0,
        activity_count=stats.get("activity_count", 0) if stats else 0,
        parent_session_id=session.parent_session_id,
        parent_session_reason=session.parent_session_reason,
        child_session_count=child_session_count,
        resume_command=resume_command,
        summary_embedded=session.summary_embedded,
        source_machine_id=session.source_machine_id,
        plan_count=plan_count,
    )


def prompt_batch_to_item(batch: PromptBatch, activity_count: int = 0) -> PromptBatchItem:
    """Convert PromptBatch dataclass to PromptBatchItem Pydantic model."""
    return PromptBatchItem(
        id=str(batch.id) if batch.id is not None else "",
        session_id=batch.session_id,
        prompt_number=batch.prompt_number,
        user_prompt=batch.user_prompt,
        classification=batch.classification,
        source_type=batch.source_type,
        plan_file_path=batch.plan_file_path,
        plan_content=batch.plan_content,
        started_at=batch.started_at,
        ended_at=batch.ended_at,
        activity_count=activity_count,
        response_summary=batch.response_summary,
    )


def handle_route_errors(operation_name: str) -> Callable:
    """Decorator that wraps route handlers with standard error handling.

    Catches ``ROUTE_EXCEPTION_TYPES``, logs the error, and raises
    ``HTTPException(500)``.  ``HTTPException`` raised inside the handler
    (e.g. 404/503 pre-validation) is re-raised untouched.

    Args:
        operation_name: Human-readable label for log messages
            (e.g. ``"list sessions"``).

    Usage::

        @router.get("/api/activity/sessions")
        @handle_route_errors("list sessions")
        async def list_sessions(...):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except ROUTE_EXCEPTION_TYPES as e:
                logger.error(f"Failed to {operation_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

        return wrapper

    return decorator
