"""Plan service exceptions.

This module provides exception classes for plan service operations.
"""


class PlanServiceError(Exception):
    """Exception raised for plan service errors.

    This is the base exception for all plan-related errors,
    including plan creation, research operations, task management,
    and issue export failures.

    Args:
        message: Error description
        **context: Additional context for debugging

    Example:
        >>> raise PlanServiceError("Plan not found", plan_name="auth-redesign")
    """

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx_str})"
        return self.message
