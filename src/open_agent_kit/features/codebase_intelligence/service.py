"""Codebase Intelligence feature service.

Handles feature lifecycle hooks and coordinates CI functionality.
"""

import json
import logging
import os
import re
import webbrowser
from pathlib import Path
from typing import Any, cast

from open_agent_kit.features.codebase_intelligence.daemon.manager import get_project_port

logger = logging.getLogger(__name__)

# Path to the feature's hooks templates directory
HOOKS_TEMPLATE_DIR = (
    Path(__file__).parent.parent.parent.parent.parent
    / "features"
    / "codebase-intelligence"
    / "hooks"
)

# Path to the feature's MCP configuration directory
MCP_TEMPLATE_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "features" / "codebase-intelligence" / "mcp"
)


class CodebaseIntelligenceService:
    """Service for Codebase Intelligence feature lifecycle management.

    This service is called by OAK's feature system in response to
    lifecycle events defined in the manifest.yaml.
    """

    def __init__(self, project_root: Path):
        """Initialize CI service.

        Args:
            project_root: Root directory of the OAK project.
        """
        self.project_root = project_root
        self.ci_data_dir = project_root / ".oak" / "ci"
        self._port: int | None = None

    @property
    def port(self) -> int:
        """Get the daemon port for this project.

        Port is derived deterministically from the project path to support
        multiple CI daemons running simultaneously.
        """
        if self._port is None:
            self._port = get_project_port(self.project_root, self.ci_data_dir)
        return self._port

    def _is_test_environment(self) -> bool:
        """Check if we're running in a test or CI environment.

        Returns:
            True if running in pytest, CI, or non-interactive environment.
        """
        import sys

        # Check if pytest is loaded (most reliable for pytest runs)
        if "pytest" in sys.modules:
            return True

        # Check for common test/CI environment variables
        test_indicators = [
            "PYTEST_CURRENT_TEST",  # Set by pytest
            "CI",  # Common CI indicator
            "GITHUB_ACTIONS",  # GitHub Actions
            "GITLAB_CI",  # GitLab CI
            "JENKINS_URL",  # Jenkins
            "OAK_TESTING",  # Our own testing flag
        ]
        return any(os.environ.get(var) for var in test_indicators)

    def _load_hook_template(self, agent: str) -> dict[str, Any] | None:
        """Load hook template for an agent and substitute port placeholder.

        Args:
            agent: Agent name (claude, cursor, gemini).

        Returns:
            Hook configuration with {{PORT}} replaced, or None if not found.
        """
        template_file = HOOKS_TEMPLATE_DIR / agent / "hooks.json"
        if not template_file.exists():
            logger.warning(f"Hook template not found: {template_file}")
            return None

        try:
            template_content = template_file.read_text()
            # Replace {{PORT}} placeholder with actual port
            processed = re.sub(r"\{\{PORT\}\}", str(self.port), template_content)
            return cast(dict[str, Any], json.loads(processed))
        except Exception as e:
            logger.error(f"Failed to load hook template for {agent}: {e}")
            return None

    def _get_daemon_manager(self) -> Any:
        """Get daemon manager instance."""
        from open_agent_kit.features.codebase_intelligence.daemon.manager import DaemonManager

        return DaemonManager(
            project_root=self.project_root,
            port=self.port,
            ci_data_dir=self.ci_data_dir,
        )

    # Lifecycle hook handlers

    def initialize(self) -> dict:
        """Called when feature is enabled (on_feature_enabled hook).

        Sets up the CI data directory, installs agent hooks, and starts the daemon.
        Gitignore patterns are handled declaratively via the manifest 'gitignore' field.

        Returns:
            Result dictionary with status.
        """
        logger.info("Initializing Codebase Intelligence feature")

        # Create data directory
        self.ci_data_dir.mkdir(parents=True, exist_ok=True)

        # Note: .gitignore is handled declaratively via manifest.yaml gitignore field
        # The feature_service adds .oak/ci/ on enable and removes it on disable

        # Get configured agents and call ensure_daemon to install hooks + start daemon
        # This ensures CI is fully operational whether called from oak init or oak feature add
        # Pass open_browser=True for interactive initialization
        daemon_result = {}
        try:
            from open_agent_kit.services.config_service import ConfigService

            config_service = ConfigService(self.project_root)
            agents = config_service.get_agents()
            daemon_result = self.ensure_daemon(agents, open_browser=True)
        except Exception as e:
            logger.warning(f"Failed to ensure daemon during initialize: {e}")
            daemon_result = {"status": "warning", "message": str(e)}

        return {
            "status": "success",
            "message": "CI feature initialized",
            **daemon_result,
        }

    def cleanup(self, agents: list[str] | None = None) -> dict:
        """Called when feature is disabled (on_feature_disabled hook).

        Performs full cleanup:
        1. Stops the daemon
        2. Removes CI data directory (database, config)
        3. Removes agent hooks
        4. Removes MCP server registrations

        Args:
            agents: List of configured agents to remove hooks from.

        Returns:
            Result dictionary with status.
        """
        import shutil

        from open_agent_kit.utils import print_info, print_success, print_warning

        logger.info("Cleaning up Codebase Intelligence feature")
        print_info("Cleaning up Codebase Intelligence...")

        results: dict[str, bool | dict[str, str]] = {
            "daemon_stopped": False,
            "data_removed": False,
            "hooks_removed": {},
            "mcp_removed": {},
        }

        # 1. Stop the daemon
        try:
            manager = self._get_daemon_manager()
            manager.stop()
            results["daemon_stopped"] = True
            print_success("  Daemon stopped")
        except Exception as e:
            logger.warning(f"Failed to stop daemon: {e}")
            print_warning(f"  Could not stop daemon: {e}")

        # 2. Remove CI data directory (contains ChromaDB, config, logs)
        if self.ci_data_dir.exists():
            try:
                shutil.rmtree(self.ci_data_dir)
                results["data_removed"] = True
                print_success(f"  Data directory removed: {self.ci_data_dir}")
                logger.info(f"Removed CI data directory: {self.ci_data_dir}")
            except Exception as e:
                logger.warning(f"Failed to remove CI data directory: {e}")
                print_warning(f"  Could not remove data directory: {e}")

        # 3. Remove agent hooks
        if agents:
            results["hooks_removed"] = self._remove_agent_hooks(agents)
            hooks_removed = cast(dict[str, str], results["hooks_removed"])
            removed = [a for a, s in hooks_removed.items() if s == "removed"]
            if removed:
                print_success(f"  Hooks removed from: {', '.join(removed)}")

        # 4. Remove MCP server registrations
        if agents:
            results["mcp_removed"] = self.remove_mcp_server(agents)
            mcp_removed = cast(dict[str, str], results["mcp_removed"])
            removed_mcp = [a for a, s in mcp_removed.items() if s == "removed"]
            if removed_mcp:
                print_success(f"  MCP servers removed from: {', '.join(removed_mcp)}")

        return {
            "status": "success",
            "message": "CI feature cleaned up",
            **results,
        }

    def ensure_daemon(self, agents: list[str] | None = None, open_browser: bool = False) -> dict:
        """Ensure the daemon is running and agent hooks are installed.

        Called from initialize() during feature enable. Handles both daemon
        startup and hook installation in one place.

        Args:
            agents: List of configured agents.
            open_browser: If True, open browser to config page after daemon starts.
                          Only set True for interactive initialization.

        Returns:
            Result dictionary with status.
        """
        from open_agent_kit.utils import print_info, print_success, print_warning

        logger.info("Ensuring CI daemon is running")
        print_info("Starting Codebase Intelligence daemon (this may take a moment on first run)...")

        daemon_result = {"status": "unknown", "message": ""}

        try:
            manager = self._get_daemon_manager()
            if manager.ensure_running():
                port = manager.port
                print_success(f"CI daemon running at http://localhost:{port}")
                print_info(f"  Dashboard: http://localhost:{port}/ui")
                daemon_result = {"status": "success", "message": "CI daemon is running"}

                # Auto-launch browser to config page for initial setup
                # Only if explicitly requested AND not in test/CI environment
                if open_browser and not self._is_test_environment():
                    config_url = f"http://localhost:{port}/config"
                    print_info("  Opening config page in browser...")
                    try:
                        webbrowser.open(config_url)
                    except Exception as browser_err:
                        logger.warning(f"Could not open browser: {browser_err}")
                        print_info(f"  Open {config_url} to configure embedding settings")
            else:
                log_file = manager.log_file
                print_warning(f"CI daemon failed to start. Check logs: {log_file}")
                daemon_result = {
                    "status": "warning",
                    "message": f"Failed to start daemon. See {log_file}",
                }
        except Exception as e:
            logger.warning(f"Failed to ensure daemon: {e}")
            print_warning(f"CI daemon error: {e}")
            daemon_result = {"status": "warning", "message": str(e)}

        # Install agent hooks
        hooks_result: dict[str, Any] = {"agents": {}}
        if agents:
            logger.info(f"Installing CI hooks for agents: {agents}")
            hooks_result = self.update_agent_hooks(agents)
            if hooks_result.get("agents"):
                installed = [a for a, s in hooks_result["agents"].items() if s == "updated"]
                if installed:
                    print_info(f"  CI hooks installed for: {', '.join(installed)}")

        # Install MCP servers for agents that support it
        mcp_result: dict[str, Any] = {"agents": {}}
        if agents:
            logger.info(f"Installing MCP servers for agents: {agents}")
            mcp_result["agents"] = self.install_mcp_server(agents)
            installed_mcp = [a for a, s in mcp_result["agents"].items() if s == "installed"]
            if installed_mcp:
                print_info(f"  MCP server registered for: {', '.join(installed_mcp)}")

        return {
            **daemon_result,
            "hooks": hooks_result,
            "mcp": mcp_result,
        }

    def update_agent_hooks(self, agents: list[str]) -> dict:
        """Called when agents change (on_agents_changed hook) or during upgrade.

        Updates agent hook configurations to integrate with CI daemon.
        Note: MCP server registration is handled separately by update_mcp_servers().

        Args:
            agents: List of agent names that are configured.

        Returns:
            Result dictionary with status.
        """
        logger.info(f"Updating CI hooks for agents: {agents}")

        results = {}
        for agent in agents:
            try:
                if agent == "claude":
                    self._update_claude_hooks()
                    results[agent] = "updated"
                elif agent == "cursor":
                    self._update_cursor_hooks()
                    results[agent] = "updated"
                elif agent == "gemini":
                    self._update_gemini_hooks()
                    results[agent] = "updated"
                else:
                    results[agent] = "skipped"
            except Exception as e:
                logger.warning(f"Failed to update hooks for {agent}: {e}")
                results[agent] = f"error: {e}"

        return {"status": "success", "agents": results}

    def update_mcp_servers(self, agents: list[str]) -> dict:
        """Update MCP server registrations for configured agents.

        Called during upgrade or when agents change. Installs/updates MCP
        server configurations for agents that support MCP (has_mcp=true).

        Args:
            agents: List of agent names that are configured.

        Returns:
            Result dictionary with status.
        """
        logger.info(f"Updating MCP servers for agents: {agents}")
        results = self.install_mcp_server(agents)
        return {"status": "success", "agents": results}

    def _is_oak_managed_hook(self, hook: dict, agent_type: str = "claude") -> bool:
        """Check if a hook is managed by OAK.

        Identifies OAK hooks by URL patterns in the command:
        - /api/oak/ci/ - current pattern (unique to OAK)
        - /api/hook/ - legacy pattern (for cleanup during upgrade/removal)

        Both patterns are checked to ensure proper cleanup when transitioning
        from old to new hook formats.

        Args:
            hook: Hook configuration dict.
            agent_type: Type of agent (claude, cursor, gemini) for structure-specific parsing.

        Returns:
            True if the hook is managed by OAK.
        """
        # Extract command based on agent structure
        if agent_type == "cursor":
            # Cursor: simple {command: "..."} structure
            command = hook.get("command", "")
        else:
            # Claude/Gemini: nested {hooks: [{command: "..."}]} structure
            command = hook.get("hooks", [{}])[0].get("command", "")

        # Check for OAK CI URL patterns (current and legacy for cleanup)
        oak_patterns = ["/api/oak/ci/", "/api/hook/"]
        return any(pattern in command for pattern in oak_patterns)

    def _update_claude_hooks(self) -> None:
        """Update Claude Code settings with CI hooks."""
        settings_dir = self.project_root / ".claude"
        settings_file = settings_dir / "settings.json"

        settings_dir.mkdir(exist_ok=True)

        # Load existing settings or create new
        if settings_file.exists():
            with open(settings_file) as f:
                settings = json.load(f)
        else:
            settings = {}

        # Load CI hooks from template
        template = self._load_hook_template("claude")
        if not template:
            logger.error("Failed to load Claude hooks template")
            return

        ci_hooks = template.get("hooks", {})

        # Add CI hooks
        if "hooks" not in settings:
            settings["hooks"] = {}

        # Replace CI hooks (remove old CI hooks, add new ones)
        # Uses _is_oak_managed_hook for safe identification that preserves other integrations
        for event, new_hooks in ci_hooks.items():
            if event not in settings["hooks"]:
                settings["hooks"][event] = []

            # Remove existing OAK-managed hooks for this event
            settings["hooks"][event] = [
                h for h in settings["hooks"][event] if not self._is_oak_managed_hook(h, "claude")
            ]

            # Add new CI hooks
            settings["hooks"][event].extend(new_hooks)

        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Updated Claude hooks at {settings_file}")

    def _update_cursor_hooks(self) -> None:
        """Update Cursor settings with CI hooks."""
        settings_dir = self.project_root / ".cursor"
        hooks_file = settings_dir / "hooks.json"

        settings_dir.mkdir(exist_ok=True)

        # Load existing hooks or create new
        if hooks_file.exists():
            with open(hooks_file) as f:
                hooks = json.load(f)
        else:
            hooks = {"version": 1, "hooks": {}}

        # Ensure hooks key exists
        if "hooks" not in hooks:
            hooks["hooks"] = {}

        # Load CI hooks from template
        template = self._load_hook_template("cursor")
        if not template:
            logger.error("Failed to load Cursor hooks template")
            return

        ci_hooks = template.get("hooks", {})

        # Replace CI hooks (remove old CI hooks, add new ones)
        # Uses _is_oak_managed_hook for safe identification that preserves other integrations
        for event, new_hooks in ci_hooks.items():
            if event not in hooks["hooks"]:
                hooks["hooks"][event] = []

            # Remove existing OAK-managed hooks for this event
            hooks["hooks"][event] = [
                h for h in hooks["hooks"][event] if not self._is_oak_managed_hook(h, "cursor")
            ]

            # Add new CI hooks
            hooks["hooks"][event].extend(new_hooks)

        with open(hooks_file, "w") as f:
            json.dump(hooks, f, indent=2)

        logger.info(f"Updated Cursor hooks at {hooks_file}")

    def _update_gemini_hooks(self) -> None:
        """Update Gemini CLI settings with CI hooks."""
        settings_dir = self.project_root / ".gemini"
        settings_file = settings_dir / "settings.json"

        settings_dir.mkdir(exist_ok=True)

        # Load existing or create new
        if settings_file.exists():
            with open(settings_file) as f:
                settings = json.load(f)
        else:
            settings = {}

        # Load CI hooks from template
        template = self._load_hook_template("gemini")
        if not template:
            logger.error("Failed to load Gemini hooks template")
            return

        ci_hooks = template.get("hooks", {})

        # Add CI hooks
        if "hooks" not in settings:
            settings["hooks"] = {}

        # Replace CI hooks (remove old CI hooks, add new ones)
        # Uses _is_oak_managed_hook for safe identification that preserves other integrations
        for event, new_hooks in ci_hooks.items():
            if event not in settings["hooks"]:
                settings["hooks"][event] = []

            # Remove existing OAK-managed hooks for this event
            settings["hooks"][event] = [
                h for h in settings["hooks"][event] if not self._is_oak_managed_hook(h, "gemini")
            ]

            # Add new CI hooks
            settings["hooks"][event].extend(new_hooks)

        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Updated Gemini hooks at {settings_file}")

    # --- Hook Removal Methods ---

    def _remove_agent_hooks(self, agents: list[str]) -> dict[str, str]:
        """Remove CI hooks from all specified agents.

        Args:
            agents: List of agent names to remove hooks from.

        Returns:
            Dictionary mapping agent names to removal status.
        """
        logger.info(f"Removing CI hooks from agents: {agents}")

        results = {}
        for agent in agents:
            try:
                if agent == "claude":
                    self._remove_claude_hooks()
                    results[agent] = "removed"
                elif agent == "cursor":
                    self._remove_cursor_hooks()
                    results[agent] = "removed"
                elif agent == "gemini":
                    self._remove_gemini_hooks()
                    results[agent] = "removed"
                else:
                    results[agent] = "skipped"
            except Exception as e:
                logger.warning(f"Failed to remove hooks for {agent}: {e}")
                results[agent] = f"error: {e}"

        return results

    def _cleanup_empty_config_file(self, file_path: Path, empty_structures: list[dict]) -> None:
        """Remove config file if it's effectively empty, and parent dir if empty.

        Args:
            file_path: Path to the config file.
            empty_structures: List of JSON structures considered "empty"
                              (e.g., {}, {"hooks": {}}, {"version": 1, "hooks": {}}).
        """
        if not file_path.exists():
            return

        try:
            with open(file_path) as f:
                content = json.load(f)

            # Check if content matches any empty structure
            if content in empty_structures:
                file_path.unlink()
                logger.info(f"Removed empty config file: {file_path}")

                # Remove parent directory if empty
                parent = file_path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    logger.info(f"Removed empty directory: {parent}")
        except (json.JSONDecodeError, OSError):
            pass

    def _remove_claude_hooks(self) -> None:
        """Remove CI hooks from Claude Code settings."""
        settings_file = self.project_root / ".claude" / "settings.json"

        if not settings_file.exists():
            return

        with open(settings_file) as f:
            settings = json.load(f)

        if "hooks" not in settings:
            return

        # Remove OAK-managed hooks from each event
        # Uses _is_oak_managed_hook for safe identification that preserves other integrations
        events_to_remove = []
        for event in settings["hooks"]:
            # Filter out OAK-managed hooks
            settings["hooks"][event] = [
                h for h in settings["hooks"][event] if not self._is_oak_managed_hook(h, "claude")
            ]

            # Track empty event lists for removal
            if not settings["hooks"][event]:
                events_to_remove.append(event)

        # Remove empty event lists
        for event in events_to_remove:
            del settings["hooks"][event]

        # Remove empty hooks section
        if not settings["hooks"]:
            del settings["hooks"]

        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Removed CI hooks from {settings_file}")

        # Clean up if file is now empty
        self._cleanup_empty_config_file(settings_file, [{}, {"hooks": {}}])

    def _remove_cursor_hooks(self) -> None:
        """Remove CI hooks from Cursor settings."""
        hooks_file = self.project_root / ".cursor" / "hooks.json"

        if not hooks_file.exists():
            return

        with open(hooks_file) as f:
            hooks = json.load(f)

        if "hooks" not in hooks:
            return

        # Remove OAK-managed hooks from each event
        # Uses _is_oak_managed_hook for safe identification that preserves other integrations
        events_to_remove = []
        for event in hooks["hooks"]:
            # Filter out OAK-managed hooks
            hooks["hooks"][event] = [
                h for h in hooks["hooks"][event] if not self._is_oak_managed_hook(h, "cursor")
            ]

            # Track empty event lists for removal
            if not hooks["hooks"][event]:
                events_to_remove.append(event)

        # Remove empty event lists
        for event in events_to_remove:
            del hooks["hooks"][event]

        # Remove empty hooks section
        if not hooks.get("hooks"):
            hooks.pop("hooks", None)

        with open(hooks_file, "w") as f:
            json.dump(hooks, f, indent=2)

        logger.info(f"Removed CI hooks from {hooks_file}")

        # Clean up if file is now empty
        self._cleanup_empty_config_file(
            hooks_file, [{}, {"hooks": {}}, {"version": 1}, {"version": 1, "hooks": {}}]
        )

    def _remove_gemini_hooks(self) -> None:
        """Remove CI hooks from Gemini CLI settings."""
        settings_file = self.project_root / ".gemini" / "settings.json"

        if not settings_file.exists():
            return

        with open(settings_file) as f:
            settings = json.load(f)

        if "hooks" not in settings:
            return

        # Remove OAK-managed hooks from each event
        # Uses _is_oak_managed_hook for safe identification that preserves other integrations
        events_to_remove = []
        for event in settings["hooks"]:
            # Filter out OAK-managed hooks
            settings["hooks"][event] = [
                h for h in settings["hooks"][event] if not self._is_oak_managed_hook(h, "gemini")
            ]

            # Track empty event lists for removal
            if not settings["hooks"][event]:
                events_to_remove.append(event)

        # Remove empty event lists
        for event in events_to_remove:
            del settings["hooks"][event]

        # Remove empty hooks section
        if not settings["hooks"]:
            del settings["hooks"]

        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Removed CI hooks from {settings_file}")

        # Clean up if file is now empty
        self._cleanup_empty_config_file(settings_file, [{}, {"hooks": {}}])

    # --- MCP Server Registration Methods ---

    def _load_mcp_config(self) -> dict[str, Any] | None:
        """Load MCP server configuration from mcp.yaml.

        Returns:
            MCP configuration dict, or None if not found.
        """
        import yaml

        mcp_config_path = MCP_TEMPLATE_DIR / "mcp.yaml"
        if not mcp_config_path.exists():
            logger.warning(f"MCP config not found: {mcp_config_path}")
            return None

        try:
            with open(mcp_config_path) as f:
                config = yaml.safe_load(f)
            return cast(dict[str, Any], config)
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            return None

    def _get_agent_has_mcp(self, agent: str) -> bool:
        """Check if an agent has MCP capability.

        Args:
            agent: Agent name (claude, cursor, codex, etc.)

        Returns:
            True if agent supports MCP, False otherwise.
        """
        try:
            from open_agent_kit.services.agent_service import AgentService

            agent_service = AgentService(self.project_root)
            context = agent_service.get_agent_context(agent)
            return bool(context.get("has_mcp", False))
        except Exception as e:
            logger.warning(f"Failed to check MCP capability for {agent}: {e}")
            return False

    def _get_mcp_env(self) -> dict[str, str]:
        """Get environment variables for MCP install/remove scripts.

        Returns:
            Dictionary of environment variables.
        """
        mcp_config = self._load_mcp_config()
        if not mcp_config:
            return {}

        # Build command with {{PROJECT_ROOT}} substitution
        command_template = mcp_config.get("command", "")
        command = command_template.replace("{{PROJECT_ROOT}}", str(self.project_root))

        return {
            "OAK_PROJECT_ROOT": str(self.project_root),
            "OAK_MCP_NAME": mcp_config.get("name", "oak-ci"),
            "OAK_MCP_COMMAND": command,
        }

    def _run_mcp_script(self, agent: str, script_name: str) -> tuple[bool, str]:
        """Run an agent-specific MCP script.

        Args:
            agent: Agent name (claude, cursor, codex).
            script_name: Script name (install.sh or remove.sh).

        Returns:
            Tuple of (success, message).
        """
        import subprocess

        script_path = MCP_TEMPLATE_DIR / agent / script_name
        if not script_path.exists():
            return False, f"Script not found: {script_path}"

        env = self._get_mcp_env()
        if not env:
            return False, "Failed to load MCP configuration"

        # Merge with current environment
        full_env = {**os.environ, **env}

        try:
            result = subprocess.run(
                ["bash", str(script_path)],
                env=full_env,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.project_root),
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip() or result.stdout.strip()

        except subprocess.TimeoutExpired:
            return False, f"Script timed out: {script_path}"
        except Exception as e:
            return False, f"Script error: {e}"

    def install_mcp_server(self, agents: list[str]) -> dict[str, str]:
        """Install MCP server for agents that support it.

        Only installs for agents where has_mcp=True in their manifest.

        Args:
            agents: List of agent names.

        Returns:
            Dictionary mapping agent names to installation status.
        """
        results = {}
        for agent in agents:
            if not self._get_agent_has_mcp(agent):
                results[agent] = "skipped (no MCP support)"
                continue

            script_path = MCP_TEMPLATE_DIR / agent / "install.sh"
            if not script_path.exists():
                results[agent] = "skipped (no install script)"
                continue

            success, message = self._run_mcp_script(agent, "install.sh")
            if success:
                results[agent] = "installed"
                logger.info(f"Installed MCP server for {agent}")
            else:
                results[agent] = f"error: {message}"
                logger.warning(f"Failed to install MCP server for {agent}: {message}")

        return results

    def remove_mcp_server(self, agents: list[str]) -> dict[str, str]:
        """Remove MCP server from agents.

        Args:
            agents: List of agent names.

        Returns:
            Dictionary mapping agent names to removal status.
        """
        results = {}
        for agent in agents:
            script_path = MCP_TEMPLATE_DIR / agent / "remove.sh"
            if not script_path.exists():
                results[agent] = "skipped (no remove script)"
                continue

            success, message = self._run_mcp_script(agent, "remove.sh")
            if success:
                results[agent] = "removed"
                logger.info(f"Removed MCP server for {agent}")
            else:
                results[agent] = f"error: {message}"
                logger.warning(f"Failed to remove MCP server for {agent}: {message}")

        return results


