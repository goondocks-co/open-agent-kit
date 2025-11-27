"""Shared utilities for daemon route handlers.

Provides common error-handling patterns and shared converters used across
activity route modules.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from open_agent_kit.features.codebase_intelligence.daemon.models import (
    SessionLineageItem,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import Session

logger = logging.getLogger(__name__)

# Standard exception tuple caught by all activity route handlers.
# These cover the realistic failure modes of store operations:
# - OSError: filesystem / SQLite I/O errors
# - ValueError: invalid data or parameters
# - RuntimeError: ChromaDB or processing errors
# - AttributeError: store not fully initialized
ROUTE_EXCEPTION_TYPES = (OSError, ValueError, RuntimeError, AttributeError)


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
