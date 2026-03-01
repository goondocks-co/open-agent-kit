"""Route modules for the Codebase Intelligence daemon.

This package contains the FastAPI routers split by domain:
- health: Health checks and status endpoints
- search: Search, fetch, remember, and context endpoints
- search_network: Federated network search via cloud relay
- index: Index build and status endpoints
- hooks: AI agent integration hooks (claude-mem inspired)
- otel: OpenTelemetry (OTLP) receiver for agents that emit OTel events
- notifications: Agent notify handlers for response summaries
- mcp: MCP tool endpoints
- config: Core configuration CRUD and restart endpoints
- config_providers: Model discovery endpoints (embedding and summarization)
- config_test: Configuration test and context discovery endpoints
- config_exclusions: Exclusion pattern management endpoints
- activity: Core SQLite activity browsing endpoints (sessions, search, stats)
- activity_plans: Plan listing and refresh endpoints
- activity_processing: Reprocess memories and promote batches
- activity_sessions: Session lifecycle (lineage, linking, completion, summary)
- activity_relationships: Many-to-many session relationships
- activity_management: Delete endpoints for sessions, batches, activities
- devtools_processing: Observation reprocessing, summaries, session cleanup
- agents: Agent catalog (list, reload, create/copy tasks, run)
- agent_runs: Agent run lifecycle (list, get, cancel, delete)
- agent_settings: Agent provider settings (get/update settings, list models, test)
- schedules: Agent scheduling (CRUD, manual trigger, sync)
- backup: Database backup and restore endpoints
- team: Team management API routes for the dashboard UI
- ui: Web dashboard
"""

from open_agent_kit.features.codebase_intelligence.daemon.routes.activity import (
    router as activity_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.activity_management import (
    router as activity_management_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.activity_plans import (
    router as activity_plans_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.activity_processing import (
    router as activity_processing_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.activity_relationships import (
    router as activity_relationships_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.activity_sessions import (
    router as activity_sessions_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.agent_runs import (
    router as agent_runs_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.agent_settings import (
    router as agent_settings_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.backup import (
    router as backup_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.config import (
    router as config_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.config_exclusions import (
    router as config_exclusions_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.config_providers import (
    router as config_providers_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.config_test import (
    router as config_test_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.devtools_processing import (
    router as devtools_processing_router,
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
from open_agent_kit.features.codebase_intelligence.daemon.routes.search_network import (
    router as search_network_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.team import (
    router as team_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.ui import router as ui_router

__all__ = [
    "activity_router",
    "activity_management_router",
    "activity_plans_router",
    "activity_processing_router",
    "activity_relationships_router",
    "activity_sessions_router",
    "agent_runs_router",
    "agent_settings_router",
    "backup_router",
    "devtools_processing_router",
    "health_router",
    "search_router",
    "search_network_router",
    "index_router",
    "hook_router",
    "notifications_router",
    "otel_router",
    "mcp_router",
    "config_router",
    "config_exclusions_router",
    "config_providers_router",
    "config_test_router",
    "team_router",
    "ui_router",
]
