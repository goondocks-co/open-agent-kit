"""Hooks installer module.

Provides a generic Python-based installer for CI hooks that reads
configuration from agent manifests. Replaces agent-specific hook methods.

Supports three hook types via Strategy pattern (see strategies.py):
- JSON: Merge hooks into a JSON config file (Claude, Cursor, Gemini, Copilot)
- Plugin: Copy a plugin file to the agent's plugins directory (OpenCode)
- OTEL: Generate OTLP config for agents that emit OpenTelemetry events (Codex)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.hooks.strategies import (
        JsonHookStrategy,
        OtelHookStrategy,
        PluginHookStrategy,
    )
    from open_agent_kit.models.agent_manifest import AgentHooksConfig, AgentManifest

from open_agent_kit.features.codebase_intelligence.cli_command import (
    resolve_ci_cli_command,
)
from open_agent_kit.models.enums import HookType
from open_agent_kit.utils.env_utils import add_gitignore_entries, remove_gitignore_entries

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
    method: str = "unknown"  # "json", "plugin", or "otel"


class HooksInstaller:
    """Generic hooks installer using manifest-driven configuration.

    Reads all configuration from the agent's manifest.yaml hooks: section,
    eliminating the need for separate methods per agent.

    Three installation strategies:
    - JSON: Merge hooks into a JSON config file (preserving non-OAK hooks)
    - Plugin: Copy a plugin file to the agent's plugins directory
    - OTEL: Generate OTLP config for agents that emit OpenTelemetry events

    Example usage:
        installer = HooksInstaller(
            project_root=Path("/path/to/project"),
            agent="claude",
        )
        result = installer.install()
    """

    def __init__(self, project_root: Path, agent: str):
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

    def _get_strategy(
        self,
    ) -> JsonHookStrategy | PluginHookStrategy | OtelHookStrategy | None:
        """Get the appropriate strategy for this agent's hook type."""
        if not self.hooks_config:
            return None

        from open_agent_kit.features.codebase_intelligence.hooks.strategies import (
            JsonHookStrategy,
            OtelHookStrategy,
            PluginHookStrategy,
        )

        args = (
            self.project_root,
            self.agent,
            self.agent_folder,
            self.hooks_config,
            self.cli_command,
        )

        if self.hooks_config.type == HookType.PLUGIN:
            return PluginHookStrategy(*args)
        elif self.hooks_config.type == HookType.OTEL:
            return OtelHookStrategy(*args)
        else:
            return JsonHookStrategy(*args)

    def install(self) -> HooksInstallResult:
        """Install hooks for the agent."""
        strategy = self._get_strategy()
        if not strategy:
            return HooksInstallResult(
                success=False,
                message=f"No hooks configuration in manifest for {self.agent}",
            )

        result = strategy.install()

        # Hook files are now committed to git — clean up legacy gitignore entries
        if result.success:
            self._remove_hook_file_gitignore()

        return result

    def remove(self) -> HooksInstallResult:
        """Remove hooks from the agent."""
        strategy = self._get_strategy()
        if not strategy:
            return HooksInstallResult(
                success=False,
                message=f"No hooks configuration in manifest for {self.agent}",
            )

        result = strategy.remove()

        if result.success:
            self._remove_hook_file_gitignore()

        return result

    def needs_upgrade(self) -> bool:
        """Check if installed hooks differ from the package template."""
        strategy = self._get_strategy()
        if not strategy:
            return False
        return strategy.needs_upgrade()

    def _is_oak_managed_hook(self, hook: dict) -> bool:
        """Check if a hook is managed by OAK (delegates to strategy)."""
        strategy = self._get_strategy()
        if not strategy:
            return False
        return strategy.is_oak_managed_hook(hook)

    def _rewrite_plugin_content(self, content: str) -> str:
        """Render plugin source command placeholder to the configured CLI."""
        return content.replace(HOOK_CLI_COMMAND_PLACEHOLDER, self.cli_command)

    def _load_hook_template(self) -> dict[str, Any] | None:
        """Load hook template for this agent (delegates to strategies module)."""
        if not self.hooks_config:
            return None

        from open_agent_kit.features.codebase_intelligence.hooks.strategies import (
            _load_hook_template,
        )

        return _load_hook_template(self.agent, self.hooks_config, self.cli_command)

    # ------------------------------------------------------------------
    # Gitignore helpers
    # ------------------------------------------------------------------

    def _get_hook_gitignore_pattern(self) -> str | None:
        """Compute the gitignore pattern for this agent's hook file."""
        if not self.hooks_config:
            return None

        folder = self.manifest.installation.folder.rstrip("/")

        if self.hooks_config.type == HookType.PLUGIN:
            if self.hooks_config.plugin_dir and self.hooks_config.plugin_file:
                return f"{folder}/{self.hooks_config.plugin_dir}/{self.hooks_config.plugin_file}"
            return None

        config_file = self.hooks_config.config_file
        if config_file:
            return f"{folder}/{config_file}"
        return None

    def _ensure_hook_file_gitignored(self) -> None:
        """Add a .gitignore entry for this agent's hook file."""
        pattern = self._get_hook_gitignore_pattern()
        if pattern:
            add_gitignore_entries(
                self.project_root,
                [pattern],
                section_comment="open-agent-kit: CI hook configs (local-only, regenerated by oak ci start)",
            )

    def _remove_hook_file_gitignore(self) -> None:
        """Remove the .gitignore entry for this agent's hook file."""
        pattern = self._get_hook_gitignore_pattern()
        if pattern:
            remove_gitignore_entries(self.project_root, [pattern])
