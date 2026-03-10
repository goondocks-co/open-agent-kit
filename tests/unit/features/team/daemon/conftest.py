"""Shared fixtures for daemon test modules.

Provides authenticated test client helpers so that tests work correctly
with the ephemeral-token security middleware (Phase 1a).

Also provides global config I/O isolation so that no daemon test can
accidentally read from or write to the real project config on disk.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.features.team.config import CIConfig
from open_agent_kit.features.team.constants import CI_AUTH_ENV_VAR

# 64 hex chars — matches secrets.token_hex(32) format
TEST_AUTH_TOKEN = "a" * 64

FAKE_PROJECT_ROOT = Path("/tmp/fake-daemon-test-project")

_CONFIG_MODULE = "open_agent_kit.features.team.config"


@pytest.fixture
def auth_headers(monkeypatch):
    """Set auth env var so ``create_app()`` picks up the token, and return headers.

    ``create_app()`` reads ``CI_AUTH_ENV_VAR`` and sets ``state.auth_token``.
    Setting the env var *before* the TestClient is constructed ensures the
    token survives the app's own initialisation.
    """
    monkeypatch.setenv(CI_AUTH_ENV_VAR, TEST_AUTH_TOKEN)
    return {"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}


@pytest.fixture(autouse=True)
def _isolate_config_io():
    """Prevent daemon tests from reading/writing real project config.

    ``create_app()`` defaults ``state.project_root`` to ``Path.cwd()``
    (the real repo) when called without arguments.  Routes that call
    ``save_ci_config(state.project_root, ...)`` would then write test
    fixture values (tokens, auto_connect flags, etc.) into the real
    ``.oak/config*.yaml`` files.

    This autouse fixture patches ``load_ci_config`` and ``save_ci_config``
    at the module level so that all daemon tests are isolated by default.
    Individual tests that need specific return values can add their own
    ``@patch`` decorators which will take precedence.
    """
    with (
        patch(f"{_CONFIG_MODULE}.load_ci_config", return_value=CIConfig()),
        patch(f"{_CONFIG_MODULE}.save_ci_config"),
    ):
        yield
