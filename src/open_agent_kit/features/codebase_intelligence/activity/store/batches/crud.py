"""Prompt batch CRUD operations.

Create, read, update, and lifecycle management for prompt batches.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    PromptBatch,
)
from open_agent_kit.features.codebase_intelligence.utils.redact import redact_secrets

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def create_prompt_batch(
    store: ActivityStore,
    session_id: str,
    user_prompt: str | None = None,
    source_type: str = "user",
    plan_file_path: str | None = None,
    plan_content: str | None = None,
    agent: str | None = None,
) -> PromptBatch:
    """Create a new prompt batch (when user submits a prompt).

    Args:
        store: The ActivityStore instance.
        session_id: Parent session ID.
        user_prompt: Full user prompt text (up to 10K chars).
        source_type: Source type (user, agent_notification, plan, system).
        plan_file_path: Path to plan file (for source_type='plan').
        plan_content: Plan content (extracted from prompt or written to file).
        agent: Agent name for session recreation if needed.

    Returns:
        Created PromptBatch with assigned ID.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        ensure_session_exists,
        reactivate_session_if_needed,
    )

    # Reactivate session if it was completed (e.g., by stale session recovery).
    # This ensures sessions seamlessly resume when new prompts arrive after a gap.
    # Performant: single UPDATE that only affects completed sessions (no-op if active).
    reactivate_session_if_needed(store, session_id)

    # Ensure session exists (handles deleted sessions from empty session cleanup).
    # When an empty session is deleted by recover_stale_sessions and a prompt
    # later arrives, we seamlessly recreate the session.
    if agent:
        ensure_session_exists(store, session_id, agent)

    # Get current prompt count for this session
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) as count FROM prompt_batches WHERE session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    prompt_number = (row["count"] or 0) + 1

    batch = PromptBatch(
        session_id=session_id,
        prompt_number=prompt_number,
        user_prompt=user_prompt,
        started_at=datetime.now(),
        source_type=source_type,
        plan_file_path=plan_file_path,
        plan_content=plan_content,
        source_machine_id=store.machine_id,
    )

    with store._transaction() as conn:
        row_data = batch.to_row()
        cursor = conn.execute(
            """
            INSERT INTO prompt_batches (session_id, prompt_number, user_prompt,
                                       started_at, status, activity_count, processed,
                                       classification, source_type, plan_file_path,
                                       plan_content, created_at_epoch, source_machine_id,
                                       content_hash)
            VALUES (:session_id, :prompt_number, :user_prompt,
                    :started_at, :status, :activity_count, :processed,
                    :classification, :source_type, :plan_file_path,
                    :plan_content, :created_at_epoch, :source_machine_id,
                    :content_hash)
            """,
            row_data,
        )
        batch.id = cursor.lastrowid

        # Update session prompt count
        conn.execute(
            "UPDATE sessions SET prompt_count = prompt_count + 1 WHERE id = ?",
            (session_id,),
        )

    logger.debug(
        f"Created prompt batch {batch.id} (prompt #{prompt_number}, source={source_type}) "
        f"for session {session_id}"
    )
    return batch


def get_prompt_batch(store: ActivityStore, batch_id: int) -> PromptBatch | None:
    """Get prompt batch by ID."""
    conn = store._get_connection()
    cursor = conn.execute("SELECT * FROM prompt_batches WHERE id = ?", (batch_id,))
    row = cursor.fetchone()
    return PromptBatch.from_row(row) if row else None


def get_session_plan_batch(
    store: ActivityStore,
    session_id: str,
    plan_file_path: str | None = None,
) -> PromptBatch | None:
    """Get the most recent plan batch in the CURRENT session (not parents).

    Used when ExitPlanMode is detected to find the plan batch to update
    with the final approved content from disk, and when the Write hook
    checks for an existing plan batch to update in place (avoiding
    duplicate entries for iterative plan refinements).

    Args:
        store: The ActivityStore instance.
        session_id: Session to query (current session only, not parent chain).
        plan_file_path: Optional file path to filter by. When provided,
            only returns a plan batch matching this exact file path.
            Used by the Write hook to consolidate iterations of the
            same plan file into a single batch.

    Returns:
        Most recent plan PromptBatch if one exists, None otherwise.
    """
    conn = store._get_connection()

    if plan_file_path:
        cursor = conn.execute(
            """
            SELECT * FROM prompt_batches
            WHERE session_id = ?
              AND source_type = 'plan'
              AND plan_file_path = ?
            ORDER BY created_at_epoch DESC, id DESC
            LIMIT 1
            """,
            (session_id, plan_file_path),
        )
    else:
        cursor = conn.execute(
            """
            SELECT * FROM prompt_batches
            WHERE session_id = ?
              AND source_type = 'plan'
              AND plan_file_path IS NOT NULL
            ORDER BY created_at_epoch DESC, id DESC
            LIMIT 1
            """,
            (session_id,),
        )

    row = cursor.fetchone()
    return PromptBatch.from_row(row) if row else None


