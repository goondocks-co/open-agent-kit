"""Search route for the swarm daemon."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_SEARCH,
    SWARM_ERROR_NOT_CONNECTED,
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_RESPONSE_KEY_RESULTS,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


class SearchRequest(BaseModel):
    """Swarm search request body."""

    query: str
    search_type: str = "all"
    limit: int = 10


def _normalize_match(item: dict) -> dict:
    """Normalize a flat search result into the UI's SearchMatch shape.

    The relay client tags items with ``_result_type`` and type-specific
    field names.  The UI expects ``type``, ``content``, ``score``,
    ``doc_type``, and optionally ``file_path``.

    Note: this function does NOT mutate *item*.
    """
    result_type = item.get("_result_type", item.get("type", "unknown"))
    content = (
        item.get("summary")  # memory
        or item.get("preview")  # plan / session
        or item.get("observation")
        or item.get("content", "")
    )
    score = item.get("relevance") or item.get("score")
    doc_type = item.get("doc_type") or item.get("memory_type") or result_type

    return {
        "id": item.get("id"),
        "type": result_type,
        "content": content,
        "score": score,
        "doc_type": doc_type,
        "file_path": item.get("file_path") or item.get("filepath"),
    }


def _group_results_by_project(raw: dict) -> dict:
    """Group flat results into ``{project_slug, matches[]}`` groups.

    The swarm worker returns a flat array where each item has a
    ``project_slug`` key.  The UI expects an array of per-project groups,
    each containing a ``matches`` list with normalized field names.
    """
    flat = raw.get(SWARM_RESPONSE_KEY_RESULTS, [])
    if not flat:
        return raw

    # If already grouped (has ``matches`` key), pass through unchanged.
    if flat and isinstance(flat[0], dict) and "matches" in flat[0]:
        return raw

    grouped: dict[str, list[dict]] = {}
    for item in flat:
        slug = item.get("project_slug", "unknown")
        grouped.setdefault(slug, []).append(_normalize_match(item))

    result: dict = {
        SWARM_RESPONSE_KEY_RESULTS: [
            {"project_slug": slug, "matches": matches} for slug, matches in grouped.items()
        ],
    }
    # Preserve errors from the swarm worker response.
    if "errors" in raw:
        result["errors"] = raw["errors"]
    if SWARM_RESPONSE_KEY_ERROR in raw:
        result[SWARM_RESPONSE_KEY_ERROR] = raw[SWARM_RESPONSE_KEY_ERROR]
    return result


@router.post(SWARM_DAEMON_API_PATH_SEARCH)
async def swarm_search(body: SearchRequest) -> dict:
    """Search across swarm nodes."""
    state = get_swarm_state()
    if not state.http_client:
        logger.warning("Search request dropped: not connected to swarm worker")
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED, SWARM_RESPONSE_KEY_RESULTS: []}
    logger.info("Swarm search: query=%r type=%s limit=%d", body.query, body.search_type, body.limit)
    try:
        raw = await state.http_client.search(body.query, body.search_type, body.limit)
        logger.debug("Swarm search raw response keys: %s", list(raw.keys()))
        grouped = _group_results_by_project(raw)
        result_count = sum(
            len(g.get("matches", [])) for g in grouped.get(SWARM_RESPONSE_KEY_RESULTS, [])
        )
        logger.info(
            "Swarm search complete: %d results across %d projects",
            result_count,
            len(grouped.get(SWARM_RESPONSE_KEY_RESULTS, [])),
        )
        if result_count > 0:
            for group in grouped.get(SWARM_RESPONSE_KEY_RESULTS, []):
                slug = group.get("project_slug", "unknown")
                matches = group.get("matches", [])
                logger.debug(
                    "  project=%s matches=%d top_score=%.3f",
                    slug,
                    len(matches),
                    max((m.get("score") or 0 for m in matches), default=0),
                )
        return grouped
    except Exception as exc:
        logger.error("Swarm search failed: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), SWARM_RESPONSE_KEY_RESULTS: []}
