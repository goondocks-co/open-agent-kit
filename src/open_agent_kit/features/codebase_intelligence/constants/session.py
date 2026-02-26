"""Session, batch, linking, suggestion, and observation lifecycle constants."""

from typing import Final

# =============================================================================
# Session & Batch Status Values
# =============================================================================

SESSION_STATUS_ACTIVE: Final[str] = "active"
SESSION_STATUS_COMPLETED: Final[str] = "completed"

# =============================================================================
# Daemon Status
# =============================================================================

DAEMON_STATUS_RUNNING: Final[str] = "running"
DAEMON_STATUS_STOPPED: Final[str] = "stopped"
DAEMON_STATUS_HEALTHY: Final[str] = "healthy"
DAEMON_STATUS_UNHEALTHY: Final[str] = "unhealthy"

# =============================================================================
# Session Quality Threshold
# =============================================================================
# Minimum activities (tool calls) for a session to be considered "quality".
# Sessions below this threshold:
# - Will NOT have titles generated (avoids hallucinated titles from minimal context)
# - Will NOT have summaries generated
# - Will NOT be embedded to ChromaDB
# - Will be deleted during stale session cleanup
# This matches the existing threshold in summaries.py:182 for summary generation.

MIN_SESSION_ACTIVITIES: Final[int] = 3

# =============================================================================
# Session Linking
# =============================================================================
# When a session starts with source="clear", we try to link it to the previous
# session using a tiered approach:
# 1. Tier 1 (immediate): Session ended within SESSION_LINK_IMMEDIATE_GAP_SECONDS
# 2. Tier 2 (race fix): Active session (SessionEnd not yet processed)
# 3. Tier 3 (stale): Completed session within SESSION_LINK_FALLBACK_MAX_HOURS

# Parent session reasons (why a session is linked to another)
SESSION_LINK_REASON_CLEAR: Final[str] = "clear"  # Immediate transition (< 5s)
SESSION_LINK_REASON_CLEAR_ACTIVE: Final[str] = "clear_active"  # Race condition fix
SESSION_LINK_REASON_COMPACT: Final[str] = "compact"  # Auto-compact
SESSION_LINK_REASON_INFERRED: Final[str] = "inferred"  # Stale/next-day fallback
SESSION_LINK_REASON_MANUAL: Final[str] = "manual"  # User manually linked

# Timing windows for session linking
SESSION_LINK_IMMEDIATE_GAP_SECONDS: Final[int] = 5  # Tier 1: just-ended sessions
SESSION_LINK_FALLBACK_MAX_HOURS: Final[int] = 24  # Tier 3: stale session fallback

# Legacy alias (deprecated, use SESSION_LINK_IMMEDIATE_GAP_SECONDS)
SESSION_LINK_MAX_GAP_SECONDS: Final[int] = SESSION_LINK_IMMEDIATE_GAP_SECONDS

# User-accepted suggestion (distinct from auto-linked)
SESSION_LINK_REASON_SUGGESTION: Final[str] = "suggestion"

# =============================================================================
# Session Link Event Types (for analytics tracking)
# =============================================================================
# Event types logged to session_link_events table for understanding user behavior

LINK_EVENT_AUTO_LINKED: Final[str] = "auto_linked"
LINK_EVENT_SUGGESTION_ACCEPTED: Final[str] = "suggestion_accepted"
LINK_EVENT_SUGGESTION_REJECTED: Final[str] = "suggestion_rejected"
LINK_EVENT_MANUAL_LINKED: Final[str] = "manual_linked"
LINK_EVENT_UNLINKED: Final[str] = "unlinked"

# =============================================================================
# Suggestion Confidence
# =============================================================================
# Confidence levels for parent session suggestions based on vector + LLM scoring

