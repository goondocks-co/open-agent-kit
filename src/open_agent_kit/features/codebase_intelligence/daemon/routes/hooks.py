"""AI agent integration hooks for the CI daemon.

This module is now a thin router that mounts the lifecycle sub-routers.
All handler implementations live in their respective modules:

- ``hooks_common``    -- HookBody, parse_hook_body, handle_hook_errors, utilities
- ``hooks_session``   -- session-start, session-end
- ``hooks_prompt``    -- prompt-submit, before-prompt
- ``hooks_tool``      -- pre-tool-use, post-tool-use, post-tool-use-failure
- ``hooks_lifecycle`` -- stop, subagent-start/stop, agent-thought, pre-compact, catch-all
"""

from fastapi import APIRouter

from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_lifecycle import (
    router as lifecycle_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_prompt import (
    router as prompt_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_session import (
    router as session_router,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_tool import (
    router as tool_router,
)

router = APIRouter(tags=["hooks"])

# Include sub-routers in order. Specific routes (session, prompt, tool) go
# first; lifecycle router goes LAST because it contains the catch-all {event}
# route that would shadow specific routes if registered earlier.
router.include_router(session_router)
router.include_router(prompt_router)
router.include_router(tool_router)
router.include_router(lifecycle_router)
