"""Backward compatibility re-exports from plan package.

This module maintains backward compatibility for code that imports from
`open_agent_kit.services.plan_service`. All functionality has been moved
to the `open_agent_kit.services.plan` package.

New code should import directly from the package:
    from open_agent_kit.services.plan import PlanService, PlanServiceError

Deprecation Notice:
    This module will be removed in a future version. Please update imports
    to use `open_agent_kit.services.plan` instead.
"""

# Re-export everything from the new package location
from open_agent_kit.services.plan import (
    PROVIDER_REGISTRY,
    PlanService,
    PlanServiceError,
    _clean_html,
    _detect_issue_changes,
    _format_timestamp,
    _parse_list_items,
    _render_issue_plan,
    _render_issue_summary,
    _render_plan_file,
    _render_research_findings,
    _render_tasks,
    _simplify_relation_type,
    _status_emoji,
    get_plan_service,
)

__all__ = [
    "PlanService",
    "PlanServiceError",
    "get_plan_service",
    "PROVIDER_REGISTRY",
    # Legacy underscore-prefixed functions
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
    "_detect_issue_changes",
]
