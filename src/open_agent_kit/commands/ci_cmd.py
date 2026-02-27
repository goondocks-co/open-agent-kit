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
- ci.cloud: Cloud relay (cloud-init, cloud-connect, cloud-disconnect, cloud-status, cloud-url)
- ci.team: Team sync (team join, team leave, team status, team members, team serve, team key)
"""

from open_agent_kit.commands.ci import (
    ci_app,
    cloud,
    config,
    daemon,
    data,
    dev,
    hooks,
    index,
    mcp,
    notify,
    query,
    search,
    sync,
    team,
)

# Re-export for backwards compatibility and explicit reference
__all__ = [
    "ci_app",
    "cloud",
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
    "notify",
    "team",
]
