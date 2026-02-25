"""Shared fixtures for daemon test modules.

Provides authenticated test client helpers so that tests work correctly
with the ephemeral-token security middleware (Phase 1a).
"""

import pytest

from open_agent_kit.features.codebase_intelligence.constants import CI_AUTH_ENV_VAR

# 64 hex chars — matches secrets.token_hex(32) format
TEST_AUTH_TOKEN = "a" * 64


@pytest.fixture
def auth_headers(monkeypatch):
    """Set auth env var so ``create_app()`` picks up the token, and return headers.

    ``create_app()`` reads ``CI_AUTH_ENV_VAR`` and sets ``state.auth_token``.
    Setting the env var *before* the TestClient is constructed ensures the
    token survives the app's own initialisation.
    """
    monkeypatch.setenv(CI_AUTH_ENV_VAR, TEST_AUTH_TOKEN)
    return {"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}
