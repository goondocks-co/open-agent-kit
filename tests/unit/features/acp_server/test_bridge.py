"""Tests for the ACP bridge (ExecutionEvent -> ACP mapping)."""

from open_agent_kit.features.acp_server.bridge import AcpBridge
from open_agent_kit.features.acp_server.constants import (
    ACP_TOOL_KIND_COMMAND,
    ACP_TOOL_KIND_EDIT,
    ACP_TOOL_KIND_READ,
)
from open_agent_kit.features.team.daemon.models_acp import (
    CancelledEvent,
    CostEvent,
    DoneEvent,
    ErrorEvent,
    PlanEntryData,
    PlanProposedEvent,
    PlanUpdateEvent,
    TextEvent,
    ThoughtEvent,
    ToolProgressEvent,
    ToolResultEvent,
    ToolStartEvent,
)


class TestClassifyToolKind:
    def test_read_tools(self):
        for tool in ("Read", "Glob", "Grep", "LS", "NotebookRead"):
            assert AcpBridge.classify_tool_kind(tool) == ACP_TOOL_KIND_READ

    def test_edit_tools(self):
        for tool in ("Edit", "MultiEdit", "Write", "NotebookEdit"):
            assert AcpBridge.classify_tool_kind(tool) == ACP_TOOL_KIND_EDIT

    def test_command_tools(self):
        for tool in ("Bash", "Task"):
            assert AcpBridge.classify_tool_kind(tool) == ACP_TOOL_KIND_COMMAND

    def test_unknown_tool_defaults_to_command(self):
        assert AcpBridge.classify_tool_kind("UnknownTool") == ACP_TOOL_KIND_COMMAND


class TestMapEvent:
    def test_text_event_produces_update(self):
        """TextEvent produces update_agent_message."""
        event = TextEvent(text="Hello world")
        updates = AcpBridge.map_event(event)
        assert len(updates) == 1

    def test_thought_event_produces_update(self):
        """ThoughtEvent produces update_agent_message (no dedicated helper)."""
        event = ThoughtEvent(text="Let me think about this...")
        updates = AcpBridge.map_event(event)
        assert len(updates) == 1

    def test_tool_start_produces_tool_call(self):
        """ToolStartEvent produces start_tool_call with correct kind."""
        event = ToolStartEvent(tool_id="call-1", tool_name="Read")
        updates = AcpBridge.map_event(event)
        assert len(updates) == 1

    def test_tool_progress_returns_empty(self):
        """ToolProgressEvent is skipped (no ACP equivalent)."""
        event = ToolProgressEvent(tool_id="call-1", status="in_progress")
        updates = AcpBridge.map_event(event)
        assert updates == []

    def test_tool_result_returns_empty(self):
        """ToolResultEvent is skipped (lifecycle handled by start)."""
        event = ToolResultEvent(tool_id="call-1", output_summary="done")
        updates = AcpBridge.map_event(event)
        assert updates == []

    def test_plan_update_renders_as_text(self):
        """PlanUpdateEvent renders entries as formatted text."""
        entries = [
            PlanEntryData(content="Read the file", status="completed"),
            PlanEntryData(content="Edit the module", status="in_progress"),
            PlanEntryData(content="Run tests", status="pending"),
        ]
        event = PlanUpdateEvent(entries=entries)
        updates = AcpBridge.map_event(event)
        assert len(updates) == 1

    def test_plan_update_empty_returns_empty(self):
        """PlanUpdateEvent with no entries returns empty."""
        event = PlanUpdateEvent(entries=[])
        updates = AcpBridge.map_event(event)
        assert updates == []

    def test_plan_proposed_produces_update(self):
        """PlanProposedEvent produces update_agent_message."""
        event = PlanProposedEvent(plan="Step 1: Do something\nStep 2: Do more")
        updates = AcpBridge.map_event(event)
        assert len(updates) == 1

    def test_cost_event_returns_empty(self):
        """CostEvent is skipped (no ACP equivalent)."""
        event = CostEvent(total_cost_usd=0.05, input_tokens=100, output_tokens=50)
        updates = AcpBridge.map_event(event)
        assert updates == []

    def test_done_event_returns_empty(self):
        """DoneEvent is handled by caller, not bridge."""
        event = DoneEvent(session_id="s1")
        updates = AcpBridge.map_event(event)
        assert updates == []

    def test_error_event_produces_update(self):
        """ErrorEvent produces update_agent_message."""
        event = ErrorEvent(message="Something went wrong")
        updates = AcpBridge.map_event(event)
        assert len(updates) == 1

    def test_cancelled_event_returns_empty(self):
        """CancelledEvent is handled by caller."""
        event = CancelledEvent()
        updates = AcpBridge.map_event(event)
        assert updates == []
