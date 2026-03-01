"""Tests for GET /machine/{machine_id}/events server route.

Tests cover:
- Missing/invalid auth token returns 401
- Valid auth returns events for the correct machine
- limit and offset params are forwarded correctly
"""

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import TeamEvent
from open_agent_kit.features.codebase_intelligence.team.server.auth import (
    TEAM_API_KEYS_DDL,
    create_api_key,
)
from open_agent_kit.features.codebase_intelligence.team.server.cursors import (
    TEAM_EVENTS_DDL,
    store_events,
)
from open_agent_kit.features.codebase_intelligence.team.server.membership import (
    TEAM_MEMBERS_DDL,
)

# Test constants
_TEST_PROJECT_ID = "test-project:abcd1234"
_MACHINE_A = "machine-A"
_MACHINE_B = "machine-B"


def _setup_db() -> sqlite3.Connection:
    """Create in-memory DB with all team server tables."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(TEAM_API_KEYS_DDL)
    conn.executescript(TEAM_MEMBERS_DDL)
    conn.executescript(TEAM_EVENTS_DDL)
    return conn


def _make_event(
    content_hash: str,
    source_machine_id: str = _MACHINE_A,
) -> TeamEvent:
    """Create a test TeamEvent."""
    return TeamEvent(
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload={"test": True},
        source_machine_id=source_machine_id,
        content_hash=content_hash,
        schema_version=9,
        timestamp="2026-02-26T10:00:00Z",
        project_id=_TEST_PROJECT_ID,
    )


@pytest.fixture
def _team_client():
    """Create a test client with team routes and valid auth."""
    conn = _setup_db()
    _, api_key = create_api_key(conn, "test-key")

    from fastapi import FastAPI

    from open_agent_kit.features.codebase_intelligence.team.server.routes import router

    app = FastAPI()
    app.include_router(router)

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
# Auth tests
# =============================================================================


class TestMachineEventsAuth:
    """Test authentication for machine events endpoint."""

    def test_missing_auth_returns_401(self, _team_client):
        """Request without auth token returns 401."""
        client, _, _ = _team_client
        response = client.get(f"/api/team/machine/{_MACHINE_A}/events")
        assert response.status_code == 401

    def test_invalid_auth_returns_401(self, _team_client):
        """Request with invalid auth token returns 401."""
        client, _, _ = _team_client
        response = client.get(
            f"/api/team/machine/{_MACHINE_A}/events",
            headers={"Authorization": "Bearer invalid-token-value"},
        )
        assert response.status_code == 401


# =============================================================================
# Successful retrieval tests
# =============================================================================


class TestMachineEventsRetrieval:
    """Test event retrieval for a specific machine."""

    def test_returns_events_for_machine(self, _team_client):
        """Returns events for the requested machine_id."""
        client, api_key, conn = _team_client

        # Insert events for machine A
        events = [_make_event(f"h{i}", source_machine_id=_MACHINE_A) for i in range(3)]
        store_events(conn, events, _TEST_PROJECT_ID)

        response = client.get(
            f"/api/team/machine/{_MACHINE_A}/events",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_returns_empty_for_unknown_machine(self, _team_client):
        """Returns empty list for a machine with no events."""
        client, api_key, _ = _team_client
        response = client.get(
            "/api/team/machine/nonexistent-machine/events",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_excludes_other_machines(self, _team_client):
        """Only returns events for the requested machine, not others."""
        client, api_key, conn = _team_client

        store_events(
            conn,
            [_make_event("a1", source_machine_id=_MACHINE_A)],
            _TEST_PROJECT_ID,
        )
        store_events(
            conn,
            [_make_event("b1", source_machine_id=_MACHINE_B)],
            _TEST_PROJECT_ID,
        )

        response = client.get(
            f"/api/team/machine/{_MACHINE_A}/events",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content_hash"] == "a1"


# =============================================================================
# Pagination forwarding tests
# =============================================================================


class TestMachineEventsPagination:
    """Test that limit and offset params are forwarded correctly."""

    def test_limit_param(self, _team_client):
        """Limit query parameter constrains results."""
        client, api_key, conn = _team_client

        events = [_make_event(f"h{i}", source_machine_id=_MACHINE_A) for i in range(10)]
        store_events(conn, events, _TEST_PROJECT_ID)

        response = client.get(
            f"/api/team/machine/{_MACHINE_A}/events",
            params={"limit": 3},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_offset_param(self, _team_client):
        """Offset query parameter skips rows."""
        client, api_key, conn = _team_client

        events = [_make_event(f"h{i}", source_machine_id=_MACHINE_A) for i in range(5)]
        store_events(conn, events, _TEST_PROJECT_ID)

        response = client.get(
            f"/api/team/machine/{_MACHINE_A}/events",
            params={"offset": 3},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_limit_and_offset_together(self, _team_client):
        """Limit and offset work together for pagination."""
        client, api_key, conn = _team_client

        events = [_make_event(f"h{i}", source_machine_id=_MACHINE_A) for i in range(10)]
        store_events(conn, events, _TEST_PROJECT_ID)

        page1 = client.get(
            f"/api/team/machine/{_MACHINE_A}/events",
            params={"limit": 3, "offset": 0},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        page2 = client.get(
            f"/api/team/machine/{_MACHINE_A}/events",
            params={"limit": 3, "offset": 3},
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert page1.status_code == 200
        assert page2.status_code == 200
        assert len(page1.json()) == 3
        assert len(page2.json()) == 3

        # No overlap between pages
        hashes_1 = {e["content_hash"] for e in page1.json()}
        hashes_2 = {e["content_hash"] for e in page2.json()}
        assert hashes_1.isdisjoint(hashes_2)
