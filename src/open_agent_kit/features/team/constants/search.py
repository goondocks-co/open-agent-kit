"""Search type constants."""

from typing import Final

# =============================================================================
# Search Types
# =============================================================================

SEARCH_TYPE_ALL: Final[str] = "all"
SEARCH_TYPE_CODE: Final[str] = "code"
SEARCH_TYPE_MEMORY: Final[str] = "memory"
SEARCH_TYPE_PLANS: Final[str] = "plans"
SEARCH_TYPE_SESSIONS: Final[str] = "sessions"
VALID_SEARCH_TYPES: Final[tuple[str, ...]] = (
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
    SEARCH_TYPE_PLANS,
    SEARCH_TYPE_SESSIONS,
)

# =============================================================================
# Chunk Types
# =============================================================================

CHUNK_TYPE_FUNCTION: Final[str] = "function"
CHUNK_TYPE_CLASS: Final[str] = "class"
CHUNK_TYPE_METHOD: Final[str] = "method"
CHUNK_TYPE_MODULE: Final[str] = "module"
CHUNK_TYPE_UNKNOWN: Final[str] = "unknown"

# =============================================================================
# Memory Types
# =============================================================================
# NOTE: Memory types are now defined in schema.yaml (features/team/schema.yaml)
# and loaded dynamically. The MemoryType enum in daemon/models.py provides validation.
# See: open_agent_kit.features.team.activity.prompts.CISchema

# Special memory type for plans (indexed from prompt_batches, not memory_observations)
MEMORY_TYPE_PLAN: Final[str] = "plan"

# DEPRECATED: summaries now stored in sessions.summary column.
# Kept for backup compatibility (old backups may contain session_summary observations).
SESSION_SUMMARY_OBS_ID_PREFIX: Final[str] = "session_summary:"

# =============================================================================
# Memory Embedding Format
# =============================================================================

MEMORY_EMBED_LABEL_FILE: Final[str] = "file"
MEMORY_EMBED_LABEL_CONTEXT: Final[str] = "context"
MEMORY_EMBED_LABEL_SEPARATOR: Final[str] = ": "
MEMORY_EMBED_LABEL_TEMPLATE: Final[str] = "{label}{separator}{value}"
MEMORY_EMBED_LINE_SEPARATOR: Final[str] = "\n"

# =============================================================================
# Confidence Levels (model-agnostic)
# =============================================================================

# Confidence levels for search results.
# These are model-agnostic and based on relative positioning within
# a result set, not absolute similarity scores (which vary significantly
# across embedding models like nomic-embed-text vs bge-m3).
CONFIDENCE_HIGH: Final[str] = "high"
CONFIDENCE_MEDIUM: Final[str] = "medium"
CONFIDENCE_LOW: Final[str] = "low"
VALID_CONFIDENCE_LEVELS: Final[tuple[str, ...]] = (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
)

# Thresholds for confidence bands (based on normalized position in result set)
# These define what percentage of the score range qualifies for each level
CONFIDENCE_HIGH_THRESHOLD: Final[float] = 0.7  # Top 30% of score range
CONFIDENCE_MEDIUM_THRESHOLD: Final[float] = 0.4  # Top 60% of score range
# Minimum gap ratio to boost confidence (gap to next / total range)
CONFIDENCE_GAP_BOOST_THRESHOLD: Final[float] = 0.15
# Minimum score range to use range-based calculation (below this, use fallback)
CONFIDENCE_MIN_MEANINGFUL_RANGE: Final[float] = 0.001

# =============================================================================
# Importance Levels (for memory observations)
# =============================================================================
# Importance is stored on a 1-10 scale in SQLite/ChromaDB.
# These thresholds map the scale to high/medium/low categories.

IMPORTANCE_HIGH_THRESHOLD: Final[int] = 7  # >= 7 is high importance
IMPORTANCE_MEDIUM_THRESHOLD: Final[int] = 4  # >= 4 is medium importance
# Below 4 is low importance

# =============================================================================
# Combined Retrieval Scoring
# =============================================================================
# Weights for combining semantic confidence with importance in retrieval.
# combined_score = (confidence_weight * confidence) + (importance_weight * importance_normalized)

RETRIEVAL_CONFIDENCE_WEIGHT: Final[float] = 0.7
RETRIEVAL_IMPORTANCE_WEIGHT: Final[float] = 0.3

# Confidence score mapping for combined scoring (confidence level -> numeric score)
CONFIDENCE_SCORE_HIGH: Final[float] = 1.0
CONFIDENCE_SCORE_MEDIUM: Final[float] = 0.6
CONFIDENCE_SCORE_LOW: Final[float] = 0.3

# Tags for auto-captured observations
TAG_AUTO_CAPTURED: Final[str] = "auto-captured"
TAG_SESSION_SUMMARY: Final[str] = "session-summary"
