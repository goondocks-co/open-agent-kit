"""Pydantic models for ACP execution events.

These models define the NDJSON streaming format used between the daemon
and the ACP stdio bridge.  Each line in the stream is a JSON-serialized
``ExecutionEvent`` subclass.

The daemon yields these events as it processes a prompt via the
InteractiveSessionManager.  The ACP bridge reads them and translates
each into the appropriate ACP SDK helper call.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Plan entry data (shared between plan events)
# ---------------------------------------------------------------------------


class PlanEntryData(BaseModel):
    """A single entry in a task plan (maps to ACP's plan_entry)."""

    content: str
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["pending", "in_progress", "completed"] = "pending"


# ---------------------------------------------------------------------------
# Event type literal
# ---------------------------------------------------------------------------

EventType = Literal[
    "text",
    "thought",
    "tool_start",
    "tool_progress",
    "tool_result",
    "plan_update",
    "plan_proposed",
    "cost",
    "done",
    "error",
    "cancelled",
]


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


class ExecutionEvent(BaseModel):
    """Base class for all NDJSON execution events."""

    type: EventType


# ---------------------------------------------------------------------------
# Concrete event types
# ---------------------------------------------------------------------------


class TextEvent(ExecutionEvent):
    """Agent response text."""

    type: Literal["text"] = "text"
    text: str


class ThoughtEvent(ExecutionEvent):
    """Agent internal reasoning (thinking block)."""

    type: Literal["thought"] = "thought"
    text: str


class ToolStartEvent(ExecutionEvent):
    """Tool invocation started."""

    type: Literal["tool_start"] = "tool_start"
    tool_id: str
    tool_name: str
    tool_input: dict = Field(default_factory=dict)


class ToolProgressEvent(ExecutionEvent):
    """Tool execution progress update."""

    type: Literal["tool_progress"] = "tool_progress"
    tool_id: str
    status: Literal["in_progress", "completed", "failed"] = "in_progress"


class ToolResultEvent(ExecutionEvent):
    """Tool execution completed."""

    type: Literal["tool_result"] = "tool_result"
    tool_id: str
    output_summary: str = ""
    success: bool = True


class PlanUpdateEvent(ExecutionEvent):
    """Task breakdown for visibility (maps to ACP update_plan)."""

    type: Literal["plan_update"] = "plan_update"
    entries: list[PlanEntryData] = Field(default_factory=list)


class PlanProposedEvent(ExecutionEvent):
    """ExitPlanMode content that needs user approval."""

    type: Literal["plan_proposed"] = "plan_proposed"
    plan: str


class CostEvent(ExecutionEvent):
    """Token usage and cost tracking."""

    type: Literal["cost"] = "cost"
    total_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class DoneEvent(ExecutionEvent):
    """Stream completed."""

    type: Literal["done"] = "done"
    session_id: str = ""
    needs_plan_approval: bool = False


class ErrorEvent(ExecutionEvent):
    """Error during execution."""

    type: Literal["error"] = "error"
    message: str


class CancelledEvent(ExecutionEvent):
    """Execution was cancelled."""

    type: Literal["cancelled"] = "cancelled"


# ---------------------------------------------------------------------------
# Discriminated union for deserialization
# ---------------------------------------------------------------------------

AnyExecutionEvent = (
    TextEvent
    | ThoughtEvent
    | ToolStartEvent
    | ToolProgressEvent
    | ToolResultEvent
    | PlanUpdateEvent
    | PlanProposedEvent
    | CostEvent
    | DoneEvent
    | ErrorEvent
    | CancelledEvent
)


def parse_execution_event(data: dict) -> AnyExecutionEvent:
    """Parse a dictionary into the correct ExecutionEvent subclass.

    Uses the ``type`` field as discriminator.

    Args:
        data: Dictionary from JSON deserialization.

    Returns:
        The appropriate ExecutionEvent subclass instance.

    Raises:
        ValueError: If the ``type`` field is missing or unrecognized.
    """
    event_type = data.get("type")
    if not event_type:
        raise ValueError("Missing 'type' field in execution event")

    type_map: dict[str, type[AnyExecutionEvent]] = {
        "text": TextEvent,
        "thought": ThoughtEvent,
        "tool_start": ToolStartEvent,
        "tool_progress": ToolProgressEvent,
        "tool_result": ToolResultEvent,
        "plan_update": PlanUpdateEvent,
        "plan_proposed": PlanProposedEvent,
        "cost": CostEvent,
        "done": DoneEvent,
        "error": ErrorEvent,
        "cancelled": CancelledEvent,
    }

    cls = type_map.get(event_type)
    if cls is None:
        raise ValueError(f"Unrecognized event type: {event_type}")

    return cls.model_validate(data)
