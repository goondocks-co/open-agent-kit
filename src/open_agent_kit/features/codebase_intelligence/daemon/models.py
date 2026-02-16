"""Pydantic models for daemon API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from open_agent_kit.features.codebase_intelligence.retrieval.engine import Confidence


class ChunkType(str, Enum):
    """Types of code chunks."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    UNKNOWN = "unknown"


class MemoryType(str, Enum):
    """Types of memory observations.

    This enum provides API validation for memory types. The canonical definitions
    including descriptions and examples are in schema.yaml:
        features/codebase-intelligence/schema.yaml

    When adding new types:
    1. Add to schema.yaml (source of truth for LLM prompts)
    2. Add here for API validation
    """

    GOTCHA = "gotcha"
    BUG_FIX = "bug_fix"
    DECISION = "decision"
    DISCOVERY = "discovery"
    TRADE_OFF = "trade_off"
    SESSION_SUMMARY = "session_summary"
    # Special type for indexed plans (from prompt_batches, not memory_observations)
    PLAN = "plan"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"  # Keep for backward compat
    oak_version: str | None = None  # OAK package version
    schema_version: int | None = None  # DB schema version
    uptime_seconds: float = 0.0
    project_root: str | None = None


class StatusResponse(BaseModel):
    """Detailed status response."""

    daemon: dict = Field(default_factory=dict)
    index: dict = Field(default_factory=dict)
    memory: dict = Field(default_factory=dict)
    embedding: dict = Field(default_factory=dict)


class SearchRequest(BaseModel):
    """Search request."""

    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=20, ge=1, le=100)
    search_type: str = Field(default="all", pattern="^(all|code|memory|plans|sessions)$")
    apply_doc_type_weights: bool = Field(
        default=True,
        description="Apply doc_type weighting to deprioritize i18n/config files. Disable for translation searches.",
    )
    include_resolved: bool = False


class DocType(str, Enum):
    """Document type classification for search result filtering/weighting."""

    CODE = "code"
    I18N = "i18n"
    CONFIG = "config"
    TEST = "test"
    DOCS = "docs"


class CodeResult(BaseModel):
    """Code search result."""

    id: str
    chunk_type: ChunkType
    name: str | None
    filepath: str
    start_line: int
    end_line: int
    tokens: int
    relevance: float
    confidence: Confidence = Confidence.MEDIUM
    doc_type: DocType = DocType.CODE
    preview: str | None = None


class MemoryResult(BaseModel):
    """Memory search result."""

    id: str
    memory_type: MemoryType
    summary: str
    tokens: int
    relevance: float
    confidence: Confidence = Confidence.MEDIUM
    created_at: datetime | None = None
    status: str = "active"


class PlanResult(BaseModel):
    """Plan search result.

    Plans represent the "intention" layer - the why behind code changes.
    They are indexed from prompt_batches with source_type='plan'.
    """

    id: str
    relevance: float
    confidence: Confidence = Confidence.MEDIUM
    title: str
    preview: str
    session_id: str | None = None
    created_at: datetime | None = None
    tokens: int = 0


class SessionResult(BaseModel):
    """Session search result.

    Sessions are searched via their embedded summaries in ChromaDB.
    """

    id: str
    relevance: float
    confidence: Confidence = Confidence.MEDIUM
    title: str | None = None
    preview: str
    status: str = "completed"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    prompt_batch_count: int = 0


class SearchResponse(BaseModel):
    """Search results."""

    query: str
    code: list[CodeResult] = Field(default_factory=list)
    memory: list[MemoryResult] = Field(default_factory=list)
    plans: list[PlanResult] = Field(default_factory=list)
    sessions: list[SessionResult] = Field(default_factory=list)
    total_tokens_available: int = 0


class FetchRequest(BaseModel):
    """Request to fetch full content."""

    ids: list[str] = Field(..., min_length=1, max_length=20)


class FetchResult(BaseModel):
    """Fetched content."""

    id: str
    content: str
    tokens: int


class FetchResponse(BaseModel):
    """Fetch results."""

    results: list[FetchResult] = Field(default_factory=list)
    total_tokens: int = 0


class RememberRequest(BaseModel):
    """Request to store an observation."""

    observation: str = Field(..., min_length=1)
    memory_type: MemoryType = MemoryType.DISCOVERY
    context: str | None = None
    tags: list[str] = Field(default_factory=list)
    session_id: str | None = None


