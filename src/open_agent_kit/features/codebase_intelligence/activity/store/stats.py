"""Statistics operations for activity store.

Functions for computing and caching session and batch statistics.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def invalidate_stats_cache(store: ActivityStore, session_id: str | None = None) -> None:
    """Invalidate stats cache for a specific session or all sessions.

    Args:
        store: The ActivityStore instance.
        session_id: Session ID to invalidate, or None to clear all cache.
    """
    with store._cache_lock:
        if session_id:
            # Remove specific session from cache
            keys_to_remove = [
                k for k in store._stats_cache.keys() if k.startswith(f"stats:{session_id}")
            ]
            for key in keys_to_remove:
                store._stats_cache.pop(key, None)
        else:
            # Clear all cache
            store._stats_cache.clear()


def get_cached_stats(store: ActivityStore, cache_key: str) -> dict[str, Any] | None:
    """Get cached stats if still valid.

    Args:
        store: The ActivityStore instance.
        cache_key: Cache key (e.g., "stats:session-id").

    Returns:
        Cached stats dict if valid, None otherwise.
    """
    with store._cache_lock:
        if cache_key in store._stats_cache:
            cached_data, cached_time = store._stats_cache[cache_key]
            if time.time() - cached_time < store._cache_ttl:
                return cached_data
            # Expired, remove it
            store._stats_cache.pop(cache_key, None)
    return None


def set_cached_stats(store: ActivityStore, cache_key: str, data: dict[str, Any]) -> None:
    """Cache stats data.

    Args:
        store: The ActivityStore instance.
        cache_key: Cache key (e.g., "stats:session-id").
        data: Stats data to cache.
    """
    with store._cache_lock:
        # Clean up old entries periodically (keep cache size reasonable)
        if len(store._stats_cache) > 1000:
            now = time.time()
            store._stats_cache = {
                k: v for k, v in store._stats_cache.items() if now - v[1] < store._cache_ttl
            }
        store._stats_cache[cache_key] = (data, time.time())


def get_session_stats(store: ActivityStore, session_id: str) -> dict[str, Any]:
    """Get statistics for a session (with low TTL caching for debugging).

    Args:
        store: The ActivityStore instance.
        session_id: Session to query.

    Returns:
        Dictionary with session statistics.
    """
    # Check cache first (low TTL for near real-time debugging)
    cache_key = f"stats:{session_id}"
    cached = get_cached_stats(store, cache_key)
    if cached is not None:
        logger.debug(f"Session stats cache hit: {session_id}")
        return cached

    conn = store._get_connection()

    # Tool counts by name
    cursor = conn.execute(
        """
        SELECT tool_name, COUNT(*) as count
        FROM activities
        WHERE session_id = ?
        GROUP BY tool_name
        ORDER BY count DESC
        """,
        (session_id,),
    )
    tool_counts = {row["tool_name"]: row["count"] for row in cursor.fetchall()}

    # File operation counts
    cursor = conn.execute(
        """
        SELECT
            COUNT(DISTINCT file_path) as files_touched,
            SUM(CASE WHEN tool_name = 'Read' THEN 1 ELSE 0 END) as reads,
            SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as edits,
            SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as writes,
            SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errors
        FROM activities
        WHERE session_id = ?
        """,
        (session_id,),
    )
    row = cursor.fetchone()

    # Get total activity count
    cursor = conn.execute(
        "SELECT COUNT(*) as count FROM activities WHERE session_id = ?",
        (session_id,),
    )
    activity_count = cursor.fetchone()["count"]

    # Get prompt batch count
    cursor = conn.execute(
        "SELECT COUNT(*) as count FROM prompt_batches WHERE session_id = ?",
        (session_id,),
    )
    prompt_batch_count = cursor.fetchone()["count"]

    stats = {
        "tool_counts": tool_counts,
        "activity_count": activity_count,
        "prompt_batch_count": prompt_batch_count,
        "files_touched": row["files_touched"] or 0,
        "reads": row["reads"] or 0,
        "edits": row["edits"] or 0,
        "writes": row["writes"] or 0,
        "errors": row["errors"] or 0,
    }

    # Cache the result
    set_cached_stats(store, cache_key, stats)
    logger.debug(f"Session stats cached: {session_id} (TTL: {store._cache_ttl}s)")
    return stats


def get_bulk_session_stats(
    store: ActivityStore, session_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Get statistics for multiple sessions in a single query.

    This method eliminates the N+1 query pattern by fetching stats for
    all sessions in a single aggregated query.

    Args:
        store: The ActivityStore instance.
        session_ids: List of session IDs to query.

    Returns:
        Dictionary mapping session_id -> stats dict with keys:
        - tool_counts: dict[str, int] - Tool name -> count
        - activity_count: int
        - prompt_batch_count: int
        - files_touched: int
        - reads: int
        - edits: int
        - writes: int
        - errors: int
    """
    if not session_ids:
        return {}

    conn = store._get_connection()

    # Build placeholders for IN clause
    placeholders = ",".join("?" * len(session_ids))

    # Single aggregated query for all sessions
    cursor = conn.execute(
        f"""
        SELECT
            a.session_id,
            COUNT(DISTINCT a.id) as activity_count,
            COUNT(DISTINCT a.file_path) as files_touched,
            SUM(CASE WHEN a.tool_name = 'Read' THEN 1 ELSE 0 END) as reads,
            SUM(CASE WHEN a.tool_name = 'Edit' THEN 1 ELSE 0 END) as edits,
            SUM(CASE WHEN a.tool_name = 'Write' THEN 1 ELSE 0 END) as writes,
            SUM(CASE WHEN a.success = FALSE THEN 1 ELSE 0 END) as errors,
            COUNT(DISTINCT pb.id) as prompt_batch_count
        FROM activities a
        LEFT JOIN prompt_batches pb ON a.session_id = pb.session_id
        WHERE a.session_id IN ({placeholders})
        GROUP BY a.session_id
        """,
        session_ids,
    )

    # Build result dict with aggregated stats
    stats_map: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall():
        session_id = row["session_id"]

        # Get tool counts for this session (still need separate query for tool breakdown)
        tool_cursor = conn.execute(
            """
            SELECT tool_name, COUNT(*) as count
            FROM activities
            WHERE session_id = ?
            GROUP BY tool_name
            ORDER BY count DESC
            """,
            (session_id,),
        )
        tool_counts = {r["tool_name"]: r["count"] for r in tool_cursor.fetchall()}

        stats_map[session_id] = {
            "tool_counts": tool_counts,
            "activity_count": row["activity_count"] or 0,
            "prompt_batch_count": row["prompt_batch_count"] or 0,
            "files_touched": row["files_touched"] or 0,
            "reads": row["reads"] or 0,
            "edits": row["edits"] or 0,
            "writes": row["writes"] or 0,
            "errors": row["errors"] or 0,
        }

    # Fill in missing sessions (sessions with no activities)
    for session_id in session_ids:
        if session_id not in stats_map:
            # Still need prompt_batch_count even if no activities
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM prompt_batches WHERE session_id = ?",
                (session_id,),
            )
            prompt_batch_count = cursor.fetchone()["count"]

            stats_map[session_id] = {
                "tool_counts": {},
                "activity_count": 0,
                "prompt_batch_count": prompt_batch_count or 0,
                "files_touched": 0,
                "reads": 0,
                "edits": 0,
                "writes": 0,
                "errors": 0,
            }

    return stats_map


