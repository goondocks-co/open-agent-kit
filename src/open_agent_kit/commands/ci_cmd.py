"""CI CLI commands.

Commands are organized into submodules:
- ci.config: Configuration settings (config, exclude, debug)
- ci.index: Indexing and parsers (index, install-parsers, languages)
- ci.dev: Development tools (dev, port)
- ci.search: AI-facing search/remember/context
- ci.query: History queries (memories, sessions, test)
- ci.data: Backup and restore
- ci.sync: Code sync after upgrades
- ci.hooks: Hook event handling (hidden)

MCP integration has moved to ``oak team mcp``
(see ``open_agent_kit.commands.team.mcp``).

Daemon lifecycle, cloud relay, and team member commands are now
under ``oak team`` (see ``open_agent_kit.commands.team``).
"""

from open_agent_kit.commands.ci import (
    ci_app,
    config,
    data,
    dev,
    hooks,
    index,
    notify,
    query,
    search,
    sync,
)

# Re-export for backwards compatibility and explicit reference
__all__ = [
    "ci_app",
    "config",
    "index",
    "dev",
    "search",
    "query",
    "data",
    "sync",
    "hooks",
    "notify",
]
