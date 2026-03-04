"""Hook event, field, deduplication, and truncation constants."""

from typing import Final

# =============================================================================
# Session and Hook Events
# =============================================================================

HOOK_EVENT_SESSION_START: Final[str] = "session-start"
HOOK_EVENT_SESSION_END: Final[str] = "session-end"
HOOK_EVENT_POST_TOOL_USE: Final[str] = "post-tool-use"
HOOK_EVENT_POST_TOOL_USE_FAILURE: Final[str] = "post-tool-use-failure"
HOOK_EVENT_BEFORE_PROMPT: Final[str] = "before-prompt"
HOOK_EVENT_STOP: Final[str] = "stop"
HOOK_EVENT_PROMPT_SUBMIT: Final[str] = "prompt-submit"
HOOK_EVENT_SUBAGENT_START: Final[str] = "subagent-start"
HOOK_EVENT_SUBAGENT_STOP: Final[str] = "subagent-stop"
HOOK_EVENT_AGENT_THOUGHT: Final[str] = "agent-thought"
HOOK_EVENT_PRE_COMPACT: Final[str] = "pre-compact"
HOOK_EVENT_PRE_TOOL_USE: Final[str] = "pre-tool-use"

# Hook origins for deduplication when multiple configs fire
HOOK_ORIGIN_CLAUDE_CONFIG: Final[str] = "claude_config"
HOOK_ORIGIN_CURSOR_CONFIG: Final[str] = "cursor_config"

# Hook payload field names
HOOK_FIELD_SESSION_ID: Final[str] = "session_id"
HOOK_FIELD_CONVERSATION_ID: Final[str] = "conversation_id"
HOOK_FIELD_AGENT: Final[str] = "agent"
HOOK_FIELD_PROMPT: Final[str] = "prompt"
HOOK_FIELD_TOOL_NAME: Final[str] = "tool_name"
HOOK_FIELD_TOOL_INPUT: Final[str] = "tool_input"
HOOK_FIELD_TOOL_OUTPUT_B64: Final[str] = "tool_output_b64"
HOOK_FIELD_HOOK_ORIGIN: Final[str] = "hook_origin"
HOOK_FIELD_HOOK_EVENT_NAME: Final[str] = "hook_event_name"
HOOK_FIELD_GENERATION_ID: Final[str] = "generation_id"
HOOK_FIELD_TOOL_USE_ID: Final[str] = "tool_use_id"
HOOK_FIELD_ERROR_MESSAGE: Final[str] = "error_message"

# Stop hook fields (for transcript parsing)
HOOK_FIELD_TRANSCRIPT_PATH: Final[str] = "transcript_path"

# Subagent hook fields
HOOK_FIELD_AGENT_ID: Final[str] = "agent_id"
HOOK_FIELD_AGENT_TYPE: Final[str] = "agent_type"
HOOK_FIELD_AGENT_TRANSCRIPT_PATH: Final[str] = "agent_transcript_path"
HOOK_FIELD_STOP_HOOK_ACTIVE: Final[str] = "stop_hook_active"

# Hook deduplication configuration
HOOK_DEDUP_CACHE_MAX: Final[int] = 500
HOOK_DEDUP_HASH_ALGORITHM: Final[str] = "sha256"
HOOK_DROP_LOG_TAG: Final[str] = "[DROP]"

# Hook payload truncation limits (characters)
HOOK_TOOL_TRUNCATE_LENGTH: Final[int] = 500
HOOK_READ_TRUNCATE_LENGTH: Final[int] = 200

# Hook types
HOOK_TYPE_JSON: Final[str] = "json"
HOOK_TYPE_PLUGIN: Final[str] = "plugin"
HOOK_TYPE_OTEL: Final[str] = "otel"

# Hook stdin select timeout
HOOK_STDIN_TIMEOUT_SECONDS: Final[float] = 2.0
