"""Tests for constitution CLI commands."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from open_agent_kit.cli import app
from open_agent_kit.config.paths import CONSTITUTION_FILENAME

# Default directory for test fixtures (matching config default)
CONSTITUTION_DIR = "oak"


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


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


def test_constitution_create_file_basic(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test creating constitution file with basic parameters."""
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "create-file",
            "--project-name",
            "Test Project",
            "--author",
            "Test Author",
        ],
    )
    assert result.exit_code == 0
    constitution_path = initialized_project / CONSTITUTION_DIR / CONSTITUTION_FILENAME
    assert constitution_path.exists()
    # Normalize paths for Windows comparison (resolves short paths)
    expected_path = str(constitution_path.resolve())
    assert expected_path in result.stdout or str(constitution_path) in result.stdout


def test_constitution_create_file_with_optional_fields(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test creating constitution with optional fields."""
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "create-file",
            "--project-name",
            "Test Project",
            "--author",
            "Author",
            "--tech-stack",
            "Python, FastAPI",
            "--description",
            "Test description",
        ],
    )
    assert result.exit_code == 0
    constitution_path = initialized_project / CONSTITUTION_DIR / CONSTITUTION_FILENAME
    assert constitution_path.exists()
    content = constitution_path.read_text(encoding="utf-8")
    assert "Python, FastAPI" in content
    assert "Test description" in content


def test_constitution_create_file_already_exists(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test that creating constitution when it exists fails."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test2", "--author", "Author2"]
    )
    assert result.exit_code != 0
    assert "already exists" in result.stdout.lower()


def test_constitution_get_content(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test getting constitution content."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(app, ["constitution", "get-content"])
    assert result.exit_code == 0
    assert "# Test Engineering Constitution" in result.stdout
    assert "## Metadata" in result.stdout
    assert "## Principles" in result.stdout


def test_constitution_get_content_not_exists(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test getting content when constitution doesn't exist."""
    result = cli_runner.invoke(app, ["constitution", "get-content"])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower()


def test_constitution_validate_valid(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test validating constitution command works."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(app, ["constitution", "validate"])
    assert "issues" in result.stdout.lower() or "valid" in result.stdout.lower()


def test_constitution_validate_json_output(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test validation with JSON output."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(app, ["constitution", "validate", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert "is_valid" in output
    assert "issues" in output
    assert isinstance(output["is_valid"], bool)
    assert isinstance(output["issues"], list)


def test_constitution_validate_not_exists(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test validating non-existent constitution."""
    result = cli_runner.invoke(app, ["constitution", "validate"])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower()


def test_constitution_get_version(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test getting constitution version."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(app, ["constitution", "get-version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.stdout


def test_constitution_get_version_not_exists(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test getting version when constitution doesn't exist."""
    result = cli_runner.invoke(app, ["constitution", "get-version"])
    assert result.exit_code != 0


def test_constitution_add_amendment_minor(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test adding a minor amendment."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "add-amendment",
            "--summary",
            "Add security requirements",
            "--rationale",
            "Security audit found gaps",
            "--type",
            "minor",
            "--author",
            "Security Team",
        ],
    )
    assert result.exit_code == 0
    assert "1.1.0" in result.stdout


def test_constitution_add_amendment_with_optional_fields(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test adding amendment with optional fields."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "add-amendment",
            "--summary",
            "Add testing requirements",
            "--rationale",
            "Need better coverage",
            "--type",
            "minor",
            "--author",
            "Tech Lead",
            "--section",
            "Testing",
            "--impact",
            "Teams must write more tests",
        ],
    )
    assert result.exit_code == 0
    constitution_path = initialized_project / CONSTITUTION_DIR / CONSTITUTION_FILENAME
    content = constitution_path.read_text(encoding="utf-8")
    assert "Add testing requirements" in content
    assert "Testing" in content
    assert "Teams must write more tests" in content


def test_constitution_add_amendment_major(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test adding a major amendment."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "add-amendment",
            "--summary",
            "Remove requirement",
            "--rationale",
            "No longer needed",
            "--type",
            "major",
            "--author",
            "Lead",
        ],
    )
    assert result.exit_code == 0
    assert "2.0.0" in result.stdout


def test_constitution_add_amendment_patch(cli_runner: CliRunner, initialized_project: Path) -> None:
    """Test adding a patch amendment."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "add-amendment",
            "--summary",
            "Clarify wording",
            "--rationale",
            "Ambiguous",
            "--type",
            "patch",
            "--author",
            "Editor",
        ],
    )
    assert result.exit_code == 0
    assert "1.0.1" in result.stdout


def test_constitution_add_amendment_invalid_type(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test adding amendment with invalid type fails."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "add-amendment",
            "--summary",
            "Test",
            "--rationale",
            "Test",
            "--type",
            "invalid",
            "--author",
            "Author",
        ],
    )
    assert result.exit_code != 0
    assert "invalid" in result.stdout.lower()


def test_constitution_add_amendment_not_exists(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test adding amendment when constitution doesn't exist."""
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "add-amendment",
            "--summary",
            "Test",
            "--rationale",
            "Test",
            "--type",
            "minor",
            "--author",
            "Author",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower()


def test_constitution_list_agent_files_json(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test listing agent files with JSON output."""
    (initialized_project / ".claude").mkdir()
    (initialized_project / ".github").mkdir()
    result = cli_runner.invoke(app, ["constitution", "list-agent-files", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert isinstance(output, dict)
    assert "claude" in output
    assert "copilot" in output


def test_constitution_list_agent_files_no_agents(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test listing agent files when no agents detected."""
    result = cli_runner.invoke(app, ["constitution", "list-agent-files", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert isinstance(output, dict)
    assert len(output) == 0


def test_constitution_generate_agent_files(
    cli_runner: CliRunner, initialized_project_with_agent: Path
) -> None:
    """Test generating agent instruction files."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(app, ["constitution", "generate-agent-files"])
    assert result.exit_code == 0
    assert "claude" in result.stdout.lower()
    agent_file = initialized_project_with_agent / "CLAUDE.md"
    assert agent_file.exists()


def test_constitution_generate_agent_files_json_output(
    cli_runner: CliRunner, initialized_project_with_agent: Path
) -> None:
    """Test generating agent files with JSON output."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    result = cli_runner.invoke(app, ["constitution", "generate-agent-files", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert isinstance(output, dict)
    assert "claude" in output


def test_constitution_generate_agent_files_not_exists(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test generating agent files when constitution doesn't exist."""
    result = cli_runner.invoke(app, ["constitution", "generate-agent-files"])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower()


def test_constitution_update_agent_files(
    cli_runner: CliRunner, initialized_project_with_agent: Path
) -> None:
    """Test updating agent instruction files."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    cli_runner.invoke(app, ["constitution", "generate-agent-files"])
    cli_runner.invoke(
        app,
        [
            "constitution",
            "add-amendment",
            "--summary",
            "Test",
            "--rationale",
            "Test",
            "--type",
            "minor",
            "--author",
            "Author",
        ],
    )
    result = cli_runner.invoke(app, ["constitution", "update-agent-files"])
    assert result.exit_code == 0
    assert "claude" in result.stdout.lower()
    agent_file = initialized_project_with_agent / "CLAUDE.md"
    assert agent_file.exists()
    content = agent_file.read_text(encoding="utf-8")
    assert "constitution" in content.lower()
    cli_runner.invoke(app, ["constitution", "generate-agent-files"])
    content = agent_file.read_text(encoding="utf-8")
    assert "1.1.0" in content


def test_constitution_update_agent_files_json_output(
    cli_runner: CliRunner, initialized_project_with_agent: Path
) -> None:
    """Test updating agent files with JSON output."""
    cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    cli_runner.invoke(app, ["constitution", "generate-agent-files"])
    result = cli_runner.invoke(app, ["constitution", "update-agent-files", "--json"])
    assert result.exit_code == 0
    output = json.loads(result.stdout)
    assert isinstance(output, dict)
    assert "claude" in output or "skipped" in output


def test_constitution_update_agent_files_not_exists(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test updating agent files when constitution doesn't exist."""
    result = cli_runner.invoke(app, ["constitution", "update-agent-files"])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower()


def test_constitution_commands_work_in_sequence(
    cli_runner: CliRunner, initialized_project: Path
) -> None:
    """Test that constitution commands work correctly in sequence."""
    result = cli_runner.invoke(
        app, ["constitution", "create-file", "--project-name", "Test", "--author", "Author"]
    )
    assert result.exit_code == 0
    result = cli_runner.invoke(app, ["constitution", "get-version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.stdout
    result = cli_runner.invoke(app, ["constitution", "validate"])
    assert "issues" in result.stdout.lower() or "valid" in result.stdout.lower()
    result = cli_runner.invoke(
        app,
        [
            "constitution",
            "add-amendment",
            "--summary",
            "Test",
            "--rationale",
            "Test",
            "--type",
            "minor",
            "--author",
            "Author",
        ],
    )
    assert result.exit_code == 0
    result = cli_runner.invoke(app, ["constitution", "get-version"])
    assert result.exit_code == 0
    assert "1.1.0" in result.stdout
    result = cli_runner.invoke(app, ["constitution", "get-content"])
    assert result.exit_code == 0
    assert "Amendment 1.1.0" in result.stdout
