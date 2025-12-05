"""Plan service package for strategic planning workflows.

This package provides the PlanService class and related utilities
for managing strategic plans, research, tasks, and issue export.

Public API:
    PlanService: Main service class for plan operations
    PlanServiceError: Exception for plan service errors
    get_plan_service: Factory function to create PlanService instance
    PROVIDER_REGISTRY: Available issue provider implementations

Example:
    >>> from open_agent_kit.services.plan import PlanService, PlanServiceError
    >>> service = PlanService(project_root=Path.cwd())
    >>> try:
    ...     manifest = service.create_plan("auth-redesign", "Authentication Redesign")
    ... except PlanServiceError as e:
    ...     print(f"Failed: {e}")
"""

from open_agent_kit.services.plan.core import PlanService, get_plan_service
from open_agent_kit.services.plan.exceptions import PlanServiceError
from open_agent_kit.services.plan.export import PROVIDER_REGISTRY

# Re-export parsing functions for backward compatibility
# Legacy underscore-prefixed aliases for existing code
from open_agent_kit.services.plan.parsing import (
    _detect_issue_changes,
    _parse_list_items,
    _parse_plan_file,
    detect_issue_changes,
    parse_list_items,
    parse_plan_file,
)

# Re-export rendering functions for backward compatibility
# These were previously module-level functions in plan_service.py
# Legacy underscore-prefixed aliases for existing code
from open_agent_kit.services.plan.rendering import (
    _clean_html,
    _format_timestamp,
    _render_issue_plan,
    _render_issue_summary,
    _render_plan_file,
    _render_research_findings,
    _render_tasks,
    _simplify_relation_type,
    _status_emoji,
    clean_html,
    format_timestamp,
    get_status_emoji,
    render_issue_plan,
    render_issue_summary,
    render_plan_file,
    render_research_findings,
    render_tasks,
    simplify_relation_type,
)

__all__ = [
    # Main API
    "PlanService",
    "PlanServiceError",
    "get_plan_service",
    "PROVIDER_REGISTRY",
    # Rendering functions (public names)
    "render_plan_file",
    "render_research_findings",
    "render_tasks",
    "get_status_emoji",
    "render_issue_summary",
    "render_issue_plan",
    "clean_html",
    "simplify_relation_type",
    "format_timestamp",
    # Parsing functions (public names)
    "parse_list_items",
    "parse_plan_file",
    "detect_issue_changes",
    # Legacy underscore-prefixed exports (backward compatibility)
    "_render_plan_file",
    "_render_research_findings",
    "_render_tasks",
    "_status_emoji",
    "_render_issue_summary",
    "_render_issue_plan",
    "_clean_html",
    "_simplify_relation_type",
    "_format_timestamp",
    "_parse_list_items",
    "_parse_plan_file",
    "_detect_issue_changes",
]
