"""Hook installation strategies.

Each strategy encapsulates the format-specific logic for one hook type:
- JsonHookStrategy:   Merge hooks into a JSON config file (Claude, Cursor, Gemini, Copilot)
- PluginHookStrategy: Copy a plugin file to the agent's plugins directory (OpenCode)
- OtelHookStrategy:   Generate OTLP config for agents that emit OpenTelemetry events (Codex)

All strategies implement the same protocol: install, remove, needs_upgrade,
is_oak_managed_hook.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from open_agent_kit.models.agent_manifest import AgentHooksConfig

from open_agent_kit.features.codebase_intelligence.hooks.installer import (
    HOOK_AGENT_FLAG_PREFIX,
    HOOK_CI_COMMAND_TOKEN,
    HOOK_CLI_COMMAND_PLACEHOLDER,
    HOOK_COMMAND_KEYS,
    HOOKS_TEMPLATE_DIR,
    OAK_HOOK_PATTERNS,
    HooksInstallResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TOML availability (consolidated single check)
# ---------------------------------------------------------------------------

_TOMLLIB_AVAILABLE: bool | None = None
_TOMLI_W_AVAILABLE: bool | None = None


def _check_tomllib() -> bool:
    global _TOMLLIB_AVAILABLE
    if _TOMLLIB_AVAILABLE is None:
        try:
            import tomllib  # noqa: F401

            _TOMLLIB_AVAILABLE = True
        except ImportError:
            _TOMLLIB_AVAILABLE = False
    return _TOMLLIB_AVAILABLE


def _check_tomli_w() -> bool:
    global _TOMLI_W_AVAILABLE
    if _TOMLI_W_AVAILABLE is None:
        try:
            import tomli_w  # noqa: F401

            _TOMLI_W_AVAILABLE = True
        except ImportError:
            _TOMLI_W_AVAILABLE = False
    return _TOMLI_W_AVAILABLE


# ---------------------------------------------------------------------------
# Strategy protocol
# ---------------------------------------------------------------------------


class HookStrategy(Protocol):
    """Protocol for hook installation strategies."""

    def install(self) -> HooksInstallResult: ...

    def remove(self) -> HooksInstallResult: ...

    def needs_upgrade(self) -> bool: ...

    def is_oak_managed_hook(self, hook: dict) -> bool: ...


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _rewrite_plugin_content(content: str, cli_command: str) -> str:
    """Render plugin source command placeholder to the configured CLI."""
    return content.replace(HOOK_CLI_COMMAND_PLACEHOLDER, cli_command)


def _render_hook_template_commands(data: dict[str, Any], cli_command: str) -> dict[str, Any]:
    """Render hook command placeholders in hook template payloads."""

    def _render_node(node: Any) -> Any:
        if isinstance(node, dict):
            rendered: dict[str, Any] = {}
            for key, value in node.items():
                if key in HOOK_COMMAND_KEYS and isinstance(value, str):
                    rendered[key] = value.replace(HOOK_CLI_COMMAND_PLACEHOLDER, cli_command)
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


def _load_hook_template(
    agent: str,
    hooks_config: AgentHooksConfig,
    cli_command: str,
) -> dict[str, Any] | None:
    """Load hook template for an agent."""
    template_file = HOOKS_TEMPLATE_DIR / agent / hooks_config.template_file
    if not template_file.exists():
        logger.warning(f"Hook template not found: {template_file}")
        return None

    try:
        with open(template_file) as f:
            result: dict[str, Any] = json.load(f)
            return _render_hook_template_commands(result, cli_command)
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to load hook template for {agent}: {e}")
        return None


def _get_daemon_port(project_root: Path) -> int:
    """Get the daemon port for this project."""
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
        read_project_port,
    )

    port = read_project_port(project_root)
    if port is not None:
        return port

    logger.warning("No port file found; deriving port (daemon may not be running yet)")
    return get_project_port(project_root)


def _is_config_effectively_empty(
    config: dict[str, Any],
    hooks_config: AgentHooksConfig,
) -> bool:
    """Check if a config dict is effectively empty (only scaffolding keys)."""
    meaningful_keys = set(config.keys())

    # Remove known scaffolding keys
    meaningful_keys.discard(hooks_config.hooks_key)
    if hooks_config.version_key:
        meaningful_keys.discard(hooks_config.version_key)

    if meaningful_keys:
        return False

    # If only scaffolding remains, check if hooks section is empty
    hooks_section = config.get(hooks_config.hooks_key, {})
    return not hooks_section


def _write_or_cleanup_config(
    config_path: Path,
    config: dict[str, Any],
    hooks_config: AgentHooksConfig,
) -> None:
    """Write config or remove file if effectively empty."""
    if _is_config_effectively_empty(config, hooks_config):
        config_path.unlink()
        logger.info(f"Removed empty config file: {config_path}")

        parent = config_path.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            logger.info(f"Removed empty directory: {parent}")
    else:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)


def _remove_empty_parent(path: Path) -> None:
    """Remove path's parent directory if it's empty."""
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        logger.info(f"Removed empty directory: {parent}")


# ---------------------------------------------------------------------------
# Shared OAK managed hook detection
# ---------------------------------------------------------------------------


def _check_oak_managed(
    hook: dict,
    hooks_config: AgentHooksConfig,
    cli_command: str,
    agent: str,
) -> bool:
    """Check if a hook is managed by OAK.

    Extracts the command based on the hook format and checks for OAK patterns.
    """
    hook_format = hooks_config.format

    if hook_format == "flat":
        command = hook.get("command", "")
    elif hook_format == "copilot":
        command = hook.get("command", "") or hook.get("bash", "") or hook.get("powershell", "")
    else:
        # Nested (Claude/Gemini): {hooks: [{command: "..."}]} structure
        inner_hooks = hook.get("hooks", [])
        if inner_hooks and isinstance(inner_hooks, list):
            command = inner_hooks[0].get("command", "")
        else:
            command = ""

    patterns = list(OAK_HOOK_PATTERNS)
    configured_hook_pattern = f"{cli_command} ci hook"
    if configured_hook_pattern not in patterns:
        patterns.append(configured_hook_pattern)
    if any(pattern in command for pattern in patterns):
        return True

    command_lower = command.lower()
    agent_flag = f"{HOOK_AGENT_FLAG_PREFIX}{agent}".lower()
    return HOOK_CI_COMMAND_TOKEN in command_lower and agent_flag in command_lower


# ===========================================================================
# JsonHookStrategy
# ===========================================================================


class JsonHookStrategy:
    """Strategy for JSON config-based hooks (Claude, Cursor, Gemini, Copilot)."""

    def __init__(
        self,
        project_root: Path,
        agent: str,
        agent_folder: Path,
        hooks_config: AgentHooksConfig,
        cli_command: str,
    ):
        self.project_root = project_root
        self.agent = agent
        self.agent_folder = agent_folder
        self.hooks_config = hooks_config
        self.cli_command = cli_command

    def is_oak_managed_hook(self, hook: dict) -> bool:
        return _check_oak_managed(hook, self.hooks_config, self.cli_command, self.agent)

    def install(self) -> HooksInstallResult:
        """Install hooks by merging into a JSON config file."""
        if not self.hooks_config.config_file:
            return HooksInstallResult(
                success=False,
                message="No config_file specified in hooks config",
            )

        config_path = self.agent_folder / self.hooks_config.config_file
        hooks_key = self.hooks_config.hooks_key
        config_path.parent.mkdir(parents=True, exist_ok=True)

        template = _load_hook_template(self.agent, self.hooks_config, self.cli_command)
        if not template:
            return HooksInstallResult(
                success=False,
                message=f"Failed to load hook template for {self.agent}",
            )

        ci_hooks = template.get(hooks_key, {})

        try:
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
            else:
                config = {}

            if self.hooks_config.version_key:
                if self.hooks_config.version_key not in config:
                    config[self.hooks_config.version_key] = 1

            if hooks_key not in config:
                config[hooks_key] = {}

            for event, new_hooks in ci_hooks.items():
                if event not in config[hooks_key]:
                    config[hooks_key][event] = []

                config[hooks_key][event] = [
                    h for h in config[hooks_key][event] if not self.is_oak_managed_hook(h)
                ]
                config[hooks_key][event].extend(new_hooks)

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

    def remove(self) -> HooksInstallResult:
        """Remove OAK hooks from a JSON config file."""
        if not self.hooks_config.config_file:
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

            events_to_remove = []
            for event in config[hooks_key]:
                config[hooks_key][event] = [
                    h for h in config[hooks_key][event] if not self.is_oak_managed_hook(h)
                ]
                if not config[hooks_key][event]:
                    events_to_remove.append(event)

            for event in events_to_remove:
                del config[hooks_key][event]

            if not config[hooks_key]:
                del config[hooks_key]

            _write_or_cleanup_config(config_path, config, self.hooks_config)

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

    def needs_upgrade(self) -> bool:
        """Check if JSON-based hooks differ from the package template."""
        if not self.hooks_config.config_file:
            return False

        template = _load_hook_template(self.agent, self.hooks_config, self.cli_command)
        if not template:
            return False

        hooks_key = self.hooks_config.hooks_key
        source_hooks = template.get(hooks_key, {})

        config_path = self.agent_folder / self.hooks_config.config_file
        if not config_path.exists():
            return bool(source_hooks)

        try:
            with open(config_path) as f:
                config = json.load(f)
            installed_hooks = config.get(hooks_key, {})
        except (OSError, json.JSONDecodeError):
            return True

        for event, source_event_hooks in source_hooks.items():
            installed_event_hooks = installed_hooks.get(event, [])
            oak_installed = [h for h in installed_event_hooks if self.is_oak_managed_hook(h)]

            if len(source_event_hooks) != len(oak_installed):
                return True
            if json.dumps(source_event_hooks, sort_keys=True) != json.dumps(
                oak_installed, sort_keys=True
            ):
                return True

        for event, installed_event_hooks in installed_hooks.items():
            if event not in source_hooks:
                if any(self.is_oak_managed_hook(h) for h in installed_event_hooks):
                    return True

        return False


# ===========================================================================
# PluginHookStrategy
# ===========================================================================


class PluginHookStrategy:
    """Strategy for plugin file-based hooks (OpenCode)."""

    def __init__(
        self,
        project_root: Path,
        agent: str,
        agent_folder: Path,
        hooks_config: AgentHooksConfig,
        cli_command: str,
    ):
        self.project_root = project_root
        self.agent = agent
        self.agent_folder = agent_folder
        self.hooks_config = hooks_config
        self.cli_command = cli_command

    def is_oak_managed_hook(self, hook: dict) -> bool:
        return _check_oak_managed(hook, self.hooks_config, self.cli_command, self.agent)

    def install(self) -> HooksInstallResult:
        """Install hooks by copying a plugin file."""
        if not self.hooks_config.plugin_dir or not self.hooks_config.plugin_file:
            return HooksInstallResult(
                success=False,
                message="Plugin configuration incomplete (missing plugin_dir or plugin_file)",
            )

        template_file = HOOKS_TEMPLATE_DIR / self.agent / self.hooks_config.template_file
        if not template_file.exists():
            return HooksInstallResult(
                success=False,
                message=f"Plugin template not found: {template_file}",
            )

        plugins_dir = self.agent_folder / self.hooks_config.plugin_dir
        plugin_path = plugins_dir / self.hooks_config.plugin_file

        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
            rendered_plugin = _rewrite_plugin_content(template_file.read_text(), self.cli_command)
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

    def remove(self) -> HooksInstallResult:
        """Remove plugin file and clean up empty directories."""
        if not self.hooks_config.plugin_dir or not self.hooks_config.plugin_file:
            return HooksInstallResult(
                success=True,
                message="No plugin configuration, nothing to remove",
            )

        plugins_dir = self.agent_folder / self.hooks_config.plugin_dir
        plugin_path = plugins_dir / self.hooks_config.plugin_file

        try:
            if plugin_path.exists():
                plugin_path.unlink()
                logger.info(f"Removed plugin: {plugin_path}")

            if plugins_dir.exists() and not any(plugins_dir.iterdir()):
                plugins_dir.rmdir()
                logger.info(f"Removed empty plugins directory: {plugins_dir}")

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

    def needs_upgrade(self) -> bool:
        """Check if a plugin file differs from the package template."""
        if not self.hooks_config.plugin_dir or not self.hooks_config.plugin_file:
            return False

        template_file = HOOKS_TEMPLATE_DIR / self.agent / self.hooks_config.template_file
        if not template_file.exists():
            return False

        installed_path = (
            self.agent_folder / self.hooks_config.plugin_dir / self.hooks_config.plugin_file
        )
        if not installed_path.exists():
            return True

        try:
            expected_content = _rewrite_plugin_content(template_file.read_text(), self.cli_command)
            return expected_content != installed_path.read_text()
        except OSError:
            return True


# ===========================================================================
# OtelHookStrategy
# ===========================================================================


class OtelHookStrategy:
    """Strategy for OTEL config-based hooks (Codex)."""

    def __init__(
        self,
        project_root: Path,
        agent: str,
        agent_folder: Path,
        hooks_config: AgentHooksConfig,
        cli_command: str,
    ):
        self.project_root = project_root
        self.agent = agent
        self.agent_folder = agent_folder
        self.hooks_config = hooks_config
        self.cli_command = cli_command

    def is_oak_managed_hook(self, hook: dict) -> bool:
        return _check_oak_managed(hook, self.hooks_config, self.cli_command, self.agent)

    def install(self) -> HooksInstallResult:
        """Install OTEL hooks by generating and merging config into agent's TOML file."""
        otel_config = self.hooks_config.otel
        if not otel_config:
            return HooksInstallResult(
                success=False,
                message="No OTEL configuration in hooks config",
                method="otel",
            )

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

        template_path = HOOKS_TEMPLATE_DIR / self.agent / otel_config.config_template
        if not template_path.exists():
            return HooksInstallResult(
                success=False,
                message=f"OTEL config template not found: {template_path}",
                method="otel",
            )

        try:
            daemon_port = _get_daemon_port(self.project_root)

            from jinja2 import Template

            template_content = template_path.read_text()
            template = Template(template_content)
            rendered_config = template.render(daemon_port=daemon_port)

            import tomllib

            if not _check_tomli_w():
                return HooksInstallResult(
                    success=False,
                    message="TOML write support requires 'tomli_w' package",
                    method="otel",
                )

            import tomli_w

            new_config = tomllib.loads(rendered_config)

            config_file = self.hooks_config.config_file or "config.toml"
            config_path = self.agent_folder / config_file
            config_path.parent.mkdir(parents=True, exist_ok=True)

            existing_config: dict[str, Any] = {}
            if config_path.exists():
                existing_config = tomllib.loads(config_path.read_text())

            config_section = otel_config.config_section or "otel"
            existing_config[config_section] = new_config.get(config_section, new_config)

            config_path.write_text(tomli_w.dumps(existing_config))

            return HooksInstallResult(
                success=True,
                message=f"OTEL hooks installed at {config_path} (port {daemon_port})",
                method="otel",
            )

        except ImportError as e:
            return HooksInstallResult(
                success=False,
                message=(
                    f"Missing dependency for OTEL hooks: {e}. "
                    "Install with: pip install jinja2 tomli-w"
                ),
                method="otel",
            )
        except (OSError, ValueError) as e:
            return HooksInstallResult(
                success=False,
                message=f"Failed to install OTEL hooks: {e}",
                method="otel",
            )

    def remove(self) -> HooksInstallResult:
        """Remove OTEL hooks from the agent's config file."""
        otel_config = self.hooks_config.otel
        if not otel_config:
            return HooksInstallResult(
                success=True,
                message="No OTEL configuration, nothing to remove",
                method="otel",
            )

        config_file = self.hooks_config.config_file or "config.toml"
        config_path = self.agent_folder / config_file

        if not config_path.exists():
            return HooksInstallResult(
                success=True,
                message=f"Config file {config_path} doesn't exist, nothing to remove",
                method="otel",
            )

        try:
            if not _check_tomllib():
                return HooksInstallResult(
                    success=False,
                    message="TOML read support requires Python 3.11+ (tomllib)",
                    method="otel",
                )

            import tomllib

            if not _check_tomli_w():
                return HooksInstallResult(
                    success=False,
                    message="TOML write support requires 'tomli_w' package",
                    method="otel",
                )

            import tomli_w

            existing_config = tomllib.loads(config_path.read_text())

            config_section = otel_config.config_section or "otel"
            if config_section in existing_config:
                del existing_config[config_section]
                logger.info(f"Removed [{config_section}] section from {config_path}")

            if existing_config:
                config_path.write_text(tomli_w.dumps(existing_config))
            else:
                config_path.unlink()
                logger.info(f"Removed empty config file: {config_path}")
                _remove_empty_parent(config_path)

            return HooksInstallResult(
                success=True,
                message=f"OTEL hooks removed from {config_path}",
                method="otel",
            )

        except ImportError as e:
            return HooksInstallResult(
                success=False,
                message=(
                    f"Missing dependency for OTEL hooks: {e}. " "Install with: pip install tomli-w"
                ),
                method="otel",
            )
        except (OSError, ValueError) as e:
            return HooksInstallResult(
                success=False,
                message=f"Failed to remove OTEL hooks: {e}",
                method="otel",
            )

    def needs_upgrade(self) -> bool:
        """Check if the OTEL config section differs from the rendered template."""
        otel_config = self.hooks_config.otel
        if not otel_config or not otel_config.enabled or not otel_config.config_template:
            return False

        template_path = HOOKS_TEMPLATE_DIR / self.agent / otel_config.config_template
        if not template_path.exists():
            return False

        config_file = self.hooks_config.config_file or "config.toml"
        config_path = self.agent_folder / config_file
        if not config_path.exists():
            return True

        try:
            import tomllib

            from jinja2 import Template

            daemon_port = _get_daemon_port(self.project_root)
            rendered = Template(template_path.read_text()).render(daemon_port=daemon_port)
            expected_section = tomllib.loads(rendered)

            installed_config = tomllib.loads(config_path.read_text())
            section_key = otel_config.config_section or "otel"

            if section_key not in installed_config:
                return True

            expected_value = expected_section.get(section_key, expected_section)
            installed_value = installed_config[section_key]
            return bool(installed_value != expected_value)
        except (ImportError, OSError, ValueError):
            return True
