"""Service for managing agent settings (command auto-approval).

This service handles agent-specific settings for command auto-approval.
Configuration is declared in agent manifests (agents/<agent>/manifest.yaml)
under the `settings.auto_approve` section:

```yaml
settings:
  auto_approve:
    enabled: true/false       # Whether OAK manages this agent's settings
    file: ".claude/settings.local.json"  # Settings file path
    format: json              # File format (json, toml)
    template: "agent-settings/claude-settings.json"  # Template in features/core/
```

Templates define WHAT settings to merge, manifests define WHERE they go.
"""

import copy
import json
import logging
from pathlib import Path
from typing import Any

from open_agent_kit.config.paths import FEATURES_DIR
from open_agent_kit.features.codebase_intelligence.cli_command import (
    render_cli_command_placeholder,
    resolve_ci_cli_command,
)
from open_agent_kit.models.agent_manifest import AgentManifest
from open_agent_kit.utils import (
    cleanup_empty_directories,
    ensure_dir,
    file_exists,
    read_file,
    write_file,
)

logger = logging.getLogger(__name__)

# Path to agent manifests in the package
# Path: services/agent_settings_service.py -> services/ -> open_agent_kit/
AGENTS_DIR = Path(__file__).parent.parent / "agents"


class AgentSettingsService:
    """Service for managing agent command auto-approval settings.

    This service handles agent-specific settings that control whether
    oak commands are auto-approved or require user confirmation.

    Configuration is read from agent manifests (declarative approach).
    Templates in features/core/agent-settings/ define the actual settings content.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize agent settings service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()

        # Package directories
        self.agents_dir = AGENTS_DIR
        # Path: services/agent_settings_service.py -> services/ -> open_agent_kit/
        self.core_dir = Path(__file__).parent.parent / FEATURES_DIR / "core"
        self.cli_command = resolve_ci_cli_command(self.project_root)

        # Cache for loaded manifests
        self._manifest_cache: dict[str, AgentManifest] = {}

    def _load_manifest(self, agent: str) -> AgentManifest | None:
        """Load agent manifest from package.

        Args:
            agent: Agent name

        Returns:
            AgentManifest instance, or None if not found
        """
        if agent in self._manifest_cache:
            return self._manifest_cache[agent]

        manifest_path = self.agents_dir / agent / "manifest.yaml"
        if not manifest_path.exists():
            logger.debug(f"No manifest found for agent: {agent}")
            return None

        try:
            manifest = AgentManifest.load(manifest_path)
            self._manifest_cache[agent] = manifest
            return manifest
        except (ValueError, OSError) as e:
            logger.warning(f"Failed to load manifest for {agent}: {e}")
            return None

    def _get_auto_approve_config(self, agent: str) -> dict[str, Any] | None:
        """Get auto-approval settings config from agent manifest.

        Args:
            agent: Agent name

        Returns:
            Auto-approve config dict, or None if not configured/disabled
        """
        manifest = self._load_manifest(agent)
        if not manifest:
            return None

        auto_approve: dict[str, Any] = manifest.settings.get("auto_approve", {})

        # Check if auto-approval is enabled for this agent
        if not auto_approve.get("enabled", False):
            logger.debug(f"Auto-approval not enabled for agent: {agent}")
            return None

        return auto_approve

    def get_settings_path(self, agent: str) -> Path | None:
        """Get path to the agent's settings file.

        Args:
            agent: Agent name

        Returns:
            Path to settings file or None if agent not supported
        """
        config = self._get_auto_approve_config(agent)
        if not config or not config.get("file"):
            return None

        file_path: str = config["file"]

        # Handle home directory expansion for global configs
        if file_path.startswith("~"):
            return Path(file_path).expanduser()

        return Path(self.project_root / file_path)

    def _load_template(self, agent: str) -> dict[str, Any] | None:
        """Load the template settings for an agent.

        Args:
            agent: Agent name

        Returns:
            Template settings dictionary, or None if not found
        """
        config = self._get_auto_approve_config(agent)
        if not config or not config.get("template"):
            return None

        template_path = self.core_dir / config["template"]
        if not template_path.exists():
            logger.warning(f"Template not found: {template_path}")
            return None

        try:
            content = read_file(template_path)
            content = render_cli_command_placeholder(content, self.cli_command)
            result: dict[str, Any] = json.loads(content)
            return result
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load template {template_path}: {e}")
            return None

    def _read_settings(self, settings_file: Path) -> dict[str, Any]:
        """Read and parse JSON settings file.

        Args:
            settings_file: Path to settings file

        Returns:
            Parsed settings dictionary, or empty dict if file doesn't exist
        """
        if not file_exists(settings_file):
            return {}
        try:
            content = read_file(settings_file)
            result: dict[str, Any] = json.loads(content)
            return result
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {settings_file}: {e}")
            return {}

    def _write_settings(self, settings_file: Path, settings: dict[str, Any]) -> None:
        """Write settings to JSON file with proper formatting.

        Args:
            settings_file: Path to settings file
            settings: Settings dictionary to write
        """
        ensure_dir(settings_file.parent)
        content = json.dumps(settings, indent=2, ensure_ascii=False)
        content += "\n"  # Trailing newline for better git diffs
        write_file(settings_file, content)

    def _merge_settings(self, existing: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
        """Merge template settings into existing settings.

        Recursively merges nested dictionaries and arrays.
        Template values are added if missing, but existing user values are preserved.

        Special handling:
        - For arrays (like permissions.allow), appends missing items
        - For dicts, recursively merges
        - Ignores $comment keys (template documentation)

        Args:
            existing: Existing settings dictionary
            template: Template settings to merge in

        Returns:
            Merged settings dictionary (deep copy, does not mutate existing)
        """
        # Use deepcopy to avoid mutating the original existing dict
        # (shallow copy would share nested lists/dicts, causing comparison bugs)
        result = copy.deepcopy(existing)

        for key, value in template.items():
            # Skip comment fields
            if key == "$comment":
                continue

            if key not in result:
                # Key doesn't exist - add it
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                # Both are dicts - merge recursively
                result[key] = self._merge_settings(result[key], value)
            elif isinstance(value, list) and isinstance(result[key], list):
                # Both are lists - append missing items
                for item in value:
                    if item not in result[key]:
                        result[key].append(item)
            # else: key exists and is not dict/list - keep existing value

        return result

    def _remove_oak_settings_from_dict(
        self,
        settings: dict[str, Any],
        template: dict[str, Any],
        path: str = "",
    ) -> tuple[dict[str, Any], bool]:
        """Remove OAK-managed settings from a settings dict.

        Args:
            settings: Current settings dictionary
            template: Template defining what to remove
            path: Current path for logging

        Returns:
            Tuple of (cleaned settings, was_modified)
        """
        result = settings.copy()
        modified = False

        for key, template_value in template.items():
            if key == "$comment":
                continue

            if key not in result:
                continue

            if isinstance(template_value, dict) and isinstance(result[key], dict):
                # Recursively remove from nested dict
                cleaned, nested_modified = self._remove_oak_settings_from_dict(
                    result[key], template_value, f"{path}.{key}"
                )
                if nested_modified:
                    if cleaned:
                        result[key] = cleaned
                    else:
                        del result[key]
                    modified = True
            elif isinstance(template_value, list) and isinstance(result[key], list):
                # Remove template items from list
                original_len = len(result[key])
                result[key] = [item for item in result[key] if item not in template_value]
                if len(result[key]) != original_len:
                    modified = True
                if not result[key]:
                    del result[key]
            else:
                # Simple value - remove if matches template
                if result[key] == template_value:
                    del result[key]
                    modified = True

        return result, modified

    def is_auto_approve_enabled(self, agent: str) -> bool:
        """Check if auto-approval is enabled for an agent.

        Args:
            agent: Agent name

        Returns:
            True if auto-approval is enabled and configured
        """
        config = self._get_auto_approve_config(agent)
        return config is not None

    def install_settings(self, agent: str, force: bool = False) -> bool:
        """Install OAK command auto-approval settings for an agent.

        Merges template settings with existing settings if file exists.

        Args:
            agent: Agent name
            force: If True, overwrite existing OAK settings

        Returns:
            True if settings were installed/updated, False otherwise
        """
        if not self.is_auto_approve_enabled(agent):
            logger.debug(f"Auto-approval not enabled for agent: {agent}")
            return False

        settings_file = self.get_settings_path(agent)
        if not settings_file:
            return False

        template = self._load_template(agent)
        if not template:
            logger.warning(f"Failed to load template for agent: {agent}")
            return False

        # If file doesn't exist, create it with template
        if not file_exists(settings_file):
            # Remove $comment before writing
            clean_template = {k: v for k, v in template.items() if k != "$comment"}
            self._write_settings(settings_file, clean_template)
            return True

        # File exists - merge settings
        existing_settings = self._read_settings(settings_file)

        if force:
            # Force mode: completely overwrite with template
            clean_template = {k: v for k, v in template.items() if k != "$comment"}
            merged_settings = self._merge_settings({}, clean_template)
            # Merge user's other settings back
            for key, value in existing_settings.items():
                if key not in merged_settings:
                    merged_settings[key] = value
        else:
            merged_settings = self._merge_settings(existing_settings, template)

        # Only write if settings changed
        if merged_settings != existing_settings:
            self._write_settings(settings_file, merged_settings)
            return True

        return False

    def remove_settings(self, agent: str) -> bool:
        """Remove OAK settings from agent config.

        Only removes OAK-managed settings, preserving user's custom settings.

        Args:
            agent: Agent name

        Returns:
            True if settings were removed, False if no changes needed
        """
        if not self.is_auto_approve_enabled(agent):
            return False

        settings_file = self.get_settings_path(agent)
        if not settings_file or not file_exists(settings_file):
            return False

        template = self._load_template(agent)
        if not template:
            return False

        existing_settings = self._read_settings(settings_file)
        if not existing_settings:
            return False

        # Remove OAK-managed settings
        cleaned_settings, modified = self._remove_oak_settings_from_dict(
            existing_settings, template
        )

        if modified:
            if cleaned_settings:
                # Still have user settings, write them
                self._write_settings(settings_file, cleaned_settings)
            else:
                # No settings left, delete the file
                try:
                    settings_file.unlink()
                    # Clean up empty parent directory
                    cleanup_empty_directories(settings_file.parent, self.project_root)
                except OSError:
                    pass

        return modified

    def needs_upgrade(self, agent: str) -> bool:
        """Check if agent settings need to be upgraded.

        Args:
            agent: Agent name

        Returns:
            True if settings need upgrading, False otherwise
        """
        if not self.is_auto_approve_enabled(agent):
            return False

        settings_file = self.get_settings_path(agent)
        if not settings_file:
            return False

        if not file_exists(settings_file):
            # File doesn't exist - needs installation
            return True

        template = self._load_template(agent)
        if not template:
            return False

        existing_settings = self._read_settings(settings_file)

        # Check if template adds new keys
        merged_settings = self._merge_settings(existing_settings, template)
        return merged_settings != existing_settings

    def install_settings_for_agents(
        self, agents: list[str], force: bool = False
    ) -> dict[str, bool]:
        """Install OAK settings for multiple agents.

        Args:
            agents: List of agent names
            force: If True, overwrite existing settings

        Returns:
            Dictionary mapping agent names to installation success
        """
        results = {}
        for agent in agents:
            results[agent] = self.install_settings(agent, force)
        return results

    def remove_settings_for_agents(self, agents: list[str]) -> dict[str, bool]:
        """Remove OAK settings from multiple agents.

        Args:
            agents: List of agent names

        Returns:
            Dictionary mapping agent names to removal success
        """
        results = {}
        for agent in agents:
            results[agent] = self.remove_settings(agent)
        return results

    def get_upgradeable_agents(self, agents: list[str]) -> list[str]:
        """Get list of agents that need settings upgrade.

        Args:
            agents: List of agent names to check

        Returns:
            List of agent names that need upgrading
        """
        upgradeable = []
        for agent in agents:
            if self.needs_upgrade(agent):
                upgradeable.append(agent)
        return upgradeable


def get_agent_settings_service(project_root: Path | None = None) -> AgentSettingsService:
    """Get an AgentSettingsService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        AgentSettingsService instance
    """
    return AgentSettingsService(project_root)
