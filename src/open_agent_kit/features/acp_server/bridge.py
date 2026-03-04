"""Bridge between daemon execution events and ACP session updates.

Translates NDJSON ExecutionEvent objects from the daemon into ACP protocol
update payloads so the ACP client receives a stream of structured updates.
"""

from __future__ import annotations

import logging
from typing import Any

from acp import start_tool_call, text_block, update_agent_message
from acp.schema import ToolKind

from open_agent_kit.features.acp_server.constants import (
    ACP_COMMAND_TOOLS,
    ACP_EDIT_TOOLS,
    ACP_READ_TOOLS,
    ACP_TOOL_KIND_COMMAND,
    ACP_TOOL_KIND_EDIT,
    ACP_TOOL_KIND_READ,
)
from open_agent_kit.features.team.daemon.models_acp import (
    CancelledEvent,
    CostEvent,
    DoneEvent,
    ErrorEvent,
    ExecutionEvent,
    PlanProposedEvent,
    PlanUpdateEvent,
    TextEvent,
    ThoughtEvent,
    ToolProgressEvent,
    ToolResultEvent,
    ToolStartEvent,
)

logger = logging.getLogger(__name__)


class AcpBridge:
    """Static helpers that map daemon ExecutionEvents to ACP update payloads."""

    @staticmethod
    def classify_tool_kind(tool_name: str) -> ToolKind:
        """Classify a tool name into an ACP tool kind.

        Returns one of ``read``, ``edit``, or ``execute``.
        """
        if tool_name in ACP_READ_TOOLS:
            return ACP_TOOL_KIND_READ
        if tool_name in ACP_EDIT_TOOLS:
            return ACP_TOOL_KIND_EDIT
        if tool_name in ACP_COMMAND_TOOLS:
            return ACP_TOOL_KIND_COMMAND
        # Default unknown tools to execute (most restrictive)
        return ACP_TOOL_KIND_COMMAND

    @staticmethod
    def map_event(event: ExecutionEvent) -> list[Any]:
        """Convert an ExecutionEvent into ACP session updates.

        Args:
            event: An ExecutionEvent from the daemon NDJSON stream.

        Returns:
            A (possibly empty) list of ACP update payloads.
        """
        updates: list[Any] = []

        if isinstance(event, TextEvent):
            updates.append(update_agent_message(text_block(event.text)))

        elif isinstance(event, ThoughtEvent):
            # ACP SDK does not have a dedicated thought helper;
            # surface as agent message text
            updates.append(update_agent_message(text_block(event.text)))

        elif isinstance(event, ToolStartEvent):
            kind = AcpBridge.classify_tool_kind(event.tool_name)
            updates.append(start_tool_call(event.tool_id, event.tool_name, kind=kind))

        elif isinstance(event, ToolProgressEvent):
            # ACP SDK does not have update_tool_call; skip
            pass

        elif isinstance(event, ToolResultEvent):
            # Tool lifecycle handled by start; skip
            pass

        elif isinstance(event, PlanUpdateEvent):
            # ACP SDK does not have update_plan/plan_entry helpers;
            # render as formatted text
            if event.entries:
                lines = ["**Plan:**"]
                for entry in event.entries:
                    status_icon = {
                        "completed": "[x]",
                        "in_progress": "[-]",
                        "pending": "[ ]",
                    }.get(entry.status, "[ ]")
                    lines.append(f"- {status_icon} {entry.content}")
                updates.append(update_agent_message(text_block("\n".join(lines))))

        elif isinstance(event, PlanProposedEvent):
            updates.append(update_agent_message(text_block(event.plan)))

        elif isinstance(event, CostEvent):
            # No ACP equivalent; skip
            pass

        elif isinstance(event, DoneEvent):
            # Signal end of stream; handled by caller
            pass

        elif isinstance(event, ErrorEvent):
            updates.append(update_agent_message(text_block(event.message)))

        elif isinstance(event, CancelledEvent):
            # Cancellation signal; handled by caller
            pass

        return updates
