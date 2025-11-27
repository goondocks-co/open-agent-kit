"""Tests for OTEL event mapping from agent manifests."""

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_CODEX,
    HOOK_EVENT_POST_TOOL_USE,
    HOOK_EVENT_PROMPT_SUBMIT,
    HOOK_EVENT_SESSION_START,
    OTEL_ATTR_CONVERSATION_ID,
    OTEL_EVENT_CODEX_CONVERSATION_STARTS,
    OTEL_EVENT_CODEX_TOOL_DECISION,
    OTEL_EVENT_CODEX_TOOL_RESULT,
    OTEL_EVENT_CODEX_USER_PROMPT,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes import otel as otel_routes
from open_agent_kit.services.agent_service import AgentService


def test_codex_manifest_otel_mapping_includes_session_and_prompt_events() -> None:
    """Codex manifest should map core OTEL events to hook actions."""
    service = AgentService()
    manifest = service.get_agent_manifest(AGENT_CODEX)

    hooks = manifest.hooks
    assert hooks is not None
    otel = hooks.otel
    assert otel is not None

    mapping = otel.event_mapping
    assert mapping[OTEL_EVENT_CODEX_CONVERSATION_STARTS] == HOOK_EVENT_SESSION_START
    assert mapping[OTEL_EVENT_CODEX_USER_PROMPT] == HOOK_EVENT_PROMPT_SUBMIT
    assert mapping[OTEL_EVENT_CODEX_TOOL_DECISION] == HOOK_EVENT_PROMPT_SUBMIT
    assert mapping[OTEL_EVENT_CODEX_TOOL_RESULT] == HOOK_EVENT_POST_TOOL_USE


def test_combined_otel_mapping_exposes_codex_session_id_attribute() -> None:
    """Combined OTEL mapping should expose Codex session id attribute."""
    event_mapping, session_id_attrs, _ = otel_routes._build_combined_event_mapping()

    assert event_mapping[OTEL_EVENT_CODEX_CONVERSATION_STARTS] == HOOK_EVENT_SESSION_START
    assert session_id_attrs[AGENT_CODEX] == OTEL_ATTR_CONVERSATION_ID
