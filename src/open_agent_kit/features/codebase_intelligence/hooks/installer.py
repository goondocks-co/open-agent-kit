"""Hooks installer module.

Provides a generic Python-based installer for CI hooks that reads
configuration from agent manifests. Replaces agent-specific hook methods.

Supports three hook types:
- JSON: Merge hooks into a JSON config file (Claude, Cursor, Gemini, Copilot)
- Plugin: Copy a plugin file to the agent's plugins directory (OpenCode)
- OTEL: Generate OTLP config for agents that emit OpenTelemetry events (Codex)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.models.agent_manifest import AgentHooksConfig, AgentManifest

from open_agent_kit.features.codebase_intelligence.cli_command import (
    resolve_ci_cli_command,
)

logger = logging.getLogger(__name__)

# Path to hook templates directory (sibling directories: claude/, cursor/, etc.)
HOOKS_TEMPLATE_DIR = Path(__file__).parent

# Patterns that identify OAK-managed hooks (for safe replacement)
OAK_HOOK_PATTERNS = ("oak ci hook", "/api/oak/ci/", "/api/hook/", "oak-ci-hook.sh")
HOOK_COMMAND_KEYS = ("command", "bash", "powershell")
HOOK_CI_COMMAND_TOKEN = " ci hook "
HOOK_AGENT_FLAG_PREFIX = "--agent "
HOOK_CLI_COMMAND_PLACEHOLDER = "{oak-cli-command}"


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
        self.cli_command = resolve_ci_cli_command(project_root)
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

        Routes to JSON, plugin, or OTEL installer based on manifest config.

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
        elif self.hooks_config.type == "otel":
            return self._install_otel_hooks()
        else:
            return self._install_json_hooks()

    def remove(self) -> HooksInstallResult:
        """Remove hooks from the agent.

        Routes to JSON, plugin, or OTEL remover based on manifest config.

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
        elif self.hooks_config.type == "otel":
            return self._remove_otel_hooks()
        else:
            return self._remove_json_hooks()

    # ------------------------------------------------------------------
    # Upgrade detection (mirrors NotificationsInstaller.needs_upgrade)
    # ------------------------------------------------------------------

    def needs_upgrade(self) -> bool:
        """Check if installed hooks differ from the package template.

        Routes to a type-specific comparison based on ``hooks_config.type``.

        Returns:
            True if the installed hooks need to be upgraded, False otherwise.
        """
        if not self.hooks_config:
            return False

        hook_type = self.hooks_config.type

        if hook_type == "plugin":
            return self._plugin_needs_upgrade()
        elif hook_type == "otel":
            return self._otel_needs_upgrade()
        else:
            return self._json_needs_upgrade()

    def _plugin_needs_upgrade(self) -> bool:
        """Check if a plugin file differs from the package template.

        Compares the raw file content of the template against the installed
        plugin file.
        """
        if (
            not self.hooks_config
            or not self.hooks_config.plugin_dir
            or not self.hooks_config.plugin_file
        ):
            return False

        template_file = HOOKS_TEMPLATE_DIR / self.agent / self.hooks_config.template_file
        if not template_file.exists():
            return False

        installed_path = (
            self.agent_folder / self.hooks_config.plugin_dir / self.hooks_config.plugin_file
        )
        if not installed_path.exists():
            return True  # Not installed yet

        try:
            expected_content = self._rewrite_plugin_content(template_file.read_text())
            return expected_content != installed_path.read_text()
        except OSError:
            return True

    def _otel_needs_upgrade(self) -> bool:
        """Check if the OTEL config section differs from the rendered template.

        Renders the Jinja2 template with the current daemon port and compares
        the resulting TOML section against the installed config file.
        """
        if not self.hooks_config or not self.hooks_config.otel:
            return False

        otel_config = self.hooks_config.otel
        if not otel_config.enabled or not otel_config.config_template:
            return False

        template_path = HOOKS_TEMPLATE_DIR / self.agent / otel_config.config_template
        if not template_path.exists():
            return False

        config_file = self.hooks_config.config_file or "config.toml"
        config_path = self.agent_folder / config_file
        if not config_path.exists():
            return True  # Not installed yet

        try:
            import tomllib

            from jinja2 import Template

            daemon_port = self._get_daemon_port()
            rendered = Template(template_path.read_text()).render(daemon_port=daemon_port)
            expected_section = tomllib.loads(rendered)

            installed_config = tomllib.loads(config_path.read_text())
            section_key = otel_config.config_section or "otel"

            if section_key not in installed_config:
                return True

            # Compare only the managed section (other config keys are user-owned)
            expected_value = expected_section.get(section_key, expected_section)
            installed_value = installed_config[section_key]
            return bool(installed_value != expected_value)
        except (ImportError, OSError, ValueError):
            return True

    def _json_needs_upgrade(self) -> bool:
        """Check if JSON-based hooks differ from the package template.

        Loads the template hooks, then compares each event's OAK-managed
        hooks against what is currently installed in the agent's config file.
        Uses ``_is_oak_managed_hook`` for identification so the logic stays
        manifest-aware (flat / nested / copilot formats).
        """
        if not self.hooks_config or not self.hooks_config.config_file:
            return False

        template = self._load_hook_template()
        if not template:
            return False

        hooks_key = self.hooks_config.hooks_key
        source_hooks = template.get(hooks_key, {})

        config_path = self.agent_folder / self.hooks_config.config_file
        if not config_path.exists():
            # Not installed yet — needs upgrade only if template has hooks
            return bool(source_hooks)

        try:
            with open(config_path) as f:
                config = json.load(f)
            installed_hooks = config.get(hooks_key, {})
        except (OSError, json.JSONDecodeError):
            return True

        # For each event in the template, compare OAK-managed hooks
        for event, source_event_hooks in source_hooks.items():
            installed_event_hooks = installed_hooks.get(event, [])

            oak_installed = [h for h in installed_event_hooks if self._is_oak_managed_hook(h)]

            if len(source_event_hooks) != len(oak_installed):
                return True

            if json.dumps(source_event_hooks, sort_keys=True) != json.dumps(
                oak_installed, sort_keys=True
            ):
                return True

        # Check for orphaned OAK hooks in events the template doesn't define
        for event, installed_event_hooks in installed_hooks.items():
            if event not in source_hooks:
                if any(self._is_oak_managed_hook(h) for h in installed_event_hooks):
                    return True

        return False

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
                return self._render_hook_template_commands(result)
        except Exception as e:
            logger.error(f"Failed to load hook template for {self.agent}: {e}")
            return None

    def _render_hook_template_commands(self, data: dict[str, Any]) -> dict[str, Any]:
        """Render hook command placeholders in hook template payloads."""

        def _render_node(node: Any) -> Any:
            if isinstance(node, dict):
                rendered: dict[str, Any] = {}
                for key, value in node.items():
                    if key in HOOK_COMMAND_KEYS and isinstance(value, str):
                        rendered[key] = value.replace(
                            HOOK_CLI_COMMAND_PLACEHOLDER, self.cli_command
                        )
                    else:
                        rendered[key] = _render_node(value)
                return rendered
            if isinstance(node, list):
                return [_render_node(item) for item in node]
            return node

        rendered = _render_node(data)
        if isinstance(rendered, dict):
            return rendered
        return data

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

        patterns = list(OAK_HOOK_PATTERNS)
        configured_hook_pattern = f"{self.cli_command} ci hook"
        if configured_hook_pattern not in patterns:
            patterns.append(configured_hook_pattern)
        if any(pattern in command for pattern in patterns):
            return True

        command_lower = command.lower()
        agent_flag = f"{HOOK_AGENT_FLAG_PREFIX}{self.agent}".lower()
        return HOOK_CI_COMMAND_TOKEN in command_lower and agent_flag in command_lower

    def _rewrite_plugin_content(self, content: str) -> str:
        """Render plugin source command placeholder to the configured CLI."""
        return content.replace(HOOK_CLI_COMMAND_PLACEHOLDER, self.cli_command)

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
            rendered_plugin = self._rewrite_plugin_content(template_file.read_text())
            plugin_path.write_text(rendered_plugin)

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

    def _get_daemon_port(self) -> int:
        """Get the daemon port from the shared port file or return default.

        Reads from the shared port file (oak/daemon.port) which is
        git-tracked and represents the assigned port for this project.
        The daemon will always use this port (killing any hanging process
        if necessary), so this is the stable source of truth.

        Returns:
            The daemon port number.
        """
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_SHARED_PORT_DIR,
            CI_SHARED_PORT_FILE,
        )
        from open_agent_kit.features.codebase_intelligence.daemon.manager import (
            DEFAULT_PORT,
        )

        # Shared port file is the source of truth (git-tracked)
        shared_port_file = self.project_root / CI_SHARED_PORT_DIR / CI_SHARED_PORT_FILE
        if shared_port_file.exists():
            try:
                port = int(shared_port_file.read_text().strip())
                logger.debug(f"Read daemon port {port} from {shared_port_file}")
                return port
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to read shared port file {shared_port_file}: {e}")

        logger.debug(f"Using default daemon port {DEFAULT_PORT}")
        return DEFAULT_PORT

    def _install_otel_hooks(self) -> HooksInstallResult:
        """Install OTEL hooks by generating and merging config into agent's TOML file.

        Used for agents like Codex that emit OpenTelemetry events instead of
        using traditional hooks. Generates an [otel] section in the agent's
        config file that points to the CI daemon's OTLP receiver.
        """
        if not self.hooks_config or not self.hooks_config.otel:
            return HooksInstallResult(
                success=False,
                message="No OTEL configuration in hooks config",
                method="otel",
            )

        otel_config = self.hooks_config.otel
        if not otel_config.enabled:
            return HooksInstallResult(
                success=True,
                message="OTEL hooks disabled in manifest",
                method="otel",
            )

        if not otel_config.config_template:
            return HooksInstallResult(
                success=False,
                message="No config_template specified in OTEL config",
                method="otel",
            )

        # Load the Jinja2 template
        template_path = HOOKS_TEMPLATE_DIR / self.agent / otel_config.config_template
        if not template_path.exists():
            return HooksInstallResult(
                success=False,
                message=f"OTEL config template not found: {template_path}",
                method="otel",
            )

        try:
            # Get the daemon port - read from port file or use default
            daemon_port = self._get_daemon_port()

            # Render the template with the daemon port
            # Note: Codex doesn't support env var substitution in its config,
            # so we must write the actual port value at install time.
            from jinja2 import Template

            template_content = template_path.read_text()
            template = Template(template_content)
            rendered_config = template.render(
                daemon_port=daemon_port,
            )

            # Parse the rendered TOML
            import tomllib

            try:
                import tomli_w
            except ImportError:
                return HooksInstallResult(
                    success=False,
                    message="TOML write support requires 'tomli_w' package",
                    method="otel",
                )

            new_config = tomllib.loads(rendered_config)

            # Determine the config file path
            # For Codex, the config is at .codex/config.toml (project-scoped)
            config_file = self.hooks_config.config_file or "config.toml"
            config_path = self.agent_folder / config_file

            # Ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing config or create new
            existing_config: dict[str, Any] = {}
            if config_path.exists():
                existing_config = tomllib.loads(config_path.read_text())

            # Merge the OTEL section (replace if exists)
            config_section = otel_config.config_section or "otel"
            existing_config[config_section] = new_config.get(config_section, new_config)

            # Write the merged config
            config_path.write_text(tomli_w.dumps(existing_config))

            return HooksInstallResult(
                success=True,
                message=f"OTEL hooks installed at {config_path} (port {daemon_port})",
                method="otel",
            )

        except ImportError as e:
            return HooksInstallResult(
                success=False,
                message=f"Missing dependency for OTEL hooks: {e}. Install with: pip install jinja2 tomli-w",
                method="otel",
            )
        except (OSError, ValueError) as e:
            return HooksInstallResult(
                success=False,
                message=f"Failed to install OTEL hooks: {e}",
                method="otel",
            )

    def _remove_otel_hooks(self) -> HooksInstallResult:
        """Remove OTEL hooks from the agent's config file.

        Removes the [otel] section from the config file while preserving
        other configuration.
        """
        if not self.hooks_config or not self.hooks_config.otel:
            return HooksInstallResult(
                success=True,
                message="No OTEL configuration, nothing to remove",
                method="otel",
            )

        otel_config = self.hooks_config.otel

        # Determine the config file path
        config_file = self.hooks_config.config_file or "config.toml"
        config_path = self.agent_folder / config_file

        if not config_path.exists():
            return HooksInstallResult(
                success=True,
                message=f"Config file {config_path} doesn't exist, nothing to remove",
                method="otel",
            )

        try:
            import tomllib

            try:
                import tomli_w
            except ImportError:
                return HooksInstallResult(
                    success=False,
                    message="TOML write support requires 'tomli_w' package",
                    method="otel",
                )

            # Load existing config
            existing_config = tomllib.loads(config_path.read_text())

            # Remove the OTEL section
            config_section = otel_config.config_section or "otel"
            if config_section in existing_config:
                del existing_config[config_section]
                logger.info(f"Removed [{config_section}] section from {config_path}")

            # Write updated config or remove if empty
            if existing_config:
                config_path.write_text(tomli_w.dumps(existing_config))
            else:
                config_path.unlink()
                logger.info(f"Removed empty config file: {config_path}")

                # Remove parent directory if empty
                parent = config_path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    logger.info(f"Removed empty directory: {parent}")

            return HooksInstallResult(
                success=True,
                message=f"OTEL hooks removed from {config_path}",
                method="otel",
            )

        except ImportError as e:
            return HooksInstallResult(
                success=False,
                message=f"Missing dependency for OTEL hooks: {e}. Install with: pip install tomli-w",
                method="otel",
            )
        except (OSError, ValueError) as e:
            return HooksInstallResult(
                success=False,
                message=f"Failed to remove OTEL hooks: {e}",
                method="otel",
            )
