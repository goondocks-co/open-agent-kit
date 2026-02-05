"""Schedule operations for ActivityStore.

Database operations for agent schedule management.
The database is now the sole source of truth for schedules (YAML support deprecated).
All schedule definitions (cron, description) and runtime state live in SQLite.
"""

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    SCHEDULE_TRIGGER_CRON,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import (
        ActivityStore,
    )

logger = logging.getLogger(__name__)


def create_schedule(
    store: "ActivityStore",
    task_name: str,
    cron_expression: str | None = None,
    description: str | None = None,
    trigger_type: str = SCHEDULE_TRIGGER_CRON,
    next_run_at: datetime | None = None,
) -> None:
    """Create a new schedule record.

    Args:
        store: ActivityStore instance.
        task_name: Name of the agent task.
        cron_expression: Cron expression (e.g., '0 0 * * MON').
        description: Human-readable schedule description.
        trigger_type: Type of trigger ('cron' or 'manual').
        next_run_at: Next scheduled run time.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_machine_identifier,
    )

    now = datetime.now()
    now_epoch = int(time.time())

    next_run_at_str = next_run_at.isoformat() if next_run_at else None
    next_run_at_epoch = int(next_run_at.timestamp()) if next_run_at else None
    machine_id = get_machine_identifier()

    with store._transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_schedules (
                task_name, enabled, cron_expression, description, trigger_type,
                next_run_at, next_run_at_epoch,
                created_at, created_at_epoch, updated_at, updated_at_epoch,
                source_machine_id
            )
            VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_name,
                cron_expression,
                description,
                trigger_type,
                next_run_at_str,
                next_run_at_epoch,
                now.isoformat(),
                now_epoch,
                now.isoformat(),
                now_epoch,
                machine_id,
            ),
        )
        logger.debug(
            f"Created schedule for task '{task_name}': "
            f"cron={cron_expression}, trigger_type={trigger_type}"
        )


def get_schedule(store: "ActivityStore", task_name: str) -> dict[str, Any] | None:
    """Get a schedule by task name.

    Args:
        store: ActivityStore instance.
        task_name: Name of the agent task.

    Returns:
        Schedule record as dict, or None if not found.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT task_name, enabled, cron_expression, description, trigger_type,
               last_run_at, last_run_at_epoch, last_run_id,
               next_run_at, next_run_at_epoch,
               created_at, created_at_epoch, updated_at, updated_at_epoch,
               source_machine_id
        FROM agent_schedules
        WHERE task_name = ?
        """,
        (task_name,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "task_name": row["task_name"],
        "enabled": bool(row["enabled"]),
        "cron_expression": row["cron_expression"],
        "description": row["description"],
        "trigger_type": row["trigger_type"] or SCHEDULE_TRIGGER_CRON,
        "last_run_at": row["last_run_at"],
        "last_run_at_epoch": row["last_run_at_epoch"],
        "last_run_id": row["last_run_id"],
        "next_run_at": row["next_run_at"],
        "next_run_at_epoch": row["next_run_at_epoch"],
        "created_at": row["created_at"],
        "created_at_epoch": row["created_at_epoch"],
        "updated_at": row["updated_at"],
        "updated_at_epoch": row["updated_at_epoch"],
        "source_machine_id": row["source_machine_id"],
    }


def update_schedule(
    store: "ActivityStore",
    task_name: str,
    enabled: bool | None = None,
    cron_expression: str | None = None,
    description: str | None = None,
    trigger_type: str | None = None,
    last_run_at: datetime | None = None,
    last_run_id: str | None = None,
    next_run_at: datetime | None = None,
) -> None:
    """Update a schedule record.

    Args:
        store: ActivityStore instance.
        task_name: Name of the agent task.
        enabled: Whether schedule is enabled.
        cron_expression: Cron expression to set.
        description: Description to set.
        trigger_type: Trigger type to set.
        last_run_at: When the schedule last ran.
        last_run_id: ID of the last run.
        next_run_at: Next scheduled run time.
    """
    updates: list[str] = []
    params: list[Any] = []

    now = datetime.now()
    now_epoch = int(time.time())

    if enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if enabled else 0)

    if cron_expression is not None:
        updates.append("cron_expression = ?")
        params.append(cron_expression)

    if description is not None:
        updates.append("description = ?")
        params.append(description)

    if trigger_type is not None:
        updates.append("trigger_type = ?")
        params.append(trigger_type)

    if last_run_at is not None:
        updates.append("last_run_at = ?")
        params.append(last_run_at.isoformat())
        updates.append("last_run_at_epoch = ?")
        params.append(int(last_run_at.timestamp()))

    if last_run_id is not None:
        updates.append("last_run_id = ?")
        params.append(last_run_id)

    if next_run_at is not None:
        updates.append("next_run_at = ?")
        params.append(next_run_at.isoformat())
        updates.append("next_run_at_epoch = ?")
        params.append(int(next_run_at.timestamp()))

    # Always update timestamp
    updates.append("updated_at = ?")
    params.append(now.isoformat())
    updates.append("updated_at_epoch = ?")
    params.append(now_epoch)

    if not updates:
        return

    params.append(task_name)

    with store._transaction() as conn:
        conn.execute(
            f"UPDATE agent_schedules SET {', '.join(updates)} WHERE task_name = ?",
            params,
        )
        logger.debug(f"Updated schedule for task '{task_name}'")


def list_schedules(
    store: "ActivityStore",
    enabled_only: bool = False,
) -> list[dict[str, Any]]:
    """List all schedules.

    Args:
        store: ActivityStore instance.
        enabled_only: If True, only return enabled schedules.

    Returns:
        List of schedule records.
    """
    conn = store._get_connection()

    query = """
        SELECT task_name, enabled, cron_expression, description, trigger_type,
               last_run_at, last_run_at_epoch, last_run_id,
               next_run_at, next_run_at_epoch,
               created_at, created_at_epoch, updated_at, updated_at_epoch,
               source_machine_id
        FROM agent_schedules
    """
    params: list[Any] = []

    if enabled_only:
        query += " WHERE enabled = 1"

    query += " ORDER BY task_name"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    return [
        {
            "task_name": row["task_name"],
            "enabled": bool(row["enabled"]),
            "cron_expression": row["cron_expression"],
            "description": row["description"],
            "trigger_type": row["trigger_type"] or SCHEDULE_TRIGGER_CRON,
            "last_run_at": row["last_run_at"],
            "last_run_at_epoch": row["last_run_at_epoch"],
            "last_run_id": row["last_run_id"],
            "next_run_at": row["next_run_at"],
            "next_run_at_epoch": row["next_run_at_epoch"],
            "created_at": row["created_at"],
            "created_at_epoch": row["created_at_epoch"],
            "updated_at": row["updated_at"],
            "updated_at_epoch": row["updated_at_epoch"],
            "source_machine_id": row["source_machine_id"],
        }
        for row in rows
    ]


def get_due_schedules(store: "ActivityStore") -> list[dict[str, Any]]:
    """Get schedules that are due to run.

    Returns schedules where:
    - enabled = 1
    - trigger_type = 'cron' (manual schedules are never auto-triggered)
    - next_run_at_epoch <= now

    Args:
        store: ActivityStore instance.

    Returns:
        List of due schedule records.
    """
    conn = store._get_connection()
    now_epoch = int(time.time())

    cursor = conn.execute(
        """
        SELECT task_name, enabled, cron_expression, description, trigger_type,
               last_run_at, last_run_at_epoch, last_run_id,
               next_run_at, next_run_at_epoch,
               created_at, created_at_epoch, updated_at, updated_at_epoch,
               source_machine_id
        FROM agent_schedules
        WHERE enabled = 1
          AND trigger_type = 'cron'
          AND next_run_at_epoch IS NOT NULL
          AND next_run_at_epoch <= ?
        ORDER BY next_run_at_epoch
        """,
        (now_epoch,),
    )
    rows = cursor.fetchall()

    return [
        {
            "task_name": row["task_name"],
            "enabled": bool(row["enabled"]),
            "cron_expression": row["cron_expression"],
            "description": row["description"],
            "trigger_type": row["trigger_type"] or SCHEDULE_TRIGGER_CRON,
            "last_run_at": row["last_run_at"],
            "last_run_at_epoch": row["last_run_at_epoch"],
            "last_run_id": row["last_run_id"],
            "next_run_at": row["next_run_at"],
            "next_run_at_epoch": row["next_run_at_epoch"],
            "created_at": row["created_at"],
            "created_at_epoch": row["created_at_epoch"],
            "updated_at": row["updated_at"],
            "updated_at_epoch": row["updated_at_epoch"],
            "source_machine_id": row["source_machine_id"],
        }
        for row in rows
    ]


def delete_schedule(store: "ActivityStore", task_name: str) -> bool:
    """Delete a schedule record.

    Args:
        store: ActivityStore instance.
        task_name: Name of the agent task.

    Returns:
        True if a record was deleted.
    """
    with store._transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM agent_schedules WHERE task_name = ?",
            (task_name,),
        )
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"Deleted schedule for task '{task_name}'")
        return deleted


def upsert_schedule(
    store: "ActivityStore",
    task_name: str,
    cron_expression: str | None = None,
    description: str | None = None,
    trigger_type: str = SCHEDULE_TRIGGER_CRON,
    next_run_at: datetime | None = None,
) -> None:
    """Create or update a schedule record.

    Args:
        store: ActivityStore instance.
        task_name: Name of the agent task.
        cron_expression: Cron expression (e.g., '0 0 * * MON').
        description: Human-readable schedule description.
        trigger_type: Type of trigger ('cron' or 'manual').
        next_run_at: Next scheduled run time.
    """
    existing = get_schedule(store, task_name)
    if existing:
        update_schedule(
            store,
            task_name,
            cron_expression=cron_expression,
            description=description,
            trigger_type=trigger_type,
            next_run_at=next_run_at,
        )
    else:
        create_schedule(
            store,
            task_name,
            cron_expression=cron_expression,
            description=description,
            trigger_type=trigger_type,
            next_run_at=next_run_at,
        )


def get_all_schedule_task_names(store: "ActivityStore") -> set[str]:
    """Get all schedule task names for dedup checking during import.

    Args:
        store: ActivityStore instance.

    Returns:
        Set of task_name values.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT task_name FROM agent_schedules")
    return {row[0] for row in cursor.fetchall()}
