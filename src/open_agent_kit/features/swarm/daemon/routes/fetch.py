"""Fetch detail route for the swarm daemon."""

import json
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    MCP_TOOL_FETCH,
    SWARM_DAEMON_API_PATH_FETCH,
    SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
    SWARM_ERROR_NOT_CONNECTED,
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


class FetchRequest(BaseModel):
    """Swarm fetch request body."""

    ids: list[str]
    project_slug: str


def _extract_fetch_payload(mcp_result: dict) -> dict | None:
    """Extract the parsed JSON payload from an MCP tool-result envelope.

    Expects ``{content: [{type: "text", text: "...json..."}]}``.
    Returns the parsed dict or None on failure.
    """
    if mcp_result.get("isError"):
        return None
    for block in mcp_result.get("content", []):
        if block.get("type") != "text":
            continue
        try:
            parsed: dict = json.loads(block["text"])
            return parsed
        except (json.JSONDecodeError, KeyError):
            continue
    return None


def _merge_broadcast_results(raw: dict) -> dict:
    """Merge broadcast responses into a single fetch result.

    Broadcast returns::

        {results: [{
            project_slug: str,
            result: {
                results: [{from_machine_id, result: {content: [...]}}]
            },
            error: str | null,
        }]}

    Each inner ``result`` is an MCP tool-result envelope whose text is a
    JSON string with ``{results: [...], total_tokens: N}``.

    We extract and merge all inner results, deduplicating by chunk ID.
    """
    merged: list[dict] = []
    seen_ids: set[str] = set()
    total_tokens = 0

    for project_entry in raw.get("results", []):
        if project_entry.get("error"):
            continue
        project_result = project_entry.get("result")
        if not project_result:
            continue

        # Each project_result contains per-node results from the relay fanout
        for node_entry in project_result.get("results", []):
            mcp_result = node_entry.get("result")
            if not mcp_result:
                continue

            parsed = _extract_fetch_payload(mcp_result)
            if not parsed:
                continue

            for item in parsed.get("results", []):
                chunk_id = item.get("id")
                if chunk_id and chunk_id not in seen_ids:
                    merged.append(item)
                    seen_ids.add(chunk_id)
                    total_tokens += item.get("tokens", 0)

    # Return in the same MCP envelope shape the frontend expects.
    return {
        "type": "tool_result",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"results": merged, "total_tokens": total_tokens}),
                }
            ]
        },
        "error": None,
    }


@router.post(SWARM_DAEMON_API_PATH_FETCH)
async def swarm_fetch(body: FetchRequest) -> dict:
    """Fetch full content for chunk IDs across all nodes.

    Uses broadcast (fan-out) because chunk IDs are local to each node's
    vector store — the swarm daemon doesn't know which node owns a given ID.
    """
    state = get_swarm_state()
    if not state.http_client:
        logger.warning("Fetch request dropped: not connected to swarm worker")
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED}
    logger.info("Swarm fetch: %d chunk IDs from project=%s", len(body.ids), body.project_slug)
    logger.debug("Swarm fetch IDs: %s", body.ids[:10] if len(body.ids) > 10 else body.ids)
    try:
        raw = await state.http_client.broadcast(
            tool_name=MCP_TOOL_FETCH,
            arguments={"ids": body.ids},
            timeout=SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
        )
        merged = _merge_broadcast_results(raw)
        # Count returned results from the merged payload
        result_text = merged.get("result", {}).get("content", [{}])[0].get("text", "{}")
        try:
            result_count = len(json.loads(result_text).get("results", []))
        except (json.JSONDecodeError, IndexError):
            result_count = 0
        logger.info("Swarm fetch complete: %d chunks returned", result_count)
        return merged
    except Exception as exc:
        logger.error("Swarm fetch failed: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc)}