def get_active_prompt_batch(store: ActivityStore, session_id: str) -> PromptBatch | None:
    """Get the current active prompt batch for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to query.

    Returns:
        Active PromptBatch if one exists, None otherwise.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM prompt_batches
        WHERE session_id = ? AND status = 'active'
        ORDER BY prompt_number DESC
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    return PromptBatch.from_row(row) if row else None


def get_latest_prompt_batch(store: ActivityStore, session_id: str) -> PromptBatch | None:
    """Get the most recent prompt batch for a session regardless of status.

    Unlike ``get_active_prompt_batch`` (which filters on ``status='active'``),
    this returns the latest batch even if it was already completed.  This is
    used by the dual-fire stop handler: the first fire finalizes the active
    batch, so the second fire (which carries the ``transcript_path``) needs
    to find the just-completed batch.

    Args:
        store: The ActivityStore instance.
        session_id: Session to query.

    Returns:
        Most recent PromptBatch if one exists, None otherwise.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM prompt_batches
        WHERE session_id = ?
        ORDER BY prompt_number DESC
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    return PromptBatch.from_row(row) if row else None


def end_prompt_batch(store: ActivityStore, batch_id: int) -> None:
    """Mark a prompt batch as completed (when agent stops responding).

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch to end.
    """
    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE prompt_batches
            SET ended_at = ?, status = 'completed'
            WHERE id = ?
            """,
            (datetime.now().isoformat(), batch_id),
        )
    logger.debug(f"Ended prompt batch {batch_id}")


def reactivate_prompt_batch(store: ActivityStore, batch_id: int) -> None:
    """Reactivate a completed prompt batch (when tool activity continues).

    This handles cases where stuck batch recovery prematurely marked a batch
    as completed while Claude is still actively working on it.

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch to reactivate.
    """
    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE prompt_batches
            SET status = 'active', ended_at = NULL
            WHERE id = ?
            """,
            (batch_id,),
        )
    logger.debug(f"Reactivated prompt batch {batch_id}")


def update_prompt_batch_response(
    store: ActivityStore,
    batch_id: int,
    response_summary: str,
    max_length: int = 5000,
) -> None:
    """Update a prompt batch with the agent's response summary.

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch to update.
        response_summary: Agent's final response text.
        max_length: Maximum length to store (default 5000 chars).
    """
    truncated = response_summary[:max_length] if response_summary else None
    if truncated:
        truncated = redact_secrets(truncated)
    with store._transaction() as conn:
        conn.execute(
            "UPDATE prompt_batches SET response_summary = ? WHERE id = ?",
            (truncated, batch_id),
        )
    logger.debug(f"Updated response summary for batch {batch_id}")


def update_prompt_batch_source_type(
    store: ActivityStore,
    batch_id: int,
    source_type: str,
    plan_file_path: str | None = None,
    plan_content: str | None = None,
) -> None:
    """Update the source type for a prompt batch.

    Used when plan mode is detected mid-batch (e.g., Write to plans directory).

    Args:
        store: The ActivityStore instance.
        batch_id: Batch to update.
        source_type: New source type (user, agent_notification, plan, system).
        plan_file_path: Path to plan file (for source_type='plan').
        plan_content: Full plan content (for source_type='plan').
    """
    # Truncate plan content to max length
    if plan_content and len(plan_content) > PromptBatch.MAX_PLAN_CONTENT_LENGTH:
        plan_content = plan_content[: PromptBatch.MAX_PLAN_CONTENT_LENGTH]
    if plan_content:
        plan_content = redact_secrets(plan_content)

    with store._transaction() as conn:
        if plan_file_path or plan_content:
            conn.execute(
                """
                UPDATE prompt_batches
                SET source_type = ?, plan_file_path = ?, plan_content = ?
                WHERE id = ?
                """,
                (source_type, plan_file_path, plan_content, batch_id),
            )
        else:
            conn.execute(
                """
                UPDATE prompt_batches
                SET source_type = ?
                WHERE id = ?
                """,
                (source_type, batch_id),
            )
    logger.debug(f"Updated prompt batch {batch_id} source_type to {source_type}")


def mark_prompt_batch_processed(
    store: ActivityStore,
    batch_id: int,
    classification: str | None = None,
) -> None:
    """Mark prompt batch as processed.

    Args:
        store: The ActivityStore instance.
        batch_id: Batch to mark.
        classification: LLM classification result.
    """
    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE prompt_batches
            SET processed = TRUE, classification = ?
            WHERE id = ?
            """,
            (classification, batch_id),
        )
