"""Session operations for activity store.

Barrel re-export of all session functions from domain modules:
- crud: Create, read, update operations
- queries: Listing, counting, filtering
- lifecycle: Recovery, cleanup, subagent parent finding
- linking: Parent-child linking, lineage, cycle detection
"""

from open_agent_kit.features.team.activity.store.sessions.crud import (
    create_session,
    end_session,
    ensure_session_exists,
    get_or_create_session,
    get_session,
    increment_prompt_count,
    mark_session_summary_embedded,
    reactivate_session_if_needed,
    update_session_summary,
    update_session_title,
    update_session_transcript_path,
)
from open_agent_kit.features.team.activity.store.sessions.lifecycle import (
    cleanup_low_quality_sessions,
    find_active_parent_for_subagent,
    recover_stale_sessions,
)
from open_agent_kit.features.team.activity.store.sessions.linking import (
    clear_session_parent,
    enrich_sessions_with_lineage,
    find_just_ended_session,
    find_linkable_parent_session,
    get_bulk_child_session_counts,
    get_child_session_count,
    get_child_sessions,
    get_session_lineage,
    is_suggestion_dismissed,
    log_link_event,
    update_session_parent,
    would_create_cycle,
)
from open_agent_kit.features.team.activity.store.sessions.queries import (
    count_session_activities,
    count_sessions,
    count_sessions_with_summaries,
    get_completed_sessions,
    get_recent_sessions,
    get_session_members,
    get_sessions_missing_summaries,
    get_sessions_needing_titles,
    get_unprocessed_sessions,
    is_session_sufficient,
    list_sessions_with_summaries,
    mark_session_processed,
)

__all__ = [
    # crud
    "create_session",
    "end_session",
    "ensure_session_exists",
    "get_or_create_session",
    "get_session",
    "increment_prompt_count",
    "mark_session_summary_embedded",
    "reactivate_session_if_needed",
    "update_session_summary",
    "update_session_title",
    "update_session_transcript_path",
    # queries
    "count_session_activities",
    "count_sessions",
    "count_sessions_with_summaries",
    "get_completed_sessions",
    "get_recent_sessions",
    "get_session_members",
    "get_sessions_missing_summaries",
    "get_sessions_needing_titles",
    "get_unprocessed_sessions",
    "is_session_sufficient",
    "list_sessions_with_summaries",
    "mark_session_processed",
    # lifecycle
    "cleanup_low_quality_sessions",
    "find_active_parent_for_subagent",
    "recover_stale_sessions",
    # linking
    "clear_session_parent",
    "enrich_sessions_with_lineage",
    "find_just_ended_session",
    "find_linkable_parent_session",
    "get_bulk_child_session_counts",
    "get_child_session_count",
    "get_child_sessions",
    "get_session_lineage",
    "is_suggestion_dismissed",
    "log_link_event",
    "update_session_parent",
    "would_create_cycle",
]
