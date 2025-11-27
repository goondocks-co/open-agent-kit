"""Pipeline stages for init/upgrade flows.

Each module in this package provides stages for a specific concern:
- setup: Directory creation, environment validation
- config: Configuration loading/creation
- agents: Agent command installation
- languages: Language parser installation
- skills: Skill installation for capable agents
- hooks: Lifecycle hook execution
- mcp: MCP server registration
- finalization: Migrations, version updates, cleanup
- upgrade: Upgrade-specific stages (command/template/skill upgrades)
"""

from open_agent_kit.pipeline.stages.agents import get_agent_stages
from open_agent_kit.pipeline.stages.config import get_config_stages
from open_agent_kit.pipeline.stages.finalization import get_finalization_stages
from open_agent_kit.pipeline.stages.hooks import get_hook_stages
from open_agent_kit.pipeline.stages.languages import get_language_stages
from open_agent_kit.pipeline.stages.mcp import get_mcp_stages
from open_agent_kit.pipeline.stages.setup import get_setup_stages
from open_agent_kit.pipeline.stages.skills import get_skill_stages
from open_agent_kit.pipeline.stages.upgrade import get_upgrade_stages

__all__ = [
    "get_setup_stages",
    "get_config_stages",
    "get_agent_stages",
    "get_language_stages",
    "get_skill_stages",
    "get_hook_stages",
    "get_mcp_stages",
    "get_finalization_stages",
    "get_upgrade_stages",
]
