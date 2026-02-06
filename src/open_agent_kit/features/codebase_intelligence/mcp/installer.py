"""MCP server installer module.

Provides a generic Python-based installer for MCP servers that reads
configuration from agent manifests. Replaces platform-specific shell scripts.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.models.agent_manifest import AgentManifest, AgentMcpConfig

logger = logging.getLogger(__name__)

# Conservative allowlist for CLI argument values (server names, commands).
# Rejects shell metacharacters that could enable command injection.
_SAFE_VALUE_RE = re.compile(r"^[a-zA-Z0-9._\- ]+$")


def _validate_cli_value(value: str, label: str) -> None:
    """Validate a CLI argument value against the safe-character allowlist.

    Args:
        value: The value to validate (e.g., server name or command string).
        label: Human-readable label for error messages (e.g., "server_name").

    Raises:
        ValueError: If the value contains disallowed characters.
    """
    if not value or not _SAFE_VALUE_RE.match(value):
        raise ValueError(
            f"Unsafe characters in {label}: {value!r}. "
            f"Only alphanumerics, dots, hyphens, underscores, and spaces are allowed."
        )


@dataclass
class InstallResult:
    """Result of an MCP install/remove operation."""

    success: bool
    message: str
    method: str = "unknown"  # "cli" or "json"


class MCPInstaller:
    """Generic MCP server installer using manifest-driven configuration.

    Reads all configuration from the agent's manifest.yaml mcp: section,
    eliminating the need for separate shell scripts per agent.

    Installation strategy:
    1. Try CLI command if available in manifest (preferred)
    2. Fall back to direct JSON manipulation if CLI fails or unavailable

    Example usage:
        installer = MCPInstaller(
            project_root=Path("/path/to/project"),
            agent="claude",
            server_name="oak-ci",
            command="oak ci mcp"
        )
        result = installer.install()
    """

    def __init__(
        self,
        project_root: Path,
        agent: str,
        server_name: str,
        command: str,
    ):
        """Initialize MCP installer.

        Args:
            project_root: Project root directory.
            agent: Agent name (e.g., "claude", "cursor").
            server_name: Name for the MCP server (e.g., "oak-ci").
            command: Full command to run the MCP server (e.g., "oak ci mcp").
        """
        self.project_root = project_root
        self.agent = agent
        self.server_name = server_name
        self.command = command
        self._manifest: AgentManifest | None = None
        self._mcp_config: AgentMcpConfig | None = None

    @property
    def manifest(self) -> AgentManifest:
        """Load and cache agent manifest."""
        if self._manifest is None:
            from open_agent_kit.services.agent_service import AgentService

            agent_service = AgentService(self.project_root)
            self._manifest = agent_service.get_agent_manifest(self.agent)
        return self._manifest

    @property
    def mcp_config(self) -> AgentMcpConfig | None:
        """Get MCP config from manifest."""
        if self._mcp_config is None:
            self._mcp_config = self.manifest.mcp
        return self._mcp_config

    def install(self) -> InstallResult:
        """Install MCP server for the agent.

        Tries CLI first if available, falls back to config file manipulation.

        Returns:
            InstallResult with success status and details.
        """
        if not self.mcp_config:
            return InstallResult(
                success=False,
                message=f"No MCP configuration in manifest for {self.agent}",
            )

        # Try CLI first if available
        if self._has_cli():
            result = self._install_via_cli()
            if result.success:
                return result
            logger.info(f"CLI install failed for {self.agent}, falling back to config file")

        # Fall back to config file manipulation (JSON or TOML based on format)
        return self._install_via_config()

    def remove(self) -> InstallResult:
        """Remove MCP server from the agent.

        Tries CLI first if available, falls back to config file manipulation.

        Returns:
            InstallResult with success status and details.
        """
        if not self.mcp_config:
            return InstallResult(
                success=False,
                message=f"No MCP configuration in manifest for {self.agent}",
            )

        # Try CLI first if available
        if self._has_cli(for_remove=True):
            result = self._remove_via_cli()
            if result.success:
                return result
            logger.info(f"CLI remove failed for {self.agent}, falling back to config file")

        # Fall back to config file manipulation (JSON or TOML based on format)
        return self._remove_via_config()

    def _has_cli(self, for_remove: bool = False) -> bool:
        """Check if agent has CLI support for MCP operations."""
        if not self.mcp_config or not self.mcp_config.cli:
            return False

        if for_remove:
            return bool(self.mcp_config.cli.remove)
        return bool(self.mcp_config.cli.install)

    def _get_cli_binary(self) -> str | None:
        """Extract CLI binary name from the CLI install command."""
        if not self.mcp_config or not self.mcp_config.cli or not self.mcp_config.cli.install:
            return None

        # First word of the install command is the binary
        cmd = self.mcp_config.cli.install.split()[0]
        return cmd

    def _cli_is_available(self) -> bool:
        """Check if the CLI binary is available on PATH."""
        binary = self._get_cli_binary()
        if not binary:
            return False
        return shutil.which(binary) is not None

    def _install_via_cli(self) -> InstallResult:
        """Install MCP server using CLI command."""
        if not self.mcp_config or not self.mcp_config.cli or not self.mcp_config.cli.install:
            return InstallResult(
                success=False,
                message="No CLI install command configured",
            )

        if not self._cli_is_available():
            binary = self._get_cli_binary()
            return InstallResult(
                success=False,
                message=f"CLI binary '{binary}' not found on PATH",
            )

        # Build command with placeholders replaced
        cmd_template = self.mcp_config.cli.install
        cmd = cmd_template.format(
            name=self.server_name,
            command=self.command,
        )

        try:
            # Defense-in-depth: validate BEFORE shell expansion
            _validate_cli_value(self.server_name, "server_name")
            _validate_cli_value(self.command, "command")

            # For some agents, we need to remove first to make it idempotent
            if self.mcp_config.cli.remove:
                remove_cmd = self.mcp_config.cli.remove.format(name=self.server_name)
                subprocess.run(
                    shlex.split(remove_cmd),
                    cwd=str(self.project_root),
                    capture_output=True,
                    timeout=30,
                )

            result = subprocess.run(
                shlex.split(cmd),
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return InstallResult(
                    success=True,
                    message=f"MCP server '{self.server_name}' installed via CLI",
                    method="cli",
                )
            else:
                return InstallResult(
                    success=False,
                    message=f"CLI failed: {result.stderr.strip() or result.stdout.strip()}",
                    method="cli",
                )

        except ValueError as e:
            return InstallResult(
                success=False,
                message=f"CLI validation error: {e}",
                method="cli",
            )
        except subprocess.TimeoutExpired:
            return InstallResult(
                success=False,
                message="CLI command timed out",
                method="cli",
            )
        except Exception as e:
            return InstallResult(
                success=False,
                message=f"CLI error: {e}",
                method="cli",
            )

    def _remove_via_cli(self) -> InstallResult:
        """Remove MCP server using CLI command."""
        if not self.mcp_config or not self.mcp_config.cli or not self.mcp_config.cli.remove:
            return InstallResult(
                success=False,
                message="No CLI remove command configured",
            )

        if not self._cli_is_available():
            binary = self._get_cli_binary()
            return InstallResult(
                success=False,
                message=f"CLI binary '{binary}' not found on PATH",
            )

        cmd_template = self.mcp_config.cli.remove
        cmd = cmd_template.format(name=self.server_name)

        try:
            # Defense-in-depth: validate BEFORE shell expansion
            _validate_cli_value(self.server_name, "server_name")

            result = subprocess.run(
                shlex.split(cmd),
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Consider success even if server wasn't registered (idempotent)
            if result.returncode == 0 or "not found" in result.stderr.lower():
                return InstallResult(
                    success=True,
                    message=f"MCP server '{self.server_name}' removed via CLI",
                    method="cli",
                )
            else:
                return InstallResult(
                    success=False,
                    message=f"CLI failed: {result.stderr.strip() or result.stdout.strip()}",
                    method="cli",
                )

        except ValueError as e:
            return InstallResult(
                success=False,
                message=f"CLI validation error: {e}",
                method="cli",
            )
        except subprocess.TimeoutExpired:
            return InstallResult(
                success=False,
                message="CLI command timed out",
                method="cli",
            )
        except Exception as e:
            return InstallResult(
                success=False,
                message=f"CLI error: {e}",
                method="cli",
            )

    def _install_via_config(self) -> InstallResult:
        """Install MCP server by directly manipulating the config file.

        Routes to JSON or TOML handler based on manifest format setting.
        """
        if not self.mcp_config:
            return InstallResult(
                success=False,
                message="No MCP configuration available",
            )

        config_format = self.mcp_config.format
        if config_format == "toml":
            return self._install_via_toml()
        else:
            return self._install_via_json()

    def _install_via_json(self) -> InstallResult:
        """Install MCP server by directly manipulating the JSON config file."""
        if not self.mcp_config:
            return InstallResult(
                success=False,
                message="No MCP configuration available",
            )

        config_path = self.project_root / self.mcp_config.config_file
        servers_key = self.mcp_config.servers_key

        # Parse command into parts
        parts = self.command.split()
        cmd = parts[0] if parts else self.command
        args = parts[1:] if len(parts) > 1 else []

        try:
            # Ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing config or create new
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
            else:
                config = {}

            # Ensure servers key exists
            if servers_key not in config:
                config[servers_key] = {}

            # Build server entry based on agent's entry_format
            server_entry = self._build_server_entry(cmd, args)

            # Add/update server entry
            config[servers_key][self.server_name] = server_entry

            # Write config
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            return InstallResult(
                success=True,
                message=f"MCP server '{self.server_name}' registered in {config_path}",
                method="json",
            )

        except (OSError, json.JSONDecodeError) as e:
            return InstallResult(
                success=False,
                message=f"JSON manipulation failed: {e}",
                method="json",
            )

    def _install_via_toml(self) -> InstallResult:
        """Install MCP server by directly manipulating the TOML config file.

        Used for Codex which stores MCP config in .codex/config.toml with
        [mcp_servers.<name>] section format.
        """
        import tomllib

        try:
            import tomli_w
        except ImportError:
            return InstallResult(
                success=False,
                message="TOML write support requires 'tomli_w' package",
                method="toml",
            )

        if not self.mcp_config:
            return InstallResult(
                success=False,
                message="No MCP configuration available",
            )

        config_path = self.project_root / self.mcp_config.config_file
        servers_key = self.mcp_config.servers_key  # e.g., "mcp_servers"

        # Parse command into parts
        parts = self.command.split()
        cmd = parts[0] if parts else self.command
        args = parts[1:] if len(parts) > 1 else []

        try:
            # Ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing config or create new
            if config_path.exists():
                with open(config_path, "rb") as f:
                    config = tomllib.load(f)
            else:
                config = {}

            # Ensure servers key exists
            if servers_key not in config:
                config[servers_key] = {}

            # Build server entry based on agent's entry_format
            server_entry = self._build_server_entry(cmd, args)

            # Add/update server entry
            config[servers_key][self.server_name] = server_entry

            # Write config
            with open(config_path, "wb") as f:
                tomli_w.dump(config, f)

            return InstallResult(
                success=True,
                message=f"MCP server '{self.server_name}' registered in {config_path}",
                method="toml",
            )

        except (OSError, tomllib.TOMLDecodeError) as e:
            return InstallResult(
                success=False,
                message=f"TOML manipulation failed: {e}",
                method="toml",
            )

    def _remove_via_config(self) -> InstallResult:
        """Remove MCP server by directly manipulating the config file.

        Routes to JSON or TOML handler based on manifest format setting.
        """
        if not self.mcp_config:
            return InstallResult(
                success=False,
                message="No MCP configuration available",
            )

        config_format = self.mcp_config.format
        if config_format == "toml":
            return self._remove_via_toml()
        else:
            return self._remove_via_json()

    def _remove_via_json(self) -> InstallResult:
        """Remove MCP server by directly manipulating the JSON config file."""
        if not self.mcp_config:
            return InstallResult(
                success=False,
                message="No MCP configuration available",
            )

        config_path = self.project_root / self.mcp_config.config_file
        servers_key = self.mcp_config.servers_key

        # If config file doesn't exist, nothing to remove
        if not config_path.exists():
            return InstallResult(
                success=True,
                message=f"Config file {config_path} doesn't exist, nothing to remove",
                method="json",
            )

        try:
            with open(config_path) as f:
                config = json.load(f)

            # Remove server if present
            if servers_key in config and self.server_name in config[servers_key]:
                del config[servers_key][self.server_name]

                # Clean up empty servers section
                if not config[servers_key]:
                    del config[servers_key]

                # Write updated config (or remove file if empty)
                if config:
                    with open(config_path, "w") as f:
                        json.dump(config, f, indent=2)
                else:
                    config_path.unlink()

                return InstallResult(
                    success=True,
                    message=f"MCP server '{self.server_name}' removed from {config_path}",
                    method="json",
                )
            else:
                return InstallResult(
                    success=True,
                    message=f"MCP server '{self.server_name}' not found, nothing to remove",
                    method="json",
                )

        except (OSError, json.JSONDecodeError) as e:
            return InstallResult(
                success=False,
                message=f"JSON manipulation failed: {e}",
                method="json",
            )

    def _remove_via_toml(self) -> InstallResult:
        """Remove MCP server by directly manipulating the TOML config file.

        Used for Codex which stores MCP config in .codex/config.toml.
        """
        import tomllib

        try:
            import tomli_w
        except ImportError:
            return InstallResult(
                success=False,
                message="TOML write support requires 'tomli_w' package",
                method="toml",
            )

        if not self.mcp_config:
            return InstallResult(
                success=False,
                message="No MCP configuration available",
            )

        config_path = self.project_root / self.mcp_config.config_file
        servers_key = self.mcp_config.servers_key

        # If config file doesn't exist, nothing to remove
        if not config_path.exists():
            return InstallResult(
                success=True,
                message=f"Config file {config_path} doesn't exist, nothing to remove",
                method="toml",
            )

        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)

            # Remove server if present
            if servers_key in config and self.server_name in config[servers_key]:
                del config[servers_key][self.server_name]

                # Clean up empty servers section
                if not config[servers_key]:
                    del config[servers_key]

                # Write updated config (don't remove file - may have other settings)
                with open(config_path, "wb") as f:
                    tomli_w.dump(config, f)

                return InstallResult(
                    success=True,
                    message=f"MCP server '{self.server_name}' removed from {config_path}",
                    method="toml",
                )
            else:
                return InstallResult(
                    success=True,
                    message=f"MCP server '{self.server_name}' not found, nothing to remove",
                    method="toml",
                )

        except (OSError, tomllib.TOMLDecodeError) as e:
            return InstallResult(
                success=False,
                message=f"TOML manipulation failed: {e}",
                method="toml",
            )

    def _build_server_entry(self, cmd: str, args: list[str]) -> dict:
        """Build the server entry dict based on agent's entry_format.

        Args:
            cmd: Command executable (e.g., "oak")
            args: Command arguments (e.g., ["ci", "mcp"])

        Returns:
            Server entry dictionary for the config file.
        """
        if not self.mcp_config or not self.mcp_config.entry_format:
            # Default format (most common)
            return {
                "command": cmd,
                "args": args,
            }

        entry_format = self.mcp_config.entry_format.copy()

        # Replace placeholders in the entry format
        # Handle different placeholder patterns
        result: dict[str, str | list[str] | dict[str, str]] = {}
        for key, value in entry_format.items():
            if isinstance(value, str):
                if value == "{cmd}":
                    result[key] = cmd
                elif value == "{args}":
                    result[key] = args
                elif value == "{command_array}":
                    # Special case: OpenCode uses full command as array
                    result[key] = [cmd] + args
                else:
                    result[key] = value
            else:
                result[key] = value

        return result
