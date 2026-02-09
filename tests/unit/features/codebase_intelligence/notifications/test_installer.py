"""Tests for notification installer CLI command rendering."""

from pathlib import Path
from unittest.mock import MagicMock

from open_agent_kit.features.codebase_intelligence.cli_command import CLI_COMMAND_PLACEHOLDER
from open_agent_kit.features.codebase_intelligence.notifications.installer import (
    NotificationsInstaller,
)


def test_render_notify_config_renders_configured_cli_command(tmp_path: Path) -> None:
    """Notify config rendering should use configured CLI executable."""
    installer = NotificationsInstaller(tmp_path, "codex")
    installer.cli_command = "oak-dev"

    notify_config = MagicMock()
    notify_config.command = "oak"
    notify_config.args = ["ci", "notify", "--agent", "codex"]
    notify_config.script_template = None
    notify_config.script_path = None
    notify_config.enabled = True
    notify_config.config_key = "notify"

    notifications_config = MagicMock()
    notifications_config.notify = notify_config
    installer._notifications_config = notifications_config

    template_path = tmp_path / "notify_config.toml.j2"
    template_path.write_text(
        'notify = ["{oak-cli-command}"{% for arg in notify_args %}, "{{ arg }}"{% endfor %}]'
    )

    rendered = installer._render_notify_config(template_path, script_path=None)
    assert rendered["notify"][0] == "oak-dev"


def test_notify_template_uses_cli_command_placeholder() -> None:
    """Notify template must use the explicit CLI command placeholder."""
    template_path = Path(
        "src/open_agent_kit/features/codebase_intelligence/notifications/codex/notify_config.toml.j2"
    )
    template_content = template_path.read_text(encoding="utf-8")

    assert CLI_COMMAND_PLACEHOLDER in template_content
    assert '"oak"' not in template_content
