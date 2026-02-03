"""CI notify handling commands: notify (hidden)."""

import json as json_module
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, cast

import typer

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_CODEX,
    AGENT_NOTIFY_ENDPOINT,
    AGENT_NOTIFY_FIELD_AGENT,
    AGENT_NOTIFY_FIELD_TYPE,
    AGENT_NOTIFY_PAYLOAD_DEFAULT,
    AGENT_NOTIFY_PAYLOAD_JOIN_SEPARATOR,
    CI_CORS_HOST_LOCALHOST,
    CI_DATA_DIR,
    DAEMON_START_TIMEOUT_SECONDS,
    ENCODING_UTF8,
    HTTP_HEADER_CONTENT_TYPE,
    HTTP_METHOD_POST,
    HTTP_TIMEOUT_HEALTH_CHECK,
    HTTP_TIMEOUT_LONG,
    OTLP_CONTENT_TYPE_JSON,
)

from . import ci_app


@ci_app.command("notify", hidden=True)
def ci_notify(
    agent: str = typer.Option(
        AGENT_CODEX,
        "--agent",
        "-a",
        help="Agent name (codex)",
    ),
    payload_file: Path | None = typer.Option(
        None,
        "--payload-file",
        "-p",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to notify payload JSON file",
    ),
    raw_payload: list[str] | None = typer.Argument(
        None,
        help="Notify payload JSON (passed by agent notify handler)",
    ),
) -> None:
    """Handle notify events from AI coding assistants.

    This command is invoked by notify configurations in .codex/config.toml.
    It reads JSON input from argv and calls the CI daemon notify API.

    Example:
        oak ci notify --agent codex '{"type": "agent-turn-complete", ...}'
    """
    from open_agent_kit.features.codebase_intelligence.daemon.manager import get_project_port

    project_root = Path.cwd()

    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
    port = get_project_port(project_root, ci_data_dir)

    def _coalesce_payload(payload_parts: list[str] | None) -> str:
        if not payload_parts:
            return AGENT_NOTIFY_PAYLOAD_DEFAULT
        return AGENT_NOTIFY_PAYLOAD_JOIN_SEPARATOR.join(payload_parts)

    def _load_notification_from_text(payload: str) -> dict[str, Any]:
        if not payload:
            return {}
        try:
            return cast(dict[str, Any], json_module.loads(payload))
        except json_module.JSONDecodeError:
            return {}

    def _load_notification_from_file(payload_path: Path) -> dict[str, Any]:
        try:
            return _load_notification_from_text(payload_path.read_text(encoding=ENCODING_UTF8))
        except OSError:
            return {}

    def _ensure_daemon_running() -> None:
        health_url = f"http://{CI_CORS_HOST_LOCALHOST}:{port}/api/health"
        try:
            with urllib.request.urlopen(health_url, timeout=HTTP_TIMEOUT_HEALTH_CHECK):
                return
        except Exception:
            pass

        try:
            import subprocess

            subprocess.run(
                ["oak", "ci", "start", "--quiet"],
                capture_output=True,
                timeout=DAEMON_START_TIMEOUT_SECONDS,
            )
        except Exception:
            pass

    def _call_api(payload: dict[str, Any]) -> dict[str, Any]:
        url = f"http://{CI_CORS_HOST_LOCALHOST}:{port}{AGENT_NOTIFY_ENDPOINT}"
        data = json_module.dumps(payload).encode(ENCODING_UTF8)
        req = urllib.request.Request(
            url,
            data=data,
            headers={HTTP_HEADER_CONTENT_TYPE: OTLP_CONTENT_TYPE_JSON},
            method=HTTP_METHOD_POST,
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_LONG) as resp:
                return cast(dict[str, Any], json_module.loads(resp.read().decode("utf-8")))
        except urllib.error.URLError:
            return {}
        except Exception:
            return {}

    payload = _coalesce_payload(raw_payload)
    notification = (
        _load_notification_from_file(payload_file)
        if payload_file
        else _load_notification_from_text(payload)
    )
    event_type = notification.get(AGENT_NOTIFY_FIELD_TYPE)
    if not event_type:
        return

    body = dict(notification)
    body[AGENT_NOTIFY_FIELD_AGENT] = agent

    _ensure_daemon_running()
    _call_api(body)