SUGGESTION_CONFIDENCE_HIGH: Final[str] = "high"
SUGGESTION_CONFIDENCE_MEDIUM: Final[str] = "medium"
SUGGESTION_CONFIDENCE_LOW: Final[str] = "low"
VALID_SUGGESTION_CONFIDENCE_LEVELS: Final[tuple[str, ...]] = (
    SUGGESTION_CONFIDENCE_HIGH,
    SUGGESTION_CONFIDENCE_MEDIUM,
    SUGGESTION_CONFIDENCE_LOW,
)

# Confidence thresholds for categorizing suggestions
# These are intentionally conservative to avoid showing poor-quality suggestions
# With LLM refinement enabled, scores combine vector similarity (40%) + LLM (60%)
SUGGESTION_HIGH_THRESHOLD: Final[float] = 0.8  # Strong match - high confidence
SUGGESTION_MEDIUM_THRESHOLD: Final[float] = 0.65  # Decent match - worth considering
SUGGESTION_LOW_THRESHOLD: Final[float] = 0.5  # Minimum to show any suggestion

# Time bonus thresholds for suggestion scoring
SUGGESTION_TIME_BONUS_1H_SECONDS: Final[int] = 3600  # < 1 hour: +0.1 bonus
SUGGESTION_TIME_BONUS_6H_SECONDS: Final[int] = 21600  # < 6 hours: +0.05 bonus
SUGGESTION_TIME_BONUS_1H_VALUE: Final[float] = 0.1
SUGGESTION_TIME_BONUS_6H_VALUE: Final[float] = 0.05

# Weights for combining vector similarity and LLM score
SUGGESTION_VECTOR_WEIGHT: Final[float] = 0.4
SUGGESTION_LLM_WEIGHT: Final[float] = 0.6

# Max candidate sessions to consider for LLM refinement
SUGGESTION_MAX_CANDIDATES: Final[int] = 5

# Max age in days for suggestion candidates
SUGGESTION_MAX_AGE_DAYS: Final[int] = 7

# =============================================================================
# Session Relationships (many-to-many semantic links)
# =============================================================================
# These complement parent-child links (temporal continuity) with semantic
# relationships that can span any time gap.

# Relationship types
RELATIONSHIP_TYPE_RELATED: Final[str] = "related"

# Created by sources
RELATIONSHIP_CREATED_BY_SUGGESTION: Final[str] = "suggestion"
RELATIONSHIP_CREATED_BY_MANUAL: Final[str] = "manual"

# Extended age limit for related session suggestions (effectively unlimited)
# Unlike parent suggestions (7 days), related sessions can span any time gap
# because they're based on semantic similarity, not temporal proximity.
RELATED_SUGGESTION_MAX_AGE_DAYS: Final[int] = 365

# =============================================================================
# Observation Lifecycle
# =============================================================================

OBSERVATION_STATUS_ACTIVE: Final[str] = "active"
OBSERVATION_STATUS_RESOLVED: Final[str] = "resolved"
OBSERVATION_STATUS_SUPERSEDED: Final[str] = "superseded"
VALID_OBSERVATION_STATUSES: Final[tuple[str, ...]] = (
    OBSERVATION_STATUS_ACTIVE,
    OBSERVATION_STATUS_RESOLVED,
    OBSERVATION_STATUS_SUPERSEDED,
)

# Observation Origin Types (distinguishes how observations were created)
ORIGIN_TYPE_AUTO_EXTRACTED: Final[str] = "auto_extracted"
ORIGIN_TYPE_AGENT_CREATED: Final[str] = "agent_created"

# Archive status filters (for ci_archive / oak_archive_memories)
ARCHIVE_FILTER_BOTH: Final[str] = "both"
VALID_ARCHIVE_FILTERS: Final[tuple[str, ...]] = (
    OBSERVATION_STATUS_RESOLVED,
    OBSERVATION_STATUS_SUPERSEDED,
    ARCHIVE_FILTER_BOTH,
)

