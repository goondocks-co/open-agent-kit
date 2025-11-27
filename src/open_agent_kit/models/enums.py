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
