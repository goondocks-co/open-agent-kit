"""Wire protocol models for Oak Teams sync.

Defines Pydantic models for JSON messages exchanged between
team clients and the team server.
"""

from pydantic import BaseModel


class TeamSyncStatus(BaseModel):
    """Status of the team sync worker."""

    enabled: bool = False
    queue_depth: int = 0
    last_sync: str | None = None
    last_error: str | None = None
    events_sent_total: int = 0
