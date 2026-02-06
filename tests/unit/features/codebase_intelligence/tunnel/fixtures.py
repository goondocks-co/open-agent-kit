"""Test fixtures for tunnel providers and routes."""

from open_agent_kit.features.codebase_intelligence.constants import (
    TUNNEL_PROVIDER_CLOUDFLARED,
    TUNNEL_PROVIDER_NGROK,
)

TEST_PORT = 8080
TEST_TIMEOUT_SECONDS = 0.1
TEST_RETURN_CODE = 1

# Providers
TEST_PROVIDER_CLOUDFLARED = TUNNEL_PROVIDER_CLOUDFLARED
TEST_PROVIDER_NGROK = TUNNEL_PROVIDER_NGROK
TEST_PROVIDER_FAKE = "fake"
TEST_PROVIDER_UNKNOWN = "unknown-provider"

# URLs
TEST_URL_CLOUDFLARE = "https://test.trycloudflare.com"
TEST_URL_CLOUDFLARE_EXISTING = "https://existing.trycloudflare.com"
TEST_URL_CLOUDFLARE_ABC = "https://abc-xyz.trycloudflare.com"
TEST_URL_NGROK = "https://test.ngrok-free.app"
TEST_URL_NGROK_EXISTING = "https://existing.ngrok-free.app"
TEST_URL_NGROK_ABC = "https://abc123.ngrok-free.app"
TEST_URL_NGROK_TEST = "https://test123.ngrok-free.app"

# Timestamps
TEST_STARTED_AT = "2024-01-01T00:00:00Z"

# Binary paths
TEST_CLOUDFLARED_PATH = "/usr/local/bin/cloudflared"
TEST_CLOUDFLARED_CUSTOM_PATH = "/custom/cloudflared"
TEST_CLOUDFLARED_MISSING_PATH = "/nonexistent/cloudflared"
TEST_NGROK_PATH = "/usr/local/bin/ngrok"
TEST_NGROK_CUSTOM_PATH = "/custom/ngrok"
TEST_NGROK_MISSING_PATH = "/nonexistent/ngrok"

# Log lines
TEST_CLOUDFLARED_LOG_LINES = [
    b"2024-01-01 INFO Starting tunnel\n",
    b"2024-01-01 INFO +----------------------------+\n",
    b"2024-01-01 INFO | https://abc-xyz.trycloudflare.com |\n",
    b"2024-01-01 INFO +----------------------------+\n",
]

TEST_NGROK_START_LINE = b'{"lvl":"info","msg":"starting web service"}\n'
TEST_NGROK_INVALID_LINE = b"not json at all\n"
TEST_NGROK_ADDR_KEY = "addr"
TEST_NGROK_ADDR_VALUE = "http://localhost:8080"

# Misc
TEST_PROCESS_EXITED_MESSAGE = "Process exited"
TEST_ERROR_PERMISSION_DENIED = "Permission denied"
TEST_ERROR_NOT_FOUND = "not found"
TEST_ERROR_BINARY_NOT_FOUND = "Binary not found"
TEST_ERROR_GENERIC = "test error"
TEST_URL_FAKE = "https://fake.example.com"
