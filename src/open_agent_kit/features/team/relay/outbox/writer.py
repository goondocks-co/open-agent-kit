"""Outbox writer for team sync events.

Called within _transaction() blocks -- same SQLite transaction as the data write.
This ensures zero-latency impact and guaranteed delivery.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from open_agent_kit.features.team.constants.team import (
    TEAM_OUTBOX_STATUS_PENDING,
)

logger = logging.getLogger(__name__)


def enqueue_team_event(
    conn: Any,  # sqlite3.Connection -- already in transaction
    event_type: str,
    payload: dict[str, Any],
    source_machine_id: str,
    content_hash: str,
    schema_version: int,
) -> None:
    """Enqueue a team sync event in the outbox.

    Called within the same transaction as the data write.
    The ObsFlushWorker will flush these to the cloud relay.

    Args:
        conn: SQLite connection (already in an active transaction).
        event_type: Type of event (e.g. observation_upsert).
        payload: Event data dictionary.
        source_machine_id: Machine that created this event.
        content_hash: Content hash for deduplication.
        schema_version: Activity store schema version.
    """
    conn.execute(
        """
        INSERT INTO team_outbox (event_type, payload, source_machine_id, content_hash,
                                 schema_version, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            json.dumps(payload),
            source_machine_id,
            content_hash,
            schema_version,
            datetime.now(UTC).isoformat(),
            TEAM_OUTBOX_STATUS_PENDING,
        ),
    )
