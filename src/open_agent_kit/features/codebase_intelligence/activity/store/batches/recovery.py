"""Prompt batch recovery operations.

Recovery of stuck, orphaned, and stale prompt batches.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import RECOVERY_BATCH_PROMPT
from open_agent_kit.features.codebase_intelligence.utils.redact import redact_secrets

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def queue_batches_for_reprocessing(
    store: ActivityStore,
    batch_ids: list[int] | None = None,
    recover_stuck: bool = True,
) -> tuple[int, int]:
    """Recover stuck batches and reset processed flag for reprocessing.

    This is a two-step operation:
    1. Optionally mark stuck 'active' batches as 'completed'
    2. Reset the 'processed' flag on completed batches so the background
       processor will re-extract memories from them.

    Args:
        store: The ActivityStore instance.
        batch_ids: Optional list of specific batch IDs to reprocess.
            If not provided, all batches are eligible.
        recover_stuck: If True, also marks stuck 'active' batches as 'completed'.

    Returns:
        Tuple of (batches_recovered, batches_queued).
    """
    batches_recovered = 0
    batches_queued = 0

    with store._transaction() as conn:
        # Step 1: Recover stuck batches
        if recover_stuck:
            if batch_ids:
                placeholders = ",".join("?" * len(batch_ids))
                cursor = conn.execute(
                    f"UPDATE prompt_batches SET status = 'completed' WHERE id IN ({placeholders}) AND status = 'active'",
                    batch_ids,
                )
            else:
                cursor = conn.execute(
                    "UPDATE prompt_batches SET status = 'completed' WHERE status = 'active'"
                )
            batches_recovered = cursor.rowcount

        # Step 2: Reset processed flag on completed batches
        if batch_ids:
            placeholders = ",".join("?" * len(batch_ids))
            cursor = conn.execute(
                f"UPDATE prompt_batches SET processed = 0 WHERE id IN ({placeholders}) AND status = 'completed'",
                batch_ids,
            )
        else:
            cursor = conn.execute(
                "UPDATE prompt_batches SET processed = 0 WHERE status = 'completed'"
            )
        batches_queued = cursor.rowcount

    if batches_recovered > 0:
        logger.info(f"Recovered {batches_recovered} stuck batches")
    logger.info(f"Queued {batches_queued} prompt batches for memory reprocessing")

    return batches_recovered, batches_queued


def recover_stuck_batches(
    store: ActivityStore,
    timeout_seconds: int = 1800,
    project_root: str | None = None,
) -> int:
    """Auto-end batches stuck in 'active' status for too long.

    This handles cases where the session ended unexpectedly (crash, network
    disconnect) without calling the stop hook.

    Before marking batches as completed, attempts to capture the response_summary
    from the transcript file if available.

    Args:
        store: The ActivityStore instance.
        timeout_seconds: Batches active longer than this are auto-ended.
        project_root: Project root for resolving transcript paths.

    Returns:
        Number of batches recovered.
    """
    from pathlib import Path

    cutoff_epoch = time.time() - timeout_seconds

    # First, find stuck batches with their session info
    with store._transaction() as conn:
        cursor = conn.execute(
            """
            SELECT pb.id, pb.session_id, s.agent, s.project_root
            FROM prompt_batches pb
            JOIN sessions s ON pb.session_id = s.id
            WHERE pb.status = 'active' AND pb.created_at_epoch < ?
            """,
            (cutoff_epoch,),
        )
        stuck_batches = cursor.fetchall()

    if not stuck_batches:
        return 0

    recovered_ids = []

    # Try to capture response_summary for each stuck batch before completing
    for batch_id, session_id, agent, session_project_root in stuck_batches:
        response_summary = None

        # Try to capture response from transcript
        effective_root = session_project_root or project_root
        if effective_root and session_id:
            try:
                from open_agent_kit.features.codebase_intelligence.transcript import (
                    parse_transcript_response,
                )
                from open_agent_kit.features.codebase_intelligence.transcript_resolver import (
                    get_transcript_resolver,
                )

                resolver = get_transcript_resolver(Path(effective_root))
                result = resolver.resolve(
                    session_id=session_id,
                    agent_type=agent if agent != "unknown" else None,
                    project_root=effective_root,
                )
                if result.path and result.exists:
                    response_summary = parse_transcript_response(str(result.path))
                    if response_summary:
                        logger.debug(
                            f"[RECOVERY] Captured response_summary for stuck batch {batch_id}"
                        )
            except (OSError, ValueError, RuntimeError, ImportError, AttributeError) as e:
                logger.debug(f"Failed to capture response for stuck batch {batch_id}: {e}")

        # Redact secrets from response_summary before persistence
        if response_summary:
            response_summary = redact_secrets(response_summary)

        # Update batch: mark as completed and optionally set response_summary
        # Set ended_at to NOW for consistency with normal batch ending
        with store._transaction() as conn:
            if response_summary:
                conn.execute(
                    """
                    UPDATE prompt_batches
                    SET status = 'completed', ended_at = ?, response_summary = ?
                    WHERE id = ?
                    """,
                    (datetime.now().isoformat(), response_summary, batch_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE prompt_batches
                    SET status = 'completed', ended_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now().isoformat(), batch_id),
                )

        recovered_ids.append(batch_id)

    if recovered_ids:
        logger.info(
            f"Recovered {len(recovered_ids)} stuck batches "
            f"(active > {timeout_seconds}s): {recovered_ids}"
        )

    return len(recovered_ids)


def recover_orphaned_activities(store: ActivityStore) -> int:
    """Associate orphaned activities (NULL batch) with appropriate batches.

    For each orphaned activity, finds the most recent batch for that session
    and associates the activity with it. If no batch exists, creates a
    recovery batch.

    Args:
        store: The ActivityStore instance.

    Returns:
        Number of activities recovered.
    """
    conn = store._get_connection()

    # Find sessions with orphaned activities
    cursor = conn.execute("""
        SELECT DISTINCT session_id, COUNT(*) as orphan_count
        FROM activities
        WHERE prompt_batch_id IS NULL
        GROUP BY session_id
        """)
    orphan_sessions = cursor.fetchall()

    if not orphan_sessions:
        return 0

    total_recovered = 0

    for session_id, orphan_count in orphan_sessions:
        # Find the most recent batch for this session
        cursor = conn.execute(
            """
            SELECT id FROM prompt_batches
            WHERE session_id = ?
            ORDER BY created_at_epoch DESC
            LIMIT 1
            """,
            (session_id,),
        )
        batch_row = cursor.fetchone()

        if batch_row:
            batch_id = batch_row[0]
        else:
            # Create a continuation batch for this session (prompt_number=1 for consistency)
            now = time.time()
            with store._transaction() as tx_conn:
                tx_conn.execute(
                    """
                    INSERT INTO prompt_batches
                    (session_id, prompt_number, user_prompt, started_at, created_at_epoch,
                     status, source_machine_id)
                    VALUES (?, 1, ?, datetime(?, 'unixepoch'), ?, 'completed', ?)
                    """,
                    (session_id, RECOVERY_BATCH_PROMPT, now, now, store.machine_id),
                )
                cursor = tx_conn.execute("SELECT last_insert_rowid()")
                batch_id = cursor.fetchone()[0]
                logger.info(f"Created continuation batch {batch_id} for session {session_id}")

        # Get orphaned activities before updating (for plan detection)
        cursor = conn.execute(
            """
            SELECT tool_name, tool_input
            FROM activities
            WHERE session_id = ? AND prompt_batch_id IS NULL
            """,
            (session_id,),
        )
        orphaned_activities = cursor.fetchall()

        # Associate orphaned activities with the batch
        with store._transaction() as tx_conn:
            tx_conn.execute(
                """
                UPDATE activities
                SET prompt_batch_id = ?
                WHERE session_id = ? AND prompt_batch_id IS NULL
                """,
                (batch_id, session_id),
            )

        # Detect plans in recovered activities (fixes plan mode detection gap)
        # Plan detection was skipped at hook time because batch_id was None
        _detect_plans_in_recovered_activities(store, batch_id, orphaned_activities)

        logger.info(
            f"Recovered {orphan_count} orphaned activities for session "
            f"{session_id[:8]}... -> batch {batch_id}"
        )
        total_recovered += orphan_count

    return total_recovered


def _detect_plans_in_recovered_activities(
    store: ActivityStore,
    batch_id: int,
    activities: list[tuple[str, str | None]],
) -> None:
    """Detect and capture plan files from recovered orphaned activities.

    This fixes a gap where plan detection is skipped during plan mode because
    activities are stored with prompt_batch_id=None. When orphaned activities
    are later associated with a batch, we need to check for plan files.

    Args:
        store: The ActivityStore instance.
        batch_id: Batch the activities were associated with.
        activities: List of (tool_name, tool_input) tuples.
    """
    import json
    from pathlib import Path

    from open_agent_kit.features.codebase_intelligence.activity.store.batches.crud import (
        update_prompt_batch_source_type,
    )
    from open_agent_kit.features.codebase_intelligence.constants import (
        PROMPT_SOURCE_PLAN,
    )
    from open_agent_kit.features.codebase_intelligence.plan_detector import detect_plan

    for tool_name, tool_input_str in activities:
        if tool_name not in ("Write", "Read", "Edit"):
            continue

        # Parse tool_input JSON
        tool_input: dict[str, Any] = {}
        if tool_input_str:
            try:
                tool_input = json.loads(tool_input_str)
            except (json.JSONDecodeError, TypeError):
                continue

        file_path = tool_input.get("file_path", "")
        if not file_path:
            continue

        detection = detect_plan(file_path)
        if detection.is_plan:
            # Read plan content from disk instead of tool_input.
            # The stored tool_input is sanitized and contains "<N chars>"
            # instead of actual content. The file is the source of truth.
            plan_content = ""
            plan_path = Path(file_path)

            try:
                if plan_path.exists():
                    plan_content = plan_path.read_text(encoding="utf-8")
                    logger.debug(
                        f"Read plan content from disk: {file_path} ({len(plan_content)} chars)"
                    )
                else:
                    # File doesn't exist, can't recover content
                    logger.warning(f"Plan file not found for recovery: {file_path}")
                    # Skip this activity - we can't capture content from missing file
                    continue
            except (OSError, ValueError) as e:
                logger.warning(f"Failed to read plan file {file_path}: {e}")
                continue

            # Update batch with plan source type
            update_prompt_batch_source_type(
                store,
                batch_id,
                PROMPT_SOURCE_PLAN,
                plan_file_path=file_path,
                plan_content=plan_content,
            )

            logger.info(f"Detected plan in recovered activity: {file_path} -> batch {batch_id}")
            # Only capture first plan per batch
            break
