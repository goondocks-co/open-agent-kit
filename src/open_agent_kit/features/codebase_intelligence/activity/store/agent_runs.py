"""Agent run operations for activity store.

Handles persistence of agent execution records (runs) in SQLite.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def create_run(
    store: ActivityStore,
    run_id: str,
    agent_name: str,
    task: str,
    status: str = "pending",
    project_config: dict[str, Any] | None = None,
    system_prompt_hash: str | None = None,
) -> None:
    """Create a new agent run record.

    Args:
        store: ActivityStore instance.
        run_id: Unique run identifier.
        agent_name: Name of the agent being run.
        task: Task description given to the agent.
        status: Initial status (default: pending).
        project_config: Snapshot of project configuration.
        system_prompt_hash: Hash of the system prompt used.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_machine_identifier,
    )

    now = datetime.now()
    now_iso = now.isoformat()
    now_epoch = int(now.timestamp())
    machine_id = get_machine_identifier()

    config_json = json.dumps(project_config) if project_config else None

    with store._transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_runs (
                id, agent_name, task, status,
                created_at, created_at_epoch,
                project_config, system_prompt_hash, source_machine_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                agent_name,
                task,
                status,
                now_iso,
                now_epoch,
                config_json,
                system_prompt_hash,
                machine_id,
            ),
        )

    logger.debug(f"Created agent run: {run_id} for {agent_name}")


