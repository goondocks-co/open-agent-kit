"""Agent notification receiver for Codebase Intelligence.

Handles agent notification events (e.g., Codex notify handlers) and
translates them into CI actions such as response summary capture.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Request

from open_agent_kit.features.codebase_intelligence.activity import finalize_prompt_batch
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_NOTIFY_ACTION_RESPONSE_SUMMARY,
    AGENT_NOTIFY_CONFIG_TYPE,
    AGENT_NOTIFY_DEFAULT_COMMAND,
    AGENT_NOTIFY_ENDPOINT,
    AGENT_NOTIFY_FIELD_AGENT,
    AGENT_NOTIFY_FIELD_INPUT_MESSAGES,
    AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE,
    AGENT_NOTIFY_FIELD_THREAD_ID,
    AGENT_NOTIFY_FIELD_TURN_ID,
    AGENT_NOTIFY_FIELD_TYPE,
    HOOK_DEDUP_CACHE_MAX,
    HOOK_DROP_LOG_TAG,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notify"])


@lru_cache(maxsize=32)
def _load_notify_config(agent: str) -> dict[str, Any] | None:
    """Load notify configuration from an agent's manifest."""
    from open_agent_kit.services.agent_service import AgentService

    try:
        service = AgentService()
        manifest = service.get_agent_manifest(agent)
        if not manifest:
            return None

        notifications = manifest.notifications
        if not notifications or notifications.type != AGENT_NOTIFY_CONFIG_TYPE:
            return None

        notify = notifications.notify
        if not notify or not notify.enabled:
            return None

        return {
            "event_mapping": notify.event_mapping or {},
            "session_id_field": notify.session_id_field or AGENT_NOTIFY_FIELD_THREAD_ID,
            "response_field": notify.response_field or AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE,
            "input_messages_field": notify.input_messages_field
            or AGENT_NOTIFY_FIELD_INPUT_MESSAGES,
            "command": notify.command or AGENT_NOTIFY_DEFAULT_COMMAND,
        }
    except (OSError, ValueError, KeyError, AttributeError) as e:
        logger.debug(f"Failed to load notify config for agent {agent}: {e}")
        return None


def _get_all_notify_agents() -> list[str]:
    """Get list of all agents that use notify handlers."""
    from open_agent_kit.services.agent_service import AgentService

    try:
        service = AgentService()
        agents = []
        for agent in service.list_available_agents():
            config = _load_notify_config(agent)
            if config:
                agents.append(agent)
        return agents
    except (OSError, ValueError, KeyError, AttributeError) as e:
        logger.debug(f"Failed to list notify agents: {e}")
        return []


def _build_notify_mapping() -> (
    tuple[dict[str, dict[str, str]], dict[str, str], dict[str, str], dict[str, str]]
):
    """Build combined notify mapping from all notify-enabled agents."""
    event_mapping: dict[str, dict[str, str]] = {}
    session_id_fields: dict[str, str] = {}
    response_fields: dict[str, str] = {}
    input_messages_fields: dict[str, str] = {}

    for agent in _get_all_notify_agents():
        config = _load_notify_config(agent)
        if not config:
            continue

        event_mapping[agent] = config.get("event_mapping", {})
        session_id_fields[agent] = config.get("session_id_field", AGENT_NOTIFY_FIELD_THREAD_ID)
        response_fields[agent] = config.get(
            "response_field", AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE
        )
        input_messages_fields[agent] = config.get(
            "input_messages_field", AGENT_NOTIFY_FIELD_INPUT_MESSAGES
        )

    return event_mapping, session_id_fields, response_fields, input_messages_fields


_cached_notify_mapping: (
    tuple[dict[str, dict[str, str]], dict[str, str], dict[str, str], dict[str, str]] | None
) = None


def _get_notify_mapping() -> (
    tuple[dict[str, dict[str, str]], dict[str, str], dict[str, str], dict[str, str]]
):
    global _cached_notify_mapping
    if _cached_notify_mapping is None:
        _cached_notify_mapping = _build_notify_mapping()
        if _cached_notify_mapping[0]:
            logger.info(f"Loaded notify mapping for {len(_cached_notify_mapping[0])} agents")
        else:
            logger.debug("No notify agents configured, using empty mapping")
    return _cached_notify_mapping


def _build_dedupe_key(event_name: str, session_id: str, parts: list[str]) -> str:
    """Build a dedupe key for notification events."""
    return "|".join([event_name, session_id, *parts])


@router.post(AGENT_NOTIFY_ENDPOINT)
async def notify_receiver(request: Request) -> dict[str, Any]:
    """Handle agent notification events."""
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in notify handler")
        body = {}

    event_type = body.get(AGENT_NOTIFY_FIELD_TYPE)
    agent = body.get(AGENT_NOTIFY_FIELD_AGENT)

    if not event_type or not agent:
        logger.debug(f"{HOOK_DROP_LOG_TAG} Dropped notify event: missing type or agent")
        return {"status": "ok"}

    event_mapping, session_id_fields, response_fields, _ = _get_notify_mapping()
    agent_mapping = event_mapping.get(agent, {})
    action = agent_mapping.get(event_type)

    if not action:
        logger.debug(f"Ignoring unmapped notify event: {event_type!r} (agent={agent})")
        return {"status": "ok"}

    if not state.activity_store:
        return {"status": "ok"}

    if action != AGENT_NOTIFY_ACTION_RESPONSE_SUMMARY:
        logger.debug(f"Unhandled notify action: {action}")
        return {"status": "ok"}

    session_id_field = session_id_fields.get(agent, AGENT_NOTIFY_FIELD_THREAD_ID)
    response_field = response_fields.get(agent, AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE)

    session_id = body.get(session_id_field)
    response_summary = body.get(response_field, "")

    if not session_id or not response_summary:
        logger.debug(
            f"{HOOK_DROP_LOG_TAG} Dropped notify event {event_type!r}: missing session_id "
            f"or response summary"
        )
        return {"status": "ok"}

    # Ensure session exists
    if state.project_root:
        try:
            state.activity_store.get_or_create_session(
                session_id=session_id,
                agent=agent,
                project_root=str(state.project_root),
            )
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to ensure session exists for notify: {e}")

    # Flush buffered activities before closing batch
    try:
        flushed_ids = state.activity_store.flush_activity_buffer()
        if flushed_ids:
            logger.debug(f"Flushed {len(flushed_ids)} buffered activities before notify")
    except (OSError, ValueError, RuntimeError) as e:
        logger.debug(f"Failed to flush activity buffer: {e}")

    active_batch = state.activity_store.get_active_prompt_batch(session_id)
    if not active_batch or not active_batch.id:
        logger.debug(f"{HOOK_DROP_LOG_TAG} Dropped notify event {event_type!r}: no active batch")
        return {"status": "ok"}

    # Dedupe using turn-id + batch id if provided
    dedupe_parts = []
    turn_id = body.get(AGENT_NOTIFY_FIELD_TURN_ID)
    if turn_id:
        dedupe_parts.extend([str(turn_id), str(active_batch.id)])

    if dedupe_parts:
        dedupe_key = _build_dedupe_key(event_type, session_id, dedupe_parts)
        if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
            logger.debug(
                "Deduped notify event session=%s event=%s",
                session_id,
                event_type,
            )
            return {"status": "ok"}

    result = finalize_prompt_batch(
        activity_store=state.activity_store,
        activity_processor=state.activity_processor,
        prompt_batch_id=active_batch.id,
        response_summary=response_summary,
    )

    return {"status": "ok", **result}
