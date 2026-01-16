#!/bin/bash
# Install OAK Codebase Intelligence MCP server for Claude Code
#
# Environment variables (set by OAK):
#   OAK_PROJECT_ROOT  - Project root directory
#   OAK_MCP_NAME      - Server name (e.g., "oak-ci")
#   OAK_MCP_COMMAND   - Full command to run the MCP server
#
# Claude Code MCP registration:
#   claude mcp add <name> --scope project -- <command> [args...]
#
# See: https://code.claude.com/docs/en/mcp#option-3%3A-add-a-local-stdio-server

set -e

# Validate environment
if [ -z "$OAK_PROJECT_ROOT" ] || [ -z "$OAK_MCP_NAME" ] || [ -z "$OAK_MCP_COMMAND" ]; then
    echo "Error: Required environment variables not set" >&2
    echo "  OAK_PROJECT_ROOT=$OAK_PROJECT_ROOT" >&2
    echo "  OAK_MCP_NAME=$OAK_MCP_NAME" >&2
    echo "  OAK_MCP_COMMAND=$OAK_MCP_COMMAND" >&2
    exit 1
fi

# Check if claude CLI is available
if ! command -v claude &> /dev/null; then
    echo "Warning: claude CLI not found, skipping MCP registration" >&2
    echo "Install Claude Code CLI to enable MCP: https://code.claude.com/docs/en/getting-started" >&2
    exit 0
fi

# Change to project directory (claude mcp add uses current directory for scope)
cd "$OAK_PROJECT_ROOT"

# Remove existing registration if present (idempotent)
claude mcp remove "$OAK_MCP_NAME" --scope project 2>/dev/null || true

# Register the MCP server
# Note: We use --scope project so it's only available in this project
echo "Registering MCP server '$OAK_MCP_NAME' for Claude Code..."
claude mcp add "$OAK_MCP_NAME" --scope project -- $OAK_MCP_COMMAND

echo "MCP server registered successfully"
echo "  Name: $OAK_MCP_NAME"
echo "  Scope: project"
echo "  Command: $OAK_MCP_COMMAND"
