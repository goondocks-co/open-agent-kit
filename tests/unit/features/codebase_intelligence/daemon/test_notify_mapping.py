"""Tests for notify event mapping from agent manifests."""

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_CODEX,
    AGENT_NOTIFY_ACTION_RESPONSE_SUMMARY,
    AGENT_NOTIFY_COMMAND_ARGS_CODEX,
    AGENT_NOTIFY_COMMAND_OAK,
    AGENT_NOTIFY_EVENT_TURN_COMPLETE,
    AGENT_NOTIFY_FIELD_INPUT_MESSAGES,
    AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE,
    AGENT_NOTIFY_FIELD_THREAD_ID,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes import (
    notifications as notifications_routes,
)
from open_agent_kit.services.agent_service import AgentService


def test_codex_manifest_notify_mapping_includes_turn_complete() -> None:
    """Codex manifest should map notify events to CI actions."""
    service = AgentService()
    manifest = service.get_agent_manifest(AGENT_CODEX)

    notifications = manifest.notifications
    assert notifications is not None
    notify = notifications.notify
    assert notify is not None

    mapping = notify.event_mapping
    assert mapping[AGENT_NOTIFY_EVENT_TURN_COMPLETE] == AGENT_NOTIFY_ACTION_RESPONSE_SUMMARY
    assert notify.session_id_field == AGENT_NOTIFY_FIELD_THREAD_ID
    assert notify.response_field == AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE
    assert notify.input_messages_field == AGENT_NOTIFY_FIELD_INPUT_MESSAGES
    assert notify.command == AGENT_NOTIFY_COMMAND_OAK
    assert notify.args == list(AGENT_NOTIFY_COMMAND_ARGS_CODEX)


def test_combined_notify_mapping_exposes_codex_fields() -> None:
    """Combined notify mapping should include Codex config fields."""
    event_mapping, session_id_fields, response_fields, input_messages_fields = (
        notifications_routes._build_notify_mapping()
    )

    assert (
        event_mapping[AGENT_CODEX][AGENT_NOTIFY_EVENT_TURN_COMPLETE]
        == AGENT_NOTIFY_ACTION_RESPONSE_SUMMARY
    )
    assert session_id_fields[AGENT_CODEX] == AGENT_NOTIFY_FIELD_THREAD_ID
    assert response_fields[AGENT_CODEX] == AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE
    assert input_messages_fields[AGENT_CODEX] == AGENT_NOTIFY_FIELD_INPUT_MESSAGES
