"""Tests for CI CLI command resolution and rewrite helpers."""

from pathlib import Path
from unittest.mock import patch

import yaml

from open_agent_kit.features.team.cli_command import (
    detect_invoked_cli_command,
    resolve_ci_cli_command,
    rewrite_oak_command,
)
from open_agent_kit.features.team.constants import (
    CI_CLI_COMMAND_DEFAULT,
)


def test_resolve_cli_command_defaults_when_not_configured(tmp_path: Path) -> None:
    """Resolver should return default command when config is absent."""
    assert resolve_ci_cli_command(tmp_path) == CI_CLI_COMMAND_DEFAULT


def test_resolve_cli_command_from_project_config(tmp_path: Path) -> None:
    """Resolver should return configured project command."""
    oak_dir = tmp_path / ".oak"
    oak_dir.mkdir(parents=True)
    config_path = oak_dir / "config.yaml"
    config_path.write_text(
        yaml.dump(
            {"team": {"cli_command": "oak-dev"}},
            sort_keys=False,
        )
    )

    assert resolve_ci_cli_command(tmp_path) == "oak-dev"


def test_rewrite_oak_command_rewrites_root_command() -> None:
    """Rewriter should transform plain ``oak`` command."""
    assert rewrite_oak_command("oak", "oak-dev") == "oak-dev"


def test_rewrite_oak_command_rewrites_prefixed_command() -> None:
    """Rewriter should transform ``oak ...`` command prefix."""
    assert rewrite_oak_command("oak team mcp", "oak-dev") == "oak-dev team mcp"


def test_rewrite_oak_command_keeps_non_oak_commands() -> None:
    """Rewriter should preserve non-oak commands."""
    assert rewrite_oak_command("python -m app", "oak-dev") == "python -m app"


# -- detect_invoked_cli_command tests --


def test_detect_rejects_dunder_main_py() -> None:
    """Detector should reject __main__.py (e.g. python -m uvicorn)."""
    with patch("sys.argv", ["/path/to/uvicorn/__main__.py"]):
        assert detect_invoked_cli_command() == CI_CLI_COMMAND_DEFAULT


def test_detect_rejects_any_py_suffix() -> None:
    """Detector should reject any .py filename."""
    with patch("sys.argv", ["main.py"]):
        assert detect_invoked_cli_command() == CI_CLI_COMMAND_DEFAULT


def test_detect_accepts_oak() -> None:
    """Detector should accept plain 'oak' binary (stable package)."""
    with (
        patch("sys.argv", ["/usr/local/bin/oak"]),
        patch(
            "open_agent_kit.features.team.cli_command._correct_for_beta_package", return_value="oak"
        ),
    ):
        assert detect_invoked_cli_command() == "oak"


def test_detect_accepts_oak_dev() -> None:
    """Detector should accept 'oak-dev' binary."""
    with patch("sys.argv", ["/home/user/.local/bin/oak-dev"]):
        assert detect_invoked_cli_command() == "oak-dev"


def test_detect_accepts_oak_beta() -> None:
    """Detector should accept 'oak-beta' binary."""
    with patch("sys.argv", ["/usr/bin/oak-beta"]):
        assert detect_invoked_cli_command() == "oak-beta"


def test_detect_homebrew_beta_correction() -> None:
    """Homebrew beta: argv[0] is 'oak' but package is beta and oak-beta on PATH."""
    with (
        patch("sys.argv", ["/opt/homebrew/Cellar/oak-ci-beta/1.5.0b3/libexec/bin/oak"]),
        patch("shutil.which", return_value="/opt/homebrew/bin/oak-beta"),
        patch("open_agent_kit._version.__version__", "1.5.0b3"),
    ):
        assert detect_invoked_cli_command() == "oak-beta"


def test_detect_no_beta_correction_without_binary() -> None:
    """Beta package but no oak-beta on PATH: keep 'oak'."""
    with (
        patch("sys.argv", ["/usr/local/bin/oak"]),
        patch("shutil.which", return_value=None),
        patch("open_agent_kit._version.__version__", "1.5.0b1"),
    ):
        assert detect_invoked_cli_command() == "oak"


def test_detect_fallback_on_invalid_chars() -> None:
    """Detector should fall back when argv[0] contains invalid chars."""
    with patch("sys.argv", ["some command with spaces"]):
        assert detect_invoked_cli_command() == CI_CLI_COMMAND_DEFAULT
