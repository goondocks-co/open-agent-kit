"""Tests for agent settings template rendering and guardrails."""

from pathlib import Path

from open_agent_kit.features.codebase_intelligence.cli_command import CLI_COMMAND_PLACEHOLDER
from open_agent_kit.services.agent_settings_service import AgentSettingsService

AGENT_SETTINGS_DIR = Path("src/open_agent_kit/features/core/agent-settings")
AGENT_SETTINGS_JSON_GLOB = "*.json"
TEST_CLI_COMMAND = "oak-dev"
CLAUDE_TEMPLATE_KEY = "agent-settings/claude-settings.json"

HARDCODED_AGENT_SETTINGS_PATTERNS = (
    "Bash(oak:*)",
    "Bash(oak *)",
    "ShellTool(oak *)",
    '"oak *": "allow"',
    '"oak": true',
    '"oak"',
)


def test_agent_settings_template_renders_cli_command_placeholder(tmp_path: Path) -> None:
    """Agent settings templates should render the configured CLI command."""
    service = AgentSettingsService(project_root=tmp_path)
    service.cli_command = TEST_CLI_COMMAND

    service._get_auto_approve_config = lambda _agent: {  # type: ignore[method-assign]
        "enabled": True,
        "template": CLAUDE_TEMPLATE_KEY,
    }

    template = service._load_template("claude")

    assert template is not None
    allowlist = template["permissions"]["allow"]
    assert f"Bash({TEST_CLI_COMMAND}:*)" in allowlist
    assert f"Bash({TEST_CLI_COMMAND} *)" in allowlist


def test_agent_settings_templates_use_cli_command_placeholder() -> None:
    """Managed agent settings templates must use explicit CLI command placeholders."""
    errors: list[str] = []

    for template_path in sorted(AGENT_SETTINGS_DIR.glob(AGENT_SETTINGS_JSON_GLOB)):
        text = template_path.read_text(encoding="utf-8")

        if CLI_COMMAND_PLACEHOLDER not in text:
            errors.append(f"{template_path}: missing {CLI_COMMAND_PLACEHOLDER}")

        for pattern in HARDCODED_AGENT_SETTINGS_PATTERNS:
            if pattern in text:
                errors.append(f"{template_path}: contains hardcoded command pattern {pattern!r}")

    assert not errors, "Use '{oak-cli-command}' placeholder in:\n" + "\n".join(errors)


class TestScrubInvalidCliEntries:
    """Tests for _scrub_invalid_cli_entries removing stale .py entries."""

    def test_scrub_removes_dict_keys_with_py_command(self) -> None:
        """Dict keys containing a .py command should be removed."""
        settings = {
            "permission": {
                "bash": {
                    "oak *": "allow",
                    "oak-dev *": "allow",
                    "__main__.py *": "allow",
                }
            }
        }
        result = AgentSettingsService._scrub_invalid_cli_entries(settings)
        assert "__main__.py *" not in result["permission"]["bash"]
        assert "oak *" in result["permission"]["bash"]
        assert "oak-dev *" in result["permission"]["bash"]

    def test_scrub_removes_list_items_with_py_command(self) -> None:
        """List items containing a .py command should be removed."""
        settings = {
            "permissions": {
                "allow": [
                    "Bash(oak-dev:*)",
                    "Bash(oak-dev *)",
                    "Bash(__main__.py:*)",
                    "Bash(__main__.py *)",
                ]
            }
        }
        result = AgentSettingsService._scrub_invalid_cli_entries(settings)
        allow = result["permissions"]["allow"]
        assert "Bash(oak-dev:*)" in allow
        assert "Bash(oak-dev *)" in allow
        assert "Bash(__main__.py:*)" not in allow
        assert "Bash(__main__.py *)" not in allow

    def test_scrub_removes_shell_tool_py_entry(self) -> None:
        """ShellTool entries with .py commands should be removed."""
        settings = {"allowlist": ["ShellTool(oak-dev *)", "ShellTool(__main__.py *)"]}
        result = AgentSettingsService._scrub_invalid_cli_entries(settings)
        assert result["allowlist"] == ["ShellTool(oak-dev *)"]

    def test_scrub_preserves_clean_settings(self) -> None:
        """Settings without .py entries should be returned unchanged."""
        settings = {
            "permission": {"bash": {"oak-dev *": "allow"}},
            "mcp": {"oak-ci": {"type": "local"}},
        }
        result = AgentSettingsService._scrub_invalid_cli_entries(settings)
        assert result == settings

    def test_scrub_handles_empty_settings(self) -> None:
        """Empty settings dict should be returned as-is."""
        assert AgentSettingsService._scrub_invalid_cli_entries({}) == {}
