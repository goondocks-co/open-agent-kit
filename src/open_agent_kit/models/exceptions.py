"""Exception hierarchy for open-agent-kit.

This module provides a centralized exception hierarchy for all oak errors. All
exceptions inherit from OakError and support context information for better
error reporting and debugging.

Exception Hierarchy:
    OakError (base)
    ├── ConfigurationError - Configuration and settings issues
    ├── ValidationError - RFC/Constitution validation failures
    ├── TemplateError - Template rendering/loading errors
    ├── MigrationError - State migration errors
    └── ServiceError (base for service-layer errors)
        ├── PlanServiceError - Plan service specific errors
        ├── RFCServiceError - RFC service specific errors
        ├── ConstitutionServiceError - Constitution service errors
        └── IssueProviderError - Issue provider (GitHub/ADO) errors

Example:
    >>> raise ValidationError(
    ...     "RFC validation failed",
    ...     rfc_number="001",
    ...     issues=["Missing section: Motivation"]
    ... )

    >>> raise ConfigurationError(
    ...     "Provider not configured",
    ...     provider="github",
    ...     suggestion="Run 'oak config --setup-provider github' to configure"
    ... )
"""

from typing import Any


class OakError(Exception):
    """Base exception for all oak errors with context support.

    All oak exceptions inherit from this base class and support storing
    additional context information as keyword arguments. The context is
    automatically included in the error message for better debugging.

    Attributes:
        message: The primary error message
        context: Additional context information as key-value pairs

    Example:
        >>> error = OakError("Operation failed", file="config.yaml", line=42)
        >>> str(error)
        'Operation failed (file: config.yaml, line: 42)'
    """

    def __init__(self, message: str, **context: Any) -> None:
        """Initialize the error with a message and optional context.

        Args:
            message: The primary error message
            **context: Additional context information as key-value pairs
        """
        self.message = message
        self.context = context
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation including context if present.

        Returns:
            Error message with context formatted as key-value pairs
        """
        if not self.context:
            return self.message

        context_str = ", ".join(f"{k}: {v}" for k, v in self.context.items())
        return f"{self.message} ({context_str})"


class ConfigurationError(OakError):
    """Configuration file issues and missing settings.

    Raised when there are problems with configuration files, missing required
    settings, or invalid configuration values. Supports an optional suggestion
    for how to fix the issue.

    Attributes:
        message: The primary error message
        context: Additional context information
        suggestion: Optional suggestion for fixing the issue

    Example:
        >>> raise ConfigurationError(
        ...     "Provider not configured",
        ...     provider="github",
        ...     suggestion="Run 'oak config --setup-provider github'"
        ... )
    """

    def __init__(self, message: str, suggestion: str | None = None, **context: Any) -> None:
        """Initialize configuration error with optional suggestion.

        Args:
            message: The primary error message
            suggestion: Optional suggestion for fixing the issue
            **context: Additional context information
        """
        self.suggestion = suggestion
        super().__init__(message, **context)

    def __str__(self) -> str:
        """Return string representation with optional suggestion.

        Returns:
            Error message with context and suggestion if provided
        """
        base_str = super().__str__()
        if self.suggestion:
            return f"{base_str}\nSuggestion: {self.suggestion}"
        return base_str


class ValidationError(OakError):
    """RFC and Constitution validation failures.

    Raised when validation of RFC documents, constitution files, or other
    structured content fails. Context should include details about what
    failed validation.

    Example:
        >>> raise ValidationError(
        ...     "RFC validation failed",
        ...     rfc_number="001",
        ...     issues=["Missing section: Motivation", "Invalid status"]
        ... )
    """

    pass


class ServiceError(OakError):
    """Base exception for service-layer errors.

    All service-specific exceptions should inherit from this class. Used
    for errors that occur in the business logic layer of the application.

    Example:
        >>> raise ServiceError(
        ...     "Failed to process request",
        ...     service="rfc_service",
        ...     operation="create"
        ... )
    """

    pass


class PlanServiceError(ServiceError):
    """Plan service specific errors.

    Raised when errors occur in the plan service, such as plan creation,
    validation, or state management failures.

    Example:
        >>> raise PlanServiceError(
        ...     "Failed to create plan",
        ...     plan_id="plan-001",
        ...     reason="Invalid task dependencies"
        ... )
    """

    pass


class RFCServiceError(ServiceError):
    """RFC service specific errors.

    Raised when errors occur in the RFC service, such as RFC creation,
    listing, or file operations.

    Example:
        >>> raise RFCServiceError(
        ...     "Failed to create RFC",
        ...     rfc_number="001",
        ...     reason="RFC already exists"
        ... )
    """

    pass


class ConstitutionServiceError(ServiceError):
    """Constitution service errors.

    Raised when errors occur in the constitution service, such as
    constitution creation, amendment processing, or validation failures.

    Example:
        >>> raise ConstitutionServiceError(
        ...     "Failed to apply amendment",
        ...     amendment_number="A001",
        ...     reason="Constitution not found"
        ... )
    """

    pass


class IssueProviderError(ServiceError):
    """Issue provider (GitHub/ADO) errors.

    Raised when errors occur while interacting with issue providers such as
    GitHub Issues or Azure DevOps. Context should include provider details
    and the specific operation that failed.

    Example:
        >>> raise IssueProviderError(
        ...     "Failed to fetch issue",
        ...     provider="github",
        ...     issue_id="123",
        ...     reason="Authentication failed"
        ... )
    """

    pass


class TemplateError(OakError):
    """Template rendering and loading errors.

    Raised when errors occur during template loading, rendering, or when
    template syntax is invalid. Context should include template details
    and the specific error.

    Example:
        >>> raise TemplateError(
        ...     "Failed to render template",
        ...     template="rfc-engineering.md.j2",
        ...     reason="Undefined variable: author"
        ... )
    """

    pass


class MigrationError(OakError):
    """State migration errors.

    Raised when errors occur during state migrations, such as when upgrading
    configuration files or migrating data structures. Context should include
    migration details and failure reason.

    Example:
        >>> raise MigrationError(
        ...     "Migration failed",
        ...     migration_id="2025.11.28_features",
        ...     reason="Failed to backup config file"
        ... )
    """

    pass
