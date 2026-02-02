"""OpenTelemetry (OTLP) HTTP receiver for Codebase Intelligence.

This module provides an OTLP HTTP receiver that accepts OpenTelemetry log records
and translates them into OAK CI activities. This enables agents like Codex that
emit OTel events (instead of using traditional hooks) to integrate with CI.

The receiver:
- Accepts JSON-encoded OTLP log records at /v1/logs
- Extracts event name and attributes from each log record
- Maps events to hook actions using agent manifest configuration
- Dispatches to existing hook handlers for consistent activity storage

Reference: OpenTelemetry Protocol (OTLP) Specification
https://opentelemetry.io/docs/specs/otlp/
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_CODEX,
    HOOK_DROP_LOG_TAG,
    HOOK_EVENT_POST_TOOL_USE,
    HOOK_EVENT_PROMPT_SUBMIT,
    HOOK_EVENT_SESSION_START,
    OTEL_ATTR_CONVERSATION_ID,
    OTEL_ATTR_MODEL,
    OTEL_ATTR_PROMPT,
    OTEL_ATTR_PROMPT_LENGTH,
    OTEL_ATTR_TOOL_ARGUMENTS,
    OTEL_ATTR_TOOL_CALL_ID,
    OTEL_ATTR_TOOL_DURATION_MS,
    OTEL_ATTR_TOOL_NAME,
    OTEL_ATTR_TOOL_OUTPUT,
    OTEL_ATTR_TOOL_SUCCESS,
    OTEL_EVENT_CODEX_CONVERSATION_STARTS,
    OTEL_EVENT_CODEX_TOOL_RESULT,
    OTEL_EVENT_CODEX_USER_PROMPT,
    OTLP_CONTENT_TYPE_JSON,
    OTLP_LOGS_ENDPOINT,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

# Dedicated OTEL logger for lifecycle events (writes to hooks.log)
otel_logger = logging.getLogger("oak.ci.otel")

router = APIRouter(tags=["otel"])

# Default event mapping for Codex (can be overridden by manifest)
DEFAULT_CODEX_EVENT_MAPPING: dict[str, str] = {
    OTEL_EVENT_CODEX_CONVERSATION_STARTS: HOOK_EVENT_SESSION_START,
    OTEL_EVENT_CODEX_USER_PROMPT: HOOK_EVENT_PROMPT_SUBMIT,
    OTEL_EVENT_CODEX_TOOL_RESULT: HOOK_EVENT_POST_TOOL_USE,
}


def _attributes_to_dict(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert OTel KeyValue list to a simple dict.

    OTel attributes are structured as:
    [{"key": "name", "value": {"stringValue": "foo"}}, ...]

    Args:
        attributes: List of OTel KeyValue objects.

    Returns:
        Simple dict mapping keys to values.
    """
    result: dict[str, Any] = {}
    for attr in attributes:
        key = attr.get("key", "")
        value_obj = attr.get("value", {})

        # Extract value based on type
        if "stringValue" in value_obj:
            result[key] = value_obj["stringValue"]
        elif "intValue" in value_obj:
            result[key] = int(value_obj["intValue"])
        elif "doubleValue" in value_obj:
            result[key] = float(value_obj["doubleValue"])
        elif "boolValue" in value_obj:
            result[key] = value_obj["boolValue"]
        elif "arrayValue" in value_obj:
            # Recursively handle array values
            result[key] = [_extract_value(v) for v in value_obj["arrayValue"].get("values", [])]
        elif "kvlistValue" in value_obj:
            # Recursively handle nested key-value lists
            result[key] = _attributes_to_dict(value_obj["kvlistValue"].get("values", []))

    return result


def _extract_value(value_obj: dict[str, Any]) -> Any:
    """Extract a single value from an OTel value object."""
    if "stringValue" in value_obj:
        return value_obj["stringValue"]
    elif "intValue" in value_obj:
        return int(value_obj["intValue"])
    elif "doubleValue" in value_obj:
        return float(value_obj["doubleValue"])
    elif "boolValue" in value_obj:
        return value_obj["boolValue"]
    return None


def _extract_session_id(
    attributes: dict[str, Any],
    resource_attributes: dict[str, Any],
    session_id_attribute: str = OTEL_ATTR_CONVERSATION_ID,
) -> str | None:
    """Extract session ID from log record attributes.

    Checks both log-level attributes and resource-level attributes.

    Args:
        attributes: Log record attributes.
        resource_attributes: Resource-level attributes.
        session_id_attribute: Attribute key for session ID.

    Returns:
        Session ID string or None if not found.
    """
    # Check log attributes first
    session_id = attributes.get(session_id_attribute)
    if session_id:
        return str(session_id)

    # Fall back to resource attributes
    session_id = resource_attributes.get(session_id_attribute)
    if session_id:
        return str(session_id)

    return None


