"""Integration tests for plan CLI commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from open_agent_kit.cli import app
from open_agent_kit.config.paths import CONSTITUTION_FILENAME

# Default directories for test fixtures (matching config defaults)
CONSTITUTION_DIR = "oak"
PLAN_DIR = "oak/plan"


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def project_with_constitution(initialized_project: Path) -> Path:
    """Create a project with constitution file (required for plan).

    Args:
        initialized_project: Initialized oak project

    Returns:
        Path to project with constitution
    """
    # Constitution is at oak/constitution.md
    constitution_dir = initialized_project / CONSTITUTION_DIR
    constitution_dir.mkdir(parents=True, exist_ok=True)
    constitution_path = constitution_dir / CONSTITUTION_FILENAME
    constitution_path.write_text("# Project Constitution\n\n## Principles\n\n- Quality first\n")
    return initialized_project


class TestPlanCreate:
    """Tests for oak plan create command."""

    def test_plan_create_basic(
        self, cli_runner: CliRunner, project_with_constitution: Path
    ) -> None:
        """Test creating a basic plan."""
        result = cli_runner.invoke(
            app,
            [
                "plan",
                "create",
                "auth-redesign",
                "--display-name",
                "Authentication Redesign",
                "--no-branch",
            ],
        )
        assert result.exit_code == 0
        assert "auth-redesign" in result.stdout.lower() or "created" in result.stdout.lower()

        # Verify plan directory exists
        plan_dir = project_with_constitution / PLAN_DIR / "auth-redesign"
        assert plan_dir.exists()

    def test_plan_create_with_overview(
        self, cli_runner: CliRunner, project_with_constitution: Path
    ) -> None:
        """Test creating a plan with overview."""
        result = cli_runner.invoke(
            app,
            [
                "plan",
                "create",
                "api-v2",
                "--display-name",
                "API Version 2",
                "--overview",
                "Complete API redesign for v2",
                "--no-branch",
            ],
        )
        assert result.exit_code == 0

        # Verify plan.md contains overview
        plan_file = project_with_constitution / PLAN_DIR / "api-v2" / "plan.md"
        assert plan_file.exists()
        content = plan_file.read_text()
        assert "Complete API redesign" in content

    def test_plan_create_duplicate_fails(
        self, cli_runner: CliRunner, project_with_constitution: Path
    ) -> None:
        """Test that creating duplicate plan fails."""
        cli_runner.invoke(
            app,
            ["plan", "create", "existing-plan", "--display-name", "Existing", "--no-branch"],
        )
        result = cli_runner.invoke(
            app,
            ["plan", "create", "existing-plan", "--display-name", "Duplicate", "--no-branch"],
        )
        assert result.exit_code != 0
        assert "already exists" in result.stdout.lower()

    def test_plan_create_no_constitution_fails(
        self, cli_runner: CliRunner, initialized_project: Path
    ) -> None:
        """Test that creating plan without constitution fails."""
        result = cli_runner.invoke(
            app,
            ["plan", "create", "test-plan", "--display-name", "Test", "--no-branch"],
        )
        assert result.exit_code != 0
        assert "constitution" in result.stdout.lower()


class TestPlanShow:
    """Tests for oak plan show command."""

    def test_plan_show(self, cli_runner: CliRunner, project_with_constitution: Path) -> None:
        """Test showing plan details."""
        # Create a plan first
        cli_runner.invoke(
            app,
            ["plan", "create", "show-test", "--display-name", "Show Test Plan", "--no-branch"],
        )

        result = cli_runner.invoke(app, ["plan", "show", "show-test"])
        assert result.exit_code == 0
        assert "show test plan" in result.stdout.lower()
        assert "draft" in result.stdout.lower()

    def test_plan_show_not_found(
        self, cli_runner: CliRunner, project_with_constitution: Path
    ) -> None:
        """Test showing nonexistent plan."""
        result = cli_runner.invoke(app, ["plan", "show", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()


class TestPlanList:
    """Tests for oak plan list command."""

    def test_plan_list_empty(self, cli_runner: CliRunner, project_with_constitution: Path) -> None:
        """Test listing plans when none exist."""
        result = cli_runner.invoke(app, ["plan", "list"])
        assert result.exit_code == 0
        assert "no plans" in result.stdout.lower()

    def test_plan_list_multiple(
        self, cli_runner: CliRunner, project_with_constitution: Path
    ) -> None:
        """Test listing multiple plans."""
        cli_runner.invoke(
            app, ["plan", "create", "plan-a", "--display-name", "Plan A", "--no-branch"]
        )
        cli_runner.invoke(
            app, ["plan", "create", "plan-b", "--display-name", "Plan B", "--no-branch"]
        )

        result = cli_runner.invoke(app, ["plan", "list"])
        assert result.exit_code == 0
        assert "plan-a" in result.stdout.lower()
        assert "plan-b" in result.stdout.lower()


class TestPlanStatus:
    """Tests for oak plan status command."""

    def test_plan_status_update(
        self, cli_runner: CliRunner, project_with_constitution: Path
    ) -> None:
        """Test updating plan status."""
        cli_runner.invoke(
            app, ["plan", "create", "status-test", "--display-name", "Status Test", "--no-branch"]
        )

        result = cli_runner.invoke(app, ["plan", "status", "status-test", "researching"])
        assert result.exit_code == 0

        # Verify status changed
        show_result = cli_runner.invoke(app, ["plan", "show", "status-test"])
        assert "researching" in show_result.stdout.lower()

    def test_plan_status_invalid(
        self, cli_runner: CliRunner, project_with_constitution: Path
    ) -> None:
        """Test setting invalid status."""
        cli_runner.invoke(
            app, ["plan", "create", "invalid-status", "--display-name", "Test", "--no-branch"]
        )

        result = cli_runner.invoke(app, ["plan", "status", "invalid-status", "invalid-status"])
        assert result.exit_code != 0


class TestPlanResearch:
    """Tests for oak plan research command."""

    def test_plan_research_status(
        self, cli_runner: CliRunner, project_with_constitution: Path
    ) -> None:
        """Test viewing research status."""
        cli_runner.invoke(
            app,
            ["plan", "create", "research-test", "--display-name", "Research Test", "--no-branch"],
        )

        result = cli_runner.invoke(app, ["plan", "research", "research-test"])
        assert result.exit_code == 0
        # Should show no topics or empty status
        assert "research" in result.stdout.lower()


class TestPlanTasks:
    """Tests for oak plan tasks command."""

    def test_plan_tasks_empty(self, cli_runner: CliRunner, project_with_constitution: Path) -> None:
        """Test viewing tasks when none exist."""
        cli_runner.invoke(
            app,
            ["plan", "create", "tasks-test", "--display-name", "Tasks Test", "--no-branch"],
        )

        result = cli_runner.invoke(app, ["plan", "tasks", "tasks-test"])
        assert result.exit_code == 0
        assert "no tasks" in result.stdout.lower()


class TestPlanWorkflow:
    """Integration tests for complete plan workflow."""

    def test_full_workflow(self, cli_runner: CliRunner, project_with_constitution: Path) -> None:
        """Test complete plan creation workflow."""
        # 1. Create plan
        result = cli_runner.invoke(
            app,
            [
                "plan",
                "create",
                "full-workflow",
                "--display-name",
                "Full Workflow Test",
                "--overview",
                "Testing the complete workflow",
                "--no-branch",
            ],
        )
        assert result.exit_code == 0

        # 2. Show plan
        result = cli_runner.invoke(app, ["plan", "show", "full-workflow"])
        assert result.exit_code == 0
        assert "full workflow test" in result.stdout.lower()

        # 3. Update status
        result = cli_runner.invoke(app, ["plan", "status", "full-workflow", "researching"])
        assert result.exit_code == 0

        # 4. List plans
        result = cli_runner.invoke(app, ["plan", "list"])
        assert result.exit_code == 0
        assert "full-workflow" in result.stdout.lower()

        # 5. Check research status
        result = cli_runner.invoke(app, ["plan", "research", "full-workflow"])
        assert result.exit_code == 0

        # 6. Check tasks
        result = cli_runner.invoke(app, ["plan", "tasks", "full-workflow"])
        assert result.exit_code == 0
