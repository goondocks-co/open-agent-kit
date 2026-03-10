"""Shared fixtures for integration tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.features.team.config import CIConfig
from open_agent_kit.features.team.constants import CI_AUTH_ENV_VAR

TEST_AUTH_TOKEN = "a" * 64
FAKE_PROJECT_ROOT = Path("/tmp/fake-integration-test-project")

_CONFIG_MODULE = "open_agent_kit.features.team.config"


@pytest.fixture
def auth_headers(monkeypatch):
    """Set auth env var and return headers for authenticated requests."""
    monkeypatch.setenv(CI_AUTH_ENV_VAR, TEST_AUTH_TOKEN)
    return {"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}


@pytest.fixture(autouse=True)
def _isolate_config_io():
    """Prevent integration tests from reading/writing real project config."""
    with (
        patch(f"{_CONFIG_MODULE}.load_ci_config", return_value=CIConfig()),
        patch(f"{_CONFIG_MODULE}.save_ci_config"),
    ):
        yield
