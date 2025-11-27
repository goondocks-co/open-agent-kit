"""Base classes for issue providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from open_agent_kit.models.issue import Issue


class IssueProviderError(Exception):
    """Raised when a provider fails to perform an operation."""


class IssueProvider(ABC):
    """Abstract base class for issue providers."""

    key: str
    label: str

    def __init__(self, settings: Any, environment: Mapping[str, str]):
        """Initialize provider.

        Args:
            settings: Provider-specific configuration model
            environment: Environment variables (read-only)
        """
        self.settings = settings
        self.environment = environment

    @abstractmethod
    def validate(self) -> list[str]:
        """Validate provider configuration.

        Returns:
            List of validation issues (empty list if valid)
        """

    @abstractmethod
    def fetch(self, identifier: str) -> Issue:
        """Fetch an issue from the provider.

        Args:
            identifier: Provider-specific issue identifier

        Returns:
            Issue model
        """

    def build_branch_name(self, identifier: str, title: str | None = None) -> str:
        """Build a default branch name for the issue.

        Args:
            identifier: Issue identifier
            title: Optional title to include in branch name

        Returns:
            Suggested branch name
        """
        from open_agent_kit.utils import sanitize_title

        base = identifier.lower().replace(" ", "-")
        if title:
            slug = sanitize_title(title)
            if slug:
                base = f"{base}-{slug.lower()}"
        return base
