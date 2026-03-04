"""OpenTelemetry (OTLP) HTTP receiver for Team.

Thin protocol adapter that accepts OTLP HTTP log records and delegates
processing to ``otel_processor.OtelProcessor``.

Configuration is loaded from agent manifests (e.g., agents/codex/manifest.yaml):
  hooks:
    type: otel
    otel:
      session_id_attribute: "conversation.id"
      agent_attribute: "slug"
      event_mapping:
        "agent.event_name": "hook-action"

Reference: OpenTelemetry Protocol (OTLP) Specification
https://opentelemetry.io/docs/specs/otlp/
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response

from open_agent_kit.features.team.constants import (
    OTLP_CONTENT_TYPE_JSON,
    OTLP_LOGS_ENDPOINT,
)
from open_agent_kit.features.team.daemon.routes.otel_processor import (
    OtelProcessor,
    attributes_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["otel"])

# Single processor instance per daemon process (replaces former global mutable)
_processor = OtelProcessor()


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

    for resource_log in resource_logs:
        # Extract resource-level attributes
        resource = resource_log.get("resource", {})
        resource_attributes = attributes_to_dict(resource.get("attributes", []))

        # Process scope logs
        scope_logs = resource_log.get("scopeLogs", [])
        for scope_log in scope_logs:
            log_records = scope_log.get("logRecords", [])
            for log_record in log_records:
                try:
                    result = await _processor.process_log_record(
                        log_record,
                        resource_attributes,
                    )
                    if result:
                        processed += 1
                    else:
                        rejected += 1
                except (OSError, ValueError, KeyError, RuntimeError) as e:
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
        except (OSError, ValueError, UnicodeDecodeError):
            pass

    # Not an OTLP request, return 404
    return Response(
        content=json.dumps({"error": "Not Found"}),
        status_code=404,
        media_type="application/json",
    )
