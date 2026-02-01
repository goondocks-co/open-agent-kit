"""Hooks installer module.

Provides a generic Python-based installer for CI hooks that reads
configuration from agent manifests. Replaces agent-specific hook methods.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.models.agent_manifest import AgentHooksConfig, AgentManifest

logger = logging.getLogger(__name__)

# Path to hook templates directory (sibling directories: claude/, cursor/, etc.)
HOOKS_TEMPLATE_DIR = Path(__file__).parent

# Patterns that identify OAK-managed hooks (for safe replacement)
OAK_HOOK_PATTERNS = ("oak ci hook", "/api/oak/ci/", "/api/hook/", "oak-ci-hook.sh")


@dataclass
class HooksInstallResult:
    """Result of a hooks install/remove operation."""

    success: bool
    message: str
    method: str = "unknown"  # "json" or "plugin"


class HooksInstaller:
    """Generic hooks installer using manifest-driven configuration.

    Reads all configuration from the agent's manifest.yaml hooks: section,
    eliminating the need for separate methods per agent.

    Two installation strategies:
    - JSON: Merge hooks into a JSON config file (preserving non-OAK hooks)
    - Plugin: Copy a plugin file to the agent's plugins directory

    Example usage:
        installer = HooksInstaller(
            project_root=Path("/path/to/project"),
            agent="claude",
        )
        result = installer.install()
    """

    def __init__(self, project_root: Path, agent: str):
        """Initialize hooks installer.

        Args:
            project_root: Project root directory.
            agent: Agent name (e.g., "claude", "cursor").
        """
        self.project_root = project_root
        self.agent = agent
        self._manifest: AgentManifest | None = None
        self._hooks_config: AgentHooksConfig | None = None

    @property
    def manifest(self) -> AgentManifest:
        """Load and cache agent manifest."""
        if self._manifest is None:
            from open_agent_kit.services.agent_service import AgentService

            agent_service = AgentService(self.project_root)
            self._manifest = agent_service.get_agent_manifest(self.agent)
        return self._manifest

    @property
    def hooks_config(self) -> AgentHooksConfig | None:
        """Get hooks config from manifest."""
        if self._hooks_config is None:
            self._hooks_config = self.manifest.hooks
        return self._hooks_config

    @property
    def agent_folder(self) -> Path:
        """Get the agent's installation folder as an absolute path."""
        folder = self.manifest.installation.folder.rstrip("/")
        return self.project_root / folder

    def install(self) -> HooksInstallResult:
        """Install hooks for the agent.

        Routes to JSON or plugin installer based on manifest config.

        Returns:
            HooksInstallResult with success status and details.
        """
        if not self.hooks_config:
            return HooksInstallResult(
                success=False,
                message=f"No hooks configuration in manifest for {self.agent}",
            )

        if self.hooks_config.type == "plugin":
            return self._install_plugin()
        else:
            return self._install_json_hooks()

    def remove(self) -> HooksInstallResult:
        """Remove hooks from the agent.

        Routes to JSON or plugin remover based on manifest config.

        Returns:
            HooksInstallResult with success status and details.
        """
        if not self.hooks_config:
            return HooksInstallResult(
                success=False,
                message=f"No hooks configuration in manifest for {self.agent}",
            )

        if self.hooks_config.type == "plugin":
            return self._remove_plugin()
        else:
            return self._remove_json_hooks()

    def _load_hook_template(self) -> dict[str, Any] | None:
        """Load hook template for this agent.

        Returns:
            Hook template dict, or None if not found.
        """
        if not self.hooks_config:
            return None

        template_file = HOOKS_TEMPLATE_DIR / self.agent / self.hooks_config.template_file
        if not template_file.exists():
            logger.warning(f"Hook template not found: {template_file}")
            return None

        try:
            with open(template_file) as f:
                result: dict[str, Any] = json.load(f)
                return result
        except Exception as e:
            logger.error(f"Failed to load hook template for {self.agent}: {e}")
            return None

    def _is_oak_managed_hook(self, hook: dict) -> bool:
        """Check if a hook is managed by OAK.

        Identifies OAK hooks by patterns in the command.

        Args:
            hook: Hook configuration dict.

        Returns:
            True if the hook is managed by OAK.
        """
        if not self.hooks_config:
            return False

        hook_format = self.hooks_config.format

        # Extract command based on format
        if hook_format == "flat":
            # Cursor: simple {command: "..."} structure
            command = hook.get("command", "")
        elif hook_format == "copilot":
            # Copilot: {bash: "...", powershell: "..."} structure
            command = hook.get("bash", "") or hook.get("powershell", "")
        else:
            # Nested (Claude/Gemini): {hooks: [{command: "..."}]} structure
            inner_hooks = hook.get("hooks", [])
            if inner_hooks and isinstance(inner_hooks, list):
                command = inner_hooks[0].get("command", "")
            else:
                command = ""

        return any(pattern in command for pattern in OAK_HOOK_PATTERNS)

    def _install_json_hooks(self) -> HooksInstallResult:
        """Install hooks by merging into a JSON config file.

        Preserves non-OAK hooks while replacing OAK-managed hooks.
        """
        if not self.hooks_config or not self.hooks_config.config_file:
            return HooksInstallResult(
                success=False,
                message="No config_file specified in hooks config",
            )

        # Determine config file path
        config_path = self.agent_folder / self.hooks_config.config_file
        hooks_key = self.hooks_config.hooks_key

        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load hook template
        template = self._load_hook_template()
        if not template:
            return HooksInstallResult(
                success=False,
                message=f"Failed to load hook template for {self.agent}",
            )

        ci_hooks = template.get(hooks_key, {})

        try:
            # Load existing config or create new
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
            else:
                config = {}

            # Add version key if specified (Cursor, Copilot)
            if self.hooks_config.version_key:
                if self.hooks_config.version_key not in config:
                    config[self.hooks_config.version_key] = 1

            # Ensure hooks key exists
            if hooks_key not in config:
                config[hooks_key] = {}

            # Replace CI hooks (remove old OAK hooks, add new ones)
            for event, new_hooks in ci_hooks.items():
                if event not in config[hooks_key]:
                    config[hooks_key][event] = []

                # Remove existing OAK-managed hooks for this event
                config[hooks_key][event] = [
                    h for h in config[hooks_key][event] if not self._is_oak_managed_hook(h)
                ]

                # Add new CI hooks
                config[hooks_key][event].extend(new_hooks)

            # Write config
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            return HooksInstallResult(
                success=True,
                message=f"Hooks installed at {config_path}",
                method="json",
            )

        except (OSError, json.JSONDecodeError) as e:
            return HooksInstallResult(
                success=False,
                message=f"Failed to install hooks: {e}",
                method="json",
            )

    def _remove_json_hooks(self) -> HooksInstallResult:
        """Remove OAK hooks from a JSON config file.

        Preserves non-OAK hooks and cleans up empty structures.
        """
        if not self.hooks_config or not self.hooks_config.config_file:
            return HooksInstallResult(
                success=True,
                message="No config_file specified, nothing to remove",
            )

        config_path = self.agent_folder / self.hooks_config.config_file
        hooks_key = self.hooks_config.hooks_key

        if not config_path.exists():
            return HooksInstallResult(
                success=True,
                message=f"Config file {config_path} doesn't exist, nothing to remove",
                method="json",
            )

        try:
            with open(config_path) as f:
                config = json.load(f)

            if hooks_key not in config:
                return HooksInstallResult(
                    success=True,
                    message="No hooks section found, nothing to remove",
                    method="json",
                )

            # Remove OAK-managed hooks from each event
            events_to_remove = []
            for event in config[hooks_key]:
                config[hooks_key][event] = [
                    h for h in config[hooks_key][event] if not self._is_oak_managed_hook(h)
                ]

                # Track empty event lists for removal
                if not config[hooks_key][event]:
                    events_to_remove.append(event)

            # Remove empty event lists
            for event in events_to_remove:
                del config[hooks_key][event]

            # Remove empty hooks section
            if not config[hooks_key]:
                del config[hooks_key]

            # Write updated config or remove if empty
            self._write_or_cleanup_config(config_path, config)

            return HooksInstallResult(
                success=True,
                message=f"Hooks removed from {config_path}",
                method="json",
            )

        except (OSError, json.JSONDecodeError) as e:
            return HooksInstallResult(
                success=False,
                message=f"Failed to remove hooks: {e}",
                method="json",
            )

    def _write_or_cleanup_config(self, config_path: Path, config: dict[str, Any]) -> None:
        """Write config or remove file if effectively empty.

        Args:
            config_path: Path to config file.
            config: Config dict to write.
        """
        # Define empty structures for this agent
        empty_structures: list[dict[str, Any]] = [
            {},
            {"hooks": {}},
        ]
        if self.hooks_config and self.hooks_config.version_key:
            empty_structures.extend(
                [
                    {self.hooks_config.version_key: 1},
                    {self.hooks_config.version_key: 1, "hooks": {}},
                ]
            )

        if config in empty_structures:
            config_path.unlink()
            logger.info(f"Removed empty config file: {config_path}")

            # Remove parent directory if empty
            parent = config_path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
                logger.info(f"Removed empty directory: {parent}")
        else:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

    def _install_plugin(self) -> HooksInstallResult:
        """Install hooks by copying a plugin file.

        Used for agents like OpenCode that use TypeScript plugins.
        """
        if not self.hooks_config:
            return HooksInstallResult(
                success=False,
                message="No hooks configuration available",
            )

        if not self.hooks_config.plugin_dir or not self.hooks_config.plugin_file:
            return HooksInstallResult(
                success=False,
                message="Plugin configuration incomplete (missing plugin_dir or plugin_file)",
            )

        # Source template
        template_file = HOOKS_TEMPLATE_DIR / self.agent / self.hooks_config.template_file
        if not template_file.exists():
            return HooksInstallResult(
                success=False,
                message=f"Plugin template not found: {template_file}",
            )

        # Destination
        plugins_dir = self.agent_folder / self.hooks_config.plugin_dir
        plugin_path = plugins_dir / self.hooks_config.plugin_file

        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template_file, plugin_path)

            return HooksInstallResult(
                success=True,
                message=f"Plugin installed at {plugin_path}",
                method="plugin",
            )

        except OSError as e:
            return HooksInstallResult(
                success=False,
                message=f"Failed to install plugin: {e}",
                method="plugin",
            )

    def _remove_plugin(self) -> HooksInstallResult:
        """Remove plugin file and clean up empty directories."""
        if not self.hooks_config:
            return HooksInstallResult(
                success=True,
                message="No hooks configuration, nothing to remove",
            )

        if not self.hooks_config.plugin_dir or not self.hooks_config.plugin_file:
            return HooksInstallResult(
                success=True,
                message="No plugin configuration, nothing to remove",
            )

        plugins_dir = self.agent_folder / self.hooks_config.plugin_dir
        plugin_path = plugins_dir / self.hooks_config.plugin_file

        try:
            # Remove plugin file
            if plugin_path.exists():
                plugin_path.unlink()
                logger.info(f"Removed plugin: {plugin_path}")

            # Remove plugins directory if empty
            if plugins_dir.exists() and not any(plugins_dir.iterdir()):
                plugins_dir.rmdir()
                logger.info(f"Removed empty plugins directory: {plugins_dir}")

            # Remove agent directory if empty
            if self.agent_folder.exists() and not any(self.agent_folder.iterdir()):
                self.agent_folder.rmdir()
                logger.info(f"Removed empty agent directory: {self.agent_folder}")

            return HooksInstallResult(
                success=True,
                message=f"Plugin removed from {plugin_path}",
                method="plugin",
            )

        except OSError as e:
            return HooksInstallResult(
                success=False,
                message=f"Failed to remove plugin: {e}",
                method="plugin",
            )
