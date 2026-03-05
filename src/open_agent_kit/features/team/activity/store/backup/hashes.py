"""Hash generation functions for content-based deduplication."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore


def compute_hash(*parts: str | int | None) -> str:
    """Compute stable hash from parts, ignoring None values.

    Args:
        *parts: Variable parts to include in hash computation.

    Returns:
        16-character hex hash string.
    """
    content = "|".join(str(p) if p is not None else "" for p in parts)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def backfill_content_hashes(store: ActivityStore) -> dict[str, int]:
    """Backfill content_hash for records missing them.

    New records created after the v11 migration don't get content_hash
    populated at insert time. This computes and stores hashes for all
    records that are missing them.

    Args:
        store: The ActivityStore instance.

    Returns:
        Dict with counts: {prompt_batches, observations, activities}.
    """
    import logging

    logger = logging.getLogger(__name__)
    counts = {"prompt_batches": 0, "observations": 0, "activities": 0}

    with store._transaction() as conn:
        # Backfill prompt_batches
        cursor = conn.execute(
            "SELECT id, session_id, prompt_number FROM prompt_batches WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            batch_id, session_id, prompt_number = row
            hash_val = compute_prompt_batch_hash(str(session_id), int(prompt_number))
            conn.execute(
                "UPDATE OR IGNORE prompt_batches SET content_hash = ? WHERE id = ?",
                (hash_val, batch_id),
            )
            counts["prompt_batches"] += 1

        # Backfill memory_observations
        cursor = conn.execute(
            "SELECT id, observation, memory_type, context FROM memory_observations "
            "WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            obs_id, observation, memory_type, context = row
            hash_val = compute_observation_hash(str(observation), str(memory_type), context)
            conn.execute(
                "UPDATE memory_observations SET content_hash = ? WHERE id = ?",
                (hash_val, obs_id),
            )
            counts["observations"] += 1

        # Backfill activities
        cursor = conn.execute(
            "SELECT id, session_id, timestamp_epoch, tool_name FROM activities "
            "WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            activity_id, session_id, timestamp_epoch, tool_name = row
            hash_val = compute_activity_hash(str(session_id), int(timestamp_epoch), str(tool_name))
            conn.execute(
                "UPDATE activities SET content_hash = ? WHERE id = ?",
                (hash_val, activity_id),
            )
            counts["activities"] += 1

    total = sum(counts.values())
    if total > 0:
        logger.info(
            f"Backfilled content hashes: {counts['prompt_batches']} batches, "
            f"{counts['observations']} observations, {counts['activities']} activities"
        )

    return counts


def compute_prompt_batch_hash(session_id: str, prompt_number: int) -> str:
    """Hash for prompt_batches deduplication.

    Uses session_id + prompt_number as unique identifier.
    """
    return compute_hash(session_id, prompt_number)


def compute_observation_hash(observation: str, memory_type: str, context: str | None) -> str:
    """Hash for memory_observations deduplication.

    Uses observation content + type + context as unique identifier.
    """
    return compute_hash(observation, memory_type, context)


def compute_activity_hash(session_id: str, timestamp_epoch: int, tool_name: str) -> str:
    """Hash for activities deduplication.

    Uses session_id + timestamp + tool_name as unique identifier.
    """
    return compute_hash(session_id, timestamp_epoch, tool_name)


def compute_resolution_event_hash(
    observation_id: str, action: str, source_machine_id: str, superseded_by: str
) -> str:
    """Hash for resolution_events deduplication.

    Same machine resolving the same observation deduplicates;
    different machines resolving the same observation both preserved.
    """
    return compute_hash(observation_id, action, source_machine_id, superseded_by)


# ---------------------------------------------------------------------------
# Hash retrieval helpers (used by importer for dedup checking)
# ---------------------------------------------------------------------------


def get_all_session_ids(store: ActivityStore) -> set[str]:
    """Get all session IDs for dedup checking during import."""
    conn = store._get_connection()
    cursor = conn.execute("SELECT id FROM sessions")
    return {row[0] for row in cursor.fetchall()}


def get_all_prompt_batch_hashes(store: ActivityStore) -> set[str]:
    """Get all prompt_batch content_hash values for dedup checking.

    Falls back to computing hashes if content_hash column is empty.
    """
    conn = store._get_connection()

    cursor = conn.execute("SELECT content_hash FROM prompt_batches WHERE content_hash IS NOT NULL")
    hashes = {row[0] for row in cursor.fetchall()}

    cursor = conn.execute(
        "SELECT session_id, prompt_number FROM prompt_batches WHERE content_hash IS NULL"
    )
    for row in cursor.fetchall():
        hashes.add(compute_prompt_batch_hash(str(row[0]), int(row[1])))

    return hashes


def get_all_observation_hashes(store: ActivityStore) -> set[str]:
    """Get all memory_observation content_hash values for dedup checking.

    Falls back to computing hashes if content_hash column is empty.
    """
    conn = store._get_connection()

    cursor = conn.execute(
        "SELECT content_hash FROM memory_observations WHERE content_hash IS NOT NULL"
    )
    hashes = {row[0] for row in cursor.fetchall()}

    cursor = conn.execute(
        "SELECT observation, memory_type, context FROM memory_observations "
        "WHERE content_hash IS NULL"
    )
    for row in cursor.fetchall():
        hashes.add(compute_observation_hash(str(row[0]), str(row[1]), row[2]))

    return hashes


def get_all_activity_hashes(store: ActivityStore) -> set[str]:
    """Get all activity content_hash values for dedup checking.

    Falls back to computing hashes if content_hash column is empty.
    """
    conn = store._get_connection()

    cursor = conn.execute("SELECT content_hash FROM activities WHERE content_hash IS NOT NULL")
    hashes = {row[0] for row in cursor.fetchall()}

    cursor = conn.execute(
        "SELECT session_id, timestamp_epoch, tool_name FROM activities WHERE content_hash IS NULL"
    )
    for row in cursor.fetchall():
        hashes.add(compute_activity_hash(str(row[0]), int(row[1]), str(row[2])))

    return hashes
