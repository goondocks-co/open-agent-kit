"""Shared infrastructure for hook route handlers.

Provides common types, body parsing, error handling, and utility functions
used across all hook lifecycle modules (hooks_session, hooks_prompt, etc.).

This module is the hook-specific counterpart to ``_utils.py`` (which serves
regular route handlers).  Key difference: hooks are **fire-and-forget** --
they always return ``{"status": "ok"}`` even on internal errors, whereas
regular routes raise ``HTTPException(500)``.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_UNKNOWN,
    HOOK_DEDUP_HASH_ALGORITHM,
    HOOK_FIELD_AGENT,
    HOOK_FIELD_CONVERSATION_ID,
    HOOK_FIELD_GENERATION_ID,
    HOOK_FIELD_HOOK_ORIGIN,
    HOOK_FIELD_SESSION_ID,
    HOOK_FIELD_TOOL_INPUT,
    HOOK_FIELD_TOOL_NAME,
    HOOK_FIELD_TOOL_USE_ID,
)
from open_agent_kit.utils.file_utils import get_relative_path

logger = logging.getLogger(__name__)

# Dedicated hooks logger for lifecycle events (writes to hooks.log)
# This provides a clean, focused view of hook activity separate from daemon.log
hooks_logger = logging.getLogger("oak.ci.hooks")

# Standard exception tuple for hook store operations.
# Hooks are fire-and-forget -- they must return {"status": "ok"} even on
# internal errors to avoid blocking the calling agent.  This differs from
# ROUTE_EXCEPTION_TYPES (which converts errors to HTTPException(500)).
HOOK_STORE_EXCEPTIONS = (OSError, ValueError, RuntimeError, sqlite3.Error)

# Route prefix -- uses /api/oak/ci/ to avoid conflicts with other integrations
OAK_CI_PREFIX = "/api/oak/ci"


# =============================================================================
# HookBody -- parsed hook request body
# =============================================================================


@dataclass
class HookBody:
    """Parsed hook request body with common fields extracted.

    Every hook handler receives the same JSON structure.  ``HookBody``
    centralizes the parsing so individual handlers can focus on their
    domain logic.
    """

    raw: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    agent: str = AGENT_UNKNOWN
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    hook_origin: str = ""
    tool_use_id: str = ""
    generation_id: str = ""


async def parse_hook_body(request: Request) -> HookBody:
    """Parse JSON body from a hook request and extract common fields.

    This replaces the duplicated body-parsing pattern found in every handler:

    .. code-block:: python

        try:
            body = await request.json()
        except (ValueError, json.JSONDecodeError):
            body = {}
        session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
        agent = body.get("agent", "unknown")
        ...

    Returns:
        HookBody with common fields extracted and normalized.
    """
    try:
        raw = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body")
        raw = {}

    session_id = raw.get(HOOK_FIELD_SESSION_ID) or raw.get(HOOK_FIELD_CONVERSATION_ID)

    # Normalize tool_input: could be dict (JSON), string, or None
    tool_input = raw.get(HOOK_FIELD_TOOL_INPUT, {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (ValueError, json.JSONDecodeError):
            tool_input = {"raw": tool_input}
    elif tool_input is None:
        tool_input = {}

    return HookBody(
        raw=raw,
        session_id=session_id,
        agent=raw.get(HOOK_FIELD_AGENT, AGENT_UNKNOWN),
        tool_name=raw.get(HOOK_FIELD_TOOL_NAME, ""),
        tool_input=tool_input,
        hook_origin=raw.get(HOOK_FIELD_HOOK_ORIGIN, ""),
        tool_use_id=raw.get(HOOK_FIELD_TOOL_USE_ID, ""),
        generation_id=raw.get(HOOK_FIELD_GENERATION_ID, ""),
    )


# =============================================================================
# @handle_hook_errors -- fire-and-forget error decorator
# =============================================================================


def handle_hook_errors(hook_name: str) -> Callable:
    """Decorator that wraps hook handlers with fire-and-forget error handling.

    Unlike ``@handle_route_errors`` (which raises ``HTTPException(500)``),
    hooks must **always** return ``{"status": "ok"}`` -- even on internal
    errors -- to avoid blocking the calling agent.

    Args:
        hook_name: Human-readable label for log messages
            (e.g. ``"session-start"``, ``"post-tool-use"``).

    Usage::

        @router.post(f"{OAK_CI_PREFIX}/session-start")
        @handle_hook_errors("session-start")
        async def hook_session_start(request: Request) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> dict:
            try:
                return await func(*args, **kwargs)
            except Exception as e:  # broad catch intentional: hooks are fire-and-forget
                logger.error(f"Hook {hook_name} failed: {e}")
                return {"status": "ok"}

        return wrapper

    return decorator