def get_run(store: ActivityStore, run_id: str) -> dict[str, Any] | None:
    """Get an agent run by ID.

    Args:
        store: ActivityStore instance.
        run_id: Run identifier.

    Returns:
        Run data as dict, or None if not found.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
    row = cursor.fetchone()

    if not row:
        return None

    return _row_to_dict(row)


def update_run(
    store: ActivityStore,
    run_id: str,
    status: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    result: str | None = None,
    error: str | None = None,
    turns_used: int | None = None,
    cost_usd: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    files_created: list[str] | None = None,
    files_modified: list[str] | None = None,
    files_deleted: list[str] | None = None,
    warnings: list[str] | None = None,
) -> None:
    """Update an agent run record.

    Args:
        store: ActivityStore instance.
        run_id: Run identifier.
        status: New status.
        started_at: When execution started.
        completed_at: When execution completed.
        result: Result/output from the agent.
        error: Error message if failed.
        turns_used: Number of turns used.
        cost_usd: Cost in USD.
        input_tokens: Input tokens used.
        output_tokens: Output tokens generated.
        files_created: List of created file paths.
        files_modified: List of modified file paths.
        files_deleted: List of deleted file paths.
        warnings: List of warning messages.
    """
    updates: list[str] = []
    params: list[Any] = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)

    if started_at is not None:
        updates.append("started_at = ?")
        params.append(started_at.isoformat())
        updates.append("started_at_epoch = ?")
        params.append(int(started_at.timestamp()))

    if completed_at is not None:
        updates.append("completed_at = ?")
        params.append(completed_at.isoformat())
        updates.append("completed_at_epoch = ?")
        params.append(int(completed_at.timestamp()))

    if result is not None:
        updates.append("result = ?")
        params.append(result)

    if error is not None:
        updates.append("error = ?")
        params.append(error)

    if turns_used is not None:
        updates.append("turns_used = ?")
        params.append(turns_used)

    if cost_usd is not None:
        updates.append("cost_usd = ?")
        params.append(cost_usd)

    if input_tokens is not None:
        updates.append("input_tokens = ?")
        params.append(input_tokens)

    if output_tokens is not None:
        updates.append("output_tokens = ?")
        params.append(output_tokens)

    if files_created is not None:
        updates.append("files_created = ?")
        params.append(json.dumps(files_created))

    if files_modified is not None:
        updates.append("files_modified = ?")
        params.append(json.dumps(files_modified))

    if files_deleted is not None:
        updates.append("files_deleted = ?")
        params.append(json.dumps(files_deleted))

    if warnings is not None:
        updates.append("warnings = ?")
        params.append(json.dumps(warnings))

    if not updates:
        return

    params.append(run_id)

    with store._transaction() as conn:
        conn.execute(
            f"UPDATE agent_runs SET {', '.join(updates)} WHERE id = ?",  # noqa: S608
            params,
        )

    logger.debug(f"Updated agent run: {run_id}")


def list_runs(
    store: ActivityStore,
    limit: int = 20,
    offset: int = 0,
    agent_name: str | None = None,
    status: str | None = None,
    created_after_epoch: int | None = None,
    created_before_epoch: int | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[dict[str, Any]], int]:
    """List agent runs with optional filtering and sorting.

    Args:
        store: ActivityStore instance.
        limit: Maximum runs to return.
        offset: Pagination offset.
        agent_name: Filter by agent name.
        status: Filter by status.
        created_after_epoch: Filter by creation time (epoch) - inclusive.
        created_before_epoch: Filter by creation time (epoch) - exclusive.
        sort_by: Sort field (created_at, duration, cost).
        sort_order: Sort order (asc, desc).

    Returns:
        Tuple of (runs list, total count).
    """
    conn = store._get_connection()

    # Build WHERE clause
    conditions: list[str] = []
    params: list[Any] = []

    if agent_name:
        conditions.append("agent_name = ?")
        params.append(agent_name)

    if status:
        conditions.append("status = ?")
        params.append(status)

    if created_after_epoch:
        conditions.append("created_at_epoch >= ?")
        params.append(created_after_epoch)

    if created_before_epoch:
        conditions.append("created_at_epoch < ?")
        params.append(created_before_epoch)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Map sort_by to column
    sort_column_map = {
        "created_at": "created_at_epoch",
        "duration": "(COALESCE(completed_at_epoch, 0) - COALESCE(started_at_epoch, 0))",
        "cost": "COALESCE(cost_usd, 0)",
    }
    sort_column = sort_column_map.get(sort_by, "created_at_epoch")
    order = "DESC" if sort_order.lower() == "desc" else "ASC"

    # Get total count
    count_sql = f"SELECT COUNT(*) FROM agent_runs {where_clause}"  # noqa: S608
    cursor = conn.execute(count_sql, params)
    total = cursor.fetchone()[0]

    # Get paginated results
    query_sql = f"""
        SELECT * FROM agent_runs
        {where_clause}
        ORDER BY {sort_column} {order}
        LIMIT ? OFFSET ?
    """  # noqa: S608
    cursor = conn.execute(query_sql, [*params, limit, offset])

    runs = [_row_to_dict(row) for row in cursor.fetchall()]

    return runs, total


def delete_run(store: ActivityStore, run_id: str) -> bool:
    """Delete an agent run.

    Args:
        store: ActivityStore instance.
        run_id: Run identifier.

    Returns:
        True if deleted, False if not found.
    """
    with store._transaction() as conn:
        cursor = conn.execute("DELETE FROM agent_runs WHERE id = ?", (run_id,))
        deleted = cursor.rowcount > 0

    if deleted:
        logger.debug(f"Deleted agent run: {run_id}")

    return deleted


def bulk_delete_runs(
    store: ActivityStore,
    agent_name: str | None = None,
    status: str | None = None,
    before_epoch: int | None = None,
    keep_recent: int = 10,
) -> int:
    """Bulk delete agent runs with optional filtering and retention policy.

    Only deletes runs in terminal states (completed, failed, cancelled, timeout).
    Always keeps the N most recent runs per agent to maintain history.

    Args:
        store: ActivityStore instance.
        agent_name: Filter by agent name (optional).
        status: Filter by status (optional, must be terminal).
        before_epoch: Delete runs created before this epoch timestamp (optional).
        keep_recent: Keep this many most recent runs per agent (default 10).

    Returns:
        Number of runs deleted.
    """
    terminal_statuses = ("completed", "failed", "cancelled", "timeout")

    # Build conditions
    conditions = ["status IN (?, ?, ?, ?)"]
    params: list[Any] = list(terminal_statuses)

    if agent_name:
        conditions.append("agent_name = ?")
        params.append(agent_name)

    if status:
        if status not in terminal_statuses:
            logger.warning(f"Cannot bulk delete runs with non-terminal status: {status}")
            return 0
        conditions.append("status = ?")
        params.append(status)

    if before_epoch:
        conditions.append("created_at_epoch < ?")
        params.append(before_epoch)

    where_clause = " AND ".join(conditions)

    # First, identify runs to delete while respecting keep_recent per agent
    # This query finds all deletable runs except the N most recent per agent
    delete_sql = f"""
        DELETE FROM agent_runs
        WHERE id IN (
            SELECT id FROM (
                SELECT id, agent_name,
                       ROW_NUMBER() OVER (
                           PARTITION BY agent_name
                           ORDER BY created_at_epoch DESC
                       ) as rn
                FROM agent_runs
                WHERE {where_clause}
            )
            WHERE rn > ?
        )
    """  # noqa: S608

    with store._transaction() as conn:
        cursor = conn.execute(delete_sql, [*params, keep_recent])
        deleted_count = cursor.rowcount

    if deleted_count > 0:
        logger.info(
            f"Bulk deleted {deleted_count} agent runs "
            f"(agent={agent_name}, status={status}, keep_recent={keep_recent})"
        )

    return deleted_count


def recover_stale_runs(
    store: ActivityStore,
    buffer_seconds: int = 300,
    default_timeout_seconds: int = 600,
) -> list[str]:
    """Mark runs stuck in RUNNING status as FAILED.

    A run is considered stale if:
    - status = 'running'
    - started_at_epoch + default_timeout + buffer < now

    This handles the case where the daemon crashes during agent execution,
    leaving runs in RUNNING state indefinitely.

    Args:
        store: ActivityStore instance.
        buffer_seconds: Grace period beyond expected timeout (default 5 min).
        default_timeout_seconds: Default timeout if not tracked per-run (default 10 min).

    Returns:
        List of recovered run IDs.
    """
    import time

    now_epoch = int(time.time())
    # Consider stale if started_at + timeout + buffer < now
    # Since we don't track per-run timeout, use default + buffer as cutoff
    stale_threshold = now_epoch - (default_timeout_seconds + buffer_seconds)

    conn = store._get_connection()

    # Find stale runs
    cursor = conn.execute(
        """
        SELECT id, agent_name, started_at_epoch
        FROM agent_runs
        WHERE status = 'running'
          AND started_at_epoch IS NOT NULL
          AND started_at_epoch < ?
        """,
        (stale_threshold,),
    )
    stale_runs = cursor.fetchall()

    if not stale_runs:
        return []

    recovered_ids: list[str] = []
    now = datetime.now()

    for row in stale_runs:
        run_id = row[0]
        agent_name = row[1]
        started_epoch = row[2]

        # Calculate how long the run was stuck
        stuck_seconds = now_epoch - started_epoch

        update_run(
            store,
            run_id=run_id,
            status="failed",
            completed_at=now,
            error=f"Recovered by watchdog - exceeded timeout (stuck for {stuck_seconds}s)",
        )
        recovered_ids.append(run_id)
        logger.warning(
            f"Recovered stale agent run '{run_id}' for '{agent_name}' "
            f"(stuck for {stuck_seconds}s)"
        )

    return recovered_ids


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a database row to a dictionary.

    Also deserializes JSON fields.
    """
    data = dict(row)

    # Parse JSON fields
    for field in ["files_created", "files_modified", "files_deleted", "warnings"]:
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                data[field] = []
        else:
            data[field] = []

    if data.get("project_config"):
        try:
            data["project_config"] = json.loads(data["project_config"])
        except (json.JSONDecodeError, TypeError):
            data["project_config"] = None

    return data
