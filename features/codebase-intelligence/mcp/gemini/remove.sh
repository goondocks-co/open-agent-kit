#!/bin/bash
# Remove OAK Codebase Intelligence MCP server from Gemini CLI
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

# Check if gemini CLI is available
if ! command -v gemini &> /dev/null; then
    echo "Warning: gemini CLI not found, skipping MCP removal" >&2
    exit 0
fi

# Change to project directory
cd "$OAK_PROJECT_ROOT"

# Remove the MCP server registration
# Format: gemini mcp remove [options] <name>
echo "Removing MCP server '$OAK_MCP_NAME' from Gemini CLI..."
if gemini mcp remove --scope project "$OAK_MCP_NAME" 2>/dev/null; then
    echo "MCP server removed successfully"
else
    echo "MCP server was not registered (nothing to remove)"
fi

# Clean up .orig backup files created by gemini CLI
rm -f "$OAK_PROJECT_ROOT/.gemini/settings.json.orig" 2>/dev/null || true
