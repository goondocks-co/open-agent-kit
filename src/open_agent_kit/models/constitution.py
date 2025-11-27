"""Constitution document models."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AmendmentType(str, Enum):
    """Amendment types for versioning."""

    MAJOR = "major"  # Breaking changes (X.0.0)
    MINOR = "minor"  # New requirements (0.X.0)
    PATCH = "patch"  # Clarifications (0.0.X)


class ConstitutionStatus(str, Enum):
    """Constitution lifecycle status."""

    DRAFT = "draft"
    RATIFIED = "ratified"
    AMENDED = "amended"
    DEPRECATED = "deprecated"


@dataclass
class ConstitutionMetadata:
    """Constitution metadata."""

    project_name: str
    version: str
    ratification_date: date
    author: str
    last_amendment: date | None = None
    status: ConstitutionStatus = ConstitutionStatus.DRAFT
    tech_stack: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "project_name": self.project_name,
            "version": self.version,
            "ratification_date": self.ratification_date.isoformat(),
            "last_amendment": self.last_amendment.isoformat() if self.last_amendment else "N/A",
            "author": self.author,
            "status": self.status.value,
            "tech_stack": self.tech_stack or "N/A",
            "description": self.description or "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstitutionMetadata":
        """Create from dictionary."""
        # Parse dates
        ratification_date_str = data.get("ratification_date")
        if isinstance(ratification_date_str, str):
            ratification_date = date.fromisoformat(ratification_date_str)
        elif isinstance(ratification_date_str, date):
            ratification_date = ratification_date_str
        else:
            ratification_date = date.today()

        last_amendment_str = data.get("last_amendment")
        if last_amendment_str and last_amendment_str != "N/A":
            if isinstance(last_amendment_str, str):
                last_amendment = date.fromisoformat(last_amendment_str)
            else:
                last_amendment = last_amendment_str
        else:
            last_amendment = None

        # Parse status
        status_str = data.get("status", "draft")
        try:
            status = ConstitutionStatus(status_str)
        except ValueError:
            status = ConstitutionStatus.DRAFT

        return cls(
            project_name=data["project_name"],
            version=data["version"],
            ratification_date=ratification_date,
            author=data["author"],
            last_amendment=last_amendment,
            status=status,
            tech_stack=data.get("tech_stack"),
            description=data.get("description"),
        )


@dataclass
class Amendment:
    """Constitution amendment."""

    version: str
    date: date
    type: AmendmentType
    summary: str
    rationale: str
    author: str
    section: str | None = None
    impact: str | None = None

    def to_markdown(self) -> str:
        """Convert amendment to markdown format."""
        lines = [
            f"## Amendment {self.version} ({self.date.isoformat()})",
            "",
            f"**Type:** {self.type.value.capitalize()}",
            f"**Author:** {self.author}",
            "",
            f"**Summary:** {self.summary}",
            "",
            f"**Rationale:** {self.rationale}",
            "",
        ]

        if self.section:
            lines.extend(["", f"**Section:** {self.section}"])

        if self.impact:
            lines.extend(["", f"**Impact:** {self.impact}"])

        lines.append("")  # Blank line at end
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "date": self.date.isoformat(),
            "type": self.type.value,
            "summary": self.summary,
            "rationale": self.rationale,
            "author": self.author,
            "section": self.section,
            "impact": self.impact,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Amendment":
        """Create from dictionary."""
        # Parse date
        date_str = data.get("date")
        if isinstance(date_str, str):
            amendment_date = date.fromisoformat(date_str)
        elif isinstance(date_str, date):
            amendment_date = date_str
        else:
            amendment_date = date.today()

        # Parse type
        type_str = data.get("type", "patch")
        try:
            amendment_type = AmendmentType(type_str)
        except ValueError:
            amendment_type = AmendmentType.PATCH

        return cls(
            version=data["version"],
            date=amendment_date,
            type=amendment_type,
            summary=data["summary"],
            rationale=data["rationale"],
            author=data["author"],
            section=data.get("section"),
            impact=data.get("impact"),
        )


@dataclass
class ConstitutionSection:
    """Constitution section."""

    title: str
    content: str
    order: int
    required: bool = True

    def to_markdown(self) -> str:
        """Convert section to markdown."""
        return f"## {self.title}\n\n{self.content}\n"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "content": self.content,
            "order": self.order,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstitutionSection":
        """Create from dictionary."""
        return cls(
            title=data["title"],
            content=data["content"],
            order=data["order"],
            required=data.get("required", True),
        )


@dataclass
class ConstitutionDocument:
    """Complete constitution document."""

    metadata: ConstitutionMetadata
    sections: list[ConstitutionSection]
    amendments: list[Amendment] = field(default_factory=list)
    file_path: Path | None = None

    def get_section(self, title: str) -> ConstitutionSection | None:
        """Get section by title."""
        for section in self.sections:
            if section.title.lower() == title.lower():
                return section
        return None

    def add_amendment(self, amendment: Amendment) -> None:
        """Add amendment to constitution."""
        self.amendments.append(amendment)
        self.metadata.last_amendment = amendment.date
        self.metadata.version = amendment.version
        self.metadata.status = ConstitutionStatus.AMENDED

    def get_latest_version(self) -> str:
        """Get latest version number."""
        return self.metadata.version

    def to_markdown(self) -> str:
        """Convert entire constitution to markdown."""
        lines = [
            f"# {self.metadata.project_name} Engineering Constitution",
            "",
            "## Metadata",
            "",
            f"- **Project:** {self.metadata.project_name}",
            f"- **Version:** {self.metadata.version}",
            f"- **Status:** {self.metadata.status.value.capitalize()}",
            f"- **Ratification Date:** {self.metadata.ratification_date.isoformat()}",
            f"- **Last Amendment:** {self.metadata.last_amendment.isoformat() if self.metadata.last_amendment else 'N/A'}",
            f"- **Author:** {self.metadata.author}",
        ]

        if self.metadata.tech_stack:
            lines.append(f"- **Tech Stack:** {self.metadata.tech_stack}")

        if self.metadata.description:
            lines.extend(["", f"**Description:** {self.metadata.description}"])

        lines.extend(["", "---", ""])

        # Add sections
        for section in sorted(self.sections, key=lambda s: s.order):
            lines.append(section.to_markdown())

        # Add amendments section if any exist
        if self.amendments:
            lines.extend(["---", "", "# Amendments", ""])
            for amendment in self.amendments:
                lines.append(amendment.to_markdown())

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "amendments": [a.to_dict() for a in self.amendments],
            "file_path": str(self.file_path) if self.file_path else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstitutionDocument":
        """Create from dictionary."""
        metadata = ConstitutionMetadata.from_dict(data["metadata"])
        sections = [ConstitutionSection.from_dict(s) for s in data.get("sections", [])]
        amendments = [Amendment.from_dict(a) for a in data.get("amendments", [])]

        file_path_str = data.get("file_path")
        file_path = Path(file_path_str) if file_path_str else None

        return cls(
            metadata=metadata,
            sections=sections,
            amendments=amendments,
            file_path=file_path,
        )

    @property
    def is_ratified(self) -> bool:
        """Check if constitution is ratified."""
        return self.metadata.status in [
            ConstitutionStatus.RATIFIED,
            ConstitutionStatus.AMENDED,
        ]

    @property
    def has_amendments(self) -> bool:
        """Check if constitution has amendments."""
        return len(self.amendments) > 0


class DecisionContext(BaseModel):
    """Type-safe decision context for constitution generation.

    This model serves as the single source of truth for constitution decisions.
    All decision fields are validated at creation time, preventing typos and
    invalid values from causing runtime errors.

    IMPORTANT - Keeping Components in Sync:
    When adding or changing decision fields, you MUST update these files:

    1. THIS FILE (models/constitution.py) - SOURCE OF TRUTH
       - Add/modify the field with validation
       - Update Field() with description
       - Literal types define valid values

    2. templates/constitution/decision_points.yaml - AGENT GUIDANCE
       - Add/update the field in decision_categories
       - Provide description, options, and characteristics
       - Ensure option IDs match model's Literal values

    3. templates/constitution/example-decisions*.json - USER EXAMPLES
       - Will be auto-validated by tests (test_decision_context.py)
       - No action needed unless you want to update examples

    4. templates/constitution/base_constitution.md - TEMPLATE LOGIC
       - Add Jinja2 conditionals to render based on decision

    Tests will catch drift between model and YAML (see test_decision_schema_sync.py).
    The model is the authoritative source - it determines what's valid at runtime.
    The YAML guides agents during interactive conversations with users.

    Example:
        >>> decisions = DecisionContext(
        ...     testing_strategy="balanced",
        ...     coverage_target=70,
        ...     architectural_pattern="vertical_slice"
        ... )
        >>> context = decisions.to_template_context()
    """

    # Testing decisions
    testing_strategy: Literal["comprehensive", "balanced", "pragmatic", "custom"] = Field(
        default="balanced", description="Testing approach for the project"
    )
    coverage_target: int | None = Field(
        default=None, ge=0, le=100, description="Code coverage target percentage (0-100)"
    )
    coverage_strict: bool = Field(
        default=False, description="Whether coverage target is strictly enforced in CI"
    )
    has_e2e_infrastructure: bool = Field(
        default=False, description="Whether end-to-end test infrastructure exists"
    )
    e2e_planned: bool = Field(default=False, description="Whether E2E tests are planned for future")
    critical_integration_points: list[str] = Field(
        default_factory=list, description="Critical integration points requiring integration tests"
    )
    tdd_required: bool = Field(
        default=False, description="Whether Test-Driven Development is required"
    )
    testing_rationale: str = Field(
        default="Balanced approach to testing ensures reliability while maintaining velocity",
        description="Rationale for chosen testing approach",
    )

    # Code review decisions
    code_review_policy: Literal["strict", "standard", "flexible", "custom"] = Field(
        default="standard", description="Code review enforcement level"
    )
    num_reviewers: int = Field(
        default=1, ge=0, le=10, description="Number of required reviewers for PRs"
    )
    reviewer_qualifications: str | None = Field(
        default=None, description="Required reviewer qualifications (e.g., senior engineer)"
    )
    hotfix_definition: str | None = Field(
        default=None, description="Definition of what constitutes a hotfix exception"
    )

    # Documentation decisions
    documentation_level: Literal["extensive", "standard", "minimal", "custom"] = Field(
        default="standard", description="Documentation detail level"
    )
    adr_required: bool = Field(
        default=False, description="Whether Architecture Decision Records are required"
    )
    docstring_style: Literal["google", "numpy", "sphinx"] = Field(
        default="google", description="Docstring format style"
    )

    # CI/CD decisions
    ci_enforcement: Literal["full", "standard", "basic", "none", "custom"] = Field(
        default="standard", description="CI/CD enforcement level"
    )
    required_checks: list[str] = Field(
        default_factory=list, description="Required CI/CD checks that must pass"
    )
    ci_platform: str | None = Field(
        default=None, description="CI/CD platform (e.g., 'GitHub Actions', 'GitLab CI')"
    )

    # Architectural decisions
    architectural_pattern: (
        Literal[
            "vertical_slice",
            "clean_architecture",
            "layered",
            "modular_monolith",
            "pragmatic",
            "custom",
        ]
        | None
    ) = Field(default=None, description="Primary architectural pattern used in the project")
    error_handling_pattern: Literal["result_pattern", "exceptions", "mixed"] | None = Field(
        default=None, description="Error handling approach (Result Pattern, exceptions, or mixed)"
    )
    dependency_injection: bool = Field(
        default=False, description="Whether dependency injection pattern is used"
    )
    domain_events: bool = Field(
        default=False, description="Whether domain events pattern is used for decoupling"
    )
    feature_organization: str | None = Field(
        default=None, description="How features are organized (e.g., 'src/features/{feature}/')"
    )
    layer_organization: str | None = Field(
        default=None,
        description="How layers are organized (e.g., 'presentation/application/domain/infrastructure')",
    )
    coding_principles: list[str] = Field(
        default_factory=list,
        description="Key coding principles to follow (e.g., ['SOLID', 'DRY', 'KISS'])",
    )
    architectural_rationale: str | None = Field(
        default=None, description="Rationale for architectural choices made in the project"
    )

    @field_validator("coverage_target")
    @classmethod
    def validate_coverage_target(cls, v: int | None) -> int | None:
        """Validate coverage target is reasonable."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Coverage target must be between 0 and 100")
        return v

    def to_template_context(self) -> dict[str, Any]:
        """Convert to template context dict using constants as keys.

        This method maps the validated model fields to the template context
        dictionary using the DECISION_* constants as keys, ensuring consistency
        between the model and template rendering.

        Returns:
            Dictionary with DECISION_* constant keys for template rendering
        """
        from open_agent_kit.constants import (
            DECISION_ADR_REQUIRED,
            DECISION_ARCHITECTURAL_PATTERN,
            DECISION_ARCHITECTURAL_RATIONALE,
            DECISION_CI_ENFORCEMENT,
            DECISION_CI_PLATFORM,
            DECISION_CODE_REVIEW_POLICY,
            DECISION_CODING_PRINCIPLES,
            DECISION_COVERAGE_STRICT,
            DECISION_COVERAGE_TARGET,
            DECISION_CRITICAL_INTEGRATION_POINTS,
            DECISION_DEPENDENCY_INJECTION,
            DECISION_DOCSTRING_STYLE,
            DECISION_DOCUMENTATION_LEVEL,
            DECISION_DOMAIN_EVENTS,
            DECISION_E2E_PLANNED,
            DECISION_ERROR_HANDLING_PATTERN,
            DECISION_FEATURE_ORGANIZATION,
            DECISION_HAS_E2E_INFRASTRUCTURE,
            DECISION_HOTFIX_DEFINITION,
            DECISION_LAYER_ORGANIZATION,
            DECISION_NUM_REVIEWERS,
            DECISION_REQUIRED_CHECKS,
            DECISION_REVIEWER_QUALIFICATIONS,
            DECISION_TDD_REQUIRED,
            DECISION_TESTING_RATIONALE,
            DECISION_TESTING_STRATEGY,
        )

        return {
            DECISION_TESTING_STRATEGY: self.testing_strategy,
            DECISION_COVERAGE_TARGET: self.coverage_target,
            DECISION_COVERAGE_STRICT: self.coverage_strict,
            DECISION_HAS_E2E_INFRASTRUCTURE: self.has_e2e_infrastructure,
            DECISION_E2E_PLANNED: self.e2e_planned,
            DECISION_CRITICAL_INTEGRATION_POINTS: self.critical_integration_points,
            DECISION_TDD_REQUIRED: self.tdd_required,
            DECISION_TESTING_RATIONALE: self.testing_rationale,
            DECISION_CODE_REVIEW_POLICY: self.code_review_policy,
            DECISION_NUM_REVIEWERS: self.num_reviewers,
            DECISION_REVIEWER_QUALIFICATIONS: self.reviewer_qualifications,
            DECISION_HOTFIX_DEFINITION: self.hotfix_definition,
            DECISION_DOCUMENTATION_LEVEL: self.documentation_level,
            DECISION_ADR_REQUIRED: self.adr_required,
            DECISION_DOCSTRING_STYLE: self.docstring_style,
            DECISION_CI_ENFORCEMENT: self.ci_enforcement,
            DECISION_REQUIRED_CHECKS: self.required_checks,
            DECISION_CI_PLATFORM: self.ci_platform,
            DECISION_ARCHITECTURAL_PATTERN: self.architectural_pattern,
            DECISION_ERROR_HANDLING_PATTERN: self.error_handling_pattern,
            DECISION_DEPENDENCY_INJECTION: self.dependency_injection,
            DECISION_DOMAIN_EVENTS: self.domain_events,
            DECISION_FEATURE_ORGANIZATION: self.feature_organization,
            DECISION_LAYER_ORGANIZATION: self.layer_organization,
            DECISION_CODING_PRINCIPLES: self.coding_principles,
            DECISION_ARCHITECTURAL_RATIONALE: self.architectural_rationale,
        }

    @classmethod
    def get_defaults(cls) -> "DecisionContext":
        """Get default decision context with all sensible defaults.

        Returns:
            DecisionContext with default values
        """
        return cls()

    model_config = ConfigDict(
        # Allow extra fields for forward compatibility and comments in JSON
        # (fields starting with _ are ignored, useful for documentation)
        extra="ignore",
        # Use enum values for serialization
        use_enum_values=True,
    )
