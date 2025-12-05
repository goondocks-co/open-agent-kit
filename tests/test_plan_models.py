"""Tests for plan data models."""

import pytest

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


class TestPlanStatusEnum:
    """Tests for PlanStatus enumeration."""

    def test_plan_status_values(self) -> None:
        """Test plan status enumeration values."""
        assert PlanStatus.DRAFT.value == "draft"
        assert PlanStatus.RESEARCHING.value == "researching"
        assert PlanStatus.PLANNING.value == "planning"
        assert PlanStatus.READY.value == "ready"
        assert PlanStatus.EXPORTED.value == "exported"

    def test_plan_status_is_string_enum(self) -> None:
        """Test that PlanStatus is a string enum for serialization compatibility."""
        assert isinstance(PlanStatus.DRAFT.value, str)
        # String enums allow direct comparison with string values
        assert PlanStatus.DRAFT == "draft"
        assert PlanStatus("draft") == PlanStatus.DRAFT


class TestResearchDepthEnum:
    """Tests for ResearchDepth enumeration."""

    def test_research_depth_values(self) -> None:
        """Test research depth enumeration values."""
        assert ResearchDepth.MINIMAL.value == "minimal"
        assert ResearchDepth.STANDARD.value == "standard"
        assert ResearchDepth.COMPREHENSIVE.value == "comprehensive"


class TestTaskPriorityEnum:
    """Tests for TaskPriority enumeration."""

    def test_task_priority_values(self) -> None:
        """Test task priority enumeration values."""
        assert TaskPriority.CRITICAL.value == "critical"
        assert TaskPriority.HIGH.value == "high"
        assert TaskPriority.MEDIUM.value == "medium"
        assert TaskPriority.LOW.value == "low"


class TestTaskTypeEnum:
    """Tests for TaskType enumeration."""

    def test_task_type_values(self) -> None:
        """Test task type enumeration values."""
        assert TaskType.EPIC.value == "epic"
        assert TaskType.STORY.value == "story"
        assert TaskType.TASK.value == "task"
        assert TaskType.SUBTASK.value == "subtask"


class TestResearchTopic:
    """Tests for ResearchTopic model."""

    def test_research_topic_creation(self) -> None:
        """Test creating a research topic with required fields."""
        topic = ResearchTopic(
            slug="api-design",
            title="API Design Patterns",
            description="Research modern API design patterns",
        )
        assert topic.slug == "api-design"
        assert topic.title == "API Design Patterns"
        assert topic.description == "Research modern API design patterns"

    def test_research_topic_defaults(self) -> None:
        """Test research topic default values."""
        topic = ResearchTopic(
            slug="testing",
            title="Testing Strategy",
            description="Research testing approaches",
        )
        assert topic.priority == 1
        assert topic.status == "pending"
        assert topic.research_questions == []
        assert topic.sources_to_check == []
        assert topic.findings_path is None

    def test_research_topic_with_optional_fields(self) -> None:
        """Test research topic with all optional fields populated."""
        topic = ResearchTopic(
            slug="security",
            title="Security Patterns",
            description="Research security best practices",
            priority=2,
            status="in_progress",
            research_questions=["What auth pattern?", "How to handle secrets?"],
            sources_to_check=["https://owasp.org", "https://docs.example.com"],
            findings_path="research/security.md",
        )
        assert topic.priority == 2
        assert topic.status == "in_progress"
        assert len(topic.research_questions) == 2
        assert len(topic.sources_to_check) == 2
        assert topic.findings_path == "research/security.md"

    def test_research_topic_priority_bounds(self) -> None:
        """Test research topic priority validation."""
        # Valid priority
        topic = ResearchTopic(slug="t", title="T", description="D", priority=5)
        assert topic.priority == 5

        # Invalid priority (too low)
        with pytest.raises(ValueError):
            ResearchTopic(slug="t", title="T", description="D", priority=0)

        # Invalid priority (too high)
        with pytest.raises(ValueError):
            ResearchTopic(slug="t", title="T", description="D", priority=6)


