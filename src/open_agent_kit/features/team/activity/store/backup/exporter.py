"""Export database to SQL backup file."""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.features.team.activity.store.backup.hashes import (
    compute_activity_hash,
    compute_observation_hash,
    compute_prompt_batch_hash,
)
from open_agent_kit.features.team.activity.store.schema import SCHEMA_VERSION

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def export_to_sql(
    store: ActivityStore,
    output_path: Path,
    include_activities: bool = False,
) -> int:
    """Export valuable tables to SQL dump file with content hashes.

    Exports sessions, prompt_batches, and memory_observations to a SQL file
    that can be used to restore data after feature removal/reinstall.
    The file is text-based and can be committed to git.

    Each record includes a content_hash for cross-machine deduplication,
    allowing multiple developers' backups to be merged without duplicates.

    Origin Tracking: Only exports records that originated on this machine
    (source_machine_id matches current machine). This prevents backup file
    bloat when team members import each other's backups - each developer's
    backup only contains their own original work, not imported data.

    FK Integrity: Only exports records with valid foreign key references.
    Orphaned records (e.g., prompt_batches referencing deleted sessions)
    are skipped to ensure the backup can be cleanly restored.

    Args:
        store: The ActivityStore instance (provides machine_id via store.machine_id).
        output_path: Path to write SQL dump file.
        include_activities: If True, include activities table (can be large).

    Returns:
        Number of records exported.
    """
    machine_id = store.machine_id
    logger.info(
        f"Exporting database: include_activities={include_activities}, "
        f"machine={machine_id}, path={output_path}"
    )

    conn = store._get_connection()
    total_count = 0
    skipped_orphans = 0
    skipped_foreign = 0

    # Tables to export (order matters for foreign keys)
    # agent_schedules has no FKs - always export user's own schedules
    tables = ["sessions", "prompt_batches", "memory_observations"]
    if include_activities:
        tables.append("activities")
    tables.append("agent_schedules")
    tables.append("resolution_events")
    tables.append("governance_audit_events")

    # Build set of valid session IDs for FK validation
    # Only include sessions that originated on this machine (will be exported)
    valid_session_ids = {
        row[0]
        for row in conn.execute(
            "SELECT id FROM sessions WHERE source_machine_id = ?",
            (machine_id,),
        ).fetchall()
    }

    # Build set of valid prompt_batch IDs for FK validation
    # Only include batches that originated on this machine (will be exported)
    valid_batch_ids = {
        row[0]
        for row in conn.execute(
            "SELECT id FROM prompt_batches WHERE source_machine_id = ?",
            (machine_id,),
        ).fetchall()
    }

    # Count records from other machines (imported data that won't be re-exported)
    for table in tables:
        cursor = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE source_machine_id != ?",  # noqa: S608
            (machine_id,),
        )
        count = cursor.fetchone()[0]
        if count > 0:
            skipped_foreign += count
            logger.debug(f"Excluding {count} {table} records imported from other machines")

    # Generate INSERT statements
    lines: list[str] = []
    lines.append("-- OAK Team History Backup")
    lines.append(f"-- Exported: {datetime.now().isoformat()}")
    lines.append(f"-- Machine: {machine_id}")
    lines.append(f"-- Schema version: {SCHEMA_VERSION}")
    lines.append("")

    for table in tables:
        # Only export records that originated on this machine (origin tracking)
        # This prevents backup file bloat when importing from other team members
        cursor = conn.execute(
            f"SELECT * FROM {table} WHERE source_machine_id = ?",  # noqa: S608
            (machine_id,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        if rows:
            table_exported = 0
            table_skipped = 0
            table_lines: list[str] = []

            for row in rows:
                # Build row dict for hash computation and FK validation
                row_dict = dict(zip(columns, row, strict=False))

                # FK validation - skip orphaned records
                if table == "prompt_batches":
                    session_id = row_dict.get("session_id")
                    if session_id and session_id not in valid_session_ids:
                        table_skipped += 1
                        continue
                elif table == "memory_observations":
                    session_id = row_dict.get("session_id")
                    batch_id = row_dict.get("prompt_batch_id")
                    if session_id and session_id not in valid_session_ids:
                        table_skipped += 1
                        continue
                    if batch_id is not None and batch_id not in valid_batch_ids:
                        table_skipped += 1
                        continue
                elif table == "activities":
                    session_id = row_dict.get("session_id")
                    batch_id = row_dict.get("prompt_batch_id")
                    if session_id and session_id not in valid_session_ids:
                        table_skipped += 1
                        continue
                    if batch_id is not None and batch_id not in valid_batch_ids:
                        table_skipped += 1
                        continue
                elif table == "governance_audit_events":
                    session_id = row_dict.get("session_id")
                    if session_id and session_id not in valid_session_ids:
                        table_skipped += 1
                        continue

                # Compute content hash if not already present
                content_hash = row_dict.get("content_hash")
                if not content_hash and "content_hash" in columns:
                    content_hash = _compute_hash_for_table(table, row_dict)

                values = []
                for col, val in zip(columns, row, strict=False):
                    # Use computed hash if original was None
                    if col == "content_hash" and val is None and content_hash:
                        val = content_hash

                    if val is None:
                        values.append("NULL")
                    elif isinstance(val, (int, float)):
                        values.append(str(val))
                    elif isinstance(val, bool):
                        values.append("1" if val else "0")
                    else:
                        # Escape single quotes for SQL
                        escaped = str(val).replace("'", "''")
                        values.append(f"'{escaped}'")

                cols_str = ", ".join(columns)
                vals_str = ", ".join(values)
                table_lines.append(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str});")
                table_exported += 1

            # Write table header and records
            if table_exported > 0:
                lines.append(f"-- {table} ({table_exported} records)")
                lines.extend(table_lines)
                lines.append("")

            total_count += table_exported
            skipped_orphans += table_skipped

            if table_skipped > 0:
                logger.warning(
                    f"Skipped {table_skipped} orphaned {table} records with invalid FK references"
                )

        logger.debug(f"Exported {len(rows)} records from {table}")

    # Skip writing if no records to export (avoids header-only files)
    if total_count == 0:
        logger.info(
            f"Export skipped: no records for machine {machine_id} "
            f"(skipped: {skipped_foreign} from other machines, "
            f"{skipped_orphans} orphaned)"
        )
        return 0

    # Write atomically via temp file + rename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(output_path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        Path(tmp_path).replace(output_path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    # Log completion with details about skipped records
    skip_details = []
    if skipped_orphans > 0:
        skip_details.append(f"{skipped_orphans} orphaned")
    if skipped_foreign > 0:
        skip_details.append(f"{skipped_foreign} from other machines")

    if skip_details:
        logger.info(
            f"Export complete: {total_count} records to {output_path} "
            f"(skipped: {', '.join(skip_details)})"
        )
    else:
        logger.info(f"Export complete: {total_count} records to {output_path}")
    return total_count


def _compute_hash_for_table(table: str, row_dict: dict) -> str | None:
    """Compute content hash for a row based on table type.

    Args:
        table: Table name.
        row_dict: Dictionary of column names to values.

    Returns:
        Content hash string or None if table doesn't support hashing.
    """
    if table == "prompt_batches":
        session_id = row_dict.get("session_id", "")
        prompt_number = row_dict.get("prompt_number", 0)
        return compute_prompt_batch_hash(str(session_id), int(prompt_number))
    elif table == "memory_observations":
        observation = row_dict.get("observation", "")
        memory_type = row_dict.get("memory_type", "")
        context = row_dict.get("context")
        return compute_observation_hash(str(observation), str(memory_type), context)
    elif table == "activities":
        session_id = row_dict.get("session_id", "")
        timestamp_epoch = row_dict.get("timestamp_epoch", 0)
        tool_name = row_dict.get("tool_name", "")
        return compute_activity_hash(str(session_id), int(timestamp_epoch), str(tool_name))
    return None


def _parse_backup_schema_version(lines: list[str]) -> int | None:
    """Parse schema version from backup file header comments.

    Looks for a line like: -- Schema version: 11

    Args:
        lines: Lines from the backup file.

    Returns:
        Schema version as int, or None if not found.
    """
    for line in lines[:10]:  # Only check first 10 lines (header area)
        if line.startswith("-- Schema version:"):
            try:
                version_str = line.split(":")[-1].strip()
                return int(version_str)
            except ValueError:
                return None
    return None
