"""Base summarization interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SummarizationResult:
    """Result from LLM summarization."""

    observations: list[dict[str, Any]] = field(default_factory=list)
    """Extracted observations with type, content, and context."""

    session_summary: str = ""
    """Brief summary of what happened in the session."""

    success: bool = True
    """Whether summarization succeeded."""

    error: str | None = None
    """Error message if summarization failed."""


class BaseSummarizer(ABC):
    """Base class for session summarizers."""

    # Optional attributes for resolved model info (set by implementations)
    _resolved_model: str | None = None
    _context_window: int | None = None

    @abstractmethod
    def summarize_session(
        self,
        files_created: list[str],
        files_modified: list[str],
        files_read: list[str],
        commands_run: list[str],
        duration_minutes: float,
    ) -> SummarizationResult:
        """Summarize a session's activity into meaningful observations.

        Args:
            files_created: List of files that were created.
            files_modified: List of files that were modified.
            files_read: List of files that were read.
            commands_run: List of commands that were executed.
            duration_minutes: Session duration in minutes.

        Returns:
            SummarizationResult with extracted observations.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the summarizer is available and configured."""
        pass