# =============================================================================
# Utility helpers
# =============================================================================


def parse_tool_output(tool_output: str) -> dict[str, Any] | None:
    """Parse JSON tool output, return None if not valid JSON."""
    if not tool_output:
        return None
    try:
        result = json.loads(tool_output)
        if isinstance(result, dict):
            return result
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def hash_value(value: str) -> str:
    """Create a stable hash for dedupe keys."""
    hasher = hashlib.new(HOOK_DEDUP_HASH_ALGORITHM)
    hasher.update(value.encode("utf-8"))
    return hasher.hexdigest()


def build_dedupe_key(event_name: str, session_id: str, parts: list[str]) -> str:
    """Build a dedupe key for hook events."""
    return "|".join([event_name, session_id, *parts])


def normalize_file_path(file_path: str, project_root: Path | None) -> str:
    """Normalize file path to project-relative when possible."""
    if not file_path:
        return file_path
    if not project_root:
        return file_path

    path_value = Path(file_path)

    try:
        if not path_value.is_absolute():
            path_value = project_root / path_value
        path_value = path_value.resolve()
        root_path = project_root.resolve()
        if path_value == root_path or root_path in path_value.parents:
            return get_relative_path(path_value, root_path).as_posix()
    except (OSError, RuntimeError, ValueError):
        return file_path

    return file_path


# =============================================================================
# Agent Configuration Helpers
# =============================================================================


def get_continuation_sources(agent: str) -> list[str]:
    """Get session continuation sources for an agent from its manifest.

    Returns a list of SessionStart source values that indicate continuation
    (e.g., ["clear", "compact"] for Claude). When SessionStart fires with
    one of these sources, a system batch should be created immediately.

    Falls back to empty list if agent manifest is not found.
    """
    try:
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService()
        manifest = agent_service.get_agent_manifest(agent)
        if manifest and manifest.ci and manifest.ci.continuation:
            return manifest.ci.continuation.continuation_sources or []
    except (OSError, ValueError, KeyError, AttributeError) as e:
        logger.debug(f"Failed to load continuation sources for agent {agent}: {e}")

    return []


def get_continuation_label(source: str) -> str:
    """Get the appropriate batch label for a continuation source.

    Maps continuation source types to their descriptive labels.
    Uses constants to keep labels consistent across the codebase.
    """
    from open_agent_kit.features.codebase_intelligence.constants import (
        BATCH_LABEL_CLEARED_CONTEXT,
        BATCH_LABEL_CONTEXT_COMPACTION,
        BATCH_LABEL_SESSION_CONTINUATION,
    )

    # Map known sources to their labels
    source_labels = {
        "clear": BATCH_LABEL_CLEARED_CONTEXT,
        "compact": BATCH_LABEL_CONTEXT_COMPACTION,
    }

    return source_labels.get(source, BATCH_LABEL_SESSION_CONTINUATION)


# =============================================================================
# Exit Plan Tool Detection (for final plan capture)
# =============================================================================

# Cached mapping of exit plan tool names from agent manifests
_exit_plan_tools: dict[str, str] | None = None


def get_exit_plan_tools() -> dict[str, str]:
    """Get exit plan tool names from agent manifests (cached).

    Returns:
        Dict mapping agent_type to exit_plan_tool name.
        Example: {'claude': 'ExitPlanMode'}
    """
    global _exit_plan_tools
    if _exit_plan_tools is None:
        try:
            from open_agent_kit.services.agent_service import AgentService

            agent_service = AgentService()
            _exit_plan_tools = agent_service.get_all_exit_plan_tools()
            logger.debug(f"Loaded exit_plan_tools: {_exit_plan_tools}")
        except (OSError, ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Failed to load exit_plan_tools: {e}")
            _exit_plan_tools = {}
    return _exit_plan_tools


def is_exit_plan_tool(tool_name: str) -> bool:
    """Check if a tool name is an exit plan tool for any agent.

    Args:
        tool_name: The tool name to check (e.g., 'ExitPlanMode').

    Returns:
        True if this tool signals plan mode exit for any agent.
    """
    return tool_name in get_exit_plan_tools().values()


def get_active_batch_id(activity_store: Any, session_id: str) -> int | None:
    """Get the active prompt batch ID for a session, or None.

    This is a convenience wrapper around the common pattern:

    .. code-block:: python

        active_batch = state.activity_store.get_active_prompt_batch(session_id)
        prompt_batch_id = active_batch.id if active_batch else None
    """
    active_batch = activity_store.get_active_prompt_batch(session_id)
    return active_batch.id if active_batch else None
