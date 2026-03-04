"""OpenTelemetry (OTLP) and agent notification constants."""

from typing import Final

from open_agent_kit.features.team.constants.agents import AGENT_CODEX

# =============================================================================
# OpenTelemetry (OTLP) Configuration
# =============================================================================

# OTLP HTTP defaults
OTLP_LOGS_ENDPOINT: Final[str] = "/v1/logs"
OTLP_CONTENT_TYPE_PROTOBUF: Final[str] = "application/x-protobuf"
OTLP_CONTENT_TYPE_JSON: Final[str] = "application/json"

# HTTP constants
HTTP_HEADER_CONTENT_TYPE: Final[str] = "Content-Type"
HTTP_METHOD_POST: Final[str] = "POST"
ENCODING_UTF8: Final[str] = "utf-8"

# Environment variable for daemon port (used by OTEL agents like Codex)
# Agents can reference this in config files: ${OAK_CI_PORT}
OAK_CI_PORT_ENV_VAR: Final[str] = "OAK_CI_PORT"

# Codex OTel event names (from Codex telemetry docs)
OTEL_EVENT_CODEX_CONVERSATION_STARTS: Final[str] = "codex.conversation_starts"
OTEL_EVENT_CODEX_USER_PROMPT: Final[str] = "codex.user_prompt"
OTEL_EVENT_CODEX_TOOL_RESULT: Final[str] = "codex.tool_result"
OTEL_EVENT_CODEX_TOOL_DECISION: Final[str] = "codex.tool_decision"
OTEL_EVENT_CODEX_API_REQUEST: Final[str] = "codex.api_request"
OTEL_EVENT_CODEX_SSE_EVENT: Final[str] = "codex.sse_event"

# Codex notify events (agent notifications)
AGENT_NOTIFY_EVENT_TURN_COMPLETE: Final[str] = "agent-turn-complete"
AGENT_NOTIFY_ACTION_RESPONSE_SUMMARY: Final[str] = "response-summary"

# Notify payload fields
AGENT_NOTIFY_FIELD_TYPE: Final[str] = "type"
AGENT_NOTIFY_FIELD_THREAD_ID: Final[str] = "thread-id"
AGENT_NOTIFY_FIELD_TURN_ID: Final[str] = "turn-id"
AGENT_NOTIFY_FIELD_CWD: Final[str] = "cwd"
AGENT_NOTIFY_FIELD_INPUT_MESSAGES: Final[str] = "input-messages"
AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE: Final[str] = "last-assistant-message"
AGENT_NOTIFY_FIELD_AGENT: Final[str] = "agent"
AGENT_NOTIFY_PAYLOAD_DEFAULT: Final[str] = ""
AGENT_NOTIFY_PAYLOAD_JOIN_SEPARATOR: Final[str] = " "

# Notify installer configuration
AGENT_NOTIFY_CONFIG_TYPE: Final[str] = "notify"
AGENT_NOTIFY_CONFIG_KEY: Final[str] = "notify"
AGENT_NOTIFY_COMMAND_OAK: Final[str] = "oak"
AGENT_NOTIFY_DEFAULT_COMMAND: Final[str] = AGENT_NOTIFY_COMMAND_OAK
AGENT_NOTIFY_DEFAULT_ARGS: Final[tuple[str, ...]] = ("ci", "notify")
AGENT_NOTIFY_COMMAND_ARGS_CODEX: Final[tuple[str, ...]] = (
    "ci",
    "notify",
    "--agent",
    AGENT_CODEX,
)
AGENT_NOTIFY_ENDPOINT: Final[str] = "/api/oak/ci/notify"

# CI executable command configuration
CI_CONFIG_KEY_CLI_COMMAND: Final[str] = "cli_command"
CI_CLI_COMMAND_DEFAULT: Final[str] = AGENT_NOTIFY_COMMAND_OAK
CI_CLI_COMMAND_VALIDATION_PATTERN: Final[str] = r"^[A-Za-z0-9._/\-\\]+$"
CI_CLI_COMMAND_OAK_PREFIX: Final[str] = f"{AGENT_NOTIFY_COMMAND_OAK} "

# OTel attribute keys for data extraction (from Codex PR #2103)
OTEL_ATTR_CONVERSATION_ID: Final[str] = "conversation.id"
OTEL_ATTR_APP_VERSION: Final[str] = "app.version"
OTEL_ATTR_MODEL: Final[str] = "model"
OTEL_ATTR_TERMINAL_TYPE: Final[str] = "terminal.type"

# Tool-related attributes
OTEL_ATTR_TOOL_NAME: Final[str] = "tool_name"
OTEL_ATTR_TOOL_CALL_ID: Final[str] = "call_id"
OTEL_ATTR_TOOL_ARGUMENTS: Final[str] = "arguments"
OTEL_ATTR_TOOL_DURATION_MS: Final[str] = "duration_ms"
OTEL_ATTR_TOOL_SUCCESS: Final[str] = "success"
OTEL_ATTR_TOOL_OUTPUT: Final[str] = "output"

# Prompt-related attributes
OTEL_ATTR_PROMPT_LENGTH: Final[str] = "prompt_length"
OTEL_ATTR_PROMPT: Final[str] = "prompt"

# Decision-related attributes
OTEL_ATTR_DECISION: Final[str] = "decision"
OTEL_ATTR_DECISION_SOURCE: Final[str] = "source"

# Token metrics (from sse_event)
OTEL_ATTR_INPUT_TOKENS: Final[str] = "input_token_count"
OTEL_ATTR_OUTPUT_TOKENS: Final[str] = "output_token_count"
OTEL_ATTR_TOOL_TOKENS: Final[str] = "tool_token_count"
