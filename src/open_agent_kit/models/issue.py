"""Issue item models."""

from typing import Any

from pydantic import BaseModel, Field


class TestStep(BaseModel):
    """Represents a test step from ADO Test Case issues."""

    step_number: int = Field(description="Step sequence number")
    action: str = Field(description="Action to perform in this step")
    expected_result: str | None = Field(
        default=None, description="Expected outcome after performing action"
    )
    shared_step_reference: int | None = Field(
        default=None, description="Reference to shared step ID if applicable"
    )


class Comment(BaseModel):
    """Represents a comment on an issue."""

    comment_id: str | None = Field(default=None, description="Unique comment identifier")
    text: str = Field(description="Comment text content")
    created_by: str | None = Field(default=None, description="Author display name")
    created_date: str | None = Field(default=None, description="Creation timestamp (ISO 8601)")
    modified_date: str | None = Field(
        default=None, description="Last modification timestamp (ISO 8601)"
    )


class RelatedIssue(BaseModel):
    """Represents related issues (parent/child/test/etc.)."""

    relation_type: str
    identifier: str | None = None
    title: str | None = None
    url: str | None = None
    additional_metadata: dict[str, str] = Field(default_factory=dict)


class Issue(BaseModel):
    """Represents a fetched issue from an external provider."""

    provider: str = Field(description="Issue provider key (e.g., ado, github)")
    identifier: str = Field(description="Provider-specific identifier or number")
    title: str = Field(description="Human-readable title")
    description: str | None = Field(default=None, description="Detailed description or body")
    state: str | None = Field(default=None, description="Workflow state (e.g., Active, New)")
    url: str | None = Field(default=None, description="Deep link to the issue")
    assigned_to: str | None = Field(default=None, description="Assigned engineer or team")
    area_path: str | None = Field(default=None, description="Area path or component")
    iteration_path: str | None = Field(default=None, description="Iteration or sprint path")
    tags: list[str] = Field(default_factory=list, description="Provider tags or labels")
    acceptance_criteria: list[str] = Field(
        default_factory=list, description="Acceptance criteria extracted from the issue"
    )
    relations: list[RelatedIssue] = Field(
        default_factory=list,
        description="Related artifacts (parent epics, pull requests, commits, etc.)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Raw provider fields for future reference"
    )
    branch_name: str | None = Field(
        default=None, description="Git branch name associated with this issue"
    )

    # Type-specific fields (optional, backward compatible)
    test_steps: list[TestStep] | None = Field(
        default=None, description="Test steps for Test Case issues"
    )
    repro_steps: list[str] | None = Field(
        default=None, description="Reproduction steps for Bug issues"
    )
    effort: float | None = Field(default=None, description="Story points or effort estimate")
    priority: int | None = Field(default=None, description="Priority level")
    issue_type: str | None = Field(
        default=None, description="Provider-specific issue type (User Story, Task, Bug, etc.)"
    )

    # Comments (applicable to most providers)
    comments: list[Comment] = Field(default_factory=list, description="Comments on this issue")

    # GitHub-specific fields (optional)
    milestone: str | None = Field(default=None, description="Milestone name (GitHub)")
    comments_count: int | None = Field(default=None, description="Number of comments (GitHub)")
    created_at: str | None = Field(default=None, description="Creation timestamp (ISO 8601)")
    updated_at: str | None = Field(default=None, description="Last update timestamp (ISO 8601)")
    closed_at: str | None = Field(default=None, description="Closed timestamp (ISO 8601)")


class IssuePlanDetails(BaseModel):
    """Additional planning notes captured interactively."""

    objectives: str | None = Field(default=None, description="Goals or success criteria")
    environment: str | None = Field(default=None, description="Local environment constraints")
    risks: str | None = Field(default=None, description="Known risks or blockers")
    dependencies: str | None = Field(default=None, description="Dependencies or partners")
    definition_of_done: str | None = Field(
        default=None, description="Definition of done or verification steps"
    )
