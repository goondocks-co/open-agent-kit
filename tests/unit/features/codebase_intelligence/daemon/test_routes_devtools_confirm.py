"""Tests for devtools confirmation header requirement.

Tests cover:
- POST devtools endpoints require X-Devtools-Confirm: true header
- POST devtools endpoints return 403 without the header
- GET devtools endpoints (memory-stats) do NOT require the header
"""

from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_AUTH_ENV_VAR,
    CI_AUTH_SCHEME_BEARER,
    CI_DEVTOOLS_CONFIRM_HEADER,
    CI_DEVTOOLS_ERROR_CONFIRM_REQUIRED,
)
from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import reset_state

TEST_TOKEN = "b" * 64


@pytest.fixture(autouse=True)
def _reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client(monkeypatch, tmp_path: Path):
    """FastAPI test client with auth token configured."""
    monkeypatch.setenv(CI_AUTH_ENV_VAR, TEST_TOKEN)
    app = create_app(project_root=tmp_path)
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    """Return valid auth headers."""
    return {"Authorization": f"{CI_AUTH_SCHEME_BEARER} {TEST_TOKEN}"}


def _auth_and_confirm_headers() -> dict[str, str]:
    """Return valid auth + devtools confirm headers."""
    return {
        "Authorization": f"{CI_AUTH_SCHEME_BEARER} {TEST_TOKEN}",
        CI_DEVTOOLS_CONFIRM_HEADER: "true",
    }


# =============================================================================
# GET endpoints — No confirmation required
# =============================================================================


class TestDevtoolsGetEndpoints:
    """Test that GET devtools endpoints do NOT require confirmation header."""

    def test_memory_stats_without_confirm_header(self, client):
        """Test that GET /api/devtools/memory-stats works without confirm header.

        This is a read-only endpoint and should NOT require the
        X-Devtools-Confirm header.
        """
        response = client.get(
            "/api/devtools/memory-stats",
            headers=_auth_headers(),
        )
        # Should not be 403 — GET endpoints are exempt from confirmation
        assert response.status_code != HTTPStatus.FORBIDDEN


# =============================================================================
# POST endpoints — Confirmation required
# =============================================================================


class TestDevtoolsPostEndpointsRequireConfirm:
    """Test that POST devtools endpoints require X-Devtools-Confirm: true."""

    def test_backfill_hashes_without_confirm_returns_403(self, client):
        """Test POST /api/devtools/backfill-hashes returns 403 without header."""
        response = client.post(
            "/api/devtools/backfill-hashes",
            headers=_auth_headers(),
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json()["detail"] == CI_DEVTOOLS_ERROR_CONFIRM_REQUIRED

    def test_rebuild_index_without_confirm_returns_403(self, client):
        """Test POST /api/devtools/rebuild-index returns 403 without header."""
        response = client.post(
            "/api/devtools/rebuild-index",
            headers=_auth_headers(),
            json={"full_rebuild": True},
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json()["detail"] == CI_DEVTOOLS_ERROR_CONFIRM_REQUIRED

    def test_reset_processing_without_confirm_returns_403(self, client):
        """Test POST /api/devtools/reset-processing returns 403 without header."""
        response = client.post(
            "/api/devtools/reset-processing",
            headers=_auth_headers(),
            json={"scope": "memories"},
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_compact_chromadb_without_confirm_returns_403(self, client):
        """Test POST /api/devtools/compact-chromadb returns 403 without header."""
        response = client.post(
            "/api/devtools/compact-chromadb",
            headers=_auth_headers(),
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_trigger_processing_without_confirm_returns_403(self, client):
        """Test POST /api/devtools/trigger-processing returns 403 without header."""
        response = client.post(
            "/api/devtools/trigger-processing",
            headers=_auth_headers(),
        )
        assert response.status_code == HTTPStatus.FORBIDDEN


class TestDevtoolsPostEndpointsWithConfirm:
    """Test that POST devtools endpoints succeed with confirmation header."""

    def test_backfill_hashes_with_confirm_not_403(self, client):
        """Test POST /api/devtools/backfill-hashes passes with confirm header.

        The endpoint may return an error due to uninitialized state,
        but it must NOT be 403 (confirmation gate passed).
        """
        response = client.post(
            "/api/devtools/backfill-hashes",
            headers=_auth_and_confirm_headers(),
        )
        # May be 500 (uninitialized state) but must not be 403
        assert response.status_code != HTTPStatus.FORBIDDEN

    def test_trigger_processing_with_confirm_not_403(self, client):
        """Test POST /api/devtools/trigger-processing passes with confirm header."""
        response = client.post(
            "/api/devtools/trigger-processing",
            headers=_auth_and_confirm_headers(),
        )
        assert response.status_code != HTTPStatus.FORBIDDEN


class TestDevtoolsConfirmHeaderValues:
    """Test edge cases for the confirmation header value."""

    def test_confirm_header_wrong_value_returns_403(self, client):
        """Test that X-Devtools-Confirm with wrong value returns 403."""
        headers = _auth_headers()
        headers[CI_DEVTOOLS_CONFIRM_HEADER] = "yes"
        response = client.post(
            "/api/devtools/backfill-hashes",
            headers=headers,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_confirm_header_empty_returns_403(self, client):
        """Test that X-Devtools-Confirm with empty value returns 403."""
        headers = _auth_headers()
        headers[CI_DEVTOOLS_CONFIRM_HEADER] = ""
        response = client.post(
            "/api/devtools/backfill-hashes",
            headers=headers,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN
