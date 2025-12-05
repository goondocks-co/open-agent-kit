"""Tests for plan service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.config.paths import (
    CONSTITUTION_FILENAME,
    PLAN_BRANCH_PREFIX,
    PLAN_FILE_FILENAME,
    PLAN_MANIFEST_FILENAME,
    PLAN_RESEARCH_DIR,
    PLAN_TASKS_FILENAME,
)
from open_agent_kit.models.plan import (
    Plan,
    PlanManifest,
    PlanStatus,
    PlanTask,
    ResearchDepth,
    ResearchFinding,
    ResearchTopic,
    TaskPriority,
    TaskType,
)
from open_agent_kit.services.plan_service import (
    PlanService,
    PlanServiceError,
    _parse_list_items,
    _render_plan_file,
    _render_research_findings,
    _render_tasks,
    _status_emoji,
    get_plan_service,
)

# Default directories for test fixtures (matching config defaults)
CONSTITUTION_DIR = "oak"
PLAN_DIR = "oak/plan"


@pytest.fixture(name="project_root")
def fixture_project_root(tmp_path: Path) -> Path:
    """Create a temporary project root."""
    return tmp_path


@pytest.fixture(name="project_with_constitution")
def fixture_project_with_constitution(project_root: Path) -> Path:
    """Create a project with constitution file at oak/constitution.md."""
    constitution_dir = project_root / CONSTITUTION_DIR
    constitution_dir.mkdir(parents=True, exist_ok=True)
    constitution_path = constitution_dir / CONSTITUTION_FILENAME
    constitution_path.write_text("# Project Constitution\n\nPrinciples here.")
    return project_root


@pytest.fixture(name="plan_service")
def fixture_plan_service(project_with_constitution: Path) -> PlanService:
    """Create PlanService with constitution."""
    return PlanService(project_with_constitution)


class TestPlanServicePrerequisites:
    """Tests for prerequisite validation."""

    def test_check_constitution_exists_false(self, project_root: Path) -> None:
        """Test constitution check when missing."""
        service = PlanService(project_root)
        assert service.check_constitution_exists() is False

    def test_check_constitution_exists_true(self, project_with_constitution: Path) -> None:
        """Test constitution check when present."""
        service = PlanService(project_with_constitution)
        assert service.check_constitution_exists() is True

    def test_validate_prerequisites_no_constitution(self, project_root: Path) -> None:
        """Test validation fails without constitution."""
        service = PlanService(project_root)
        errors = service.validate_prerequisites()
        assert len(errors) == 1
        assert "constitution" in errors[0].lower()

    def test_validate_prerequisites_with_constitution(
        self, project_with_constitution: Path
    ) -> None:
        """Test validation passes with constitution."""
        service = PlanService(project_with_constitution)
        errors = service.validate_prerequisites()
        assert len(errors) == 0


class TestPlanServiceDirectories:
    """Tests for directory and path management."""

    def test_ensure_plan_dir(self, plan_service: PlanService) -> None:
        """Test plan directory creation."""
        plan_dir = plan_service.ensure_plan_dir()
        assert plan_dir.exists()
        assert plan_dir.name == PLAN_DIR.split("/")[-1]

    def test_get_plan_dir(self, plan_service: PlanService) -> None:
        """Test getting plan-specific directory."""
        plan_dir = plan_service.get_plan_dir("my-plan")
        assert plan_dir.name == "my-plan"
        assert PLAN_DIR.split("/")[-1] in str(plan_dir)

    def test_get_plan_file_path(self, plan_service: PlanService) -> None:
        """Test getting plan.md path."""
        path = plan_service.get_plan_file_path("test-plan")
        assert path.name == PLAN_FILE_FILENAME

    def test_get_tasks_file_path(self, plan_service: PlanService) -> None:
        """Test getting tasks.md path."""
        path = plan_service.get_tasks_file_path("test-plan")
        assert path.name == PLAN_TASKS_FILENAME

    def test_get_manifest_path(self, plan_service: PlanService) -> None:
        """Test getting manifest path."""
        path = plan_service.get_manifest_path("test-plan")
        assert path.name == PLAN_MANIFEST_FILENAME

    def test_get_research_dir(self, plan_service: PlanService) -> None:
        """Test getting research directory path."""
        path = plan_service.get_research_dir("test-plan")
        assert path.name == PLAN_RESEARCH_DIR

    def test_get_research_file_path(self, plan_service: PlanService) -> None:
        """Test getting research file path."""
        path = plan_service.get_research_file_path("test-plan", "api-design")
        assert path.name == "api-design.md"
        assert PLAN_RESEARCH_DIR in str(path)


class TestPlanServiceCRUD:
    """Tests for plan CRUD operations."""

    @patch("open_agent_kit.services.plan_service.PlanService.checkout_branch")
    def test_create_plan_basic(self, mock_checkout: MagicMock, plan_service: PlanService) -> None:
        """Test basic plan creation."""
        manifest = plan_service.create_plan(
            plan_name="auth-redesign",
            display_name="Authentication Redesign",
        )

        assert manifest.name == "auth-redesign"
        assert manifest.display_name == "Authentication Redesign"
        assert manifest.status == PlanStatus.DRAFT
        assert manifest.branch_name == f"{PLAN_BRANCH_PREFIX}auth-redesign"

        # Verify files created
        plan_dir = plan_service.get_plan_dir("auth-redesign")
        assert plan_dir.exists()
        assert plan_service.get_manifest_path("auth-redesign").exists()
        assert plan_service.get_plan_file_path("auth-redesign").exists()
        assert plan_service.get_research_dir("auth-redesign").exists()

    @patch("open_agent_kit.services.plan_service.PlanService.checkout_branch")
    def test_create_plan_with_options(
        self, mock_checkout: MagicMock, plan_service: PlanService
    ) -> None:
        """Test plan creation with all options."""
        manifest = plan_service.create_plan(
            plan_name="api-v2",
            display_name="API Version 2",
            overview="Complete API redesign",
            goals=["Improve performance", "Add versioning"],
            research_depth=ResearchDepth.COMPREHENSIVE,
        )

        assert manifest.research_depth == ResearchDepth.COMPREHENSIVE

        # Verify plan content
        plan = plan_service.load_plan("api-v2")
        assert "Complete API redesign" in plan.overview
        assert len(plan.goals) == 2

    def test_create_plan_without_branch(self, plan_service: PlanService) -> None:
        """Test plan creation without git branch."""
        manifest = plan_service.create_plan(
            plan_name="no-branch-plan",
            display_name="No Branch Plan",
            create_branch=False,
        )

        assert manifest.branch_name is None

    def test_create_plan_already_exists(self, plan_service: PlanService) -> None:
        """Test error when plan already exists."""
        plan_service.create_plan(
            plan_name="existing-plan",
            display_name="Existing Plan",
            create_branch=False,
        )

        with pytest.raises(PlanServiceError) as exc_info:
            plan_service.create_plan(
                plan_name="existing-plan",
                display_name="Duplicate Plan",
                create_branch=False,
            )
        assert "already exists" in str(exc_info.value).lower()

    def test_create_plan_no_constitution(self, project_root: Path) -> None:
        """Test error when constitution missing."""
        service = PlanService(project_root)

        with pytest.raises(PlanServiceError) as exc_info:
            service.create_plan(plan_name="test", display_name="Test", create_branch=False)
        assert "constitution" in str(exc_info.value).lower()

    def test_load_plan(self, plan_service: PlanService) -> None:
        """Test loading a plan."""
        plan_service.create_plan(
            plan_name="load-test",
            display_name="Load Test Plan",
            overview="Test overview",
            goals=["Goal 1", "Goal 2"],
            create_branch=False,
        )

        plan = plan_service.load_plan("load-test")
        assert plan.manifest.name == "load-test"
        assert plan.manifest.display_name == "Load Test Plan"
        assert "Test overview" in plan.overview

    def test_load_manifest(self, plan_service: PlanService) -> None:
        """Test loading just the manifest."""
        plan_service.create_plan(
            plan_name="manifest-test",
            display_name="Manifest Test",
            create_branch=False,
        )

        manifest = plan_service.load_manifest("manifest-test")
        assert manifest.name == "manifest-test"
        assert manifest.status == PlanStatus.DRAFT

    def test_load_manifest_not_found(self, plan_service: PlanService) -> None:
        """Test error when plan not found."""
        with pytest.raises(FileNotFoundError):
            plan_service.load_manifest("nonexistent-plan")

    def test_update_plan_status(self, plan_service: PlanService) -> None:
        """Test updating plan status."""
        plan_service.create_plan(
            plan_name="status-test",
            display_name="Status Test",
            create_branch=False,
        )

        updated = plan_service.update_plan_status("status-test", PlanStatus.RESEARCHING)
        assert updated.status == PlanStatus.RESEARCHING

        # Verify persisted
        reloaded = plan_service.load_manifest("status-test")
        assert reloaded.status == PlanStatus.RESEARCHING

    def test_list_plans_empty(self, plan_service: PlanService) -> None:
        """Test listing plans when none exist."""
        plans = plan_service.list_plans()
        assert plans == []

    def test_list_plans(self, plan_service: PlanService) -> None:
        """Test listing multiple plans."""
        plan_service.create_plan("plan-a", "Plan A", create_branch=False)
        plan_service.create_plan("plan-b", "Plan B", create_branch=False)
        plan_service.create_plan("plan-c", "Plan C", create_branch=False)

        plans = plan_service.list_plans()
        assert len(plans) == 3
        # Sorted by updated_at descending, so most recent first
        names = [p.name for p in plans]
        assert "plan-a" in names
        assert "plan-b" in names
        assert "plan-c" in names

    def test_plan_exists(self, plan_service: PlanService) -> None:
        """Test checking if plan exists."""
        assert plan_service.plan_exists("no-such-plan") is False

        plan_service.create_plan("real-plan", "Real Plan", create_branch=False)
        assert plan_service.plan_exists("real-plan") is True


class TestPlanServiceResearch:
    """Tests for research operations."""

    @pytest.fixture(autouse=True)
    def setup_plan(self, plan_service: PlanService) -> None:
        """Create a test plan."""
        plan_service.create_plan(
            plan_name="research-test",
            display_name="Research Test",
            create_branch=False,
        )

    def test_get_research_topics_empty(self, plan_service: PlanService) -> None:
        """Test getting research topics when none exist."""
        topics = plan_service.get_research_topics("research-test")
        assert topics == []

    def test_add_research_topic(self, plan_service: PlanService) -> None:
        """Test adding a research topic."""
        topic = ResearchTopic(
            slug="auth-patterns",
            title="Authentication Patterns",
            description="Research modern auth approaches",
            research_questions=["OAuth2 vs JWT?"],
        )
        plan_service.add_research_topic("research-test", topic)

        topics = plan_service.get_research_topics("research-test")
        assert len(topics) == 1
        assert topics[0].slug == "auth-patterns"
        assert len(topics[0].research_questions) == 1

    def test_add_duplicate_research_topic(self, plan_service: PlanService) -> None:
        """Test error when adding duplicate topic."""
        topic = ResearchTopic(
            slug="duplicate",
            title="Duplicate Topic",
            description="First one",
        )
        plan_service.add_research_topic("research-test", topic)

        with pytest.raises(PlanServiceError) as exc_info:
            plan_service.add_research_topic("research-test", topic)
        assert "already exists" in str(exc_info.value).lower()

    def test_update_research_topic_status(self, plan_service: PlanService) -> None:
        """Test updating research topic status."""
        topic = ResearchTopic(
            slug="status-topic",
            title="Status Topic",
            description="Test status updates",
        )
        plan_service.add_research_topic("research-test", topic)

        plan_service.update_research_topic_status("research-test", "status-topic", "in_progress")

        topics = plan_service.get_research_topics("research-test")
        assert topics[0].status == "in_progress"

    def test_update_research_topic_status_not_found(self, plan_service: PlanService) -> None:
        """Test error when topic not found."""
        with pytest.raises(PlanServiceError) as exc_info:
            plan_service.update_research_topic_status("research-test", "nonexistent", "completed")
        assert "not found" in str(exc_info.value).lower()

    def test_write_research_findings(self, plan_service: PlanService) -> None:
        """Test writing research findings."""
        topic = ResearchTopic(
            slug="findings-topic",
            title="Findings Topic",
            description="Topic for findings test",
        )
        plan_service.add_research_topic("research-test", topic)

        findings = ResearchFinding(
            topic_slug="findings-topic",
            summary="OAuth2 is recommended for third-party auth",
            key_insights=["Easy integration", "Widely supported"],
            recommendations=["Use PKCE flow"],
            sources=["https://oauth.net"],
        )
        path = plan_service.write_research_findings("research-test", "findings-topic", findings)

        assert path.exists()
        content = path.read_text()
        assert "OAuth2 is recommended" in content
        assert "Easy integration" in content

        # Verify topic status updated
        topics = plan_service.get_research_topics("research-test")
        findings_topic = [t for t in topics if t.slug == "findings-topic"][0]
        assert findings_topic.status == "completed"
        assert findings_topic.findings_path is not None

    def test_load_research_findings(self, plan_service: PlanService) -> None:
        """Test loading research findings content."""
        topic = ResearchTopic(
            slug="load-findings",
            title="Load Findings Test",
            description="Test loading findings",
        )
        plan_service.add_research_topic("research-test", topic)

        findings = ResearchFinding(
            topic_slug="load-findings",
            summary="Test summary",
        )
        plan_service.write_research_findings("research-test", "load-findings", findings)

        content = plan_service.load_research_findings("research-test", "load-findings")
        assert "Test summary" in content

    def test_load_research_findings_not_found(self, plan_service: PlanService) -> None:
        """Test error when findings not found."""
        with pytest.raises(FileNotFoundError):
            plan_service.load_research_findings("research-test", "nonexistent")

    def test_get_research_status(self, plan_service: PlanService) -> None:
        """Test getting research status summary."""
        # Add topics with different statuses
        topics = [
            ResearchTopic(slug="topic-1", title="Topic 1", description="D1", status="completed"),
            ResearchTopic(slug="topic-2", title="Topic 2", description="D2", status="in_progress"),
            ResearchTopic(slug="topic-3", title="Topic 3", description="D3", status="pending"),
            ResearchTopic(slug="topic-4", title="Topic 4", description="D4", status="skipped"),
        ]
        for topic in topics:
            plan_service.add_research_topic("research-test", topic)

        status = plan_service.get_research_status("research-test")

        assert status["total"] == 4
        assert status["completed"] == 1
        assert status["in_progress"] == 1
        assert status["pending"] == 1
        assert status["skipped"] == 1
        assert len(status["topics"]) == 4


class TestPlanServiceTasks:
    """Tests for task operations."""

    @pytest.fixture(autouse=True)
    def setup_plan(self, plan_service: PlanService) -> None:
        """Create a test plan."""
        plan_service.create_plan(
            plan_name="tasks-test",
            display_name="Tasks Test",
            create_branch=False,
        )

    def test_write_tasks(self, plan_service: PlanService) -> None:
        """Test writing tasks to plan."""
        tasks = [
            PlanTask(
                id="T1",
                title="Implement auth",
                description="Add authentication",
                task_type=TaskType.EPIC,
                priority=TaskPriority.HIGH,
            ),
            PlanTask(
                id="T1.1",
                title="Add login form",
                description="Create login UI",
                task_type=TaskType.TASK,
                parent_id="T1",
                acceptance_criteria=["Form has email field", "Form has password field"],
            ),
        ]

        path = plan_service.write_tasks("tasks-test", tasks)

        assert path.exists()
        content = path.read_text()
        assert "Implement auth" in content
        assert "Add login form" in content
        assert "Form has email field" in content

        # Verify status updated
        manifest = plan_service.load_manifest("tasks-test")
        assert manifest.status == PlanStatus.READY

    def test_load_tasks(self, plan_service: PlanService) -> None:
        """Test loading tasks from plan."""
        tasks = [
            PlanTask(
                id="T1",
                title="Test Task",
                description="A test task",
            ),
        ]
        plan_service.write_tasks("tasks-test", tasks)

        loaded_tasks = plan_service.load_tasks("tasks-test")
        assert len(loaded_tasks) == 1
        assert loaded_tasks[0].id == "T1"

    def test_update_task_issue_link(self, plan_service: PlanService) -> None:
        """Test updating task with issue link."""
        tasks = [
            PlanTask(id="T1", title="Task", description="Desc"),
        ]
        plan_service.write_tasks("tasks-test", tasks)

        plan_service.update_task_issue_link(
            "tasks-test",
            "T1",
            issue_id="123",
            issue_link="https://github.com/org/repo/issues/123",
        )

        loaded = plan_service.load_tasks("tasks-test")
        assert loaded[0].issue_id == "123"
        assert "github.com" in loaded[0].issue_link

    def test_update_task_issue_link_not_found(self, plan_service: PlanService) -> None:
        """Test error when task not found."""
        tasks = [
            PlanTask(id="T1", title="Task", description="Desc"),
        ]
        plan_service.write_tasks("tasks-test", tasks)

        with pytest.raises(PlanServiceError) as exc_info:
            plan_service.update_task_issue_link("tasks-test", "T999", "123", "http://link")
        assert "not found" in str(exc_info.value).lower()


class TestPlanServiceExport:
    """Tests for export operations."""

    @pytest.fixture(autouse=True)
    def setup_plan(self, plan_service: PlanService) -> None:
        """Create a test plan."""
        plan_service.create_plan(
            plan_name="export-test",
            display_name="Export Test",
            create_branch=False,
        )

    def test_set_export_mode(self, plan_service: PlanService) -> None:
        """Test setting export mode."""
        plan_service.set_export_mode("export-test", "hierarchical", "github")

        manifest = plan_service.load_manifest("export-test")
        assert manifest.export_mode == "hierarchical"
        assert manifest.export_provider == "github"

    def test_mark_exported(self, plan_service: PlanService) -> None:
        """Test marking plan as exported."""
        plan_service.mark_exported("export-test")

        manifest = plan_service.load_manifest("export-test")
        assert manifest.status == PlanStatus.EXPORTED


class TestPlanServiceGit:
    """Tests for git operations."""

    def test_build_branch_name(self, plan_service: PlanService) -> None:
        """Test branch name generation."""
        branch = plan_service.build_branch_name("my-plan")
        assert branch == f"{PLAN_BRANCH_PREFIX}my-plan"

    def test_build_branch_name_sanitizes(self, plan_service: PlanService) -> None:
        """Test branch name sanitization."""
        branch = plan_service.build_branch_name("My Plan With Spaces")
        assert " " not in branch
        assert branch == f"{PLAN_BRANCH_PREFIX}My-Plan-With-Spaces"

    @patch("subprocess.run")
    def test_get_current_branch(self, mock_run: MagicMock, plan_service: PlanService) -> None:
        """Test getting current branch."""
        mock_run.return_value = MagicMock(stdout="main\n", returncode=0)

        branch = plan_service.get_current_branch()
        assert branch == "main"

    @patch("subprocess.run")
    def test_get_current_branch_not_git_repo(
        self, mock_run: MagicMock, plan_service: PlanService
    ) -> None:
        """Test getting current branch when not in git repo."""
        mock_run.side_effect = FileNotFoundError()

        branch = plan_service.get_current_branch()
        assert branch is None

    @patch("subprocess.run")
    def test_branch_exists(self, mock_run: MagicMock, plan_service: PlanService) -> None:
        """Test checking if branch exists."""
        mock_run.return_value = MagicMock(returncode=0)

        assert plan_service.branch_exists("main") is True

        mock_run.return_value = MagicMock(returncode=1)
        assert plan_service.branch_exists("nonexistent") is False

    @patch("subprocess.run")
    def test_checkout_branch_existing(self, mock_run: MagicMock, plan_service: PlanService) -> None:
        """Test checking out existing branch."""
        mock_run.return_value = MagicMock(returncode=0)

        plan_service.checkout_branch("existing-branch", create=False)

        mock_run.assert_called()
        call_args = mock_run.call_args
        assert "checkout" in call_args[0][0]
        assert "-b" not in call_args[0][0]

    @patch("open_agent_kit.services.plan_service.PlanService.branch_exists")
    @patch("subprocess.run")
    def test_checkout_branch_create(
        self, mock_run: MagicMock, mock_exists: MagicMock, plan_service: PlanService
    ) -> None:
        """Test creating and checking out new branch."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(returncode=0)

        plan_service.checkout_branch("new-branch", create=True)

        mock_run.assert_called()
        call_args = mock_run.call_args
        assert "-b" in call_args[0][0]

    @patch("subprocess.run")
    def test_infer_plan_from_branch(self, mock_run: MagicMock, plan_service: PlanService) -> None:
        """Test inferring plan name from branch."""
        # Create a plan first
        plan_service.create_plan("inferred-plan", "Inferred", create_branch=False)

        # Mock current branch as plan branch
        mock_run.return_value = MagicMock(
            stdout=f"{PLAN_BRANCH_PREFIX}inferred-plan\n", returncode=0
        )

        plan_name = plan_service.infer_plan_from_branch()
        assert plan_name == "inferred-plan"

    @patch("subprocess.run")
    def test_infer_plan_from_branch_not_plan_branch(
        self, mock_run: MagicMock, plan_service: PlanService
    ) -> None:
        """Test inferring plan when not on plan branch."""
        mock_run.return_value = MagicMock(stdout="main\n", returncode=0)

        plan_name = plan_service.infer_plan_from_branch()
        assert plan_name is None


