#!/bin/bash
# Install OAK Codebase Intelligence MCP server for OpenCode
#
# Environment variables (set by OAK):
#   OAK_PROJECT_ROOT  - Project root directory
#   OAK_MCP_NAME      - Server name (e.g., "oak-ci")
#   OAK_MCP_COMMAND   - Full command to run the MCP server
#
# OpenCode MCP configuration:
#   Stored in opencode.json at project root
#   See: https://opencode.ai/docs/mcp-servers/
#
# Format (different from other agents - uses "mcp" key, not "mcpServers"):
# {
#   "mcp": {
#     "server-name": {
#       "type": "local",
#       "command": ["cmd", "arg1", "arg2"]
#     }
#   }
# }

set -e

# Validate environment
if [ -z "$OAK_PROJECT_ROOT" ] || [ -z "$OAK_MCP_NAME" ] || [ -z "$OAK_MCP_COMMAND" ]; then
    echo "Error: Required environment variables not set" >&2
    exit 1
fi

MCP_CONFIG="$OAK_PROJECT_ROOT/opencode.json"

# Use Python for reliable JSON manipulation (OAK requires Python anyway)
python3 << PYEOF
import json
import os
from pathlib import Path

project_root = os.environ["OAK_PROJECT_ROOT"]
server_name = os.environ["OAK_MCP_NAME"]
command = os.environ["OAK_MCP_COMMAND"]

# Parse command into array format for OpenCode
# "uv run oak ci mcp --project /path" -> ["uv", "run", "oak", "ci", "mcp", "--project", "/path"]
parts = command.split()

config_path = Path(project_root) / "opencode.json"

# Load existing config or create new
if config_path.exists():
    with open(config_path) as f:
        config = json.load(f)
else:
    config = {}

# OpenCode uses "mcp" key (not "mcpServers")
if "mcp" not in config:
    config["mcp"] = {}

# Add/update our server with OpenCode's local server format
config["mcp"][server_name] = {
    "type": "local",
    "command": parts
}

# Write updated config
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"MCP server registered successfully")
print(f"  Config: {config_path}")
print(f"  Name: {server_name}")
print(f"  Command: {parts}")
PYEOF

echo "OpenCode MCP configuration updated"