# Resolution Event Actions
RESOLUTION_EVENT_ACTION_RESOLVED: Final[str] = "resolved"
RESOLUTION_EVENT_ACTION_SUPERSEDED: Final[str] = "superseded"
RESOLUTION_EVENT_ACTION_REACTIVATED: Final[str] = "reactivated"
VALID_RESOLUTION_EVENT_ACTIONS: Final[tuple[str, ...]] = (
    RESOLUTION_EVENT_ACTION_RESOLVED,
    RESOLUTION_EVENT_ACTION_SUPERSEDED,
    RESOLUTION_EVENT_ACTION_REACTIVATED,
)

# Session Origin Types
SESSION_ORIGIN_PLANNING: Final[str] = "planning"
SESSION_ORIGIN_INVESTIGATION: Final[str] = "investigation"
SESSION_ORIGIN_IMPLEMENTATION: Final[str] = "implementation"
SESSION_ORIGIN_MIXED: Final[str] = "mixed"
VALID_SESSION_ORIGIN_TYPES: Final[tuple[str, ...]] = (
    SESSION_ORIGIN_PLANNING,
    SESSION_ORIGIN_INVESTIGATION,
    SESSION_ORIGIN_IMPLEMENTATION,
    SESSION_ORIGIN_MIXED,
)

# Planning importance cap
SESSION_ORIGIN_PLANNING_IMPORTANCE_CAP: Final[int] = 5

# Maximum observations per batch (hard cap enforced after LLM extraction).
# The extraction prompts ask for "at most 5" (soft limit); this is the hard cap.
MAX_OBSERVATIONS_PER_BATCH: Final[int] = 8

# Session origin classification thresholds
SESSION_ORIGIN_READ_EDIT_RATIO_THRESHOLD: Final[float] = 5.0
SESSION_ORIGIN_MAX_EDITS_FOR_PLANNING: Final[int] = 2
SESSION_ORIGIN_MIN_EDITS_FOR_IMPLEMENTATION: Final[int] = 3

# Auto-resolve: supersede older observations when a new one is semantically equivalent
AUTO_RESOLVE_SIMILARITY_THRESHOLD: Final[float] = 0.80
AUTO_RESOLVE_SIMILARITY_THRESHOLD_NO_CONTEXT: Final[float] = 0.88
AUTO_RESOLVE_SEARCH_LIMIT: Final[int] = 10
AUTO_RESOLVE_SKIP_TYPES: Final[tuple[str, ...]] = ("session_summary",)

# Auto-resolve validation limits
AUTO_RESOLVE_SIMILARITY_MIN: Final[float] = 0.5
AUTO_RESOLVE_SIMILARITY_MAX: Final[float] = 0.99
AUTO_RESOLVE_SEARCH_LIMIT_MIN: Final[int] = 1
AUTO_RESOLVE_SEARCH_LIMIT_MAX: Final[int] = 20
AUTO_RESOLVE_CONFIG_KEY: Final[str] = "auto_resolve"

# =============================================================================
# Resiliency and Recovery
# =============================================================================

# Continuation prompt placeholder (used when session continues from another)
# This is used when activities are created without a prompt batch (e.g., during
# session transitions after "clear context and proceed")
RECOVERY_BATCH_PROMPT: Final[str] = "[Continued from previous session]"

# Auto-end batches stuck in 'active' status longer than this (5 minutes)
# This is a safety net - batches should normally be closed by Stop hook or
# the next UserPromptSubmit. A shorter timeout ensures eventual consistency.
BATCH_ACTIVE_TIMEOUT_SECONDS: Final[int] = 300

# Auto-end sessions inactive longer than this (1 hour)
SESSION_INACTIVE_TIMEOUT_SECONDS: Final[int] = 3600

# =============================================================================
# Session Continuation Labels
# =============================================================================
# Labels for system-created batches during session continuation events.
# These are descriptive labels shown in the UI, not agent-specific behavior.
# The actual triggers (SessionStart sources) are defined in agent manifests.

# When user explicitly clears context to continue in a new session
BATCH_LABEL_CLEARED_CONTEXT: Final[str] = "[Session continuation from cleared context]"

