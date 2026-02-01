"""Schedule operations for ActivityStore.

Database operations for agent schedule runtime state.
Schedule definitions (cron, description) live in YAML.
Runtime state (enabled, last_run, next_run) lives in SQLite.
"""

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import (
        ActivityStore,
    )

logger = logging.getLogger(__name__)


def create_schedule(
    store: "ActivityStore",
    instance_name: str,
    next_run_at: datetime | None = None,
) -> None:
    """Create a new schedule record.

    Args:
        store: ActivityStore instance.
        instance_name: Name of the agent instance.
        next_run_at: Next scheduled run time.
    """
    now = datetime.now()
    now_epoch = int(time.time())

    next_run_at_str = next_run_at.isoformat() if next_run_at else None
    next_run_at_epoch = int(next_run_at.timestamp()) if next_run_at else None

    with store._transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_schedules (
                instance_name, enabled, next_run_at, next_run_at_epoch,
                created_at, created_at_epoch, updated_at, updated_at_epoch
            )
            VALUES (?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_name,
                next_run_at_str,
                next_run_at_epoch,
                now.isoformat(),
                now_epoch,
                now.isoformat(),
                now_epoch,
            ),
        )
        logger.debug(f"Created schedule for instance '{instance_name}'")


def get_schedule(store: "ActivityStore", instance_name: str) -> dict[str, Any] | None:
    """Get a schedule by instance name.

    Args:
        store: ActivityStore instance.
        instance_name: Name of the agent instance.

    Returns:
        Schedule record as dict, or None if not found.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT instance_name, enabled, last_run_at, last_run_at_epoch,
               last_run_id, next_run_at, next_run_at_epoch,
               created_at, created_at_epoch, updated_at, updated_at_epoch
        FROM agent_schedules
        WHERE instance_name = ?
        """,
        (instance_name,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "instance_name": row["instance_name"],
        "enabled": bool(row["enabled"]),
        "last_run_at": row["last_run_at"],
        "last_run_at_epoch": row["last_run_at_epoch"],
        "last_run_id": row["last_run_id"],
        "next_run_at": row["next_run_at"],
        "next_run_at_epoch": row["next_run_at_epoch"],
        "created_at": row["created_at"],
        "created_at_epoch": row["created_at_epoch"],
        "updated_at": row["updated_at"],
        "updated_at_epoch": row["updated_at_epoch"],
    }


def update_schedule(
    store: "ActivityStore",
    instance_name: str,
    enabled: bool | None = None,
    last_run_at: datetime | None = None,
    last_run_id: str | None = None,
    next_run_at: datetime | None = None,
) -> None:
    """Update a schedule record.

    Args:
        store: ActivityStore instance.
        instance_name: Name of the agent instance.
        enabled: Whether schedule is enabled.
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

    params.append(instance_name)

    with store._transaction() as conn:
        conn.execute(
            f"UPDATE agent_schedules SET {', '.join(updates)} WHERE instance_name = ?",
            params,
        )
        logger.debug(f"Updated schedule for instance '{instance_name}'")


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
        SELECT instance_name, enabled, last_run_at, last_run_at_epoch,
               last_run_id, next_run_at, next_run_at_epoch,
               created_at, created_at_epoch, updated_at, updated_at_epoch
        FROM agent_schedules
    """
    params: list[Any] = []

    if enabled_only:
        query += " WHERE enabled = 1"

    query += " ORDER BY instance_name"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    return [
        {
            "instance_name": row["instance_name"],
            "enabled": bool(row["enabled"]),
            "last_run_at": row["last_run_at"],
            "last_run_at_epoch": row["last_run_at_epoch"],
            "last_run_id": row["last_run_id"],
            "next_run_at": row["next_run_at"],
            "next_run_at_epoch": row["next_run_at_epoch"],
            "created_at": row["created_at"],
            "created_at_epoch": row["created_at_epoch"],
            "updated_at": row["updated_at"],
            "updated_at_epoch": row["updated_at_epoch"],
        }
        for row in rows
    ]


def get_due_schedules(store: "ActivityStore") -> list[dict[str, Any]]:
    """Get schedules that are due to run.

    Returns schedules where:
    - enabled = 1
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
        SELECT instance_name, enabled, last_run_at, last_run_at_epoch,
               last_run_id, next_run_at, next_run_at_epoch,
               created_at, created_at_epoch, updated_at, updated_at_epoch
        FROM agent_schedules
        WHERE enabled = 1 AND next_run_at_epoch IS NOT NULL AND next_run_at_epoch <= ?
        ORDER BY next_run_at_epoch
        """,
        (now_epoch,),
    )
    rows = cursor.fetchall()

    return [
        {
            "instance_name": row["instance_name"],
            "enabled": bool(row["enabled"]),
            "last_run_at": row["last_run_at"],
            "last_run_at_epoch": row["last_run_at_epoch"],
            "last_run_id": row["last_run_id"],
            "next_run_at": row["next_run_at"],
            "next_run_at_epoch": row["next_run_at_epoch"],
            "created_at": row["created_at"],
            "created_at_epoch": row["created_at_epoch"],
            "updated_at": row["updated_at"],
            "updated_at_epoch": row["updated_at_epoch"],
        }
        for row in rows
    ]


def delete_schedule(store: "ActivityStore", instance_name: str) -> bool:
    """Delete a schedule record.

    Args:
        store: ActivityStore instance.
        instance_name: Name of the agent instance.

    Returns:
        True if a record was deleted.
    """
    with store._transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM agent_schedules WHERE instance_name = ?",
            (instance_name,),
        )
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"Deleted schedule for instance '{instance_name}'")
        return deleted


def upsert_schedule(
    store: "ActivityStore",
    instance_name: str,
    next_run_at: datetime | None = None,
) -> None:
    """Create or update a schedule record.

    Args:
        store: ActivityStore instance.
        instance_name: Name of the agent instance.
        next_run_at: Next scheduled run time.
    """
    existing = get_schedule(store, instance_name)
    if existing:
        update_schedule(store, instance_name, next_run_at=next_run_at)
    else:
        create_schedule(store, instance_name, next_run_at=next_run_at)
