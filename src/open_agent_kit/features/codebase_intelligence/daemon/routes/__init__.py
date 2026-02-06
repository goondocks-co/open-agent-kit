"""Route modules for the Codebase Intelligence daemon.

This package contains the FastAPI routers split by domain:
- health: Health checks and status endpoints
- search: Search, fetch, remember, and context endpoints
- index: Index build and status endpoints
- hooks: AI agent integration hooks (claude-mem inspired)
- otel: OpenTelemetry (OTLP) receiver for agents that emit OTel events
- notifications: Agent notify handlers for response summaries
- mcp: MCP tool endpoints
- config: Configuration management endpoints
- activity: Core SQLite activity browsing endpoints (plans, sessions, search, stats)
- activity_sessions: Session lifecycle (lineage, linking, completion, summary)
- activity_relationships: Many-to-many session relationships
- activity_management: Delete endpoints for sessions, batches, activities
- backup: Database backup and restore endpoints
- ui: Web dashboard
"""

from open_agent_kit.features.codebase_intelligence.daemon.routes.activity import (
    router as activity_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.activity_management import (
    router as activity_management_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.activity_relationships import (
    router as activity_relationships_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.activity_sessions import (
    router as activity_sessions_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.backup import (
    router as backup_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.config import (
    router as config_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.health import (
    router as health_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks import router as hook_router
from open_agent_kit.features.codebase_intelligence.daemon.routes.index import router as index_router
from open_agent_kit.features.codebase_intelligence.daemon.routes.mcp import router as mcp_router
from open_agent_kit.features.codebase_intelligence.daemon.routes.notifications import (
    router as notifications_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.otel import router as otel_router
from open_agent_kit.features.codebase_intelligence.daemon.routes.search import (
    router as search_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.ui import router as ui_router

__all__ = [
    "activity_router",
    "activity_management_router",
    "activity_relationships_router",
    "activity_sessions_router",
    "backup_router",
    "health_router",
    "search_router",
    "index_router",
    "hook_router",
    "notifications_router",
    "otel_router",
    "mcp_router",
    "config_router",
    "ui_router",
]
