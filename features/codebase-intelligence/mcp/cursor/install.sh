#!/bin/bash
# Install OAK Codebase Intelligence MCP server for Cursor
#
# Environment variables (set by OAK):
#   OAK_PROJECT_ROOT  - Project root directory
#   OAK_MCP_NAME      - Server name (e.g., "oak-ci")
#   OAK_MCP_COMMAND   - Full command to run the MCP server
#
# Cursor MCP configuration:
#   Stored in .cursor/mcp.json
#   See: https://cursor.com/docs/context/mcp
#
# Format:
# {
#   "mcpServers": {
#     "server-name": {
#       "command": "command",
#       "args": ["arg1", "arg2"]
#     }
#   }
# }

set -e

# Validate environment
if [ -z "$OAK_PROJECT_ROOT" ] || [ -z "$OAK_MCP_NAME" ] || [ -z "$OAK_MCP_COMMAND" ]; then
    echo "Error: Required environment variables not set" >&2
    exit 1
fi

MCP_CONFIG="$OAK_PROJECT_ROOT/.cursor/mcp.json"

# Use Python for reliable JSON manipulation (OAK requires Python anyway)
python3 << PYEOF
import json
import os
from pathlib import Path

project_root = os.environ["OAK_PROJECT_ROOT"]
server_name = os.environ["OAK_MCP_NAME"]
command = os.environ["OAK_MCP_COMMAND"]

# Parse command into command and args
# "uv run oak ci mcp --project /path" -> command="uv", args=["run", "oak", "ci", "mcp", "--project", "/path"]
parts = command.split()
cmd = parts[0] if parts else command
args = parts[1:] if len(parts) > 1 else []

config_path = Path(project_root) / ".cursor" / "mcp.json"
config_path.parent.mkdir(exist_ok=True)

# Load existing config or create new
if config_path.exists():
    with open(config_path) as f:
        config = json.load(f)
else:
    config = {}

if "mcpServers" not in config:
    config["mcpServers"] = {}

# Add/update our server
config["mcpServers"][server_name] = {
    "command": cmd,
    "args": args
}

# Write updated config
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"MCP server registered successfully")
print(f"  Config: {config_path}")
print(f"  Name: {server_name}")
print(f"  Command: {cmd} {' '.join(args)}")
PYEOF

echo "Cursor MCP configuration updated"
