"""Validation data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationPriority(str, Enum):
    """Validation issue priority levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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


@dataclass
class ValidationIssue:
    """Single validation issue."""

    category: ValidationCategory
    priority: ValidationPriority
    message: str
    location: str | None = None
    line_number: int | None = None
    suggested_fix: str | None = None
    auto_fixable: bool = False

    def __str__(self) -> str:
        """String representation of issue."""
        location_str = f" at {self.location}" if self.location else ""
        line_str = f" (line {self.line_number})" if self.line_number else ""
        priority_icon = {
            ValidationPriority.HIGH: "❌",
            ValidationPriority.MEDIUM: "⚠️",
            ValidationPriority.LOW: "ℹ️",
        }
        icon = priority_icon.get(self.priority, "•")
        return f"{icon} [{self.priority.value.upper()}] {self.message}{location_str}{line_str}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category.value,
            "priority": self.priority.value,
            "message": self.message,
            "location": self.location,
            "line_number": self.line_number,
            "suggested_fix": self.suggested_fix,
            "auto_fixable": self.auto_fixable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationIssue":
        """Create from dictionary."""
        category = ValidationCategory(data["category"])
        priority = ValidationPriority(data["priority"])

        return cls(
            category=category,
            priority=priority,
            message=data["message"],
            location=data.get("location"),
            line_number=data.get("line_number"),
            suggested_fix=data.get("suggested_fix"),
            auto_fixable=data.get("auto_fixable", False),
        )


@dataclass
class ValidationResult:
    """Result of constitution validation."""

    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add validation issue."""
        self.issues.append(issue)
        self.is_valid = False

    def get_issues_by_priority(self, priority: ValidationPriority) -> list[ValidationIssue]:
        """Get issues filtered by priority."""
        return [issue for issue in self.issues if issue.priority == priority]

    def get_issues_by_category(self, category: ValidationCategory) -> list[ValidationIssue]:
        """Get issues filtered by category."""
        return [issue for issue in self.issues if issue.category == category]

    def get_auto_fixable_issues(self) -> list[ValidationIssue]:
        """Get issues that can be auto-fixed."""
        return [issue for issue in self.issues if issue.auto_fixable]

    def categorize_issues(self) -> dict[ValidationPriority, list[ValidationIssue]]:
        """Group issues by priority."""
        categorized: dict[ValidationPriority, list[ValidationIssue]] = {
            ValidationPriority.HIGH: [],
            ValidationPriority.MEDIUM: [],
            ValidationPriority.LOW: [],
        }
        for issue in self.issues:
            categorized[issue.priority].append(issue)
        return categorized

    def calculate_stats(self) -> dict[str, Any]:
        """Calculate validation statistics."""
        high = len(self.get_issues_by_priority(ValidationPriority.HIGH))
        medium = len(self.get_issues_by_priority(ValidationPriority.MEDIUM))
        low = len(self.get_issues_by_priority(ValidationPriority.LOW))

        priority_counts = {
            ValidationPriority.HIGH.value: high,
            ValidationPriority.MEDIUM.value: medium,
            ValidationPriority.LOW.value: low,
        }

        category_counts = {
            category.value: len(self.get_issues_by_category(category))
            for category in ValidationCategory
        }

        self.stats = {
            "total_issues": len(self.issues),
            "high_priority": high,
            "medium_priority": medium,
            "low_priority": low,
            "auto_fixable": len(self.get_auto_fixable_issues()),
            "warnings": len(self.warnings),
            "priority_counts": priority_counts,
            "category_counts": category_counts,
        }

        for category_key, count in category_counts.items():
            self.stats[f"{category_key}_issues"] = count

        return self.stats

    def has_high_priority_issues(self) -> bool:
        """Check if any high priority issues exist."""
        return len(self.get_issues_by_priority(ValidationPriority.HIGH)) > 0

    @property
    def total_issues(self) -> int:
        """Convenience accessor for total issues."""
        count = self.stats.get("total_issues", len(self.issues))
        return int(count) if count is not None else len(self.issues)

    @property
    def high_priority_count(self) -> int:
        """Convenience accessor for high priority issue count."""
        count = self.stats.get("high_priority")
        if count is not None:
            return int(count)
        return len(self.get_issues_by_priority(ValidationPriority.HIGH))

    @property
    def medium_priority_count(self) -> int:
        """Convenience accessor for medium priority issue count."""
        count = self.stats.get("medium_priority")
        if count is not None:
            return int(count)
        return len(self.get_issues_by_priority(ValidationPriority.MEDIUM))

    @property
    def low_priority_count(self) -> int:
        """Convenience accessor for low priority issue count."""
        count = self.stats.get("low_priority")
        if count is not None:
            return int(count)
        return len(self.get_issues_by_priority(ValidationPriority.LOW))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "warnings": self.warnings,
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationResult":
        """Create from dictionary."""
        issues = [ValidationIssue.from_dict(issue_data) for issue_data in data.get("issues", [])]

        return cls(
            is_valid=data.get("is_valid", True),
            issues=issues,
            warnings=data.get("warnings", []),
            stats=data.get("stats", {}),
        )


@dataclass
class ValidationFix:
    """Proposed fix for validation issue."""

    issue: ValidationIssue
    original_content: str
    fixed_content: str
    applied: bool = False

    def apply(self) -> str:
        """Apply the fix and return fixed content."""
        self.applied = True
        return self.fixed_content

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "issue": self.issue.to_dict(),
            "original_content": self.original_content,
            "fixed_content": self.fixed_content,
            "applied": self.applied,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationFix":
        """Create from dictionary."""
        issue = ValidationIssue.from_dict(data["issue"])

        return cls(
            issue=issue,
            original_content=data["original_content"],
            fixed_content=data["fixed_content"],
            applied=data.get("applied", False),
        )