async def _handle_session_start(
    session_id: str,
    attributes: dict[str, Any],
    resource_attributes: dict[str, Any],
) -> dict[str, Any]:
    """Handle Codex conversation_starts event as session-start.

    Args:
        session_id: Session identifier.
        attributes: Log record attributes.
        resource_attributes: Resource-level attributes.

    Returns:
        Response dict.
    """
    state = get_state()
    agent = AGENT_CODEX
    model = attributes.get(OTEL_ATTR_MODEL) or resource_attributes.get(OTEL_ATTR_MODEL)

    otel_logger.info(f"[OTEL:SESSION-START] session={session_id} agent={agent} model={model}")

    # Create or resume session in activity store
    if state.activity_store and state.project_root:
        try:
            _, created = state.activity_store.get_or_create_session(
                session_id=session_id,
                agent=agent,
                project_root=str(state.project_root),
            )
            if created:
                logger.debug(f"Created activity session from OTEL: {session_id}")
            else:
                logger.debug(f"Resumed activity session from OTEL: {session_id}")
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to create/resume activity session from OTEL: {e}")

    return {"status": "ok", "session_id": session_id, "event": "session-start"}


async def _handle_prompt_submit(
    session_id: str,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    """Handle Codex user_prompt event as prompt-submit.

    Args:
        session_id: Session identifier.
        attributes: Log record attributes.

    Returns:
        Response dict.
    """
    state = get_state()
    agent = AGENT_CODEX

    prompt = attributes.get(OTEL_ATTR_PROMPT, "")
    prompt_length = attributes.get(OTEL_ATTR_PROMPT_LENGTH, 0)

    # If prompt is redacted, note it
    if not prompt and prompt_length > 0:
        prompt = f"[Redacted prompt, {prompt_length} chars]"

    otel_logger.info(f"[OTEL:PROMPT-SUBMIT] session={session_id} length={prompt_length}")

    if not state.activity_store:
        return {"status": "ok", "event": "prompt-submit"}

    prompt_batch_id = None
    try:
        # End previous prompt batch if exists
        active_batch = state.activity_store.get_active_prompt_batch(session_id)
        if active_batch and active_batch.id:
            state.activity_store.end_prompt_batch(active_batch.id)
            logger.debug(f"Ended previous prompt batch from OTEL: {active_batch.id}")

        # Create new prompt batch
        batch = state.activity_store.create_prompt_batch(
            session_id=session_id,
            user_prompt=prompt or "[Prompt from OTEL]",
            source_type="user",
            agent=agent,
        )
        prompt_batch_id = batch.id
        logger.debug(f"Created prompt batch from OTEL: {prompt_batch_id}")

    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Failed to create prompt batch from OTEL: {e}")

    return {"status": "ok", "event": "prompt-submit", "prompt_batch_id": prompt_batch_id}


async def _handle_tool_result(
    session_id: str,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    """Handle Codex tool_result event as post-tool-use.

    Args:
        session_id: Session identifier.
        attributes: Log record attributes.

    Returns:
        Response dict.
    """
    state = get_state()

    tool_name = attributes.get(OTEL_ATTR_TOOL_NAME, "unknown")
    call_id = attributes.get(OTEL_ATTR_TOOL_CALL_ID, "")
    duration_ms = attributes.get(OTEL_ATTR_TOOL_DURATION_MS, 0)
    success_str = attributes.get(OTEL_ATTR_TOOL_SUCCESS, "true")
    success = success_str.lower() == "true" if isinstance(success_str, str) else bool(success_str)
    output = attributes.get(OTEL_ATTR_TOOL_OUTPUT, "")

    # Parse arguments if present
    arguments = attributes.get(OTEL_ATTR_TOOL_ARGUMENTS)
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            arguments = {"raw": arguments}
    elif arguments is None:
        arguments = {}

    otel_logger.info(
        f"[OTEL:TOOL-USE] {tool_name} session={session_id} success={success} "
        f"duration_ms={duration_ms}"
    )

    if not state.activity_store:
        return {"status": "ok", "event": "post-tool-use"}

    try:
        from open_agent_kit.features.codebase_intelligence.activity import Activity

        # Get current prompt batch ID
        prompt_batch_id = None
        active_batch = state.activity_store.get_active_prompt_batch(session_id)
        if active_batch:
            prompt_batch_id = active_batch.id

        # Extract file_path if present in arguments
        file_path = None
        if isinstance(arguments, dict):
            file_path = arguments.get("file_path") or arguments.get("path")

        activity = Activity(
            session_id=session_id,
            prompt_batch_id=prompt_batch_id,
            tool_name=tool_name,
            tool_input=arguments if isinstance(arguments, dict) else None,
            tool_output_summary=output[:500] if output else "",
            file_path=file_path,
            success=success,
            error_message=None if success else output[:500],
        )
        state.activity_store.add_activity_buffered(activity)
        logger.debug(
            f"Stored activity from OTEL: {tool_name} (batch={prompt_batch_id}, "
            f"call_id={call_id})"
        )

    except (OSError, ValueError, RuntimeError) as e:
        logger.debug(f"Failed to store activity from OTEL: {e}")

    return {"status": "ok", "event": "post-tool-use", "tool_name": tool_name}


async def _process_log_record(
    log_record: dict[str, Any],
    resource_attributes: dict[str, Any],
    event_mapping: dict[str, str],
    session_id_attribute: str = OTEL_ATTR_CONVERSATION_ID,
) -> dict[str, Any] | None:
    """Process a single OTLP log record.

    Args:
        log_record: The log record from the OTLP payload.
        resource_attributes: Resource-level attributes.
        event_mapping: Map of OTel event names to hook actions.
        session_id_attribute: Attribute key for session ID.

    Returns:
        Response dict or None if event was skipped.
    """
    # Extract log record attributes
    attributes = _attributes_to_dict(log_record.get("attributes", []))

    # Get event name from body or attributes
    # OTel events typically have the event name in body.stringValue
    body = log_record.get("body", {})
    event_name = body.get("stringValue", "") if isinstance(body, dict) else str(body)

    # Also check for event name in attributes (fallback)
    if not event_name:
        event_name = attributes.get("event.name", "")

    # Extract session ID
    session_id = _extract_session_id(attributes, resource_attributes, session_id_attribute)
    if not session_id:
        logger.debug(f"{HOOK_DROP_LOG_TAG} Dropped OTEL event {event_name}: missing session_id")
        return None

    # Map event to hook action
    hook_action = event_mapping.get(event_name)
    if not hook_action:
        logger.debug(f"Ignoring unmapped OTEL event: {event_name}")
        return None

    # Dispatch to appropriate handler
    if hook_action == HOOK_EVENT_SESSION_START:
        return await _handle_session_start(session_id, attributes, resource_attributes)
    elif hook_action == HOOK_EVENT_PROMPT_SUBMIT:
        return await _handle_prompt_submit(session_id, attributes)
    elif hook_action == HOOK_EVENT_POST_TOOL_USE:
        return await _handle_tool_result(session_id, attributes)
    else:
        logger.debug(f"Unhandled hook action: {hook_action}")
        return None


@router.post(OTLP_LOGS_ENDPOINT)
async def otlp_logs_receiver(request: Request) -> Response:
    """OTLP HTTP logs receiver endpoint.

    Accepts JSON-encoded OTLP log records and translates them to CI activities.

    The OTLP JSON format is:
    {
      "resourceLogs": [
        {
          "resource": {"attributes": [...]},
          "scopeLogs": [
            {
              "logRecords": [
                {"body": {...}, "attributes": [...], ...}
              ]
            }
          ]
        }
      ]
    }
    """
    content_type = request.headers.get("content-type", "")

    # Only accept JSON for now
    if OTLP_CONTENT_TYPE_JSON not in content_type and "json" not in content_type:
        logger.warning(f"Unsupported OTLP content type: {content_type}")
        return Response(
            content=json.dumps({"error": "Only JSON encoding is supported"}),
            status_code=415,
            media_type="application/json",
        )

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to parse OTLP JSON: {e}")
        return Response(
            content=json.dumps({"partialSuccess": {"rejectedLogRecords": 1}}),
            status_code=200,  # OTLP uses 200 even for partial failures
            media_type="application/json",
        )

    # Process resource logs
    resource_logs = body.get("resourceLogs", [])
    processed = 0
    rejected = 0

    # Use default Codex event mapping (could be extended to load from manifest)
    event_mapping = DEFAULT_CODEX_EVENT_MAPPING

    for resource_log in resource_logs:
        # Extract resource-level attributes
        resource = resource_log.get("resource", {})
        resource_attributes = _attributes_to_dict(resource.get("attributes", []))

        # Process scope logs
        scope_logs = resource_log.get("scopeLogs", [])
        for scope_log in scope_logs:
            log_records = scope_log.get("logRecords", [])
            for log_record in log_records:
                try:
                    result = await _process_log_record(
                        log_record,
                        resource_attributes,
                        event_mapping,
                    )
                    if result:
                        processed += 1
                    else:
                        rejected += 1
                except Exception as e:
                    logger.warning(f"Error processing OTEL log record: {e}")
                    rejected += 1

    logger.debug(f"OTLP processed: {processed} accepted, {rejected} rejected")

    # Return OTLP partial success response
    response_body: dict[str, Any] = {}
    if rejected > 0:
        response_body["partialSuccess"] = {"rejectedLogRecords": rejected}

    return Response(
        content=json.dumps(response_body),
        status_code=200,
        media_type="application/json",
    )


@router.post("/")
async def otlp_root_receiver(request: Request) -> Response:
    """Fallback OTLP receiver at root path.

    Some OTel clients (like Codex) may send to root path instead of /v1/logs.
    This endpoint delegates to the main OTLP logs receiver.
    """
    # Check if this looks like an OTLP request
    content_type = request.headers.get("content-type", "")
    if "json" in content_type or OTLP_CONTENT_TYPE_JSON in content_type:
        try:
            body = await request.body()
            body_str = body.decode("utf-8")
            if "resourceLogs" in body_str or "logRecords" in body_str:
                # Reconstruct request and delegate
                return await otlp_logs_receiver(request)
        except Exception:
            pass

    # Not an OTLP request, return 404
    return Response(
        content=json.dumps({"error": "Not Found"}),
        status_code=404,
        media_type="application/json",
    )
