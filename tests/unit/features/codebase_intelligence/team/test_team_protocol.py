"""Tests for team sync wire protocol models.

Tests cover:
- TeamEvent Pydantic serialization/deserialization
- TeamEventBatch with events list
- TeamPullRequest defaults
- PushResult defaults
- TeamMemberInfo required fields
"""

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_PULL_DEFAULT_LIMIT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    PushResult,
    TeamEvent,
    TeamEventBatch,
    TeamMemberInfo,
    TeamPullRequest,
    TeamPullStatus,
    TeamSyncStatus,
    TransportStatus,
)

# =============================================================================
# TeamEvent Tests
# =============================================================================


class TestTeamEvent:
    """Test TeamEvent model serialization."""

    def test_serialization_round_trip(self):
        """Test that TeamEvent can be serialized and deserialized."""
        event = TeamEvent(
            event_type=TEAM_EVENT_OBSERVATION_UPSERT,
            payload={"observation_id": "obs-123", "text": "Found a bug"},
            source_machine_id="machine-abc",
            content_hash="hash123",
            schema_version=9,
            timestamp="2026-02-26T10:00:00Z",
            project_id="my-project:abcd1234",
        )
        data = event.model_dump()
        restored = TeamEvent.model_validate(data)
        assert restored.event_type == TEAM_EVENT_OBSERVATION_UPSERT
        assert restored.payload["observation_id"] == "obs-123"
        assert restored.source_machine_id == "machine-abc"
        assert restored.content_hash == "hash123"
        assert restored.schema_version == 9
        assert restored.timestamp == "2026-02-26T10:00:00Z"
        assert restored.project_id == "my-project:abcd1234"

    def test_json_round_trip(self):
        """Test that TeamEvent survives JSON serialization."""
        event = TeamEvent(
            event_type=TEAM_EVENT_OBSERVATION_UPSERT,
            payload={"key": "value"},
            source_machine_id="machine-1",
            content_hash="abc",
            schema_version=9,
            timestamp="2026-02-26T12:00:00Z",
            project_id="proj:12345678",
        )
        json_str = event.model_dump_json()
        restored = TeamEvent.model_validate_json(json_str)
        assert restored == event


# =============================================================================
# TeamEventBatch Tests
# =============================================================================


class TestTeamEventBatch:
    """Test TeamEventBatch model."""

    def test_empty_batch_defaults(self):
        """Test that an empty batch has correct defaults."""
        batch = TeamEventBatch()
        assert batch.events == []
        assert batch.cursor is None

    def test_batch_with_events(self):
        """Test batch containing multiple events."""
        events = [
            TeamEvent(
                event_type=TEAM_EVENT_OBSERVATION_UPSERT,
                payload={"id": str(i)},
                source_machine_id="machine-1",
                content_hash=f"hash-{i}",
                schema_version=9,
                timestamp="2026-02-26T10:00:00Z",
                project_id="proj:abcd1234",
            )
            for i in range(3)
        ]
        batch = TeamEventBatch(events=events, cursor="cursor-abc")
        assert len(batch.events) == 3
        assert batch.cursor == "cursor-abc"

    def test_batch_serialization(self):
        """Test batch model_dump/model_validate round-trip."""
        batch = TeamEventBatch(
            events=[
                TeamEvent(
                    event_type=TEAM_EVENT_OBSERVATION_UPSERT,
                    payload={},
                    source_machine_id="m1",
                    content_hash="h1",
                    schema_version=9,
                    timestamp="2026-02-26T10:00:00Z",
                    project_id="p:12345678",
                )
            ],
            cursor="c1",
        )
        data = batch.model_dump()
        restored = TeamEventBatch.model_validate(data)
        assert len(restored.events) == 1
        assert restored.cursor == "c1"


# =============================================================================
# TeamPullRequest Tests
# =============================================================================


class TestTeamPullRequest:
    """Test TeamPullRequest model."""

    def test_defaults(self):
        """Test that defaults are applied correctly."""
        req = TeamPullRequest()
        assert req.since_cursor is None
        assert req.limit == TEAM_PULL_DEFAULT_LIMIT
        assert req.exclude_machine_id is None

    def test_custom_values(self):
        """Test with custom values."""
        req = TeamPullRequest(
            since_cursor="cursor-xyz",
            limit=10,
            exclude_machine_id="machine-1",
        )
        assert req.since_cursor == "cursor-xyz"
        assert req.limit == 10
        assert req.exclude_machine_id == "machine-1"


# =============================================================================
# PushResult Tests
# =============================================================================


class TestPushResult:
    """Test PushResult model."""

    def test_defaults(self):
        """Test that defaults are applied correctly."""
        result = PushResult()
        assert result.accepted == 0
        assert result.rejected == 0
        assert result.cursor is None

    def test_custom_values(self):
        """Test with custom values."""
        result = PushResult(accepted=5, rejected=1, cursor="new-cursor")
        assert result.accepted == 5
        assert result.rejected == 1
        assert result.cursor == "new-cursor"


# =============================================================================
# TeamMemberInfo Tests
# =============================================================================


class TestTeamMemberInfo:
    """Test TeamMemberInfo model."""

    def test_required_fields(self):
        """Test that all required fields must be provided."""
        member = TeamMemberInfo(
            machine_id="machine-abc",
            display_name="Alice's Laptop",
            project_id="my-project:abcd1234",
            last_seen="2026-02-26T10:00:00Z",
        )
        assert member.machine_id == "machine-abc"
        assert member.display_name == "Alice's Laptop"
        assert member.project_id == "my-project:abcd1234"
        assert member.last_seen == "2026-02-26T10:00:00Z"
        assert member.event_count == 0

    def test_with_event_count(self):
        """Test member info with custom event count."""
        member = TeamMemberInfo(
            machine_id="m1",
            display_name="Bob",
            project_id="p:12345678",
            last_seen="2026-02-26T12:00:00Z",
            event_count=42,
        )
        assert member.event_count == 42


# =============================================================================
# Status Models Tests
# =============================================================================


class TestStatusModels:
    """Test status model defaults."""

    def test_transport_status_defaults(self):
        """Test TransportStatus defaults."""
        status = TransportStatus()
        assert status.connected is False
        assert status.server_url is None
        assert status.last_error is None
        assert status.last_connected_at is None

    def test_sync_status_defaults(self):
        """Test TeamSyncStatus defaults."""
        status = TeamSyncStatus()
        assert status.enabled is False
        assert status.queue_depth == 0
        assert status.last_sync is None
        assert status.last_error is None
        assert status.events_sent_total == 0

    def test_pull_status_defaults(self):
        """Test TeamPullStatus defaults."""
        status = TeamPullStatus()
        assert status.enabled is False
        assert status.last_pull is None
        assert status.events_applied_total == 0
        assert status.cursor is None
