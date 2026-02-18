"""Test fixtures for cloud relay tests."""

from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
)

# Worker URLs
TEST_WORKER_URL = "https://oak-relay.example.workers.dev"
TEST_WORKER_URL_ALTERNATE = "https://relay-2.example.workers.dev"

# Tokens
TEST_RELAY_TOKEN = "test-relay-token-abc123"
TEST_AGENT_TOKEN = "test-agent-token-xyz789"

# Timestamps (ISO 8601)
TEST_TIMESTAMP = "2024-06-15T12:00:00+00:00"
TEST_CONNECTED_AT = "2024-06-15T11:30:00+00:00"
TEST_HEARTBEAT_AT = "2024-06-15T11:59:30+00:00"

# Tool call data
TEST_CALL_ID = "call-abc-123"
TEST_TOOL_NAME = "oak_search"
TEST_TOOL_ARGUMENTS = {"query": "authentication middleware", "limit": 10}
TEST_TOOL_RESULT = {"matches": [{"file": "auth.py", "score": 0.95}]}
TEST_TOOL_ERROR = "tool execution failed: timeout"

# Daemon port
TEST_DAEMON_PORT = 9742

# Error messages
TEST_ERROR_AUTH_FAILED = "authentication failed"
TEST_ERROR_INSTANCE_OFFLINE = "instance offline"

# Timeouts
TEST_TIMEOUT_MS = CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS * 1000
