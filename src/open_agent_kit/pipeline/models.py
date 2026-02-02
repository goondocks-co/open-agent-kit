"""Typed models for pipeline stages and results.

This module provides type-safe dataclasses for pipeline stage results,
ensuring consistent data structures and enabling IDE autocompletion.

The module is organized as follows:
1. Generic Result Types - Reusable patterns for common result structures
2. Stage Result TypedDicts - Type definitions for each major stage category
3. Stage Result Registry - Mapping of stage names to their result types
4. Collected Results - Aggregation structures for post-execution processing
"""

from dataclasses import dataclass, field
from typing import Any, ClassVar, TypedDict

# =============================================================================
# Generic Result Types
# =============================================================================


class CategoryResult(TypedDict):
    """Result for a category with upgraded and failed items."""

    upgraded: list[str]
    failed: list[str]


@dataclass
class ProcessingResult:
    """Result of processing multiple items with success/failure tracking.

    Use this for any stage that processes a list of items and needs
    to track which succeeded and which failed.
    """

    succeeded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        """Number of successfully processed items."""
        return len(self.succeeded)

    @property
    def failure_count(self) -> int:
        """Number of failed items."""
        return len(self.failed)

    @property
    def has_failures(self) -> bool:
        """Whether any items failed."""
        return len(self.failed) > 0

    def to_dict(self) -> CategoryResult:
        """Convert to CategoryResult TypedDict."""
        return {"upgraded": self.succeeded, "failed": self.failed}


# =============================================================================
# Upgrade Plan Utilities
# =============================================================================


# Keys in an upgrade plan that indicate work to be done
UPGRADE_PLAN_KEYS: tuple[str, ...] = (
    "commands",
    "templates",
    "obsolete_templates",
    "agent_settings",
    "hooks",
    "mcp_servers",
    "gitignore",
    "migrations",
    "structural_repairs",
    "version_outdated",
)


def plan_has_upgrades(plan: dict[str, Any]) -> bool:
    """Check if an upgrade plan has any work to do.

    This is a utility function to check if an UpgradePlan dictionary
    contains any items that need upgrading.

    Args:
        plan: An UpgradePlan dictionary from UpgradeService.plan_upgrade()

    Returns:
        True if any upgrades are needed, False otherwise

    Example:
        >>> plan = upgrade_service.plan_upgrade()
        >>> if plan_has_upgrades(plan):
        ...     upgrade_service.execute_upgrade(plan)
    """
    # Check standard plan keys
    if any(plan.get(key) for key in UPGRADE_PLAN_KEYS):
        return True

    # Check skills separately (nested structure)
    skill_plan = plan.get("skills", {})
    if skill_plan.get("install") or skill_plan.get("upgrade"):
        return True

    # Check agent_tasks separately (nested structure)
    agent_tasks_plan = plan.get("agent_tasks", {})
    if agent_tasks_plan.get("install") or agent_tasks_plan.get("upgrade"):
        return True

    return False


# =============================================================================
# Stage Result Types
# =============================================================================


class PlanUpgradeData(TypedDict):
    """Data returned by PlanUpgradeStage."""

    plan: dict[str, Any]  # UpgradePlan from upgrade_service
    has_upgrades: bool


class UpgradeStageData(TypedDict, total=False):
    """Data returned by individual upgrade stages."""

    upgraded: list[str]
    failed: list[str]
    removed: list[str]
    completed: list[str]
    repaired: list[str]
    error: str


class HookResultsData(TypedDict, total=False):
    """Data returned by hook trigger stages."""

    hook_results: dict[str, dict[str, Any]]
    error: str


class VersionUpdateData(TypedDict, total=False):
    """Data returned by version update stages."""

    version: str
    error: str


class ReconcileHooksData(TypedDict, total=False):
    """Data returned by hook reconciliation stages."""

    created: list[str]
    updated: list[str]
    message: str


class McpReconcileData(TypedDict, total=False):
    """Data returned by MCP server reconciliation stages."""

    installed: list[str]
    skipped: list[str]
    message: str


class SkillsReconcileData(TypedDict, total=False):
    """Data returned by skill reconciliation stages."""

    skills_added: list[str]
    total_skills: int
    agents: list[str]


class RemovalPlanData(TypedDict):
    """Data returned by PlanRemovalStage."""

    files_to_remove: list[tuple[str, str]]
    files_modified_by_user: list[tuple[str, str]]
    files_to_inform_user: list[tuple[str, str]]
    directories_to_check: list[str]
    installed_skills: list[str]
    has_user_content: bool


# =============================================================================
# Agent Configuration Stage Results
# =============================================================================


class LoadConfigData(TypedDict):
    """Data returned by LoadExistingConfigStage."""

    agents: list[str]
    features: list[str]
    version: str


class AgentCommandsData(TypedDict, total=False):
    """Data returned by agent command stages."""

    agents: list[str]
    features: list[str]
    removed_count: int
    removed: list[str]
    installed: list[str]