def get_bulk_first_prompts(
    store: ActivityStore, session_ids: list[str], max_length: int = 100
) -> dict[str, str | None]:
    """Get the first user prompt preview for multiple sessions efficiently.

    This method fetches the first prompt batch's user_prompt for each session
    in a single query, avoiding N+1 patterns.

    Args:
        store: The ActivityStore instance.
        session_ids: List of session IDs to query.
        max_length: Maximum length of the prompt preview (truncated with ...).

    Returns:
        Dictionary mapping session_id -> first prompt preview (or None).
    """
    if not session_ids:
        return {}

    conn = store._get_connection()
    placeholders = ",".join("?" * len(session_ids))

    # Get first prompt batch for each session (by prompt_number=1)
    cursor = conn.execute(
        f"""
        SELECT session_id, user_prompt
        FROM prompt_batches
        WHERE session_id IN ({placeholders})
          AND prompt_number = 1
          AND user_prompt IS NOT NULL
          AND user_prompt != ''
        """,
        session_ids,
    )

    result: dict[str, str | None] = {}
    for row in cursor.fetchall():
        session_id = row["session_id"]
        user_prompt = row["user_prompt"]

        if user_prompt:
            # Clean up the prompt: take first line or truncate
            preview = user_prompt.strip()
            # If it starts with a plan prefix, remove it for cleaner display
            if preview.startswith("Implement the following plan:"):
                preview = preview[len("Implement the following plan:") :].strip()
            # Take first meaningful line (skip empty lines)
            lines = [line.strip() for line in preview.split("\n") if line.strip()]
            if lines:
                preview = lines[0]
            # Truncate if needed
            if len(preview) > max_length:
                preview = preview[:max_length].rstrip() + "..."
            result[session_id] = preview
        else:
            result[session_id] = None

    # Fill in missing sessions
    for session_id in session_ids:
        if session_id not in result:
            result[session_id] = None

    return result
