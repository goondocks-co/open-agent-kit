#!/bin/bash
# Remove OAK Codebase Intelligence MCP server from Cursor
#
# Environment variables (set by OAK):
#   OAK_PROJECT_ROOT  - Project root directory
#   OAK_MCP_NAME      - Server name (e.g., "oak-ci")

set -e

# Validate environment
if [ -z "$OAK_PROJECT_ROOT" ] || [ -z "$OAK_MCP_NAME" ]; then
    echo "Error: Required environment variables not set" >&2
    exit 1
fi

MCP_CONFIG="$OAK_PROJECT_ROOT/.cursor/mcp.json"

# Check if config exists
if [ ! -f "$MCP_CONFIG" ]; then
    echo "No Cursor MCP config found, nothing to remove"
    exit 0
fi

# Use Python for reliable JSON manipulation
python3 << PYEOF
import json
import os
from pathlib import Path

project_root = os.environ["OAK_PROJECT_ROOT"]
server_name = os.environ["OAK_MCP_NAME"]

config_path = Path(project_root) / ".cursor" / "mcp.json"

if not config_path.exists():
    print("No Cursor MCP config found")
    exit(0)

with open(config_path) as f:
    config = json.load(f)

if "mcpServers" not in config or server_name not in config["mcpServers"]:
    print(f"MCP server '{server_name}' was not registered")
    exit(0)

# Remove our server
del config["mcpServers"][server_name]

# Clean up empty mcpServers
if not config["mcpServers"]:
    del config["mcpServers"]

# Write updated config or remove if empty
if config:
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"MCP server '{server_name}' removed from {config_path}")
else:
    config_path.unlink()
    print(f"Removed empty config file: {config_path}")
    # Remove .cursor dir if empty
    cursor_dir = config_path.parent
    if cursor_dir.exists() and not any(cursor_dir.iterdir()):
        cursor_dir.rmdir()
        print(f"Removed empty directory: {cursor_dir}")
PYEOF

echo "Cursor MCP server removed"
