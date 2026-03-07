"""Configuration I/O and classification for Team.

Contains load_ci_config, save_ci_config, the user-config overlay system,
DEFAULT_EXCLUDE_PATTERNS, and related helpers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.team.constants import (
    AUTO_RESOLVE_CONFIG_KEY,
    BACKUP_CONFIG_KEY,
    CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN,
    CI_CONFIG_CLOUD_RELAY_KEY_TOKEN,
    CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME,
    CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL,
    CI_CONFIG_KEY_AGENTS,
    CI_CONFIG_KEY_CLI_COMMAND,
    CI_CONFIG_KEY_CLOUD_RELAY,
    CI_CONFIG_KEY_EMBEDDING,
    CI_CONFIG_KEY_EXCLUDE_PATTERNS,
    CI_CONFIG_KEY_GOVERNANCE,
    CI_CONFIG_KEY_LOG_LEVEL,
    CI_CONFIG_KEY_LOG_ROTATION,
    CI_CONFIG_KEY_SESSION_QUALITY,
    CI_CONFIG_KEY_SUMMARIZATION,
    CI_CONFIG_KEY_TEAM,
    CI_CONFIG_TEAM_KEY_API_KEY,
    CI_CONFIG_TEAM_KEY_AUTO_SYNC,
    CI_CONFIG_TEAM_KEY_KEEP_RELAY_ALIVE,
    CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL,
)
from open_agent_kit.features.team.exceptions import (
    ValidationError,
)
from open_agent_kit.models.agent_manifest import AgentManifest

if TYPE_CHECKING:
    from open_agent_kit.features.team.config.ci_config import CIConfig

logger = logging.getLogger(__name__)

# Package agents directory (where agent manifests are stored)
# Path: features/team/config/io.py -> config/ -> team/ -> features/ -> open_agent_kit/
_PACKAGE_ROOT = Path(__file__).parent.parent.parent.parent
_AGENTS_DIR = _PACKAGE_ROOT / "agents"


def _get_oak_managed_paths() -> list[str]:
    """Get paths managed by OAK from all agent manifests.

    Reads all agent manifests and collects OAK-managed paths (commands, skills,
    settings files) that should be excluded from code indexing.

    Returns:
        List of relative paths that OAK manages across all supported agents.
    """
    paths: set[str] = set()

    try:
        if not _AGENTS_DIR.exists():
            logger.debug(f"Agents directory not found: {_AGENTS_DIR}")
            return []

        for agent_dir in _AGENTS_DIR.iterdir():
            if not agent_dir.is_dir():
                continue

            manifest_path = agent_dir / "manifest.yaml"
            if not manifest_path.exists():
                continue

            try:
                manifest = AgentManifest.load(manifest_path)
                agent_paths = manifest.get_oak_managed_paths()
                paths.update(agent_paths)
                logger.debug(f"Agent {manifest.name} managed paths: {agent_paths}")
            except (OSError, ValueError, KeyError, AttributeError) as e:
                logger.warning(f"Failed to load manifest for {agent_dir.name}: {e}")

    except OSError as e:
        logger.warning(f"Error scanning agent manifests: {e}")

    return sorted(paths)


# OAK-managed paths derived from agent manifests
# These are directories/files that OAK installs (commands, skills, settings)
# User-generated files like AGENT.md and constitution are NOT excluded
_OAK_MANAGED_PATHS = _get_oak_managed_paths()


# Default patterns to exclude from indexing
DEFAULT_EXCLUDE_PATTERNS = [
    # Version control and tools
    ".git",
    ".git/**",
    ".oak",
    ".oak/**",
    # OAK-managed agent directories (derived from agent manifests)
    # Includes: commands, skills, settings files for all supported agents
    *_OAK_MANAGED_PATHS,
    # CI-managed hook configurations (installed by oak ci enable)
    # These contain generated hook scripts, not user code
    ".claude/settings.local.json",
    ".cursor/hooks.json",
    ".cursor/hooks",
    ".cursor/hooks/**",
    # Dependencies (match at any level for nested node_modules)
    "node_modules",
    "node_modules/**",
    "**/node_modules",
    "**/node_modules/**",
    # Python caches
    "__pycache__",
    "__pycache__/**",
    ".mypy_cache",
    ".mypy_cache/**",
    ".pytest_cache",
    ".pytest_cache/**",
    ".ruff_cache",
    ".ruff_cache/**",
    "htmlcov",
    "htmlcov/**",
    # Virtual environments
    ".venv",
    ".venv/**",
    "venv",
    "venv/**",
    # Environment and sensitive files (quiet exclusion)
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    # Build artifacts
    "*.pyc",
    "*.pyo",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "dist/**",
    "build/**",
    ".next/**",
    "coverage/**",
    "*.egg-info/**",
    # Localization/translation files (cause search pollution with repeated content)
    "translations/**",
    "locales/**",
    "locale/**",
    "i18n/**",
    "l10n/**",
    "*.po",
    "*.pot",
    "*.mo",
]


# =============================================================================
# User Config Overlay System (RFC-001 Section 6)
# =============================================================================

# Dot-path notation for config sections/keys classified as user-local.
# Bare names = entire section is user-classified.
# Dotted names = only that leaf key within a mixed section.
# Everything NOT listed here is project-classified (team-shared) by default.
USER_CLASSIFIED_PATHS: frozenset[str] = frozenset(
    {
        CI_CONFIG_KEY_EMBEDDING,  # Model choice + dims are machine-dependent; vector DB is local
        CI_CONFIG_KEY_SUMMARIZATION,  # LLM model availability varies per machine
        f"{CI_CONFIG_KEY_AGENTS}.provider_type",  # Agent LLM backend varies per machine
        f"{CI_CONFIG_KEY_AGENTS}.provider_base_url",  # Agent LLM backend varies per machine
        f"{CI_CONFIG_KEY_AGENTS}.provider_model",  # Agent LLM backend varies per machine
        CI_CONFIG_KEY_CLOUD_RELAY,  # Cloud relay config is machine-local (token, worker URL)
        f"{CI_CONFIG_KEY_TEAM}.{CI_CONFIG_TEAM_KEY_API_KEY}",  # Team API keys are machine-local secrets
        f"{CI_CONFIG_KEY_TEAM}.{CI_CONFIG_TEAM_KEY_AUTO_SYNC}",  # Depends on per-machine state
        f"{CI_CONFIG_KEY_TEAM}.{CI_CONFIG_TEAM_KEY_KEEP_RELAY_ALIVE}",  # Per-machine power preference
        CI_CONFIG_KEY_LOG_LEVEL,  # Personal debugging preference
        CI_CONFIG_KEY_LOG_ROTATION,  # Machine-local log management
        f"{BACKUP_CONFIG_KEY}.auto_enabled",  # Personal preference for auto-backup
        f"{BACKUP_CONFIG_KEY}.include_activities",  # Personal preference for backup scope
        f"{BACKUP_CONFIG_KEY}.interval_minutes",  # Personal preference for backup frequency
        f"{CI_CONFIG_KEY_GOVERNANCE}.enforcement_mode",  # Enforcement mode is machine-local
    }
)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay onto base. Overlay wins for scalars/lists.

    Args:
        base: Base dictionary (not mutated).
        overlay: Overlay dictionary whose values take precedence.

    Returns:
        New merged dictionary.
    """
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _split_by_classification(
    ci_dict: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a CI config dict into user-classified and project-classified parts.

    Uses USER_CLASSIFIED_PATHS to determine classification. Bare names
    (e.g. "embedding") classify the entire section. Dotted names
    (e.g. "agents.provider_type") classify only that leaf key within
    a mixed section.

    Args:
        ci_dict: Full team config dictionary.

    Returns:
        Tuple of (user_dict, project_dict) -- sparse dicts containing
        only the keys that belong to each classification.
    """
    user_dict: dict[str, Any] = {}
    project_dict: dict[str, Any] = {}

    for key, value in ci_dict.items():
        # Check if the entire section is user-classified
        if key in USER_CLASSIFIED_PATHS:
            user_dict[key] = value
            continue

        # Check if this section has mixed classification (dotted paths)
        dotted_prefix = f"{key}."
        dotted_keys = {
            p[len(dotted_prefix) :] for p in USER_CLASSIFIED_PATHS if p.startswith(dotted_prefix)
        }

        if dotted_keys and isinstance(value, dict):
            # Split the section: user-classified leaves vs project-classified leaves
            user_sub: dict[str, Any] = {}
            project_sub: dict[str, Any] = {}
            for sub_key, sub_value in value.items():
                if sub_key in dotted_keys:
                    user_sub[sub_key] = sub_value
                else:
                    project_sub[sub_key] = sub_value
            if user_sub:
                user_dict[key] = user_sub
            if project_sub:
                project_dict[key] = project_sub
        else:
            # Entirely project-classified
            project_dict[key] = value

    return user_dict, project_dict


def _scrub_dead_keys(ci_dict: dict[str, Any]) -> None:
    """Remove known dead/inert config keys from a CI config dict **in place**.

    These keys were once stored but are no longer read by any code path.
    Removing them on save keeps .oak/config.yaml clean and avoids user confusion.
    """
    # Top-level dead keys
    for key in ("tunnel", "index_on_startup", "watch_files"):
        ci_dict.pop(key, None)

    # embedding.fallback_enabled
    emb = ci_dict.get("embedding")
    if isinstance(emb, dict):
        emb.pop("fallback_enabled", None)

    # Dead team sub-keys
    team = ci_dict.get("team")
    if isinstance(team, dict):
        for key in (
            "pull_interval_seconds",
            "transport",
            "bind_host",
            "bind_port",
            "server_side_llm",
            "server_url",  # replaced by cloud_relay.worker_url / team.relay_worker_url
        ):
            team.pop(key, None)

    # Dead governance.data_collection sub-keys
    gov = ci_dict.get("governance")
    if isinstance(gov, dict):
        dc = gov.get("data_collection")
        if isinstance(dc, dict):
            for key in (
                "collect_activities",
                "collect_prompts",
                "sync_activities",
                "sync_prompts",
                "allow_server_llm",
            ):
                dc.pop(key, None)


def _scrub_user_keys_from_project(ci_dict: dict[str, Any]) -> None:
    """Remove user-classified sub-keys from a project config dict **in place**.

    After reclassifying fields (e.g. moving ``team.auto_sync`` from
    project to user), stale values linger in the shared config because
    ``_deep_merge`` only adds/overwrites. This function removes them.

    Only scrubs **dotted paths** (sub-keys within mixed sections). Entire
    user-classified sections (bare names like ``embedding``) are left
    alone — they may contain team defaults set via ``force_project``.
    """
    for path in USER_CLASSIFIED_PATHS:
        if "." not in path:
            # Entire section — leave it; may hold team defaults
            continue
        section, leaf = path.split(".", 1)
        sub = ci_dict.get(section)
        if isinstance(sub, dict):
            sub.pop(leaf, None)


def _normalize_relay_urls(ci_dict: dict[str, Any]) -> None:
    """Rewrite relay URLs to use custom domain when available **in place**.

    When ``cloud_relay.custom_domain`` and ``cloud_relay.worker_name`` are
    both set, the canonical URL is ``https://{worker_name}.{custom_domain}``.
    Updates ``cloud_relay.worker_url`` and ``team.relay_worker_url`` to match.
    """
    relay = ci_dict.get(CI_CONFIG_KEY_CLOUD_RELAY)
    if not isinstance(relay, dict):
        return

    custom_domain = relay.get(CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN)
    worker_name = relay.get(CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME)
    if not custom_domain or not worker_name:
        return

    canonical_url = f"https://{worker_name}.{custom_domain}"

    if relay.get(CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL):
        relay[CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL] = canonical_url

    team = ci_dict.get(CI_CONFIG_KEY_TEAM)
    if isinstance(team, dict):
        if team.get(CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL):
            team[CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL] = canonical_url


def _dedup_relay_credentials(ci_dict: dict[str, Any]) -> None:
    """Remove ``team.api_key`` when it duplicates ``cloud_relay.token``.

    On publisher nodes the deploy flow historically wrote the relay token
    to both locations.  Only ``cloud_relay.token`` is the source of truth;
    ``team.api_key`` is kept only for consumer nodes that don't have
    ``cloud_relay.token``.
    """
    relay = ci_dict.get(CI_CONFIG_KEY_CLOUD_RELAY)
    if not isinstance(relay, dict):
        return
    team = ci_dict.get(CI_CONFIG_KEY_TEAM)
    if not isinstance(team, dict):
        return
    relay_token = relay.get(CI_CONFIG_CLOUD_RELAY_KEY_TOKEN)
    if relay_token and team.get(CI_CONFIG_TEAM_KEY_API_KEY) == relay_token:
        team.pop(CI_CONFIG_TEAM_KEY_API_KEY, None)


def _user_config_path(project_root: Path) -> Path:
    """Get path to user config overlay file.

    Returns .oak/config.{machine_id}.yaml. The machine_id is imported
    lazily from the backup module.

    Args:
        project_root: Project root directory.

    Returns:
        Path to user config overlay file.
    """
    from open_agent_kit.features.team.activity.store.backup import (
        get_machine_identifier,
    )

    machine_id = get_machine_identifier(project_root)
    return project_root / OAK_DIR / f"config.{machine_id}.yaml"


def _write_yaml_config(path: Path, data: dict[str, Any]) -> None:
    """Write a dictionary to a YAML config file with inline short-list formatting.

    Args:
        path: File path to write.
        data: Dictionary to serialize.
    """

    class InlineListDumper(yaml.SafeDumper):
        pass

    def represent_list(dumper: yaml.SafeDumper, items: list[Any]) -> yaml.nodes.Node:
        # Keep short lists (<=3 items) inline, longer ones multi-line
        if len(items) <= 3:
            return dumper.represent_sequence("tag:yaml.org,2002:seq", items, flow_style=True)
        return dumper.represent_sequence("tag:yaml.org,2002:seq", items, flow_style=False)

    InlineListDumper.add_representer(list, represent_list)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            Dumper=InlineListDumper,
            default_flow_style=False,
            sort_keys=False,
        )


def load_ci_config(project_root: Path) -> CIConfig:
    """Load Team configuration from project.

    Reads from .oak/config.yaml under the 'team' key.

    Args:
        project_root: Project root directory.

    Returns:
        CIConfig with settings (defaults if not configured).

    Note:
        Returns defaults on error rather than raising, to allow daemon
        to start even with invalid config.
    """
    from open_agent_kit.features.team.config.ci_config import CIConfig

    config_file = project_root / OAK_DIR / "config.yaml"

    if not config_file.exists():
        logger.debug(f"No config file at {config_file}, using defaults")
        return CIConfig()

    try:
        with open(config_file, encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        ci_data = config_data.get("team") or config_data.get("codebase_intelligence", {})

        # Merge user overlay if it exists (user wins over project)
        user_file = _user_config_path(project_root)
        if user_file.exists():
            try:
                with open(user_file, encoding="utf-8") as f:
                    user_data = yaml.safe_load(f) or {}
                user_ci = user_data.get("team") or user_data.get("codebase_intelligence", {})
                if user_ci:
                    ci_data = _deep_merge(ci_data, user_ci)
                    logger.debug(f"Merged user config overlay from {user_file}")
            except (yaml.YAMLError, OSError) as e:
                logger.warning(f"Corrupted user config overlay {user_file}, ignoring: {e}")

        config = CIConfig.from_dict(ci_data)
        logger.debug(
            f"Loaded CI config: provider={config.embedding.provider}, "
            f"model={config.embedding.model}"
        )
        return config

    except ValidationError as e:
        logger.warning(f"Invalid CI config in {config_file}: {e}")
        logger.info("Using default configuration")
        return CIConfig()

    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse config YAML from {config_file}: {e}")
        return CIConfig()

    except OSError as e:
        logger.warning(f"Failed to read config from {config_file}: {e}")
        return CIConfig()


def save_ci_config(
    project_root: Path,
    config: CIConfig,
    *,
    force_project: bool = False,
) -> None:
    """Save Team configuration to project.

    By default, splits user-classified keys into a machine-local overlay
    file (.oak/config.{machine_id}.yaml) and writes project-classified
    keys to .oak/config.yaml.

    Args:
        project_root: Project root directory.
        config: Configuration to save.
        force_project: If True, write ALL settings to the project config
            (team-shared baseline). Does not touch user overlay.
    """
    config_file = project_root / OAK_DIR / "config.yaml"

    # Load existing project config (preserves non-CI keys)
    existing_config: dict[str, Any] = {}
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                existing_config = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            logger.warning(f"Failed to read existing config: {e}")

    ci_dict = config.to_dict()
    # Hard-scrub legacy team.token from project config output.
    team_dict = ci_dict.get(CI_CONFIG_KEY_TEAM)
    if isinstance(team_dict, dict):
        team_dict.pop("token", None)

    # Normalize relay URLs to use custom domain when available
    _normalize_relay_urls(ci_dict)
    # Remove team.api_key when it duplicates cloud_relay.token
    _dedup_relay_credentials(ci_dict)

    # Remove legacy "codebase_intelligence" key (renamed to "team")
    existing_config.pop("codebase_intelligence", None)

    # Scrub dead keys before any split so both user and project outputs
    # are clean.
    _scrub_dead_keys(ci_dict)

    if force_project:
        # Write everything to project config as team baseline
        existing_config["team"] = ci_dict
        _write_yaml_config(config_file, existing_config)
        logger.info(f"Saved full CI config to project file {config_file}")
    else:
        # Split user/project keys
        user_keys, project_keys = _split_by_classification(ci_dict)

        # Update project-classified keys in .oak/config.yaml while
        # preserving existing user-classified defaults for other machines
        existing_ci = existing_config.get("team", {})
        if isinstance(existing_ci, dict):
            existing_config["team"] = _deep_merge(existing_ci, project_keys)
        else:
            existing_config["team"] = project_keys
        existing_ci_section = existing_config.get("team")
        if isinstance(existing_ci_section, dict):
            # Remove user-classified keys that may have been written
            # before they were reclassified (e.g. team.auto_sync).
            _scrub_user_keys_from_project(existing_ci_section)
            _scrub_dead_keys(existing_ci_section)
            existing_team = existing_ci_section.get(CI_CONFIG_KEY_TEAM)
            if isinstance(existing_team, dict):
                existing_team.pop("token", None)
        _write_yaml_config(config_file, existing_config)

        # Write user keys to .oak/config.{machine_id}.yaml
        if user_keys:
            user_file = _user_config_path(project_root)
            # Preserve other top-level keys in user overlay
            existing_user: dict[str, Any] = {}
            if user_file.exists():
                try:
                    with open(user_file, encoding="utf-8") as f:
                        existing_user = yaml.safe_load(f) or {}
                except (OSError, yaml.YAMLError) as e:
                    logger.warning(f"Failed to read existing user config: {e}")
            existing_user.pop("codebase_intelligence", None)
            existing_user["team"] = user_keys
            _write_yaml_config(user_file, existing_user)
            logger.info(f"Saved user CI config to {user_file}")

        logger.info(f"Saved project CI config to {config_file}")


def get_config_origins(project_root: Path) -> dict[str, str]:
    """Compute the origin of each config section for dashboard display.

    For each top-level CI config section, returns whether its current
    value comes from the user overlay, the project config, or defaults.

    For mixed sections (like ``agents``), returns ``"user"`` if any
    user-classified sub-key is present in the user overlay.

    Args:
        project_root: Project root directory.

    Returns:
        Dict mapping section names to ``"user"``, ``"project"``, or ``"default"``.
    """
    config_file = project_root / OAK_DIR / "config.yaml"

    # Load raw project CI data (no merge)
    project_ci: dict[str, Any] = {}
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                project_data = yaml.safe_load(f) or {}
            project_ci = project_data.get("team", {})
        except (yaml.YAMLError, OSError):
            pass

    # Load raw user overlay CI data
    user_ci: dict[str, Any] = {}
    try:
        user_file = _user_config_path(project_root)
        if user_file.exists():
            with open(user_file, encoding="utf-8") as f:
                user_data = yaml.safe_load(f) or {}
            user_ci = user_data.get("team", {})
    except (yaml.YAMLError, OSError):
        pass

    # All top-level sections in CIConfig
    all_sections = [
        CI_CONFIG_KEY_EMBEDDING,
        CI_CONFIG_KEY_SUMMARIZATION,
        CI_CONFIG_KEY_AGENTS,
        CI_CONFIG_KEY_SESSION_QUALITY,
        CI_CONFIG_KEY_CLOUD_RELAY,
        BACKUP_CONFIG_KEY,
        AUTO_RESOLVE_CONFIG_KEY,
        CI_CONFIG_KEY_GOVERNANCE,
        CI_CONFIG_KEY_EXCLUDE_PATTERNS,
        CI_CONFIG_KEY_CLI_COMMAND,
        CI_CONFIG_KEY_LOG_LEVEL,
        CI_CONFIG_KEY_LOG_ROTATION,
    ]

    origins: dict[str, str] = {}
    for section in all_sections:
        # Check if any user-classified key for this section exists in user overlay
        if section in USER_CLASSIFIED_PATHS:
            # Entire section is user-classified
            if section in user_ci:
                origins[section] = "user"
            elif section in project_ci:
                origins[section] = "project"
            else:
                origins[section] = "default"
        else:
            # Check for dotted paths (mixed section like agents)
            dotted_prefix = f"{section}."
            user_sub_keys = {
                p[len(dotted_prefix) :]
                for p in USER_CLASSIFIED_PATHS
                if p.startswith(dotted_prefix)
            }
            if user_sub_keys:
                # Mixed section: "user" if any user-classified sub-key in overlay
                section_user_data = user_ci.get(section, {})
                if isinstance(section_user_data, dict) and any(
                    k in section_user_data for k in user_sub_keys
                ):
                    origins[section] = "user"
                elif section in project_ci:
                    origins[section] = "project"
                else:
                    origins[section] = "default"
            else:
                # Entirely project-classified
                if section in project_ci:
                    origins[section] = "project"
                else:
                    origins[section] = "default"

    return origins
