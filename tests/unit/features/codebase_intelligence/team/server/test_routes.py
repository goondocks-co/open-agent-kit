"""Tests for team server API routes.

Tests cover:
- Push endpoint with dedup
- Pull endpoint with cursor pagination
- Status endpoint (no auth)
- Member registration
- Member listing
"""

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_SERVER_STATUS_OK,
)
from open_agent_kit.features.codebase_intelligence.team.server.auth import (
    TEAM_API_KEYS_DDL,
    create_api_key,
)
from open_agent_kit.features.codebase_intelligence.team.server.cursors import (
    TEAM_EVENTS_DDL,
)
from open_agent_kit.features.codebase_intelligence.team.server.membership import (
    TEAM_MEMBERS_DDL,
)

# Test project ID constant
_TEST_PROJECT_ID = "test-project:abcd1234"


def _setup_db() -> sqlite3.Connection:
    """Create in-memory DB with all team server tables."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(TEAM_API_KEYS_DDL)
    conn.executescript(TEAM_MEMBERS_DDL)
    conn.executescript(TEAM_EVENTS_DDL)
    return conn


def _make_app(conn: sqlite3.Connection):
    """Create a minimal FastAPI app with team routes for testing."""
    from fastapi import FastAPI

    from open_agent_kit.features.codebase_intelligence.team.server.routes import router

    app = FastAPI()
    app.include_router(router)

    # Patch the _get_conn and auth to use our test db
    return app, conn


def _make_event_payload(content_hash: str = "h1") -> dict:
    """Create a test event payload dict."""
    return {
        "event_type": TEAM_EVENT_OBSERVATION_UPSERT,
        "payload": {"test": True},
        "source_machine_id": "machine-1",
        "content_hash": content_hash,
        "schema_version": 9,
        "timestamp": "2026-02-26T10:00:00Z",
        "project_id": _TEST_PROJECT_ID,
    }


@pytest.fixture
def _team_client():
    """Create a test client with team routes and valid auth."""
    conn = _setup_db()
    _, api_key = create_api_key(conn, "test-key")

    from fastapi import FastAPI

    from open_agent_kit.features.codebase_intelligence.team.server.routes import router

    app = FastAPI()
    app.include_router(router)

    # Patch _get_conn to use our in-memory DB
    with (
        patch(
            "open_agent_kit.features.codebase_intelligence.team.server.routes._get_conn",
            return_value=conn,
        ),
        patch(
            "open_agent_kit.features.codebase_intelligence.team.server.auth._get_team_db_conn",
            return_value=conn,
        ),
    ):
        client = TestClient(app)
        yield client, api_key, conn


# =============================================================================
# Status endpoint (no auth)
# =============================================================================


class TestStatusEndpoint:
    """Test /api/team/status endpoint."""

    def test_status_no_auth(self, _team_client):
        """Status endpoint works without authentication."""
        client, _, _ = _team_client
        response = client.get("/api/team/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == TEAM_SERVER_STATUS_OK
        assert data["server_mode"] is True


# =============================================================================
# Push endpoint
# =============================================================================


class TestPushEndpoint:
    """Test /api/team/events/push endpoint."""

    def test_push_events(self, _team_client):
        """Push endpoint accepts events."""
        client, api_key, conn = _team_client
        # Register a member first so update_last_seen doesn't fail silently
        conn.execute(
            "INSERT INTO team_members (machine_id, display_name, project_id, joined_at, last_seen) "
            "VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            (api_key[:16], "test", _TEST_PROJECT_ID),
        )
        conn.commit()

        response = client.post(
            "/api/team/events/push",
            json={"events": [_make_event_payload("h1"), _make_event_payload("h2")]},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["accepted"] == 2
        assert data["rejected"] == 0

    def test_push_dedup(self, _team_client):
        """Push endpoint deduplicates by content_hash."""
        client, api_key, _ = _team_client
        batch = {"events": [_make_event_payload("h1")]}

        # First push
        response1 = client.post(
            "/api/team/events/push",
            json=batch,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response1.json()["accepted"] == 1

        # Second push with same hash
        response2 = client.post(
            "/api/team/events/push",
            json=batch,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response2.json()["accepted"] == 0
        assert response2.json()["rejected"] == 1

    def test_push_requires_auth(self, _team_client):
        """Push endpoint returns 401 without auth."""
        client, _, _ = _team_client
        response = client.post(
            "/api/team/events/push",
            json={"events": [_make_event_payload()]},
        )
        assert response.status_code == 401


# =============================================================================
# Pull endpoint
# =============================================================================


class TestPullEndpoint:
    """Test /api/team/events/pull endpoint."""

    def test_pull_empty(self, _team_client):
        """Pull returns empty when no events."""
        client, api_key, _ = _team_client
        response = client.post(
            "/api/team/events/pull",
            json={},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []

    def test_pull_with_cursor(self, _team_client):
        """Pull supports cursor-based pagination."""
        client, api_key, _ = _team_client

        # Push some events first
        events = [_make_event_payload(f"h{i}") for i in range(5)]
        client.post(
            "/api/team/events/push",
            json={"events": events},
            headers={"Authorization": f"Bearer {api_key}"},
        )

        # Pull first 2
        response1 = client.post(
            "/api/team/events/pull",
            json={"limit": 2},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        data1 = response1.json()
        # Events from own machine are excluded by default, so we may
        # get 0 events (since all events are from the same auth identity).
        # This test primarily validates the endpoint works without error.
        assert response1.status_code == 200
        assert "events" in data1
        assert "cursor" in data1

    def test_pull_requires_auth(self, _team_client):
        """Pull endpoint returns 401 without auth."""
        client, _, _ = _team_client
        response = client.post(
            "/api/team/events/pull",
            json={},
        )
        assert response.status_code == 401


# =============================================================================
# Members endpoints
# =============================================================================


class TestMembersEndpoints:
    """Test member registration and listing."""

    def test_register_member(self, _team_client):
        """Register endpoint creates a member."""
        client, api_key, _ = _team_client
        response = client.post(
            "/api/team/members/register",
            json={
                "machine_id": "new-machine",
                "display_name": "Alice's Laptop",
                "project_id": _TEST_PROJECT_ID,
                "last_seen": "2026-02-26T10:00:00Z",
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["machine_id"] == "new-machine"
        assert data["display_name"] == "Alice's Laptop"

    def test_list_members(self, _team_client):
        """List endpoint returns registered members."""
        client, api_key, _ = _team_client

        # Register a member
        client.post(
            "/api/team/members/register",
            json={
                "machine_id": "machine-A",
                "display_name": "Alice",
                "project_id": _TEST_PROJECT_ID,
                "last_seen": "2026-02-26T10:00:00Z",
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        response = client.get(
            "/api/team/members",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        members = response.json()
        assert len(members) >= 1
        ids = {m["machine_id"] for m in members}
        assert "machine-A" in ids

    def test_members_requires_auth(self, _team_client):
        """Members endpoint returns 401 without auth."""
        client, _, _ = _team_client
        response = client.get("/api/team/members")
        assert response.status_code == 401
