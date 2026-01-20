#!/bin/bash
# Install OAK Codebase Intelligence MCP server for Gemini CLI
#
# Environment variables (set by OAK):
#   OAK_PROJECT_ROOT  - Project root directory
#   OAK_MCP_NAME      - Server name (e.g., "oak-ci")
#   OAK_MCP_COMMAND   - Full command to run the MCP server
#
# Gemini CLI MCP registration:
#   gemini mcp add [options] <name> <commandOrUrl> [args...]
#
# See: https://github.com/google-gemini/gemini-cli

set -e

# Validate environment
if [ -z "$OAK_PROJECT_ROOT" ] || [ -z "$OAK_MCP_NAME" ] || [ -z "$OAK_MCP_COMMAND" ]; then
    echo "Error: Required environment variables not set" >&2
    echo "  OAK_PROJECT_ROOT=$OAK_PROJECT_ROOT" >&2
    echo "  OAK_MCP_NAME=$OAK_MCP_NAME" >&2
    echo "  OAK_MCP_COMMAND=$OAK_MCP_COMMAND" >&2
    exit 1
fi

# Check if gemini CLI is available
if ! command -v gemini &> /dev/null; then
    echo "Warning: gemini CLI not found, skipping MCP registration" >&2
    echo "Install Gemini CLI to enable MCP: https://github.com/google-gemini/gemini-cli" >&2
    exit 0
fi

# Change to project directory (gemini mcp add uses current directory for project scope)
cd "$OAK_PROJECT_ROOT"

# Remove existing registration if present (idempotent)
gemini mcp remove --scope project "$OAK_MCP_NAME" 2>/dev/null || true

# Register the MCP server with project scope
# Note: We use --scope project so it's only available in this project
# Format: gemini mcp add [options] <name> <commandOrUrl> [args...]
echo "Registering MCP server '$OAK_MCP_NAME' for Gemini CLI..."
gemini mcp add --scope project "$OAK_MCP_NAME" $OAK_MCP_COMMAND

# Clean up .orig backup files created by gemini CLI
# The gemini CLI creates .orig backups when modifying settings.json
rm -f "$OAK_PROJECT_ROOT/.gemini/settings.json.orig" 2>/dev/null || true

echo "MCP server registered successfully"
echo "  Name: $OAK_MCP_NAME"
echo "  Scope: project"
echo "  Command: $OAK_MCP_COMMAND"
