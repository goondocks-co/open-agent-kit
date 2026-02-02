"""Codebase Intelligence CLI commands.

Commands are organized into submodules:
- ci.daemon: Daemon lifecycle management (status, start, stop, restart, reset, logs)
- ci.config: Configuration settings (config, exclude, debug)
- ci.index: Indexing and parsers (index, install-parsers, languages)
- ci.dev: Development tools (dev, port)
- ci.mcp: MCP integration (mcp)
- ci.search: AI-facing search/remember/context
- ci.query: History queries (memories, sessions, test)
- ci.data: Backup and restore
- ci.sync: Code sync after upgrades
- ci.hooks: Hook event handling (hidden)
"""

from open_agent_kit.commands.ci import (
    ci_app,
    config,
    daemon,
    data,
    dev,
    hooks,
    index,
    mcp,
    query,
    search,
    sync,
)

# Re-export for backwards compatibility and explicit reference
__all__ = [
    "ci_app",
    "daemon",
    "config",
    "index",
    "dev",
    "mcp",
    "search",
    "query",
    "data",
    "sync",
    "hooks",
]
