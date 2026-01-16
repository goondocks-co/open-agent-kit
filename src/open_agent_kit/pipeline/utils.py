"""Utility functions for pipeline stages.

This module provides reusable utilities for common patterns
in pipeline stage implementations.
"""

from collections.abc import Callable, Iterable
from typing import TypeVar

from open_agent_kit.pipeline.models import ProcessingResult

T = TypeVar("T")


def process_items(
    items: Iterable[T],
    processor: Callable[[T], None],
    item_name_fn: Callable[[T], str] | None = None,
) -> ProcessingResult:
    """Process items and track successes/failures.

    This is a utility for the common pattern of iterating over items,
    performing an operation on each, and tracking which succeeded
    and which failed.

    Args:
        items: Items to process
        processor: Function to call on each item. Should raise exception on failure.
        item_name_fn: Function to extract display name from item.
                     Defaults to str(item).

    Returns:
        ProcessingResult with succeeded and failed lists

    Example:
        >>> def upgrade_command(cmd):
        ...     # raises on failure
        ...     pass
        >>> result = process_items(
        ...     commands,
        ...     upgrade_command,
        ...     lambda cmd: cmd["file"]
        ... )
        >>> print(f"Upgraded {result.success_count}, failed {result.failure_count}")
    """
    if item_name_fn is None:
        item_name_fn = str

    result = ProcessingResult()

    for item in items:
        item_name = item_name_fn(item)
        try:
            processor(item)
            result.succeeded.append(item_name)
        except Exception as e:
            result.failed.append(f"{item_name}: {e}")

    return result


def format_count_message(
    action: str,
    succeeded: int,
    failed: int,
    item_name: str = "item",
) -> str:
    """Format a message for completed processing with success/failure counts.

    Args:
        action: Past tense action verb (e.g., "Upgraded", "Removed")
        succeeded: Number of successful items
        failed: Number of failed items
        item_name: Singular name for items (e.g., "command", "skill")

    Returns:
        Formatted message string

    Example:
        >>> format_count_message("Upgraded", 5, 2, "command")
        "Upgraded 5 command(s), 2 failed"
        >>> format_count_message("Removed", 3, 0, "file")
        "Removed 3 file(s)"
    """
    plural = f"{item_name}(s)"

    if failed > 0:
        return f"{action} {succeeded} {plural}, {failed} failed"
    return f"{action} {succeeded} {plural}"
