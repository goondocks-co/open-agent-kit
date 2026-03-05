"""Upgrade plan types and MCP configuration checker."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from open_agent_kit.models.agent_manifest import AgentManifest

from open_agent_kit.models.enums import HookType
from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.utils.naming import feature_name_to_dir as _feature_name_to_dir

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TypedDicts — upgrade plan items
# ---------------------------------------------------------------------------


class UpgradeCategoryResults(TypedDict):
    upgraded: list[str]
    failed: list[str]


class UpgradeResults(TypedDict):
    commands: UpgradeCategoryResults
    templates: UpgradeCategoryResults
    agent_settings: UpgradeCategoryResults
    migrations: UpgradeCategoryResults
    obsolete_removed: UpgradeCategoryResults
    legacy_commands_removed: UpgradeCategoryResults
    skills: UpgradeCategoryResults
    hooks: UpgradeCategoryResults
    mcp_servers: UpgradeCategoryResults
    gitignore: UpgradeCategoryResults
    structural_repairs: list[str]
    version_updated: bool


class UpgradePlanCommand(TypedDict):
    """A single command upgrade plan item."""

    agent: str
    command: str
    file: str
    package_path: Path
    installed_path: Path


class UpgradePlanMigration(TypedDict):
    """A single migration plan item."""

    id: str
    description: str


class UpgradePlanSkillItem(TypedDict):
    """A single skill plan item."""

    skill: str
    feature: str


class UpgradePlanObsoleteSkill(TypedDict):
    """An obsolete skill to be removed."""

    skill: str
    reason: str


class UpgradePlanSkills(TypedDict):
    """Skills upgrade plan."""

    install: list[UpgradePlanSkillItem]
    upgrade: list[UpgradePlanSkillItem]
    obsolete: list[UpgradePlanObsoleteSkill]


class UpgradePlanGitignoreItem(TypedDict):
    """A single gitignore entry to add."""

    feature: str
    entry: str


class UpgradePlanHookItem(TypedDict):
    """A single hook upgrade plan item."""

    feature: str
    agent: str
    source_path: Path
    target_description: str


class UpgradePlanNotificationItem(TypedDict):
    """A single notification upgrade plan item."""

    feature: str
    agent: str
    target_description: str


class UpgradePlanMcpItem(TypedDict):
    """A single MCP server plan item."""

    agent: str
    feature: str
    server_name: str


class UpgradePlanLegacyCommandItem(TypedDict):
    """A command file to remove for a skills-capable agent."""

    file: str
    path: Path


class UpgradePlanLegacyCommandsCleanup(TypedDict):
    """Legacy commands cleanup for a skills-capable agent."""

    agent: str
    commands: list[UpgradePlanLegacyCommandItem]


class UpgradePlan(TypedDict):
    """Structure returned by plan_upgrade()."""

    commands: list[UpgradePlanCommand]
    templates: list[str]
    templates_customized: bool
    obsolete_templates: list[str]
    agent_settings: list[str]
    skills: UpgradePlanSkills
    hooks: list[UpgradePlanHookItem]
    notifications: list[UpgradePlanNotificationItem]
    mcp_servers: list[UpgradePlanMcpItem]
    gitignore: list[UpgradePlanGitignoreItem]
    migrations: list[UpgradePlanMigration]
    structural_repairs: list[str]
    legacy_commands_cleanup: list[UpgradePlanLegacyCommandsCleanup]
    version_outdated: bool
    current_version: str
    package_version: str


# ---------------------------------------------------------------------------
# McpConfigChecker — MCP registration check helper
# ---------------------------------------------------------------------------


class McpConfigChecker:
    """Check whether MCP servers are already registered for an agent."""

    def __init__(self, project_root: Path, agent_service: AgentService):
        self._project_root = project_root
        self._agent_service = agent_service

    def agent_has_mcp(self, agent: str) -> bool:
        """Check if an agent manifest declares an MCP configuration section.

        Uses the manifest's ``mcp`` config section (structural check) rather
        than the user-overridable ``has_mcp`` capability flag.
        """
        try:
            manifest = self._agent_service.get_agent_manifest(agent)
            return manifest.mcp is not None
        except (ValueError, KeyError) as e:
            logger.debug(f"Skipping MCP planning for {agent}: {e}")
            return False

    def is_configured(self, agent: str, feature_name: str, package_features_dir: Path) -> bool:
        """Check if MCP server is already configured for an agent.

        Uses the agent's manifest.yaml to determine where MCP config is stored.
        """
        import json

        from open_agent_kit.models.agent_manifest import AgentManifest

        # Load MCP config to get server name
        mcp_config_path = (
            package_features_dir / _feature_name_to_dir(feature_name) / "mcp" / "mcp.yaml"
        )
        if not mcp_config_path.exists():
            return False

        try:
            import yaml

            with open(mcp_config_path) as f:
                mcp_config = yaml.safe_load(f)
            server_name = mcp_config.get("name", "oak-ci")
        except Exception:
            return False

        # Load agent manifest to get MCP config location
        try:
            agents_dir = Path(__file__).parent.parent / "agents"
            manifest = AgentManifest.load(agents_dir / agent / "manifest.yaml")
        except Exception:
            return False

        if not manifest.mcp:
            return False

        config_file = manifest.mcp.config_file
        servers_key = manifest.mcp.servers_key
        config_format = manifest.mcp.format or "json"

        config_path = self._project_root / config_file
        if not config_path.exists():
            return False

        try:
            if config_format == "toml":
                import tomllib

                with open(config_path, "rb") as f:
                    config = tomllib.load(f)
            else:
                with open(config_path) as f:
                    config = json.load(f)
            return server_name in config.get(servers_key, {})
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def get_hook_target_description(manifest: AgentManifest) -> str:
    """Derive a human-readable target path from the agent manifest.

    Args:
        manifest: AgentManifest with hooks configuration.

    Returns:
        Display string like ``.opencode/plugins/oak-ci.ts`` or
        ``.claude/settings.json``.
    """
    hooks = manifest.hooks
    folder = manifest.installation.folder.rstrip("/")

    if not hooks:
        return f"{folder}/hooks"

    if hooks.type == HookType.PLUGIN and hooks.plugin_dir and hooks.plugin_file:
        return f"{folder}/{hooks.plugin_dir}/{hooks.plugin_file}"
    elif hooks.type == HookType.OTEL:
        config_file = hooks.config_file or "config.toml"
        return f"{folder}/{config_file}"
    elif hooks.config_file:
        return f"{folder}/{hooks.config_file}"
    else:
        return f"{folder}/hooks"