class AgentSettingsData(TypedDict, total=False):
    """Data returned by agent settings stages."""

    installed: list[str]
    removed: list[str]


# =============================================================================
# Skill Stages Results
# =============================================================================


class SkillCleanupData(TypedDict, total=False):
    """Data returned by CleanupAgentSkillsStage."""

    agents_cleaned: list[str]
    skills_removed: list[str]
    errors: list[str]


class SkillReconcileData(TypedDict):
    """Data returned by ReconcileSkillsStage."""

    skills_added: list[str]
    total_skills: int
    agents: list[str]


# =============================================================================
# Feature Setup Results
# =============================================================================


class FeatureInstallData(TypedDict, total=False):
    """Data returned by feature installation stages."""

    features: list[str]
    installed: list[str]
    skipped: list[str]
    errors: list[str]


class FeatureRemovalData(TypedDict, total=False):
    """Data returned by feature removal stages."""

    removed: list[str]
    failed: list[str]


# =============================================================================
# Hook and Event Results
# =============================================================================


class HookEventData(TypedDict, total=False):
    """Data returned by hook trigger stages."""

    hook_results: dict[str, dict[str, Any]]
    created: list[str]
    updated: list[str]
    message: str
    error: str


# =============================================================================
# MCP Server Results
# =============================================================================


class McpInstallData(TypedDict, total=False):
    """Data returned by MCP installation stages."""

    installed: list[str]
    skipped: list[str]
    failed: list[str]
    message: str


# =============================================================================
# Stage Result Type Registry
# =============================================================================


class StageResultRegistry:
    """Registry mapping stage names to their result types.

    This provides type information for stage results, allowing better IDE
    autocompletion and type checking when accessing results from context.

    The registry is organized by stage lifecycle and functional category.
    """

    # Configuration stages
    LOAD_EXISTING_CONFIG = "load_existing_config"
    CREATE_CONFIG = "create_config"
    MARK_MIGRATIONS_COMPLETE = "mark_migrations_complete"
    UPDATE_CONFIG_AGENTS = "update_config_agents"

    # Agent setup stages
    REMOVE_AGENT_COMMANDS = "remove_agent_commands"
    CLEANUP_OBSOLETE_COMMANDS = "cleanup_obsolete_commands"
    INSTALL_AGENT_COMMANDS = "install_agent_commands"
    REMOVE_AGENT_SETTINGS = "remove_agent_settings"
    INSTALL_AGENT_SETTINGS = "install_agent_settings"

    # Skill management stages
    CLEANUP_AGENT_SKILLS = "cleanup_agent_skills"
    RECONCILE_SKILLS = "reconcile_skills"

    # Hook and event stages
    RECONCILE_FEATURE_HOOKS = "reconcile_feature_hooks"
    TRIGGER_INIT_COMPLETE = "trigger_init_complete"

    # Upgrade planning stages
    VALIDATE_UPGRADE_ENVIRONMENT = "validate_upgrade_environment"
    PLAN_UPGRADE = "plan_upgrade"
    TRIGGER_PRE_UPGRADE_HOOKS = "trigger_pre_upgrade_hooks"

    # Upgrade execution stages
    UPGRADE_STRUCTURAL_REPAIRS = "upgrade_structural_repairs"
    UPGRADE_COMMANDS = "upgrade_commands"
    UPGRADE_TEMPLATES = "upgrade_templates"
    REMOVE_OBSOLETE_TEMPLATES = "remove_obsolete_templates"
    UPGRADE_AGENT_SETTINGS = "upgrade_agent_settings"
    UPGRADE_SKILLS = "upgrade_skills"
    UPGRADE_HOOKS = "upgrade_hooks"
    UPDATE_UPGRADE_VERSION = "update_upgrade_version"
    RUN_MIGRATIONS = "run_migrations"

    # MCP stages
    RECONCILE_MCP_SERVERS = "reconcile_mcp_servers"

    # Removal stages
    VALIDATE_REMOVAL = "validate_removal"
    PLAN_REMOVAL = "plan_removal"

    @classmethod
    def get_all_stages(cls) -> set[str]:
        """Get all registered stage names.

        Returns:
            Set of all stage identifiers in the registry
        """
        return {
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith("_") and attr.isupper()
        }

    @classmethod
    def get_stages_by_category(cls, category: str) -> set[str]:
        """Get stages in a specific category.

        Categories include: config, agents, skills, hooks, upgrade, mcp, removal

        Args:
            category: Category name (lowercase)

        Returns:
            Set of stage identifiers in the category
        """
        category_lower = category.lower()

        categories: dict[str, set[str]] = {
            "config": {
                cls.LOAD_EXISTING_CONFIG,
                cls.CREATE_CONFIG,
                cls.MARK_MIGRATIONS_COMPLETE,
                cls.UPDATE_CONFIG_AGENTS,
            },
            "agents": {
                cls.REMOVE_AGENT_COMMANDS,
                cls.CLEANUP_OBSOLETE_COMMANDS,
                cls.INSTALL_AGENT_COMMANDS,
                cls.REMOVE_AGENT_SETTINGS,
                cls.INSTALL_AGENT_SETTINGS,
            },
            "skills": {
                cls.CLEANUP_AGENT_SKILLS,
                cls.RECONCILE_SKILLS,
            },
            "hooks": {
                cls.RECONCILE_FEATURE_HOOKS,
                cls.TRIGGER_INIT_COMPLETE,
                cls.TRIGGER_PRE_UPGRADE_HOOKS,
            },
            "upgrade": {
                cls.VALIDATE_UPGRADE_ENVIRONMENT,
                cls.PLAN_UPGRADE,
                cls.UPGRADE_STRUCTURAL_REPAIRS,
                cls.UPGRADE_COMMANDS,
                cls.UPGRADE_TEMPLATES,
                cls.REMOVE_OBSOLETE_TEMPLATES,
                cls.UPGRADE_AGENT_SETTINGS,
                cls.UPGRADE_SKILLS,
                cls.UPGRADE_HOOKS,
                cls.UPDATE_UPGRADE_VERSION,
                cls.RUN_MIGRATIONS,
            },
            "mcp": {
                cls.RECONCILE_MCP_SERVERS,
            },
            "removal": {
                cls.VALIDATE_REMOVAL,
                cls.PLAN_REMOVAL,
            },
        }

        return categories.get(category_lower, set())


