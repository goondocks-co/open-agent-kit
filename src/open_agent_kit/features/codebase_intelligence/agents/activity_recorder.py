"""Activity recording helpers for interactive ACP sessions.

Provides ``ActivityRecorder`` and module-level sanitization utilities
extracted from ``interactive.py`` to keep the session manager focused
on SDK orchestration.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

logger = logging.getLogger(__name__)

# Maximum length for sanitized tool input string values
SANITIZED_INPUT_MAX_LENGTH = 500

# Fields in tool_input that contain large content (file bodies, diffs)
_LARGE_CONTENT_FIELDS = frozenset({"content", "new_source", "old_string", "new_string"})


def sanitize_tool_input(tool_input: Any) -> dict[str, Any] | None:
    """Sanitize tool input by truncating large content fields.

    Args:
        tool_input: Raw tool input (dict or other).

    Returns:
        Sanitized dict, or None.
    """
    if not isinstance(tool_input, dict):
        return None

    sanitized: dict[str, Any] = {}
    for k, v in tool_input.items():
        if k in _LARGE_CONTENT_FIELDS:
            sanitized[k] = f"<{len(str(v))} chars>"
        elif isinstance(v, str) and len(v) > SANITIZED_INPUT_MAX_LENGTH:
            sanitized[k] = v[:SANITIZED_INPUT_MAX_LENGTH] + "..."
        else:
            sanitized[k] = v
    return sanitized


def build_output_summary(tool_name: str, tool_response: Any) -> str:
    """Build a concise output summary from tool response.

    Args:
        tool_name: Name of the tool.
        tool_response: Raw tool response.

    Returns:
        Truncated summary string.
    """
    if not tool_response:
        return ""

    response_str = str(tool_response)

    if tool_name == "Read" and len(response_str) > 200:
        return f"Read {len(response_str)} chars"

    return response_str[:SANITIZED_INPUT_MAX_LENGTH]


def handle_plan_detection(
    activity_store: ActivityStore,
    session_id: str,
    batch_id: int,
    tool_input: Any,
    project_root: Path,
) -> None:
    """Detect and record plan file writes.

    Args:
        activity_store: Store for batch updates.
        session_id: Current session.
        batch_id: Current batch ID.
        tool_input: Tool input dict from Write tool.
        project_root: Project root for path resolution.
    """
    from open_agent_kit.features.codebase_intelligence.constants import PROMPT_SOURCE_PLAN

    if not isinstance(tool_input, dict):
        return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    try:
        from open_agent_kit.features.codebase_intelligence.plan_detector import detect_plan

        detection = detect_plan(file_path)
        if not detection.is_plan:
            return

        plan_content = ""
        plan_path = Path(file_path)
        if not plan_path.is_absolute():
            plan_path = project_root / plan_path

        try:
            if plan_path.exists():
                plan_content = plan_path.read_text(encoding="utf-8")
            else:
                plan_content = tool_input.get("content", "")
        except (OSError, ValueError) as e:
            logger.debug(f"Failed to read plan file {plan_path}: {e}")
            plan_content = tool_input.get("content", "")

        activity_store.update_prompt_batch_source_type(
            batch_id,
            PROMPT_SOURCE_PLAN,
            plan_file_path=file_path,
            plan_content=plan_content,
        )
        logger.info(
            f"ACP: detected plan in Write to {file_path}, "
            f"batch {batch_id} ({len(plan_content)} chars)"
        )

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.debug(f"Plan detection failed: {e}")


def handle_exit_plan_mode(
    activity_store: ActivityStore,
    session_id: str,
    project_root: Path,
) -> None:
    """Re-read and update plan content on ExitPlanMode.

    Args:
        activity_store: Store for batch updates.
        session_id: Current session.
        project_root: Project root for path resolution.
    """
    from open_agent_kit.features.codebase_intelligence.constants import PROMPT_SOURCE_PLAN

    try:
        plan_batch = activity_store.get_session_plan_batch(session_id)
        if not (plan_batch and plan_batch.plan_file_path and plan_batch.id):
            return

        plan_path = Path(plan_batch.plan_file_path)
        if not plan_path.is_absolute():
            plan_path = project_root / plan_path

        if plan_path.exists():
            final_content = plan_path.read_text(encoding="utf-8")
            activity_store.update_prompt_batch_source_type(
                plan_batch.id,
                PROMPT_SOURCE_PLAN,
                plan_file_path=plan_batch.plan_file_path,
                plan_content=final_content,
            )
            activity_store.mark_plan_unembedded(plan_batch.id)
            logger.info(
                f"ACP ExitPlanMode: updated plan {plan_batch.id} ({len(final_content)} chars)"
            )
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.debug(f"ExitPlanMode handling failed: {e}")


class ActivityRecorder:
    """Builds SDK hooks for recording tool activities during ACP sessions.

    Encapsulates the hook callbacks that were previously module-level
    closures in ``InteractiveSessionManager._build_sdk_hooks()``.
    """

    def __init__(
        self,
        activity_store: ActivityStore,
        project_root: Path,
    ) -> None:
        self._activity_store = activity_store
        self._project_root = project_root

    def build_hooks(
        self,
        session_id: str,
        batch_id_ref: list[int | None],
        response_text_parts: list[str],
    ) -> dict[str, list[Any]]:
        """Build SDK hooks dict for activity recording.

        Args:
            session_id: Current session ID.
            batch_id_ref: Mutable reference [batch_id] so hooks see current batch.
            response_text_parts: Mutable list to accumulate response text.

        Returns:
            Dict suitable for ClaudeAgentOptions.hooks.
        """
        try:
            from claude_agent_sdk import HookJSONOutput, HookMatcher
        except ImportError:
            return {}

        activity_store = self._activity_store
        project_root = self._project_root

        async def _post_tool_use(
            input_data: Any,
            tool_use_id: str | None,
            context: Any,
        ) -> HookJSONOutput:
            """Record successful tool execution as an activity."""
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store.models import (
                    Activity,
                )

                tool_name = input_data.get("tool_name", "")
                tool_input = input_data.get("tool_input", {})
                tool_response = input_data.get("tool_response", "")

                sanitized_input = sanitize_tool_input(tool_input)
                output_summary = build_output_summary(tool_name, tool_response)

                activity = Activity(
                    session_id=session_id,
                    prompt_batch_id=batch_id_ref[0],
                    tool_name=tool_name,
                    tool_input=sanitized_input,
                    tool_output_summary=output_summary,
                    file_path=(
                        tool_input.get("file_path") if isinstance(tool_input, dict) else None
                    ),
                    success=True,
                )
                activity_store.add_activity_buffered(activity)
                logger.debug(f"ACP hook: stored activity {tool_name} (batch={batch_id_ref[0]})")

                if tool_name == "Write" and batch_id_ref[0] is not None:
                    handle_plan_detection(
                        activity_store,
                        session_id,
                        batch_id_ref[0],
                        tool_input,
                        project_root,
                    )

                if tool_name == "ExitPlanMode" and batch_id_ref[0] is not None:
                    handle_exit_plan_mode(activity_store, session_id, project_root)

            except Exception as e:
                logger.debug(f"ACP post-tool-use hook error: {e}")

            return {}

        async def _post_tool_use_failure(
            input_data: Any,
            tool_use_id: str | None,
            context: Any,
        ) -> HookJSONOutput:
            """Record failed tool execution as an activity."""
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store.models import (
                    Activity,
                )

                tool_name = input_data.get("tool_name", "unknown")
                tool_input = input_data.get("tool_input", {})
                error_message = str(input_data.get("tool_response", "Tool execution failed"))

                sanitized_input = sanitize_tool_input(tool_input)

                activity = Activity(
                    session_id=session_id,
                    prompt_batch_id=batch_id_ref[0],
                    tool_name=tool_name,
                    tool_input=sanitized_input,
                    tool_output_summary=error_message[:SANITIZED_INPUT_MAX_LENGTH],
                    file_path=(
                        tool_input.get("file_path") if isinstance(tool_input, dict) else None
                    ),
                    success=False,
                    error_message=error_message[:SANITIZED_INPUT_MAX_LENGTH],
                )
                activity_store.add_activity_buffered(activity)
                logger.debug(
                    f"ACP hook: stored failed activity {tool_name} (batch={batch_id_ref[0]})"
                )

            except Exception as e:
                logger.debug(f"ACP post-tool-use-failure hook error: {e}")

            return {}

        return {
            "PostToolUse": [
                HookMatcher(matcher=None, hooks=[_post_tool_use]),
            ],
            "PostToolUseFailure": [
                HookMatcher(matcher=None, hooks=[_post_tool_use_failure]),
            ],
        }
