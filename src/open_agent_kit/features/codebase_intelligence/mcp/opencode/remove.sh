#!/bin/bash
# Remove OAK Codebase Intelligence MCP server from OpenCode
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

MCP_CONFIG="$OAK_PROJECT_ROOT/opencode.json"

# Skip if no config file
if [ ! -f "$MCP_CONFIG" ]; then
    echo "No OpenCode config found, nothing to remove"
    exit 0
fi

# Use Python for reliable JSON manipulation
python3 << PYEOF
import json
import os
from pathlib import Path

project_root = os.environ["OAK_PROJECT_ROOT"]
server_name = os.environ["OAK_MCP_NAME"]

config_path = Path(project_root) / "opencode.json"

if not config_path.exists():
    print("No OpenCode config found")
    exit(0)

with open(config_path) as f:
    config = json.load(f)

# OpenCode uses "mcp" key (not "mcpServers")
if "mcp" not in config:
    print("No MCP servers configured")
    exit(0)

# Remove our server if it exists
if server_name in config["mcp"]:
    del config["mcp"][server_name]
    print(f"Removed MCP server: {server_name}")

    # Remove empty mcp section
    if not config["mcp"]:
        del config["mcp"]
        print("Removed empty mcp section")

    # If config is now empty, delete the file entirely
    if not config:
        config_path.unlink()
        print(f"Removed empty config file: {config_path}")
    else:
        # Write updated config
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
else:
    print(f"MCP server {server_name} not found")
PYEOF

echo "OpenCode MCP configuration updated"
