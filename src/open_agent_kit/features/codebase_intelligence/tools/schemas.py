"""Input schemas for CI tools.

Pydantic models for validating tool inputs. Used by both MCP handlers
and SDK tool wrappers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_QUERY_DEFAULT_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    OBSERVATION_STATUS_ACTIVE,
    SEARCH_TYPE_ALL,
)


class SearchInput(BaseModel):
    """Input for search tool (oak_search / ci_search)."""

    query: str = Field(..., description="Natural language search query")
    search_type: str = Field(
        default=SEARCH_TYPE_ALL,
        description="Type of search: 'code', 'memory', 'plans', 'sessions', or 'all'",
    )
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT,
        description="Maximum number of results to return",
        ge=1,
        le=50,
    )
    include_resolved: bool = Field(
        default=False,
        description="If True, include resolved/superseded memories in results",
    )


class RememberInput(BaseModel):
    """Input for remember tool (oak_remember)."""

    observation: str = Field(
        ...,
        description="The observation or learning to remember",
    )
    memory_type: str = Field(
        default="discovery",
        description="Type: 'gotcha', 'bug_fix', 'decision', 'discovery', 'trade_off'",
    )
    context: str | None = Field(
        default=None,
        description="Related file path or context information",
    )


class ContextInput(BaseModel):
    """Input for context tool (oak_context)."""

    task: str = Field(
        ...,
        description="Description of the current task or what you're working on",
    )
    current_files: list[str] = Field(
        default_factory=list,
        description="Files currently being viewed or edited",
    )
    max_tokens: int = Field(
        default=2000,
        description="Maximum tokens of context to return",
    )


class MemoriesInput(BaseModel):
    """Input for memories listing tool (ci_memories)."""

    memory_type: str | None = Field(
        default=None,
        description="Filter by memory type (optional)",
    )
    limit: int = Field(
        default=20,
        description="Maximum number of results to return",
        ge=1,
        le=100,
    )
    status: str = Field(
        default=OBSERVATION_STATUS_ACTIVE,
        description="Filter by observation status: 'active', 'resolved', or 'superseded'",
    )
    include_resolved: bool = Field(
        default=False,
        description="If True, include all statuses regardless of status filter",
    )


class SessionsInput(BaseModel):
    """Input for sessions listing tool (ci_sessions)."""

    limit: int = Field(
        default=10,
        description="Maximum number of sessions to return",
        ge=1,
        le=20,
    )
    include_summary: bool = Field(
        default=True,
        description="Include session summaries in output",
    )


class StatsInput(BaseModel):
    """Input for project stats tool (ci_project_stats)."""

    # No required inputs - returns all available stats
    pass


class QueryInput(BaseModel):
    """Input for SQL query tool (ci_query)."""

    sql: str = Field(..., description="SQL query (SELECT/WITH/EXPLAIN only)")
    limit: int = Field(
        default=CI_QUERY_DEFAULT_LIMIT,
        description="Maximum rows to return",
        ge=1,
        le=500,
    )


class ActivityInput(BaseModel):
    """Input for activity listing tool (oak_activity)."""

    session_id: str = Field(..., description="Session ID to get activities for")
    tool_name: str | None = Field(
        default=None,
        description="Filter by tool name (optional)",
    )
    limit: int = Field(
        default=50,
        description="Maximum number of activities to return",
        ge=1,
        le=200,
    )


class ArchiveInput(BaseModel):
    """Input for archive tool (ci_archive / oak_archive_memories)."""

    ids: list[str] | None = Field(
        default=None,
        description="Specific observation IDs to archive",
    )
    status_filter: str | None = Field(
        default=None,
        description="Archive by status: 'resolved', 'superseded', or 'both'",
    )
    older_than_days: int | None = Field(
        default=None,
        description="Only archive observations older than this many days",
        ge=1,
    )
    dry_run: bool = Field(
        default=False,
        description="If True, return count without actually archiving",
    )
