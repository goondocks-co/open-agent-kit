"""Saved task operations for activity store.

Handles persistence of reusable task templates in SQLite.
These can be run on-demand or scheduled via cron (future feature).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def create_task(
    store: ActivityStore,
    name: str,
    agent_name: str,
    task: str,
    description: str | None = None,
    schedule_cron: str | None = None,
) -> str:
    """Create a new saved task template.

    Args:
        store: ActivityStore instance.
        name: Human-readable name for the task.
        agent_name: Name of the agent to run.
        task: The task description/prompt.
        description: Optional description of what this task does.
        schedule_cron: Optional cron expression for scheduling.

    Returns:
        The ID of the created task.
    """
    task_id = str(uuid4())
    now = datetime.now()
    now_iso = now.isoformat()
    now_epoch = int(now.timestamp())

    with store._transaction() as conn:
        conn.execute(
            """
            INSERT INTO saved_tasks (
                id, name, description, agent_name, task,
                schedule_cron, schedule_enabled,
                created_at, created_at_epoch,
                updated_at, updated_at_epoch
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                name,
                description,
                agent_name,
                task,
                schedule_cron,
                1 if schedule_cron else 0,
                now_iso,
                now_epoch,
                now_iso,
                now_epoch,
            ),
        )

    logger.debug(f"Created saved task: {task_id} ({name})")
    return task_id


def get_task(store: ActivityStore, task_id: str) -> dict[str, Any] | None:
    """Get a saved task by ID.

    Args:
        store: ActivityStore instance.
        task_id: Task identifier.

    Returns:
        Task data as dict, or None if not found.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT * FROM saved_tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()

    if not row:
        return None

    return _row_to_dict(row)


def update_task(
    store: ActivityStore,
    task_id: str,
    name: str | None = None,
    description: str | None = None,
    task: str | None = None,
    schedule_cron: str | None = None,
    schedule_enabled: bool | None = None,
    last_run_at: datetime | None = None,
    last_run_id: str | None = None,
    increment_runs: bool = False,
) -> None:
    """Update a saved task.

    Args:
        store: ActivityStore instance.
        task_id: Task identifier.
        name: New name.
        description: New description.
        task: New task prompt.
        schedule_cron: New cron expression.
        schedule_enabled: Enable/disable scheduling.
        last_run_at: When this task was last run.
        last_run_id: ID of the last run triggered by this task.
        increment_runs: If True, increment total_runs counter.
    """
    updates: list[str] = []
    params: list[Any] = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)

    if description is not None:
        updates.append("description = ?")
        params.append(description)

    if task is not None:
        updates.append("task = ?")
        params.append(task)

    if schedule_cron is not None:
        updates.append("schedule_cron = ?")
        params.append(schedule_cron)

    if schedule_enabled is not None:
        updates.append("schedule_enabled = ?")
        params.append(1 if schedule_enabled else 0)

    if last_run_at is not None:
        updates.append("last_run_at = ?")
        params.append(last_run_at.isoformat())
        updates.append("last_run_id = ?")
        params.append(last_run_id)

    if increment_runs:
        updates.append("total_runs = total_runs + 1")

    if not updates:
        return

    # Always update the updated_at timestamp
    now = datetime.now()
    updates.append("updated_at = ?")
    params.append(now.isoformat())
    updates.append("updated_at_epoch = ?")
    params.append(int(now.timestamp()))

    params.append(task_id)

    with store._transaction() as conn:
        conn.execute(
            f"UPDATE saved_tasks SET {', '.join(updates)} WHERE id = ?",  # noqa: S608
            params,
        )

    logger.debug(f"Updated saved task: {task_id}")


def list_tasks(
    store: ActivityStore,
    limit: int = 50,
    offset: int = 0,
    agent_name: str | None = None,
    scheduled_only: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """List saved tasks with optional filtering.

    Args:
        store: ActivityStore instance.
        limit: Maximum tasks to return.
        offset: Pagination offset.
        agent_name: Filter by agent name.
        scheduled_only: If True, only return tasks with schedules enabled.

    Returns:
        Tuple of (tasks list, total count).
    """
    conn = store._get_connection()

    # Build WHERE clause
    conditions: list[str] = []
    params: list[Any] = []

    if agent_name:
        conditions.append("agent_name = ?")
        params.append(agent_name)

    if scheduled_only:
        conditions.append("schedule_enabled = 1")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Get total count
    count_sql = f"SELECT COUNT(*) FROM saved_tasks {where_clause}"  # noqa: S608
    cursor = conn.execute(count_sql, params)
    total = cursor.fetchone()[0]

    # Get paginated results
    query_sql = f"""
        SELECT * FROM saved_tasks
        {where_clause}
        ORDER BY updated_at_epoch DESC
        LIMIT ? OFFSET ?
    """  # noqa: S608
    cursor = conn.execute(query_sql, [*params, limit, offset])

    tasks = [_row_to_dict(row) for row in cursor.fetchall()]

    return tasks, total


def delete_task(store: ActivityStore, task_id: str) -> bool:
    """Delete a saved task.

    Args:
        store: ActivityStore instance.
        task_id: Task identifier.

    Returns:
        True if deleted, False if not found.
    """
    with store._transaction() as conn:
        cursor = conn.execute("DELETE FROM saved_tasks WHERE id = ?", (task_id,))
        deleted = cursor.rowcount > 0

    if deleted:
        logger.debug(f"Deleted saved task: {task_id}")

    return deleted


def get_due_tasks(store: ActivityStore) -> list[dict[str, Any]]:
    """Get tasks that are due to run based on their schedule.

    This is used by the cron scheduler to find tasks to execute.

    Args:
        store: ActivityStore instance.

    Returns:
        List of tasks due to run.
    """
    conn = store._get_connection()
    now_iso = datetime.now().isoformat()

    cursor = conn.execute(
        """
        SELECT * FROM saved_tasks
        WHERE schedule_enabled = 1
          AND schedule_cron IS NOT NULL
          AND (next_run_at IS NULL OR next_run_at <= ?)
        ORDER BY next_run_at ASC
        """,
        (now_iso,),
    )

    return [_row_to_dict(row) for row in cursor.fetchall()]


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a database row to a dictionary."""
    data = dict(row)

    # Convert schedule_enabled to boolean
    data["schedule_enabled"] = bool(data.get("schedule_enabled", 0))

    return data
