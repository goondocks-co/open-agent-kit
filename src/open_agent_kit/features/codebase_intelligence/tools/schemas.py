"""Input schemas for CI tools.

Pydantic models for validating tool inputs. Used by both MCP handlers
and SDK tool wrappers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_SEARCH_LIMIT,
    SEARCH_TYPE_ALL,
)


class SearchInput(BaseModel):
    """Input for search tool (oak_search / ci_search)."""

    query: str = Field(..., description="Natural language search query")
    search_type: str = Field(
        default=SEARCH_TYPE_ALL,
        description="Type of search: 'code', 'memory', 'plans', or 'all'",
    )
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT,
        description="Maximum number of results to return",
        ge=1,
        le=50,
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
