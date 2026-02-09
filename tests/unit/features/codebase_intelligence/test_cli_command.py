"""Tests for CI CLI command resolution and rewrite helpers."""

from pathlib import Path

import yaml

from open_agent_kit.features.codebase_intelligence.cli_command import (
    resolve_ci_cli_command,
    rewrite_oak_command,
)
from open_agent_kit.features.codebase_intelligence.constants import (
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
            {"codebase_intelligence": {"cli_command": "oak-dev"}},
            sort_keys=False,
        )
    )

    assert resolve_ci_cli_command(tmp_path) == "oak-dev"


def test_rewrite_oak_command_rewrites_root_command() -> None:
    """Rewriter should transform plain ``oak`` command."""
    assert rewrite_oak_command("oak", "oak-dev") == "oak-dev"


def test_rewrite_oak_command_rewrites_prefixed_command() -> None:
    """Rewriter should transform ``oak ...`` command prefix."""
    assert rewrite_oak_command("oak ci mcp", "oak-dev") == "oak-dev ci mcp"


def test_rewrite_oak_command_keeps_non_oak_commands() -> None:
    """Rewriter should preserve non-oak commands."""
    assert rewrite_oak_command("python -m app", "oak-dev") == "python -m app"
