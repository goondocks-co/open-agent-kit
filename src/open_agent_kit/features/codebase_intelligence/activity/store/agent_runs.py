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
    files_created: list[str] | None = None,
    files_modified: list[str] | None = None,
    files_deleted: list[str] | None = None,
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
        files_created: List of created file paths.
        files_modified: List of modified file paths.
        files_deleted: List of deleted file paths.
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

    if files_created is not None:
        updates.append("files_created = ?")
        params.append(json.dumps(files_created))

    if files_modified is not None:
        updates.append("files_modified = ?")
        params.append(json.dumps(files_modified))

    if files_deleted is not None:
        updates.append("files_deleted = ?")
        params.append(json.dumps(files_deleted))

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
) -> tuple[list[dict[str, Any]], int]:
    """List agent runs with optional filtering.

    Args:
        store: ActivityStore instance.
        limit: Maximum runs to return.
        offset: Pagination offset.
        agent_name: Filter by agent name.
        status: Filter by status.

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

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Get total count
    count_sql = f"SELECT COUNT(*) FROM agent_runs {where_clause}"  # noqa: S608
    cursor = conn.execute(count_sql, params)
    total = cursor.fetchone()[0]

    # Get paginated results
    query_sql = f"""
        SELECT * FROM agent_runs
        {where_clause}
        ORDER BY created_at_epoch DESC
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


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a database row to a dictionary.

    Also deserializes JSON fields.
    """
    data = dict(row)

    # Parse JSON fields
    for field in ["files_created", "files_modified", "files_deleted"]:
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