class TestResearchFinding:
    """Tests for ResearchFinding model."""

    def test_research_finding_creation(self) -> None:
        """Test creating a research finding with required fields."""
        finding = ResearchFinding(
            topic_slug="api-design",
            summary="REST APIs are well-suited for this use case",
        )
        assert finding.topic_slug == "api-design"
        assert finding.summary == "REST APIs are well-suited for this use case"

    def test_research_finding_defaults(self) -> None:
        """Test research finding default values."""
        finding = ResearchFinding(
            topic_slug="testing",
            summary="Unit tests should cover 80% of code",
        )
        assert finding.key_insights == []
        assert finding.recommendations == []
        assert finding.sources == []
        assert finding.trade_offs == []
        assert finding.research_date is None
        assert finding.researcher_notes is None

    def test_research_finding_with_all_fields(self) -> None:
        """Test research finding with all fields populated."""
        finding = ResearchFinding(
            topic_slug="caching",
            summary="Redis is recommended for caching",
            key_insights=["Reduces DB load", "Improves response time"],
            recommendations=["Use Redis Cluster for HA"],
            sources=["https://redis.io/docs"],
            trade_offs=["Added infrastructure complexity"],
            research_date="2025-01-15",
            researcher_notes="Consider Memcached as alternative",
        )
        assert len(finding.key_insights) == 2
        assert len(finding.recommendations) == 1
        assert len(finding.sources) == 1
        assert len(finding.trade_offs) == 1
        assert finding.research_date == "2025-01-15"
        assert "Memcached" in finding.researcher_notes


class TestPlanTask:
    """Tests for PlanTask model."""

    def test_plan_task_creation(self) -> None:
        """Test creating a plan task with required fields."""
        task = PlanTask(
            id="T1",
            title="Implement authentication",
            description="Add JWT-based authentication to the API",
        )
        assert task.id == "T1"
        assert task.title == "Implement authentication"
        assert task.description == "Add JWT-based authentication to the API"

    def test_plan_task_defaults(self) -> None:
        """Test plan task default values."""
        task = PlanTask(
            id="T1",
            title="Test task",
            description="A test task",
        )
        assert task.acceptance_criteria == []
        assert task.priority == TaskPriority.MEDIUM
        assert task.task_type == TaskType.TASK
        assert task.estimated_effort is None
        assert task.dependencies == []
        assert task.parent_id is None
        assert task.research_references == []
        assert task.tags == []
        assert task.issue_link is None
        assert task.issue_id is None

    def test_plan_task_with_all_fields(self) -> None:
        """Test plan task with all fields populated."""
        task = PlanTask(
            id="T2.1",
            title="Add OAuth2 support",
            description="Implement OAuth2 flow for third-party login",
            acceptance_criteria=[
                "Users can login with Google",
                "Users can login with GitHub",
            ],
            priority=TaskPriority.HIGH,
            task_type=TaskType.STORY,
            estimated_effort="3 story points",
            dependencies=["T1", "T2"],
            parent_id="T2",
            research_references=["oauth-patterns", "security"],
            tags=["auth", "security"],
            issue_link="https://github.com/org/repo/issues/123",
            issue_id="123",
        )
        assert len(task.acceptance_criteria) == 2
        assert task.priority == TaskPriority.HIGH
        assert task.task_type == TaskType.STORY
        assert task.estimated_effort == "3 story points"
        assert len(task.dependencies) == 2
        assert task.parent_id == "T2"
        assert len(task.research_references) == 2
        assert len(task.tags) == 2
        assert "123" in task.issue_link
        assert task.issue_id == "123"

    def test_plan_task_subtask_hierarchy(self) -> None:
        """Test plan task subtask organization."""
        parent = PlanTask(
            id="T1",
            title="Parent task",
            description="Parent",
            task_type=TaskType.STORY,
        )
        subtask = PlanTask(
            id="T1.1",
            title="Subtask",
            description="Child",
            task_type=TaskType.SUBTASK,
            parent_id="T1",
        )
        assert parent.task_type == TaskType.STORY
        assert subtask.task_type == TaskType.SUBTASK
        assert subtask.parent_id == parent.id


