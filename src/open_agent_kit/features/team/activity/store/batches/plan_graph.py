"""Plan source linking operations for cross-session plan tracking.

Link implementation batches back to their source plans across session lineage.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.team.activity.store.models import (
    PromptBatch,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def find_source_plan_batch(
    store: ActivityStore,
    session_id: str,
) -> PromptBatch | None:
    """Find the source plan batch for a session.

    Looks through the session's parent chain to find the most recent
    plan batch. This links implementation sessions back to their
    planning sessions.

    Args:
        store: The ActivityStore instance.
        session_id: Session to find plan for.

    Returns:
        Plan PromptBatch if found, None otherwise.
    """
    # Import here to avoid circular imports
    from open_agent_kit.features.team.activity.store.sessions import (
        get_session_lineage,
    )

    # Get session lineage (includes current session)
    lineage = get_session_lineage(store, session_id, max_depth=5)

    for session in lineage:
        # Look for plan batches in this session
        conn = store._get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM prompt_batches
            WHERE session_id = ?
              AND source_type = 'plan'
              AND plan_content IS NOT NULL
            ORDER BY created_at_epoch DESC
            LIMIT 1
            """,
            (session.id,),
        )
        row = cursor.fetchone()
        if row:
            plan_batch = PromptBatch.from_row(row)
            logger.debug(
                f"Found source plan batch {plan_batch.id} in session {session.id[:8]}... "
                f"for target session {session_id[:8]}..."
            )
            return plan_batch

    return None


def get_plan_implementations(
    store: ActivityStore,
    plan_batch_id: int,
    limit: int = 50,
) -> list[PromptBatch]:
    """Get all prompt batches that implement a given plan.

    Finds batches that have source_plan_batch_id pointing to this plan,
    allowing you to see all implementation activities derived from a plan.

    Args:
        store: The ActivityStore instance.
        plan_batch_id: The plan batch to find implementations for.
        limit: Maximum batches to return.

    Returns:
        List of PromptBatch objects implementing this plan.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM prompt_batches
        WHERE source_plan_batch_id = ?
        ORDER BY created_at_epoch ASC
        LIMIT ?
        """,
        (plan_batch_id, limit),
    )
    return [PromptBatch.from_row(row) for row in cursor.fetchall()]


def link_batch_to_source_plan(
    store: ActivityStore,
    batch_id: int,
    source_plan_batch_id: int,
) -> None:
    """Link a prompt batch to its source plan.

    Args:
        store: The ActivityStore instance.
        batch_id: Batch to link.
        source_plan_batch_id: Plan batch being implemented.
    """
    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE prompt_batches
            SET source_plan_batch_id = ?
            WHERE id = ?
            """,
            (source_plan_batch_id, batch_id),
        )
    logger.debug(f"Linked batch {batch_id} to source plan {source_plan_batch_id}")


def auto_link_batch_to_plan(
    store: ActivityStore,
    batch_id: int,
    session_id: str,
) -> int | None:
    """Automatically link a batch to its source plan if found.

    Searches the session's parent chain for a plan batch and links
    if found. Call this when creating implementation batches.

    Args:
        store: The ActivityStore instance.
        batch_id: Batch to potentially link.
        session_id: Session the batch belongs to.

    Returns:
        Source plan batch ID if linked, None otherwise.
    """
    source_plan = find_source_plan_batch(store, session_id)
    if source_plan and source_plan.id:
        link_batch_to_source_plan(store, batch_id, source_plan.id)
        return source_plan.id
    return None
