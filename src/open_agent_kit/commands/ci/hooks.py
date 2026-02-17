"""CI hook handling commands: hook (hidden)."""

import base64
import json as json_module
import os
import select
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import typer

from open_agent_kit.config.paths import GIT_DIR, OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_CLAUDE,
    AGENTS_REQUIRE_HOOK_SPECIFIC_OUTPUT,
    CI_AUTH_SCHEME_BEARER,
    CI_DATA_DIR,
    CI_TOKEN_FILE,
    DAEMON_HEALTH_POLL_INTERVAL,
    DAEMON_START_TIMEOUT_SECONDS,
    HOOK_STDIN_TIMEOUT_SECONDS,
    HTTP_TIMEOUT_HEALTH_CHECK,
    HTTP_TIMEOUT_LONG,
)

from . import ci_app


def _find_project_root() -> Path:
    """Find the true project root by walking up from cwd.

    When AI agents change their working directory (e.g., ``cd daemon/ui &&
    npm run build``), ``Path.cwd()`` no longer points at the repo root.
    This causes hooks to write to an orphaned ``.oak/ci/`` directory and
    fail to reach the daemon.

    Resolution order:
      1. Walk up from cwd looking for ``.oak/`` (OAK project marker).
      2. Fall back to ``.git/`` (git repo root).
      3. Fall back to cwd itself (original behavior).
    """
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / OAK_DIR).is_dir():
            return candidate
    # No .oak found — try .git as a fallback repo root marker
    for candidate in (cwd, *cwd.parents):
        if (candidate / GIT_DIR).exists():
            return candidate
    return cwd


