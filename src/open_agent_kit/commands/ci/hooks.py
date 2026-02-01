"""CI hook handling commands: hook (hidden)."""

import base64
import json as json_module
import select
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import typer

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_DATA_DIR,
    DAEMON_START_TIMEOUT_SECONDS,
    HOOK_STDIN_TIMEOUT_SECONDS,
    HTTP_TIMEOUT_HEALTH_CHECK,
    HTTP_TIMEOUT_LONG,
)

from . import ci_app


@ci_app.command("hook", hidden=True)
def ci_hook(
    event: str = typer.Argument(..., help="Hook event name (e.g., SessionStart, PostToolUse)"),
    agent: str = typer.Option(
        "claude",
        "--agent",
        "-a",
        help="Agent name (claude, cursor, copilot, gemini)",
    ),
) -> None:
    """Handle hook events from AI coding assistants.

    This command is invoked by hook configurations in .claude/settings.json,
    .cursor/hooks.json, etc. It reads JSON input from stdin and calls the
    CI daemon API.

    This is a cross-platform replacement for the shell scripts, eliminating
    dependencies on bash, jq, and curl.

    Examples:
        echo '{"session_id": "123"}' | oak ci hook SessionStart
        echo '{"prompt": "hello"}' | oak ci hook UserPromptSubmit --agent cursor
    """
    from open_agent_kit.features.codebase_intelligence.daemon.manager import get_project_port

    project_root = Path.cwd()

    # Get daemon port (same priority as shell scripts)
    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
    port = get_project_port(project_root, ci_data_dir)

    # Read input from stdin with timeout to prevent blocking
    # Claude sends hook data as a single JSON line, so we use readline()
    # instead of read() which would block waiting for EOF
    try:
        # Wait up to 2 seconds for stdin to be readable
        if select.select([sys.stdin], [], [], HOOK_STDIN_TIMEOUT_SECONDS)[0]:
            # Use readline() since Claude sends JSON as a single line
            # read() would block waiting for EOF which Claude may not send
            input_data = sys.stdin.readline()
            if input_data.strip():
                input_json = cast(dict[str, Any], json_module.loads(input_data))
            else:
                input_json = {}
        else:
            # No stdin available within timeout
            input_json = {}
    except Exception:
        input_json = {}

    # Extract common fields
    session_id = input_json.get("session_id") or input_json.get("conversation_id") or ""
    conversation_id = input_json.get("conversation_id") or ""
    generation_id = input_json.get("generation_id") or ""
    tool_use_id = input_json.get("tool_use_id") or ""
    hook_origin = f"{agent}_config"

    # Log to hooks.log
    hooks_log = ci_data_dir / "hooks.log"
    try:
        hooks_log.parent.mkdir(parents=True, exist_ok=True)
        with open(hooks_log, "a") as f:
            f.write(
                f"[{event}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} session_id={session_id or 'unknown'}\n"
            )
    except Exception:
        pass  # Logging is best-effort

    def _call_api(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP POST to daemon API."""
        url = f"http://localhost:{port}/api/oak/ci/{endpoint}"
        data = json_module.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_LONG) as resp:
                return cast(dict[str, Any], json_module.loads(resp.read().decode("utf-8")))
        except urllib.error.URLError:
            return {}
        except Exception:
            return {}

    def _ensure_daemon_running() -> None:
        """Ensure daemon is running, start if not."""
        health_url = f"http://localhost:{port}/api/health"
        try:
            with urllib.request.urlopen(health_url, timeout=HTTP_TIMEOUT_HEALTH_CHECK):
                return  # Daemon is running
        except Exception:
            pass

        # Try to start daemon quietly
        try:
            import subprocess

            subprocess.run(
                ["oak", "ci", "start", "--quiet"],
                capture_output=True,
                timeout=DAEMON_START_TIMEOUT_SECONDS,
            )
        except Exception:
            pass

    def _format_claude_response(response: dict[str, Any], event_name: str) -> dict[str, Any]:
        """Format response for Claude Code hooks."""
        injected = response.get("context", {}).get("injected_context") or response.get(
            "injected_context"
        )
        if injected:
            return {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": injected,
                }
            }
        return {}

    def _format_cursor_response(response: dict[str, Any]) -> dict[str, Any]:
        """Format response for Cursor hooks."""
        injected = response.get("context", {}).get("injected_context")
        if injected:
            return {"additional_context": injected}
        return {}

    # Map events to their handlers (normalized to handle different casing)
    event_lower = event.lower()
    output: dict[str, Any] = {}

    try:
        if event_lower == "sessionstart":
            _ensure_daemon_running()
            source = input_json.get("source", "startup")
            response = _call_api(
                "session-start",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "source": source,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )
            if agent == "claude":
                output = _format_claude_response(response, "SessionStart")
            elif agent == "cursor":
                output = _format_cursor_response(response)

        elif event_lower in ("userpromptsubmit", "beforesubmitprompt", "userpromptsubmitted"):
            prompt_text = input_json.get("prompt", "")
            response = _call_api(
                "prompt-submit",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "prompt": prompt_text,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )
            if agent == "claude":
                output = _format_claude_response(response, "UserPromptSubmit")
            elif agent == "cursor":
                # Cursor expects continue: true for beforeSubmitPrompt
                output = {"continue": True}

        elif event_lower in ("posttooluse", "afterfileedit", "afteragentresponse"):
            tool_name = input_json.get("tool_name", "")
            tool_input = input_json.get("tool_input", {})
            tool_response = input_json.get("tool_response", {})

            # Handle Cursor-specific events
            if event_lower == "afterfileedit":
                tool_name = "Edit"
                tool_input = {
                    "file_path": input_json.get("file_path"),
                    "edits": input_json.get("edits", []),
                }
            elif event_lower == "afteragentresponse":
                tool_name = "agent_response"
                tool_response = input_json.get("text", "")

            # Base64 encode tool output
            try:
                tool_output_str = (
                    json_module.dumps(tool_response)
                    if isinstance(tool_response, (dict, list))
                    else str(tool_response)
                )
                tool_output_b64 = base64.b64encode(tool_output_str.encode()).decode()
            except Exception:
                tool_output_b64 = ""

            response = _call_api(
                "post-tool-use",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_output_b64": tool_output_b64,
                    "tool_use_id": tool_use_id,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )
            if agent == "claude":
                output = _format_claude_response(response, "PostToolUse")

        elif event_lower == "stop":
            _call_api(
                "stop",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )

        elif event_lower == "sessionend":
            _call_api(
                "session-end",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )

        elif event_lower in ("posttoolusefailure", "erroroccurred"):
            tool_name = input_json.get("tool_name", "unknown")
            error_msg = input_json.get("error", {})
            if isinstance(error_msg, dict):
                error_msg = error_msg.get("message", str(error_msg))
            _call_api(
                "post-tool-use-failure",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "tool_name": tool_name,
                    "tool_input": input_json.get("tool_input", {}),
                    "tool_use_id": tool_use_id,
                    "error_message": str(error_msg),
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                },
            )

        elif event_lower == "subagentstart":
            agent_id = input_json.get("agent_id", "")
            agent_type = input_json.get("agent_type") or input_json.get("subagent_type", "unknown")
            _call_api(
                "subagent-start",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                },
            )

        elif event_lower == "subagentstop":
            agent_id = input_json.get("agent_id", "")
            agent_type = input_json.get("agent_type") or input_json.get("subagent_type", "unknown")
            transcript_path = input_json.get("agent_transcript_path", "")
            stop_hook_active = input_json.get("stop_hook_active", False)
            _call_api(
                "subagent-stop",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "agent_transcript_path": transcript_path,
                    "stop_hook_active": stop_hook_active,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                },
            )

        elif event_lower == "afteragentthought":
            # Agent thinking/reasoning block completed
            thought_text = input_json.get("text", "")
            duration_ms = input_json.get("duration_ms", 0)
            _call_api(
                "agent-thought",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "text": thought_text,
                    "duration_ms": duration_ms,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )

        elif event_lower == "precompact":
            # Context window compaction event
            _call_api(
                "pre-compact",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "trigger": input_json.get("trigger", "auto"),
                    "context_usage_percent": input_json.get("context_usage_percent", 0),
                    "context_tokens": input_json.get("context_tokens", 0),
                    "context_window_size": input_json.get("context_window_size", 0),
                    "message_count": input_json.get("message_count", 0),
                    "messages_to_compact": input_json.get("messages_to_compact", 0),
                    "is_first_compaction": input_json.get("is_first_compaction", False),
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )

    except Exception:
        pass  # Hooks should never crash the calling tool

    # Output JSON response
    print(json_module.dumps(output))
