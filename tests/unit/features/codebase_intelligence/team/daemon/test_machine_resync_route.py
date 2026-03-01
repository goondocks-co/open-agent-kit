"""Tests for POST /api/team/machine/resync daemon route.

Tests cover:
- Happy path: returns correct counts in response body
- Team sync not enabled: returns 400
- Empty events list: returns response with applied=0
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_API_PATH_MACHINE_RESYNC,
    TEAM_MESSAGE_RESYNC_NOT_ENABLED,
)

# Test constants
_MACHINE_ID = "machine-resync-target"


@dataclass
class _MockApplyResult:
    """Mimics ApplyResult from the applier."""

    applied: int = 0
    skipped: int = 0
    errors: int = 0


def _make_mock_state(*, team_outbox_enabled: bool = True):
    """Create a mock daemon state with activity_store."""
    state = MagicMock()
    state.activity_store = MagicMock()
    state.activity_store.team_outbox_enabled = team_outbox_enabled
    state.activity_store._get_connection.return_value = MagicMock()
    state.vector_store = MagicMock()
    state.project_root = "/tmp/test-project"
    return state


def _make_raw_events(count: int) -> list[dict]:
    """Create raw event dicts as returned by get_events_for_machine / _fetch_machine_events."""
    return [
        {
            "event_type": "observation_upsert",
            "payload": {"id": f"obs-{i}", "observation": f"Test obs {i}"},
            "source_machine_id": _MACHINE_ID,
            "content_hash": f"hash-{i}",
            "schema_version": 9,
            "timestamp": "2026-02-26T10:00:00Z",
            "project_id": "test-project:abc",
        }
        for i in range(count)
    ]


@pytest.fixture
def _resync_client():
    """Create a test client with the team daemon router mounted.

    Patches get_state to return a mock with team_outbox_enabled=True.
    Also patches delete_records_by_machine, _fetch_machine_events, and
    TeamEventApplier.apply_batch with controllable mocks.

    Yields (client, patches_dict) where patches_dict contains the mocks
    so tests can configure return values.
    """
    from open_agent_kit.features.codebase_intelligence.daemon.routes.team import (
        router,
    )

    app = FastAPI()
    app.include_router(router)

    mock_state = _make_mock_state(team_outbox_enabled=True)
    delete_mock = MagicMock(return_value={"observations": 5, "sessions": 2})
    fetch_mock = AsyncMock(return_value=_make_raw_events(3))
    applier_instance = MagicMock()
    applier_instance.apply_batch.return_value = _MockApplyResult(applied=3, skipped=0, errors=0)
    applier_cls_mock = MagicMock(return_value=applier_instance)

    with (
        patch(
            "open_agent_kit.features.codebase_intelligence.daemon.routes.team.get_state",
            return_value=mock_state,
        ),
        patch(
            "open_agent_kit.features.codebase_intelligence.activity.store.delete.delete_records_by_machine",
            delete_mock,
        ),
        patch(
            "open_agent_kit.features.codebase_intelligence.daemon.routes.team._fetch_machine_events",
            fetch_mock,
        ),
        patch(
            "open_agent_kit.features.codebase_intelligence.team.pull.applier.TeamEventApplier",
            applier_cls_mock,
        ),
    ):
        client = TestClient(app)
        yield client, {
            "state": mock_state,
            "delete": delete_mock,
            "fetch": fetch_mock,
            "applier_cls": applier_cls_mock,
            "applier_instance": applier_instance,
        }


# =============================================================================
# Happy path
# =============================================================================


class TestMachineResyncHappyPath:
    """Test successful machine resync."""

    def test_returns_correct_counts(self, _resync_client):
        """Happy path returns correct deleted/applied/skipped/errors counts."""
        client, mocks = _resync_client

        response = client.post(
            TEAM_API_PATH_MACHINE_RESYNC,
            json={"machine_id": _MACHINE_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["machine_id"] == _MACHINE_ID
        assert data["deleted"] == {"observations": 5, "sessions": 2}
        assert data["applied"] == 3
        assert data["skipped"] == 0
        assert data["errors"] == 0

    def test_calls_delete_then_fetch_then_apply(self, _resync_client):
        """Verifies the three-step flow: delete, fetch, apply."""
        client, mocks = _resync_client

        client.post(
            TEAM_API_PATH_MACHINE_RESYNC,
            json={"machine_id": _MACHINE_ID},
        )

        # delete_records_by_machine was called with the correct machine_id
        mocks["delete"].assert_called_once()
        call_args = mocks["delete"].call_args
        assert call_args[0][1] == _MACHINE_ID  # second positional arg

        # _fetch_machine_events was called
        mocks["fetch"].assert_called_once()

        # TeamEventApplier.apply_batch was called
        mocks["applier_instance"].apply_batch.assert_called_once()

    def test_response_model_fields(self, _resync_client):
        """Response contains all MachineResyncResponse fields."""
        client, _ = _resync_client

        response = client.post(
            TEAM_API_PATH_MACHINE_RESYNC,
            json={"machine_id": _MACHINE_ID},
        )
        data = response.json()
        expected_fields = {"machine_id", "deleted", "applied", "skipped", "errors"}
        assert expected_fields == set(data.keys())


# =============================================================================
# Team sync not enabled
# =============================================================================


class TestMachineResyncNotEnabled:
    """Test resync when team sync is not enabled."""

    def test_returns_400_when_outbox_disabled(self):
        """Returns 400 when team_outbox_enabled is False."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.team import (
            router,
        )

        app = FastAPI()
        app.include_router(router)

        mock_state = _make_mock_state(team_outbox_enabled=False)

        with patch(
            "open_agent_kit.features.codebase_intelligence.daemon.routes.team.get_state",
            return_value=mock_state,
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                TEAM_API_PATH_MACHINE_RESYNC,
                json={"machine_id": _MACHINE_ID},
            )

        assert response.status_code == 400
        assert TEAM_MESSAGE_RESYNC_NOT_ENABLED in response.json()["detail"]

    def test_returns_400_when_activity_store_is_none(self):
        """Returns 400 when activity_store is None."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.team import (
            router,
        )

        app = FastAPI()
        app.include_router(router)

        mock_state = MagicMock()
        mock_state.activity_store = None

        with patch(
            "open_agent_kit.features.codebase_intelligence.daemon.routes.team.get_state",
            return_value=mock_state,
        ):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                TEAM_API_PATH_MACHINE_RESYNC,
                json={"machine_id": _MACHINE_ID},
            )

        assert response.status_code == 400


# =============================================================================
# Empty events
# =============================================================================


class TestMachineResyncEmptyEvents:
    """Test resync when no events exist for the machine."""

    def test_empty_events_returns_zero_applied(self, _resync_client):
        """Empty events list results in applied=0."""
        client, mocks = _resync_client

        # Override fetch to return empty list
        mocks["fetch"].return_value = []
        mocks["applier_instance"].apply_batch.return_value = _MockApplyResult(
            applied=0, skipped=0, errors=0
        )

        response = client.post(
            TEAM_API_PATH_MACHINE_RESYNC,
            json={"machine_id": _MACHINE_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["applied"] == 0
        assert data["skipped"] == 0
        assert data["errors"] == 0
        # Delete still happens (wipe first, then discover nothing to re-apply)
        assert data["deleted"] == {"observations": 5, "sessions": 2}
