"""Plan models for strategic planning workflows."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    """Status values for plans."""

    DRAFT = "draft"
    RESEARCHING = "researching"
    PLANNING = "planning"
    READY = "ready"
    IMPLEMENTING = "implementing"
    IMPLEMENTED = "implemented"
    EXPORTED = "exported"


class PlanSource(str, Enum):
    """Source of plan content."""

    ISSUE = "issue"
    RESEARCH = "research"


class ResearchDepth(str, Enum):
    """Research depth levels."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


class TaskPriority(str, Enum):
    """Task priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskType(str, Enum):
    """Task types for issue export."""

    EPIC = "epic"
    STORY = "story"
    TASK = "task"
    SUBTASK = "subtask"


class IssueReference(BaseModel):
    """Reference to an external issue in the plan manifest."""

    provider: str = Field(..., description="Issue provider key (ado, github)")
    id: str = Field(..., description="Issue identifier")
    url: str | None = Field(default=None, description="Issue URL")
    title: str | None = Field(default=None, description="Issue title for display")


class ResearchTopic(BaseModel):
    """A research topic within a plan."""

    slug: str = Field(description="URL-safe identifier (e.g., 'api-design-patterns')")
    title: str = Field(description="Human-readable topic title")
    description: str = Field(description="What to research and why")
    priority: int = Field(default=1, ge=1, le=5, description="Priority 1-5 (1=highest)")
    status: str = Field(
        default="pending", description="Research status: pending, in_progress, completed, skipped"
    )
    research_questions: list[str] = Field(
        default_factory=list, description="Specific questions to answer during research"
    )
    sources_to_check: list[str] = Field(
        default_factory=list, description="Suggested sources (URLs, docs, repos) to investigate"
    )
    findings_path: str | None = Field(
        default=None, description="Path to research findings file if completed"
    )


class ResearchFinding(BaseModel):
    """Research findings for a topic."""

    topic_slug: str = Field(description="Reference to the research topic")
    summary: str = Field(description="Executive summary of findings")
    key_insights: list[str] = Field(default_factory=list, description="Key insights discovered")
    recommendations: list[str] = Field(
        default_factory=list, description="Recommended approaches based on research"
    )
    sources: list[str] = Field(default_factory=list, description="Sources consulted")
    trade_offs: list[str] = Field(default_factory=list, description="Trade-offs identified")
    research_date: str | None = Field(default=None, description="When research was conducted")
    researcher_notes: str | None = Field(default=None, description="Additional notes from research")


class PlanTask(BaseModel):
    """A structured task within a plan."""

    id: str = Field(description="Unique task identifier (e.g., 'T1', 'T2.1')")
    title: str = Field(description="Task title")
    description: str = Field(description="Detailed task description")
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="Acceptance criteria for the task"
    )
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    task_type: TaskType = Field(default=TaskType.TASK, description="Type for issue export")
    estimated_effort: str | None = Field(
        default=None, description="Effort estimate (e.g., '2 hours', '1 day', '3 story points')"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Task IDs this task depends on"
    )
    parent_id: str | None = Field(
        default=None, description="Parent task ID for hierarchical organization"
    )
    research_references: list[str] = Field(
        default_factory=list, description="Research topic slugs this task is informed by"
    )
    tags: list[str] = Field(default_factory=list, description="Tags/labels for categorization")
    issue_link: str | None = Field(default=None, description="Link to created issue after export")
    issue_id: str | None = Field(default=None, description="Provider issue ID after export")


class PlanManifest(BaseModel):
    """Manifest metadata for a plan (stored in .manifest.json)."""

    name: str = Field(description="Plan name (URL-safe identifier)")
    display_name: str = Field(description="Human-readable plan name")
    sources: list[str] = Field(default_factory=list, description="Source types: issue, research")
    status: PlanStatus = Field(default=PlanStatus.DRAFT, description="Current plan status")
    branch_name: str | None = Field(default=None, description="Git branch for this plan")
    issue: IssueReference | None = Field(
        default=None, description="Issue reference for issue-first plans"
    )
    research_topics: list[str] = Field(default_factory=list, description="Research topic slugs")
    created_at: str = Field(description="ISO 8601 creation timestamp")
    updated_at: str = Field(description="ISO 8601 last update timestamp")
    created_by: str | None = Field(default=None, description="Author of the plan")
    version: str = Field(default="1.0.0", description="Plan version")
    research_depth: ResearchDepth = Field(
        default=ResearchDepth.STANDARD, description="Research depth level"
    )
    export_mode: str | None = Field(
        default=None, description="Export mode: hierarchical or flat (set during export)"
    )
    export_provider: str | None = Field(
        default=None, description="Issue provider used for export (ado, github)"
    )


class Plan(BaseModel):
    """Complete plan model combining manifest and content."""

    manifest: PlanManifest = Field(description="Plan metadata")
    overview: str = Field(default="", description="High-level plan overview")
    goals: list[str] = Field(default_factory=list, description="Plan goals/objectives")
    success_criteria: list[str] = Field(
        default_factory=list, description="How success will be measured"
    )
    scope: str | None = Field(default=None, description="What's in and out of scope")
    constraints: list[str] = Field(
        default_factory=list, description="Known constraints or limitations"
    )
    research_topics: list[ResearchTopic] = Field(
        default_factory=list, description="Topics requiring research"
    )
    tasks: list[PlanTask] = Field(default_factory=list, description="Generated tasks")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
