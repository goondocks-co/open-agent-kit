"""Wire protocol models for Oak Teams sync.

Defines Pydantic models for JSON messages exchanged between
team clients and the team server.
"""

from typing import Any

from pydantic import BaseModel, Field

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_JOIN_STATUS_PENDING,
    TEAM_PULL_DEFAULT_LIMIT,
)


class TeamEvent(BaseModel):
    """A single team sync event."""

    event_type: str
    payload: dict[str, Any]
    source_machine_id: str
    content_hash: str
    schema_version: int
    timestamp: str  # ISO 8601
    project_id: str


class TeamEventBatch(BaseModel):
    """A batch of team events for push/pull."""

    events: list[TeamEvent] = Field(default_factory=list)
    cursor: str | None = None


class TeamMemberInfo(BaseModel):
    """Information about a team member."""

    machine_id: str
    display_name: str
    project_id: str
    last_seen: str
    event_count: int = 0


class TeamPullRequest(BaseModel):
    """Request to pull events from team server."""

    since_cursor: str | None = None
    limit: int = TEAM_PULL_DEFAULT_LIMIT
    exclude_machine_id: str | None = None


class PushResult(BaseModel):
    """Result of pushing events to team server."""

    accepted: int = 0
    rejected: int = 0
    cursor: str | None = None


class TransportStatus(BaseModel):
    """Status of the team transport connection."""

    connected: bool = False
    server_url: str | None = None
    last_error: str | None = None
    last_connected_at: str | None = None


class TeamSyncStatus(BaseModel):
    """Status of the team sync worker."""

    enabled: bool = False
    queue_depth: int = 0
    last_sync: str | None = None
    last_error: str | None = None
    events_sent_total: int = 0


class TeamPullStatus(BaseModel):
    """Status of the team pull worker."""

    enabled: bool = False
    last_pull: str | None = None
    events_applied_total: int = 0
    cursor: str | None = None


# ---------------------------------------------------------------------------
# Join request / approval flow
# ---------------------------------------------------------------------------


class JoinRequest(BaseModel):
    """Request from a client to join a team server."""

    machine_id: str
    display_name: str
    key_hash: str
    project_id: str


class JoinRequestResponse(BaseModel):
    """Server response after receiving a join request."""

    status: str = TEAM_JOIN_STATUS_PENDING
    key_id: str


class JoinRequestStatus(BaseModel):
    """Status of a join request (used for client polling)."""

    key_id: str
    status: str
    machine_id: str | None = None
    display_name: str | None = None


class PendingJoinInfo(BaseModel):
    """Information about a pending join request (for server admin UI)."""

    key_id: str
    name: str
    machine_id: str
    display_name: str
    created_at: str
