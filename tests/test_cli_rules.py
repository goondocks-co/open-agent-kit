"""Tests for rules CLI commands.

Tests for the utility commands: analyze, sync-agents, detect-existing.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from open_agent_kit.cli import app
from open_agent_kit.config.paths import CONSTITUTION_FILENAME

# Default directory for test fixtures (matching config default)
CONSTITUTION_DIR = "oak"

# Sample constitution content for testing
SAMPLE_CONSTITUTION = """# Test Project Engineering Constitution

## Metadata

- **Project:** Test Project
- **Version:** 1.0.0
- **Status:** Ratified
- **Ratification Date:** 2025-01-01
- **Last Amendment:** N/A
- **Author:** Test Author

---

## Principles

All code MUST pass automated checks.

## Architecture

Components MUST be loosely coupled.

## Code Standards

Follow PEP 8 guidelines.

## Testing

All new code MUST have tests.

## Documentation

Code SHOULD be self-documenting.

## Governance

All changes MUST be reviewed.
"""


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def constitution_file(initialized_project: Path) -> Path:
    """Create a sample constitution file.

    Args:
        initialized_project: Initialized project directory

    Returns:
        Path to created constitution file
    """
    constitution_dir = initialized_project / CONSTITUTION_DIR
    constitution_dir.mkdir(parents=True, exist_ok=True)
    constitution_path = constitution_dir / CONSTITUTION_FILENAME
    constitution_path.write_text(SAMPLE_CONSTITUTION, encoding="utf-8")
    return constitution_path


@pytest.fixture
def initialized_project_with_agent(temp_project_dir: Path) -> Path:
    """Create a temporary project with .oak initialized and claude agent.

    Args:
        temp_project_dir: Temporary project directory

    Returns:
        Path to initialized project with agent
    """
    from open_agent_kit.commands.init_cmd import init_command

    init_command(force=False, agent=["claude"], no_interactive=True)
    return temp_project_dir


@pytest.fixture
def constitution_file_with_agent(initialized_project_with_agent: Path) -> Path:
    """Create a sample constitution file in an agent-initialized project.

    Args:
        initialized_project_with_agent: Initialized project directory with agent

    Returns:
        Path to created constitution file
    """
    constitution_dir = initialized_project_with_agent / CONSTITUTION_DIR
    constitution_dir.mkdir(parents=True, exist_ok=True)
    constitution_path = constitution_dir / CONSTITUTION_FILENAME
    constitution_path.write_text(SAMPLE_CONSTITUTION, encoding="utf-8")
    return constitution_path


# =============================================================================
# analyze command tests
# =============================================================================


def test_rules_analyze_greenfield(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test analyze command for greenfield project."""
    result = cli_runner.invoke(app, ["rules", "analyze"])
    assert result.exit_code == 0
    assert "greenfield" in result.stdout.lower()


def test_rules_analyze_json_output(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test analyze command with JSON output."""
    result = cli_runner.invoke(app, ["rules", "analyze", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert "classification" in output
    assert "oak_installed" in output
    assert "test_infrastructure" in output
    assert "ci_cd" in output


def test_rules_analyze_with_tests(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test analyze command detects test infrastructure."""
    # Add tests directory
    (initialized_project / "tests").mkdir()
    (initialized_project / "tests" / "test_example.py").write_text("# test file")

    result = cli_runner.invoke(app, ["rules", "analyze", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["test_infrastructure"]["found"] is True


def test_rules_analyze_with_ci(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test analyze command detects CI/CD workflows."""
    # Add GitHub Actions workflow
    (initialized_project / ".github" / "workflows").mkdir(parents=True)
    (initialized_project / ".github" / "workflows" / "ci.yml").write_text("name: CI")

    result = cli_runner.invoke(app, ["rules", "analyze", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["ci_cd"]["found"] is True


def test_rules_analyze_with_constitution(
    cli_runner: CliRunner, initialized_project: Path, constitution_file: Path
) -> None:
    """Test analyze command reports constitution status."""
    result = cli_runner.invoke(app, ["rules", "analyze", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert output["has_constitution"] is True


# =============================================================================
# detect-existing command tests
# =============================================================================


def test_rules_detect_existing_no_agents(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test detect-existing when no agents are detected."""
    result = cli_runner.invoke(app, ["rules", "detect-existing"])
    assert result.exit_code == 0


def test_rules_detect_existing_json_output(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test detect-existing with JSON output."""
    result = cli_runner.invoke(app, ["rules", "detect-existing", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert isinstance(output, dict)


def test_rules_detect_existing_with_claude(
    cli_runner: CliRunner, initialized_project_with_agent: Path
) -> None:
    """Test detect-existing detects claude agent files."""
    result = cli_runner.invoke(app, ["rules", "detect-existing", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert "claude" in output


def test_rules_detect_existing_human_readable(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test detect-existing human-readable output."""
    # Create .claude directory
    (initialized_project / ".claude").mkdir()

    result = cli_runner.invoke(app, ["rules", "detect-existing"])
    assert result.exit_code == 0
    assert "claude" in result.stdout.lower() or "checking" in result.stdout.lower()


# =============================================================================
# sync-agents command tests
# =============================================================================


def test_rules_sync_agents_no_constitution(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test sync-agents fails when no constitution exists."""
    result = cli_runner.invoke(app, ["rules", "sync-agents"])
    assert result.exit_code != 0
    assert "no constitution" in result.stdout.lower()


def test_rules_sync_agents_dry_run(
    cli_runner: CliRunner, constitution_file_with_agent: Path
) -> None:
    """Test sync-agents dry run mode."""
    result = cli_runner.invoke(app, ["rules", "sync-agents", "--dry-run"])
    assert result.exit_code == 0
    assert "dry run" in result.stdout.lower()


def test_rules_sync_agents_dry_run_json(
    cli_runner: CliRunner, constitution_file_with_agent: Path
) -> None:
    """Test sync-agents dry run with JSON output."""
    result = cli_runner.invoke(app, ["rules", "sync-agents", "--dry-run", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert isinstance(output, dict)


def test_rules_sync_agents_execution(
    cli_runner: CliRunner, constitution_file_with_agent: Path
) -> None:
    """Test sync-agents actually syncs agent files."""
    result = cli_runner.invoke(app, ["rules", "sync-agents"])
    assert result.exit_code == 0


def test_rules_sync_agents_json_output(
    cli_runner: CliRunner, constitution_file_with_agent: Path
) -> None:
    """Test sync-agents with JSON output."""
    result = cli_runner.invoke(app, ["rules", "sync-agents", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert isinstance(output, dict)
    # Should have at least one of: created, updated, skipped
    assert any(key in output for key in ["created", "updated", "skipped", "errors"])