# =============================================================================
# Upgrade Results Collection
# =============================================================================


def _empty_category_result() -> CategoryResult:
    """Create an empty CategoryResult.

    This helper exists to provide proper type inference for mypy.
    Lambda expressions with empty lists result in `list[Never]` type.
    """
    return {"upgraded": [], "failed": []}


@dataclass
class CollectedUpgradeResults:
    """Collected results from all upgrade stages.

    This provides a type-safe structure for collecting results
    from multiple upgrade stages for post-upgrade hooks.
    """

    commands: CategoryResult = field(default_factory=_empty_category_result)
    templates: CategoryResult = field(default_factory=_empty_category_result)
    obsolete_removed: CategoryResult = field(default_factory=_empty_category_result)
    agent_settings: CategoryResult = field(default_factory=_empty_category_result)
    skills: CategoryResult = field(default_factory=_empty_category_result)
    hooks: CategoryResult = field(default_factory=_empty_category_result)
    gitignore: CategoryResult = field(default_factory=_empty_category_result)
    migrations: CategoryResult = field(default_factory=_empty_category_result)
    structural_repairs: list[str] = field(default_factory=list)
    version_updated: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for hook consumption."""
        return {
            "commands": self.commands,
            "templates": self.templates,
            "obsolete_removed": self.obsolete_removed,
            "agent_settings": self.agent_settings,
            "skills": self.skills,
            "hooks": self.hooks,
            "gitignore": self.gitignore,
            "migrations": self.migrations,
            "structural_repairs": self.structural_repairs,
            "version_updated": self.version_updated,
        }

    # Stage name to result attribute mapping (ClassVar to exclude from dataclass fields)
    _STAGE_MAPPINGS: ClassVar[dict[str, tuple[str, str, str]]] = {
        # stage_name: (result_attr, success_field, fail_field)
        "upgrade_commands": ("commands", "upgraded", "failed"),
        "upgrade_templates": ("templates", "upgraded", "failed"),
        "remove_obsolete_templates": ("obsolete_removed", "removed", "failed"),
        "upgrade_agent_settings": ("agent_settings", "upgraded", "failed"),
        "upgrade_skills": ("skills", "upgraded", "failed"),
        "upgrade_hooks": ("hooks", "upgraded", "failed"),
        "upgrade_gitignore": ("gitignore", "upgraded", "failed"),
        "run_migrations": ("migrations", "completed", "failed"),
    }

    @classmethod
    def from_context(cls, context: Any) -> "CollectedUpgradeResults":
        """Create from pipeline context by collecting stage results.

        Args:
            context: PipelineContext with stage_results

        Returns:
            CollectedUpgradeResults populated from context
        """
        results = cls()

        # Collect from standard stages
        for stage_name, (attr, success_field, fail_field) in cls._STAGE_MAPPINGS.items():
            stage_result = context.get_result(stage_name, {})
            if stage_result:
                category = getattr(results, attr)
                category["upgraded"] = stage_result.get(success_field, [])
                category["failed"] = stage_result.get(fail_field, [])

        # Handle special cases
        repair_result = context.get_result("upgrade_structural_repairs", {})
        if repair_result:
            results.structural_repairs = repair_result.get("repaired", [])

        version_result = context.get_result("update_upgrade_version", {})
        if version_result and version_result.get("version"):
            results.version_updated = True

        return results