class TestPlanManifest:
    """Tests for PlanManifest model."""

    def test_plan_manifest_creation(self) -> None:
        """Test creating a plan manifest with required fields."""
        manifest = PlanManifest(
            name="api-redesign",
            display_name="API Redesign",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )
        assert manifest.name == "api-redesign"
        assert manifest.display_name == "API Redesign"
        assert manifest.created_at == "2025-01-15T10:00:00Z"
        assert manifest.updated_at == "2025-01-15T10:00:00Z"

    def test_plan_manifest_defaults(self) -> None:
        """Test plan manifest default values."""
        manifest = PlanManifest(
            name="test",
            display_name="Test Plan",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )
        assert manifest.status == PlanStatus.DRAFT
        assert manifest.branch_name is None
        assert manifest.created_by is None
        assert manifest.version == "1.0.0"
        assert manifest.research_depth == ResearchDepth.STANDARD
        assert manifest.export_mode is None
        assert manifest.export_provider is None

    def test_plan_manifest_with_all_fields(self) -> None:
        """Test plan manifest with all fields populated."""
        manifest = PlanManifest(
            name="feature-x",
            display_name="Feature X Implementation",
            status=PlanStatus.EXPORTED,
            branch_name="plan/feature-x",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-20T15:30:00Z",
            created_by="engineer@example.com",
            version="1.2.0",
            research_depth=ResearchDepth.COMPREHENSIVE,
            export_mode="hierarchical",
            export_provider="github",
        )
        assert manifest.status == PlanStatus.EXPORTED
        assert manifest.branch_name == "plan/feature-x"
        assert manifest.created_by == "engineer@example.com"
        assert manifest.version == "1.2.0"
        assert manifest.research_depth == ResearchDepth.COMPREHENSIVE
        assert manifest.export_mode == "hierarchical"
        assert manifest.export_provider == "github"


class TestPlan:
    """Tests for Plan model."""

    def test_plan_creation(self) -> None:
        """Test creating a plan with required fields."""
        manifest = PlanManifest(
            name="test-plan",
            display_name="Test Plan",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )
        plan = Plan(manifest=manifest)
        assert plan.manifest.name == "test-plan"

    def test_plan_defaults(self) -> None:
        """Test plan default values."""
        manifest = PlanManifest(
            name="test",
            display_name="Test",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )
        plan = Plan(manifest=manifest)
        assert plan.overview == ""
        assert plan.goals == []
        assert plan.success_criteria == []
        assert plan.scope is None
        assert plan.constraints == []
        assert plan.research_topics == []
        assert plan.tasks == []
        assert plan.metadata == {}

    def test_plan_with_all_fields(self) -> None:
        """Test plan with all fields populated."""
        manifest = PlanManifest(
            name="full-plan",
            display_name="Full Plan",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )
        topics = [
            ResearchTopic(
                slug="topic-1",
                title="Topic 1",
                description="Research topic 1",
            )
        ]
        tasks = [
            PlanTask(
                id="T1",
                title="Task 1",
                description="First task",
            )
        ]
        plan = Plan(
            manifest=manifest,
            overview="This is a comprehensive plan",
            goals=["Goal 1", "Goal 2"],
            success_criteria=["All tests pass", "Deployed to production"],
            scope="API layer only",
            constraints=["Must use existing database", "No breaking changes"],
            research_topics=topics,
            tasks=tasks,
            metadata={"source": "rfc-123", "priority": "high"},
        )
        assert "comprehensive" in plan.overview
        assert len(plan.goals) == 2
        assert len(plan.success_criteria) == 2
        assert plan.scope == "API layer only"
        assert len(plan.constraints) == 2
        assert len(plan.research_topics) == 1
        assert len(plan.tasks) == 1
        assert plan.metadata["source"] == "rfc-123"

    def test_plan_with_nested_models(self) -> None:
        """Test plan with properly nested research topics and tasks."""
        manifest = PlanManifest(
            name="nested-plan",
            display_name="Nested Plan",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
            status=PlanStatus.READY,
        )
        topics = [
            ResearchTopic(
                slug="auth",
                title="Authentication",
                description="Research auth patterns",
                research_questions=["OAuth vs JWT?"],
            ),
            ResearchTopic(
                slug="caching",
                title="Caching Strategy",
                description="Research caching options",
                priority=2,
            ),
        ]
        tasks = [
            PlanTask(
                id="T1",
                title="Epic: Auth System",
                description="Implement authentication",
                task_type=TaskType.EPIC,
            ),
            PlanTask(
                id="T1.1",
                title="JWT Implementation",
                description="Add JWT tokens",
                task_type=TaskType.TASK,
                parent_id="T1",
                research_references=["auth"],
            ),
        ]
        plan = Plan(
            manifest=manifest,
            research_topics=topics,
            tasks=tasks,
        )
        assert len(plan.research_topics) == 2
        assert plan.research_topics[0].slug == "auth"
        assert len(plan.tasks) == 2
        assert plan.tasks[1].parent_id == "T1"
        assert "auth" in plan.tasks[1].research_references


