"""CLI-level integration tests for issue/config commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from open_agent_kit.cli import app


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Return a Typer CLI runner."""
    return CliRunner()


def test_config_set_and_show(initialized_project, cli_runner: CliRunner) -> None:
    """Ensure config commands wire up through the CLI."""
    result = cli_runner.invoke(
        app,
        [
            "config",
            "issue-provider",
            "set",
            "--provider",
            "ado",
            "--organization",
            "contoso",
            "--project",
            "web",
            "--pat-env",
            "ADO_PAT",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    result = cli_runner.invoke(app, ["config", "issue-provider", "show"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "Azure DevOps" in result.stdout
    assert "contoso" in result.stdout


def test_config_check_reports_missing_setup(initialized_project, cli_runner: CliRunner) -> None:
    """Check command should fail when provider/env is not set."""
    result = cli_runner.invoke(app, ["config", "issue-provider", "check"])
    assert result.exit_code != 0
    assert "Configure your issue provider" in result.stdout
