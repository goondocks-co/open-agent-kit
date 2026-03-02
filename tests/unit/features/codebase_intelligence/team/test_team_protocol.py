"""Tests for team sync wire protocol models.

Tests cover:
- TeamSyncStatus defaults and custom values
"""

from open_agent_kit.features.codebase_intelligence.team.protocol import (
    TeamSyncStatus,
)


class TestTeamSyncStatus:
    """Test TeamSyncStatus model."""

    def test_defaults(self):
        """Test TeamSyncStatus defaults."""
        status = TeamSyncStatus()
        assert status.enabled is False
        assert status.queue_depth == 0
        assert status.last_sync is None
        assert status.last_error is None
        assert status.events_sent_total == 0

    def test_custom_values(self):
        """Test TeamSyncStatus with custom values."""
        status = TeamSyncStatus(
            enabled=True,
            queue_depth=10,
            last_sync="2026-02-26T10:00:00Z",
            last_error=None,
            events_sent_total=42,
        )
        assert status.enabled is True
        assert status.queue_depth == 10
        assert status.last_sync == "2026-02-26T10:00:00Z"
        assert status.events_sent_total == 42