class TestModelSerialization:
    """Tests for model serialization and deserialization."""

    def test_research_topic_dict_roundtrip(self) -> None:
        """Test ResearchTopic serialization and deserialization."""
        topic = ResearchTopic(
            slug="test",
            title="Test Topic",
            description="Description",
            priority=2,
            research_questions=["Q1", "Q2"],
        )
        data = topic.model_dump()
        restored = ResearchTopic.model_validate(data)
        assert restored.slug == topic.slug
        assert restored.title == topic.title
        assert restored.priority == topic.priority
        assert restored.research_questions == topic.research_questions

    def test_plan_task_dict_roundtrip(self) -> None:
        """Test PlanTask serialization and deserialization."""
        task = PlanTask(
            id="T1",
            title="Test Task",
            description="Description",
            priority=TaskPriority.HIGH,
            task_type=TaskType.STORY,
            acceptance_criteria=["AC1", "AC2"],
        )
        data = task.model_dump()
        restored = PlanTask.model_validate(data)
        assert restored.id == task.id
        assert restored.priority == TaskPriority.HIGH
        assert restored.task_type == TaskType.STORY
        assert restored.acceptance_criteria == task.acceptance_criteria

    def test_plan_manifest_dict_roundtrip(self) -> None:
        """Test PlanManifest serialization and deserialization."""
        manifest = PlanManifest(
            name="test",
            display_name="Test",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
            status=PlanStatus.RESEARCHING,
            research_depth=ResearchDepth.COMPREHENSIVE,
        )
        data = manifest.model_dump()
        restored = PlanManifest.model_validate(data)
        assert restored.name == manifest.name
        assert restored.status == PlanStatus.RESEARCHING
        assert restored.research_depth == ResearchDepth.COMPREHENSIVE

    def test_full_plan_dict_roundtrip(self) -> None:
        """Test full Plan serialization and deserialization."""
        manifest = PlanManifest(
            name="test",
            display_name="Test Plan",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )
        plan = Plan(
            manifest=manifest,
            overview="Test overview",
            goals=["Goal 1"],
            research_topics=[
                ResearchTopic(
                    slug="topic",
                    title="Topic",
                    description="Desc",
                )
            ],
            tasks=[
                PlanTask(
                    id="T1",
                    title="Task",
                    description="Desc",
                )
            ],
        )
        data = plan.model_dump()
        restored = Plan.model_validate(data)
        assert restored.manifest.name == plan.manifest.name
        assert restored.overview == plan.overview
        assert restored.goals == plan.goals
        assert len(restored.research_topics) == 1
        assert len(restored.tasks) == 1
        assert restored.research_topics[0].slug == "topic"
        assert restored.tasks[0].id == "T1"

    def test_plan_json_roundtrip(self) -> None:
        """Test Plan JSON serialization and deserialization."""
        manifest = PlanManifest(
            name="json-test",
            display_name="JSON Test",
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )
        plan = Plan(
            manifest=manifest,
            goals=["Test goal"],
        )
        json_str = plan.model_dump_json()
        restored = Plan.model_validate_json(json_str)
        assert restored.manifest.name == "json-test"
        assert restored.goals == ["Test goal"]