class RememberResponse(BaseModel):
    """Response after storing observation."""

    id: str
    stored: bool = True
    message: str = "Observation stored successfully"


class MemoryListItem(BaseModel):
    """Memory item for listing (without relevance score)."""

    id: str
    memory_type: MemoryType
    observation: str
    context: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    archived: bool = False
    status: str = "active"
    embedded: bool = False
    session_origin_type: str | None = None


class MemoriesListResponse(BaseModel):
    """Response for listing memories."""

    memories: list[MemoryListItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class ObservationStatus(str, Enum):
    """Lifecycle status for memory observations."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


class SessionOriginType(str, Enum):
    """Classification of how a session operated."""

    PLANNING = "planning"
    INVESTIGATION = "investigation"
    IMPLEMENTATION = "implementation"
    MIXED = "mixed"


class BulkAction(str, Enum):
    """Supported bulk actions for memories."""

    DELETE = "delete"
    ARCHIVE = "archive"
    UNARCHIVE = "unarchive"
    ADD_TAG = "add_tag"
    REMOVE_TAG = "remove_tag"
    RESOLVE = "resolve"


class BulkMemoriesRequest(BaseModel):
    """Request to perform bulk operations on memories."""

    memory_ids: list[str] = Field(..., min_length=1, description="List of memory IDs to operate on")
    action: BulkAction = Field(..., description="Action to perform")
    tag: str | None = Field(default=None, description="Tag for add_tag/remove_tag actions")


class BulkMemoriesResponse(BaseModel):
    """Response for bulk memory operations."""

    success: bool = True
    affected_count: int = 0
    message: str = ""


class UpdateObservationStatusRequest(BaseModel):
    """Request to update observation lifecycle status."""

    status: ObservationStatus
    resolved_by_session_id: str | None = None
    reason: str | None = None
    superseded_by: str | None = None


class BulkResolveRequest(BaseModel):
    """Request to bulk-resolve observations."""

    session_id: str | None = None
    memory_ids: list[str] | None = None
    status: ObservationStatus = ObservationStatus.RESOLVED
    resolved_by_session_id: str = Field(...)


class BulkResolveResponse(BaseModel):
    """Response from bulk-resolve operation."""

    success: bool = True
    resolved_count: int = 0
    message: str = ""


class IndexRequest(BaseModel):
    """Request to trigger indexing."""

    full_rebuild: bool = False


class IndexResponse(BaseModel):
    """Indexing response."""

    status: str
    chunks_indexed: int = 0
    files_processed: int = 0
    duration_seconds: float = 0.0


# ============================================================================
# Session and Hook Models (claude-mem inspired)
# ============================================================================


class SessionInfo(BaseModel):
    """Active session tracking."""

    session_id: str
    agent: str
    started_at: datetime
    observations: list[str] = Field(default_factory=list)
    tool_calls: int = 0
    last_activity: datetime | None = None


class PostToolUseRequest(BaseModel):
    """Request from PostToolUse hook."""

    session_id: str | None = None
    agent: str = "unknown"
    tool_name: str
    tool_input: dict = Field(default_factory=dict)
    tool_output: str = ""
    success: bool = True
    working_directory: str | None = None


class SessionEndRequest(BaseModel):
    """Request from SessionEnd/Stop hook."""

    session_id: str | None = None
    agent: str = "unknown"
    transcript_path: str | None = None
    working_directory: str | None = None


class ObservationExtract(BaseModel):
    """Extracted observation from tool output."""

    observation: str
    memory_type: MemoryType
    context: str | None = None
    confidence: float = 0.8


# ============================================================================
# Context Request/Response Models
# ============================================================================


class ContextRequest(BaseModel):
    """Request for task context."""

    task: str = Field(..., min_length=1, description="Description of the task")
    current_files: list[str] = Field(default_factory=list, description="Files being viewed/edited")
    max_tokens: int = Field(default=2000, ge=100, le=10000)
    apply_doc_type_weights: bool = Field(
        default=True,
        description="Apply doc_type weighting to deprioritize i18n/config files. Disable for non-code tasks.",
    )


class ContextCodeResult(BaseModel):
    """Code context result."""

    file_path: str
    chunk_type: str
    name: str | None
    start_line: int
    relevance: float


class ContextMemoryResult(BaseModel):
    """Memory context result."""

    memory_type: str
    observation: str
    relevance: float


class ContextResponse(BaseModel):
    """Context response for a task."""

    task: str
    code: list[ContextCodeResult] = Field(default_factory=list)
    memories: list[ContextMemoryResult] = Field(default_factory=list)
    guidelines: list[str] = Field(default_factory=list)
    total_tokens: int = 0


# ============================================================================
# Activity Models (SQLite activity tracking)
# ============================================================================


class ActivityItem(BaseModel):
    """Single activity from a tool execution."""

    id: str
    session_id: str
    prompt_batch_id: str | None = None
    tool_name: str
    tool_input: dict | None = None
    tool_output_summary: str | None = None
    file_path: str | None = None
    success: bool = True
    error_message: str | None = None
    created_at: datetime


class PromptBatchItem(BaseModel):
    """Prompt batch - activities from a single user prompt.

    Source types categorize batches for different processing strategies:
    - user: User-initiated prompts (extract memories normally)
    - agent_notification: Background agent completions (preserve but skip memory extraction)
    - plan: Plan mode activities (extract plan as decision memory)
    - system: System messages (skip memory extraction)
    """

    id: str
    session_id: str
    prompt_number: int
    user_prompt: str | None = None
    classification: str | None = None
    source_type: str = "user"  # user, agent_notification, plan, system
    plan_file_path: str | None = None  # Path to plan file (for source_type='plan')
    plan_content: str | None = None  # Full plan content (stored for self-contained CI)
    started_at: datetime
    ended_at: datetime | None = None
    activity_count: int = 0
    response_summary: str | None = None  # Agent's final response (v21)


class SessionItem(BaseModel):
    """Session - Claude Code session from launch to exit."""

    id: str
    agent: str
    project_root: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "active"
    summary: str | None = None
    title: str | None = None
    first_prompt_preview: str | None = None
    prompt_batch_count: int = 0
    activity_count: int = 0
    # Session linking fields
    parent_session_id: str | None = None
    parent_session_reason: str | None = None
    child_session_count: int = 0
    # Resume command (populated from agent manifest)
    resume_command: str | None = None


class ActivityListResponse(BaseModel):
    """Response for listing activities."""

    activities: list[ActivityItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    sessions: list[SessionItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class PromptBatchListResponse(BaseModel):
    """Response for listing prompt batches."""

    prompt_batches: list[PromptBatchItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class PlanListItem(BaseModel):
    """Plan item for listing (from prompt_batches with source_type='plan')."""

    id: int  # batch_id
    title: str  # extracted from file path or first heading
    session_id: str
    created_at: datetime
    file_path: str | None = None
    preview: str  # first 200 chars of plan_content
    plan_embedded: bool = False  # indexed in ChromaDB?


class PlansListResponse(BaseModel):
    """Response for listing plans."""

    plans: list[PlanListItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class SessionDetailResponse(BaseModel):
    """Detailed session response with stats."""

    session: SessionItem
    stats: dict = Field(default_factory=dict)
    recent_activities: list[ActivityItem] = Field(default_factory=list)
    prompt_batches: list[PromptBatchItem] = Field(default_factory=list)


class ActivitySearchResponse(BaseModel):
    """Response for activity search."""

    query: str
    activities: list[ActivityItem] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Delete Response Models
# ============================================================================


class DeleteResponse(BaseModel):
    """Base response for delete operations."""

    success: bool = True
    deleted_count: int = 0
    message: str = ""


class DeleteSessionResponse(DeleteResponse):
    """Response for session deletion with cascade counts."""

    batches_deleted: int = 0
    activities_deleted: int = 0
    memories_deleted: int = 0


class DeleteBatchResponse(DeleteResponse):
    """Response for prompt batch deletion with cascade counts."""

    activities_deleted: int = 0
    memories_deleted: int = 0


class DeleteActivityResponse(DeleteResponse):
    """Response for activity deletion."""

    memory_deleted: bool = False


class DeleteMemoryResponse(DeleteResponse):
    """Response for memory deletion."""

    pass


# ============================================================================
# Session Linking Models
# ============================================================================


class SessionLineageItem(BaseModel):
    """Session in a lineage chain."""

    id: str
    title: str | None = None
    first_prompt_preview: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "active"
    parent_session_reason: str | None = None
    prompt_batch_count: int = 0


class SessionLineageResponse(BaseModel):
    """Response for session lineage query."""

    session_id: str
    ancestors: list[SessionLineageItem] = Field(default_factory=list)
    children: list[SessionLineageItem] = Field(default_factory=list)


class LinkSessionRequest(BaseModel):
    """Request to link a session to a parent."""

    parent_session_id: str = Field(..., min_length=1, description="Parent session ID to link to")
    reason: str = Field(
        default="manual",
        description="Link reason: 'clear', 'compact', 'inferred', 'manual'",
    )


class LinkSessionResponse(BaseModel):
    """Response after linking a session."""

    success: bool = True
    session_id: str
    parent_session_id: str
    reason: str
    message: str = ""


class UnlinkSessionResponse(BaseModel):
    """Response after unlinking a session from its parent."""

    success: bool = True
    session_id: str
    previous_parent_id: str | None = None
    message: str = ""


# ============================================================================
# Session Completion Models
# ============================================================================


class CompleteSessionResponse(BaseModel):
    """Response after manually completing a session."""

    success: bool = True
    session_id: str
    previous_status: str = ""
    summary: str | None = None
    title: str | None = None
    message: str = ""


# ============================================================================
# Summary Regeneration Models
# ============================================================================


class RegenerateSummaryResponse(BaseModel):
    """Response after regenerating a session summary and title."""

    success: bool = True
    session_id: str
    summary: str | None = None
    title: str | None = None
    message: str = ""


# ============================================================================
# Plan Refresh Models
# ============================================================================


class RefreshPlanResponse(BaseModel):
    """Response after refreshing a plan from disk."""

    success: bool = True
    batch_id: int
    plan_file_path: str | None = None
    content_length: int = 0
    message: str = ""


# ============================================================================
# Session Suggestion Models
# ============================================================================


class SuggestedParentResponse(BaseModel):
    """Response for session suggested parent query."""

    session_id: str
    has_suggestion: bool = False
    suggested_parent: SessionLineageItem | None = None
    confidence: str | None = None  # high, medium, low
    confidence_score: float | None = None
    reason: str | None = None
    dismissed: bool = False


class DismissSuggestionResponse(BaseModel):
    """Response after dismissing a suggestion."""

    success: bool = True
    session_id: str
    message: str = ""


class ReembedSessionsResponse(BaseModel):
    """Response after re-embedding session summaries."""

    success: bool = True
    sessions_processed: int = 0
    sessions_embedded: int = 0
    message: str = ""


# ============================================================================
# Session Relationship Models (many-to-many semantic links)
# ============================================================================


class RelatedSessionItem(BaseModel):
    """A session related to another via many-to-many relationship."""

    id: str
    title: str | None = None
    first_prompt_preview: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "completed"
    prompt_batch_count: int = 0
    # Relationship metadata
    relationship_id: int
    similarity_score: float | None = None
    created_by: str  # 'suggestion' or 'manual'
    related_at: datetime


class RelatedSessionsResponse(BaseModel):
    """Response for session related sessions query."""

    session_id: str
    related: list[RelatedSessionItem] = Field(default_factory=list)


class AddRelatedRequest(BaseModel):
    """Request to add a related session."""

    related_session_id: str = Field(..., min_length=1, description="Session to relate to")
    similarity_score: float | None = Field(
        default=None, description="Vector similarity score (if from suggestion)"
    )


class AddRelatedResponse(BaseModel):
    """Response after adding a related session."""

    success: bool = True
    session_id: str
    related_session_id: str
    relationship_id: int | None = None
    message: str = ""


class RemoveRelatedResponse(BaseModel):
    """Response after removing a related session."""

    success: bool = True
    session_id: str
    related_session_id: str
    message: str = ""


class SuggestedRelatedItem(BaseModel):
    """A suggested related session."""

    id: str
    title: str | None = None
    first_prompt_preview: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    status: str = "completed"
    prompt_batch_count: int = 0
    confidence: str  # high, medium, low
    confidence_score: float
    reason: str


class SuggestedRelatedResponse(BaseModel):
    """Response for suggested related sessions query."""

    session_id: str
    suggestions: list[SuggestedRelatedItem] = Field(default_factory=list)