def execute_hook(hook_action: str, project_root: Path, **kwargs: Any) -> dict[str, Any]:
    """Execute a CI hook action.

    This function is called by OAK's feature system to handle
    lifecycle hooks for the codebase-intelligence feature.

    Args:
        hook_action: The action to perform (e.g., "initialize", "cleanup").
        project_root: Root directory of the project.
        **kwargs: Additional arguments passed to the hook.

    Returns:
        Result dictionary from the hook.
    """
    service = CodebaseIntelligenceService(project_root)

    def _get_agents() -> list[str]:
        """Get agents from kwargs or load from config."""
        agents: list[str] = kwargs.get("agents", [])
        if not agents:
            # Load from config (for on_post_upgrade which doesn't pass agents)
            from open_agent_kit.services.config_service import ConfigService

            config = ConfigService(project_root).load_config()
            agents = config.agents
        return agents

    handlers = {
        "initialize": service.initialize,
        "cleanup": lambda: service.cleanup(agents=_get_agents()),
        "on_pre_remove": lambda: service.cleanup(agents=_get_agents()),  # Same as cleanup
        "ensure_daemon": lambda: service.ensure_daemon(agents=_get_agents()),
        # Hooks management
        "update_agent_hooks": lambda: service.update_agent_hooks(_get_agents()),
        # MCP server management (separate from hooks)
        "update_mcp_servers": lambda: service.update_mcp_servers(_get_agents()),
        "remove_mcp_servers": lambda: {
            "status": "success",
            "agents": service.remove_mcp_server(_get_agents()),
        },
    }

    handler = handlers.get(hook_action)
    if not handler:
        return {"status": "error", "message": f"Unknown hook action: {hook_action}"}

    return handler()
