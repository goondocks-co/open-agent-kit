"""Enum types for open-agent-kit.

This module provides type-safe enumerations for status values, priorities,
and categories used throughout the application. Using enums instead of
string constants provides:
- IDE autocomplete and type checking
- Exhaustive pattern matching
- Iteration over valid values
- Clear documentation of allowed values
"""

from enum import Enum


class RFCStatus(str, Enum):
    """RFC document status values."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ADOPTED = "adopted"
    ABANDONED = "abandoned"
    IMPLEMENTED = "implemented"
    WONT_IMPLEMENT = "wont-implement"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all status values."""
        return [s.value for s in cls]


class AmendmentType(str, Enum):
    """Constitution amendment types for semantic versioning."""

    MAJOR = "major"  # Breaking changes (X.0.0)
    MINOR = "minor"  # New requirements (0.X.0)
    PATCH = "patch"  # Clarifications (0.0.X)

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all amendment types."""
        return [t.value for t in cls]


class PlanStatus(str, Enum):
    """Strategic plan status values."""

    DRAFT = "draft"
    RESEARCHING = "researching"
    PLANNING = "planning"
    READY = "ready"
    EXPORTED = "exported"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all plan statuses."""
        return [s.value for s in cls]


class PlanSource(str, Enum):
    """Source of plan content."""

    ISSUE = "issue"
    RESEARCH = "research"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all plan sources."""
        return [s.value for s in cls]


class ResearchDepth(str, Enum):
    """Plan research depth levels."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all research depths."""
        return [d.value for d in cls]


class TaskPriority(str, Enum):
    """Plan task priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all priorities."""
        return [p.value for p in cls]


class TaskType(str, Enum):
    """Plan task types for issue export."""

    EPIC = "epic"
    STORY = "story"
    TASK = "task"
    SUBTASK = "subtask"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all task types."""
        return [t.value for t in cls]


class ExportMode(str, Enum):
    """Plan export mode options."""

    HIERARCHICAL = "hierarchical"
    FLAT = "flat"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all export modes."""
        return [m.value for m in cls]


class ValidationPriority(str, Enum):
    """Validation issue priority levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all priorities."""
        return [p.value for p in cls]


class ValidationCategory(str, Enum):
    """Validation issue categories."""

    STRUCTURE = "structure"
    METADATA = "metadata"
    TOKENS = "tokens"
    DATES = "dates"
    LANGUAGE = "language"
    VERSIONING = "versioning"
    QUALITY = "quality"
    CONSISTENCY = "consistency"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all categories."""
        return [c.value for c in cls]


class IssueProvider(str, Enum):
    """Supported issue tracking providers."""

    ADO = "ado"
    GITHUB = "github"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all providers."""
        return [p.value for p in cls]

    @property
    def display_name(self) -> str:
        """Human-readable provider name."""
        names = {
            "ado": "Azure DevOps",
            "github": "GitHub Issues",
        }
        return names[self.value]

    @property
    def config_key(self) -> str:
        """Config file key for this provider."""
        keys = {
            "ado": "azure_devops",
            "github": "github",
        }
        return keys[self.value]


class IDE(str, Enum):
    """Supported IDE types."""

    VSCODE = "vscode"
    CURSOR = "cursor"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all IDEs."""
        return [i.value for i in cls]

    @property
    def display_name(self) -> str:
        """Human-readable IDE name."""
        names = {
            "vscode": "Visual Studio Code",
            "cursor": "Cursor",
        }
        return names[self.value]


class RFCNumberFormat(str, Enum):
    """RFC number format options."""

    SEQUENTIAL = "sequential"
    YEAR_BASED = "year_based"
    FOUR_DIGIT = "four_digit"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all formats."""
        return [f.value for f in cls]

    @property
    def pattern(self) -> str:
        """Format pattern string."""
        patterns = {
            "sequential": "NNN",
            "year_based": "YYYY-NNN",
            "four_digit": "NNNN",
        }
        return patterns[self.value]