class TestRenderingHelpers:
    """Tests for rendering helper functions."""

    def test_status_emoji(self) -> None:
        """Test status emoji mapping."""
        assert _status_emoji("pending") == "⏳"
        assert _status_emoji("in_progress") == "🔄"
        assert _status_emoji("completed") == "✅"
        assert _status_emoji("skipped") == "⏭️"
        assert _status_emoji("unknown") == "❓"

    def test_parse_list_items(self) -> None:
        """Test parsing markdown list items."""
        lines = [
            "- Item 1",
            "- Item 2",
            "Some text",
            "* Item 3",
            "",
        ]
        items = _parse_list_items(lines)
        assert items == ["Item 1", "Item 2", "Item 3"]

    def test_render_plan_file(self) -> None:
        """Test plan file rendering."""
        manifest = PlanManifest(
            name="render-test",
            display_name="Render Test Plan",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
            branch_name="plan/render-test",
        )
        plan = Plan(
            manifest=manifest,
            overview="Test overview content",
            goals=["Goal 1", "Goal 2"],
            success_criteria=["Criterion 1"],
        )

        content = _render_plan_file(plan)

        assert "# Render Test Plan" in content
        assert "Test overview content" in content
        assert "Goal 1" in content
        assert "Goal 2" in content
        assert "Criterion 1" in content
        assert "plan/render-test" in content

    def test_render_research_findings(self) -> None:
        """Test research findings rendering."""
        findings = ResearchFinding(
            topic_slug="api-design",
            summary="REST is recommended",
            key_insights=["Insight 1", "Insight 2"],
            recommendations=["Use OpenAPI"],
            trade_offs=["More complex"],
            sources=["https://example.com"],
            research_date="2025-01-15",
            researcher_notes="Additional notes here",
        )

        content = _render_research_findings(findings)

        assert "# Research: api-design" in content
        assert "REST is recommended" in content
        assert "Insight 1" in content
        assert "Use OpenAPI" in content
        assert "More complex" in content
        assert "https://example.com" in content
        assert "Additional notes here" in content

    def test_render_tasks(self) -> None:
        """Test tasks rendering."""
        tasks = [
            PlanTask(
                id="T1",
                title="Epic Task",
                description="An epic",
                task_type=TaskType.EPIC,
                priority=TaskPriority.HIGH,
            ),
            PlanTask(
                id="T2",
                title="Regular Task",
                description="A task",
                task_type=TaskType.TASK,
                acceptance_criteria=["AC1", "AC2"],
                tags=["backend", "api"],
            ),
        ]

        content = _render_tasks("Test Plan", tasks)

        assert "# Tasks: Test Plan" in content
        assert "## Epics" in content
        assert "T1: Epic Task" in content
        assert "[HIGH]" in content
        assert "## Tasks" in content
        assert "T2: Regular Task" in content
        assert "AC1" in content
        assert "`backend`" in content

    def test_render_tasks_empty(self) -> None:
        """Test rendering empty task list."""
        content = _render_tasks("Empty Plan", [])
        assert "No tasks generated yet" in content


class TestPlanServiceFactory:
    """Tests for factory function."""

    def test_get_plan_service(self, project_with_constitution: Path) -> None:
        """Test factory function."""
        service = get_plan_service(project_with_constitution)
        assert isinstance(service, PlanService)
        assert service.project_root == project_with_constitution

    def test_get_plan_service_default_cwd(self) -> None:
        """Test factory function with default cwd."""
        service = get_plan_service()
        assert isinstance(service, PlanService)