# When agent automatically compacts context mid-session
BATCH_LABEL_CONTEXT_COMPACTION: Final[str] = "[Continuation after context compaction]"

# Generic fallback for other continuation scenarios
BATCH_LABEL_SESSION_CONTINUATION: Final[str] = "[Session continuation]"

# Batch reactivation timeout (seconds) - universal across agents
# If a batch was completed within this time and tools are still executing,
# reactivate it instead of creating a new batch
BATCH_REACTIVATION_TIMEOUT_SECONDS: Final[int] = 60

# =============================================================================
# Prompt Classification Thresholds
# =============================================================================
# Tool-ratio thresholds for classifying session activity type.
# If edit-tool count exceeds this fraction of total tools → "implementation"
IMPLEMENTATION_TOOL_RATIO_THRESHOLD: Final[float] = 0.3
# If explore-tool count exceeds this fraction of total tools → "exploration"
EXPLORATION_TOOL_RATIO_THRESHOLD: Final[float] = 0.5

# =============================================================================
# Prompt Source Types
# =============================================================================
# Source types categorize prompts by origin for different processing strategies.
# - user: User-initiated prompts (extract memories normally)
# - agent_notification: Background agent completions (preserve but skip memory extraction)
# - plan: Plan mode activities (extract plan as decision memory)
# - system: System messages (skip memory extraction)

PROMPT_SOURCE_USER: Final[str] = "user"
PROMPT_SOURCE_AGENT: Final[str] = "agent_notification"
PROMPT_SOURCE_SYSTEM: Final[str] = "system"
PROMPT_SOURCE_PLAN: Final[str] = "plan"
# Plan synthesized from TaskCreate activities
PROMPT_SOURCE_DERIVED_PLAN: Final[str] = "derived_plan"

VALID_PROMPT_SOURCES: Final[tuple[str, ...]] = (
    PROMPT_SOURCE_USER,
    PROMPT_SOURCE_AGENT,
    PROMPT_SOURCE_SYSTEM,
    PROMPT_SOURCE_PLAN,
    PROMPT_SOURCE_DERIVED_PLAN,
)

# =============================================================================
# Internal Message Detection
# =============================================================================
# Prefixes used to detect internal/system messages that should not generate memories.
# Plan detection is handled dynamically via AgentService.get_all_plan_directories().

INTERNAL_MESSAGE_PREFIXES: Final[tuple[str, ...]] = (
    "<task-notification>",  # Background agent completion messages
    "<system-",  # System reminder/prompt messages
)

# =============================================================================
# Context Injection Limits
# =============================================================================
# Limits for context injected into AI agent conversations via hooks.

# Code injection limits
INJECTION_MAX_CODE_CHUNKS: Final[int] = 3
INJECTION_MAX_LINES_PER_CHUNK: Final[int] = 50

# Memory injection limits
INJECTION_MAX_MEMORIES: Final[int] = 10
INJECTION_MAX_SESSION_SUMMARIES: Final[int] = 3

# Summary generation limits
SUMMARY_MAX_PLAN_CONTEXT_LENGTH: Final[int] = 1500

# Session start injection text
INJECTION_SESSION_SUMMARIES_TITLE: Final[str] = "## Recent Session Summaries (most recent first)"
INJECTION_SESSION_START_REMINDER_TITLE: Final[str] = "## OAK CI Tools"
INJECTION_SESSION_START_REMINDER_LINES: Final[tuple[str, ...]] = (
    "- MCP tools: `oak_search` (code/memories), `oak_context` (task context), "
    "`oak_remember` (store learnings), `oak_resolve_memory` (mark resolved).",
    "- After fixing a bug or addressing a gotcha, use `oak_search` to find "
    "the observation's UUID, then call `oak_resolve_memory` with that UUID.",
)
INJECTION_SESSION_START_REMINDER_BLOCK: Final[str] = "\n".join(
    (INJECTION_SESSION_START_REMINDER_TITLE, *INJECTION_SESSION_START_REMINDER_LINES)
)
