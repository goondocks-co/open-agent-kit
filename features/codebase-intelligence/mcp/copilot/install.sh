#!/bin/bash
# Install OAK Codebase Intelligence MCP server for GitHub Copilot in VS Code
#
# Environment variables (set by OAK):
#   OAK_PROJECT_ROOT  - Project root directory
#   OAK_MCP_NAME      - Server name (e.g., "oak-ci")
#   OAK_MCP_COMMAND   - Full command to run the MCP server
#
# Copilot MCP configuration:
#   Stored in .vscode/mcp.json (project-scoped)
#   See: https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/extend-copilot-chat-with-mcp
#
# Format:
# {
#   "servers": {
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

MCP_CONFIG="$OAK_PROJECT_ROOT/.vscode/mcp.json"

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

config_path = Path(project_root) / ".vscode" / "mcp.json"
config_path.parent.mkdir(exist_ok=True)

# Load existing config or create new
if config_path.exists():
    with open(config_path) as f:
        config = json.load(f)
else:
    config = {}

# Copilot uses "servers" key (not "mcpServers" like Cursor)
if "servers" not in config:
    config["servers"] = {}

# Add/update our server
config["servers"][server_name] = {
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

echo "Copilot MCP configuration updated"
echo "Note: Restart VS Code or reload window for changes to take effect"
