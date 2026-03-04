"""Tests for ACP session route request models.

Tests cover:
- CreateSessionRequest model validation
- PromptRequest model validation
- SetModeRequest model validation
- _get_session_manager helper logic
"""

import pytest
from pydantic import ValidationError

from open_agent_kit.features.team.daemon.routes.acp_sessions import (
    CreateSessionRequest,
    PromptRequest,
    SetModeRequest,
)

# =============================================================================
# CreateSessionRequest tests
# =============================================================================


class TestCreateSessionRequest:
    """Tests for CreateSessionRequest model."""

    def test_default_cwd_is_none(self) -> None:
        """CreateSessionRequest should default cwd to None."""
        request = CreateSessionRequest()

        assert request.cwd is None

    def test_accepts_cwd_string(self) -> None:
        """CreateSessionRequest should accept a cwd string."""
        request = CreateSessionRequest(cwd="/home/user/project")

        assert request.cwd == "/home/user/project"

    def test_accepts_empty_body(self) -> None:
        """CreateSessionRequest should accept empty JSON body."""
        request = CreateSessionRequest.model_validate({})

        assert request.cwd is None


# =============================================================================
# PromptRequest tests
# =============================================================================


class TestPromptRequest:
    """Tests for PromptRequest model."""

    def test_accepts_valid_text(self) -> None:
        """PromptRequest should accept valid text."""
        request = PromptRequest(text="Hello, world!")

        assert request.text == "Hello, world!"

    def test_rejects_empty_text(self) -> None:
        """PromptRequest should reject empty text (min_length=1)."""
        with pytest.raises(ValidationError):
            PromptRequest(text="")

    def test_rejects_missing_text(self) -> None:
        """PromptRequest should require text field."""
        with pytest.raises(ValidationError):
            PromptRequest.model_validate({})

    def test_accepts_max_length_text(self) -> None:
        """PromptRequest should accept text at exactly max_length."""
        text = "x" * 100_000
        request = PromptRequest(text=text)

        assert len(request.text) == 100_000

    def test_rejects_over_max_length_text(self) -> None:
        """PromptRequest should reject text exceeding max_length."""
        with pytest.raises(ValidationError):
            PromptRequest(text="x" * 100_001)


# =============================================================================
# SetModeRequest tests
# =============================================================================


class TestSetModeRequest:
    """Tests for SetModeRequest model."""

    def test_accepts_default_mode(self) -> None:
        """SetModeRequest should accept 'default' mode."""
        request = SetModeRequest(mode="default")

        assert request.mode == "default"

    def test_accepts_accept_edits_mode(self) -> None:
        """SetModeRequest should accept 'acceptEdits' mode."""
        request = SetModeRequest(mode="acceptEdits")

        assert request.mode == "acceptEdits"

    def test_accepts_plan_mode(self) -> None:
        """SetModeRequest should accept 'plan' mode."""
        request = SetModeRequest(mode="plan")

        assert request.mode == "plan"

    def test_accepts_bypass_permissions_mode(self) -> None:
        """SetModeRequest should accept 'bypassPermissions' mode."""
        request = SetModeRequest(mode="bypassPermissions")

        assert request.mode == "bypassPermissions"

    def test_rejects_invalid_mode(self) -> None:
        """SetModeRequest should reject unknown mode values."""
        with pytest.raises(ValidationError):
            SetModeRequest(mode="invalid_mode")

    def test_rejects_missing_mode(self) -> None:
        """SetModeRequest should require mode field."""
        with pytest.raises(ValidationError):
            SetModeRequest.model_validate({})