@ci_app.command("hook", hidden=True)
def ci_hook(
    event: str = typer.Argument(..., help="Hook event name (e.g., SessionStart, PostToolUse)"),
    agent: str = typer.Option(
        AGENT_CLAUDE,
        "--agent",
        "-a",
        help="Agent name (claude, cursor, copilot, gemini, windsurf)",
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

    # Find true project root by walking up from cwd.
    # Claude Code may change cwd (e.g., `cd daemon/ui && npm run build`),
    # causing hooks to target the wrong .oak/ci directory. Walking up to
    # find the .oak/ or .git/ marker ensures we always reach the real root.
    project_root = _find_project_root()

    # Get daemon port (same priority as shell scripts)
    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
    port = get_project_port(project_root, ci_data_dir)

    # Read input from stdin with timeout to prevent blocking
    # Claude sends hook data as a single JSON line, so we use readline()
    # instead of read() which would block waiting for EOF
    try:
        # Wait up to 2 seconds for stdin to be readable
        if select.select([sys.stdin], [], [], HOOK_STDIN_TIMEOUT_SECONDS)[0]:
            # Use os.read() on the raw fd instead of readline().
            # readline() blocks until it sees '\n' or EOF — if an agent sends
            # JSON without a trailing newline and keeps stdin open (as Windsurf
            # does), readline() hangs indefinitely, freezing the agent's UI.
            # os.read() returns immediately with available bytes after select()
            # confirms readability.
            raw_bytes = os.read(sys.stdin.fileno(), 65536)
            input_data = raw_bytes.decode("utf-8", errors="replace").strip()
            if input_data:
                input_json = cast(dict[str, Any], json_module.loads(input_data))
            else:
                input_json = {}
        else:
            # No stdin available within timeout
            input_json = {}
    except Exception:
        input_json = {}

    # Extract common fields (universal: accept alternative field names from any agent).
    # VS Code Copilot sends camelCase fields (sessionId, conversationId, generationId)
    # while Claude sends snake_case. Accept both.
    session_id = (
        input_json.get("session_id")
        or input_json.get("sessionId")
        or input_json.get("conversation_id")
        or input_json.get("conversationId")
        or input_json.get("trajectory_id")
        or ""
    )
    conversation_id = input_json.get("conversation_id") or input_json.get("conversationId") or ""
    generation_id = (
        input_json.get("generation_id")
        or input_json.get("generationId")
        or input_json.get("execution_id")
        or ""
    )

    # Flatten nested tool_info (Windsurf nests tool data under tool_info)
    if "tool_info" in input_json:
        input_json.update(input_json.pop("tool_info"))
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

    def _get_auth_token() -> str | None:
        """Read the daemon auth token from the token file.

        Returns:
            The token string, or None if the file doesn't exist or can't be read.
        """
        try:
            token_path = ci_data_dir / CI_TOKEN_FILE
            if token_path.is_file():
                return token_path.read_text().strip() or None
        except Exception:
            pass
        return None

    def _call_api(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP POST to daemon API."""
        url = f"http://localhost:{port}/api/oak/ci/{endpoint}"
        data = json_module.dumps(payload).encode("utf-8")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        token = _get_auth_token()
        if token:
            headers["Authorization"] = f"{CI_AUTH_SCHEME_BEARER} {token}"
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_LONG) as resp:
                return cast(dict[str, Any], json_module.loads(resp.read().decode("utf-8")))
        except urllib.error.URLError:
            return {}
        except Exception:
            return {}

    def _ensure_daemon_running(*, blocking: bool = True) -> None:
        """Ensure daemon is running, start if not.

        Args:
            blocking: If True (default), wait for daemon to start before returning.
                Used by sessionStart which needs the daemon ready for context injection.
                If False, start daemon in background and return immediately.
                Used by prompt-submit hooks for agents without sessionStart (e.g., Windsurf)
                where blocking would freeze the agent's UI.
        """
        health_url = f"http://localhost:{port}/api/health"
        try:
            with urllib.request.urlopen(health_url, timeout=HTTP_TIMEOUT_HEALTH_CHECK):
                return  # Daemon is running
        except Exception:
            pass

        # Start daemon in background. Using Popen instead of subprocess.run
        # so we can poll health directly — this returns as soon as the daemon
        # is healthy rather than waiting for `oak ci start` to fully exit.
        from open_agent_kit.features.codebase_intelligence.cli_command import (
            resolve_ci_cli_command,
        )

        cli_bin = resolve_ci_cli_command(project_root)
        try:
            import subprocess

            subprocess.Popen(
                [cli_bin, "ci", "start", "--quiet"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return  # Can't start daemon, nothing more to do

        if not blocking:
            return

        # Poll health endpoint until the daemon is ready or we hit the timeout.
        # On warm starts this returns in ~2s; cold starts (ChromaDB init,
        # embedding model load) may take 15-20s.
        import time

        deadline = time.monotonic() + DAEMON_START_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(health_url, timeout=HTTP_TIMEOUT_HEALTH_CHECK):
                    return  # Daemon is ready
            except Exception:
                time.sleep(DAEMON_HEALTH_POLL_INTERVAL)

    # Map events to their handlers (normalized to handle different casing)
    event_lower = event.lower()
    output: dict[str, Any] = {}

    try:
        if event_lower == "sessionstart":
            _ensure_daemon_running()
            source = input_json.get("source", "startup")
            parent_session_id = input_json.get("parent_session_id", "")
            response = _call_api(
                "session-start",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "source": source,
                    "parent_session_id": parent_session_id,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )
            output = response.get("hook_output", {})

        elif event_lower in (
            "userpromptsubmit",
            "beforesubmitprompt",
            "userpromptsubmitted",
            "beforeagent",
            "pre_user_prompt",
        ):
            # Ensure daemon is running for agents without a dedicated sessionStart hook.
            # Non-blocking: start daemon in background so it's ready for subsequent hooks.
            # The current API call may fail fast (connection refused), which is acceptable —
            # the daemon will be ready by the next prompt.
            _ensure_daemon_running(blocking=False)
            prompt_text = input_json.get("prompt", "") or input_json.get("user_prompt", "")
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
            output = response.get("hook_output", {})

        elif event_lower == "pretooluse":
            tool_name = input_json.get("tool_name", "")
            tool_input = input_json.get("tool_input", {})
            tool_use_id = input_json.get("tool_use_id", "")
            response = _call_api(
                "pre-tool-use",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "tool_use_id": tool_use_id,
                    "hook_origin": hook_origin,
                    "hook_event_name": event,
                    "generation_id": generation_id,
                },
            )
            output = response.get("hook_output", {})

        elif event_lower in (
            "posttooluse",
            "afterfileedit",
            "afteragentresponse",
            "post_write_code",
            "post_read_code",
            "post_run_command",
            "post_mcp_tool_use",
        ):
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
            # Handle Windsurf-specific events
            elif event_lower == "post_write_code":
                tool_name = "Write"
                tool_input = {
                    "file_path": input_json.get("file_path"),
                    "edits": input_json.get("edits", []),
                }
            elif event_lower == "post_read_code":
                tool_name = "Read"
                tool_input = {"file_path": input_json.get("file_path")}
            elif event_lower == "post_run_command":
                tool_name = "Bash"
                tool_input = {
                    "command": input_json.get("command_line"),
                    "cwd": input_json.get("cwd"),
                }
            elif event_lower == "post_mcp_tool_use":
                tool_name = input_json.get("mcp_tool_name", "MCP")
                tool_input = input_json.get("mcp_tool_arguments", {})
                tool_response = input_json.get("mcp_result", "")

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
            output = response.get("hook_output", {})

        elif event_lower in ("stop", "afteragent", "post_cascade_response"):
            transcript_path = input_json.get("transcript_path", "")
            stop_hook_active = input_json.get("stop_hook_active", False)
            # Gemini CLI sends prompt_response (the agent's final answer);
            # Claude sends response_summary; Windsurf sends response.
            # Accept all field names.
            response_summary = (
                input_json.get("response_summary", "")
                or input_json.get("prompt_response", "")
                or input_json.get("response", "")
            )
            # Log what we receive for debugging
            try:
                with open(hooks_log, "a") as f:
                    f.write(
                        f"  [{event}:debug] transcript_path={transcript_path[:80] if transcript_path else '(empty)'} "
                        f"response_summary={'yes' if response_summary else 'no'} "
                        f"input_keys={list(input_json.keys())}\n"
                    )
            except Exception:
                pass
            _call_api(
                "stop",
                {
                    "agent": agent,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                    "transcript_path": transcript_path,
                    "response_summary": response_summary,
                    "stop_hook_active": stop_hook_active,
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

        elif event_lower in ("precompact", "precompress"):
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

    # Safety net for agents that REQUIRE hookSpecificOutput in every response.
    # VS Code Copilot crashes if hookSpecificOutput is missing for events
    # that support it (accesses .additionalContext on undefined).
    #
    # VS Code Copilot requires hookSpecificOutput in ALL hook responses,
    # not just events that the docs claim support it.  Without it, VS Code
    # crashes with:
    #   "Cannot read properties of undefined (reading 'hookSpecificOutput')"
    #
    # The daemon format_hook_output() handles this for --agent vscode-copilot.
    # This CLI safety net covers edge cases where the daemon returns empty
    # output (e.g. events not handled by daemon routes).
    #
    # Claude Code is NOT included — it validates hookSpecificOutput against
    # its schema and rejects it for events without specific output.
    if agent in AGENTS_REQUIRE_HOOK_SPECIFIC_OUTPUT and "hookSpecificOutput" not in output:
        output = {
            "continue": True,
            "hookSpecificOutput": {"hookEventName": event},
        }

    # Dual-firing safety: VS Code Copilot reads hooks from BOTH
    # .claude/settings.local.json (--agent claude) AND .github/hooks/
    # (--agent vscode-copilot).  When running inside VS Code (detected
    # via VSCODE_PID), the --agent claude hook is redundant — the
    # --agent vscode-copilot hook handles context injection.
    #
    # Return empty hookSpecificOutput so VS Code doesn't crash when
    # processing the result.  Context injection is left to the
    # --agent vscode-copilot hook.
    if os.environ.get("VSCODE_PID") and agent == AGENT_CLAUDE:
        output = {
            "continue": True,
            "hookSpecificOutput": {"hookEventName": event},
        }

    # Output JSON response
    print(json_module.dumps(output))
