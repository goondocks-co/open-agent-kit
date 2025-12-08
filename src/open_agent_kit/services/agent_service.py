"""Agent service for managing AI agent configurations.

This service manages AI coding agent configurations using manifest files.
Agent manifests define where to install commands, what capabilities the
agent has, and how to render agent-specific prompts.

Lifecycle:
- oak init --agent <name>: Installs agent commands using manifest config
- oak upgrade: Updates agent commands when manifests change
- Feature install: Renders commands with agent-specific context
"""

import os
import shutil
from pathlib import Path

from open_agent_kit.models.agent_manifest import AgentManifest
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.state_service import StateService
from open_agent_kit.utils import (
    cleanup_empty_directories,
    ensure_dir,
    list_files,
    read_file,
    write_file,
)


class AgentService:
    """Service for managing AI agent configurations and commands.

    Loads agent manifests from the package's agents/ directory and provides
    methods for:
    - Getting agent installation paths
    - Getting agent capabilities for template rendering
    - Installing/removing agent commands
    - Validating agent setup
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize agent service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.state_service = StateService(project_root)

        # Package directories
        self.package_root = Path(__file__).parent.parent.parent.parent
        self.package_agents_dir = self.package_root / "agents"
        self.package_features_dir = self.package_root / "features"

        # Cache for loaded manifests
        self._manifest_cache: dict[str, AgentManifest] = {}

    def list_available_agents(self) -> list[str]:
        """List all available agent types from package manifests.

        Returns:
            List of agent names (e.g., ['claude', 'cursor', 'copilot'])
        """
        agents = []
        if self.package_agents_dir.exists():
            for agent_dir in self.package_agents_dir.iterdir():
                if agent_dir.is_dir():
                    manifest_path = agent_dir / "manifest.yaml"
                    if manifest_path.exists():
                        agents.append(agent_dir.name)
        return sorted(agents)

    def get_agent_manifest(self, agent_type: str) -> AgentManifest:
        """Load agent manifest from package.

        Args:
            agent_type: Agent type name (e.g., "claude", "copilot")

        Returns:
            AgentManifest instance

        Raises:
            ValueError: If agent type is unknown
        """
        agent_type = agent_type.lower()

        # Check cache first
        if agent_type in self._manifest_cache:
            return self._manifest_cache[agent_type]

        # Load from package agents directory
        manifest_path = self.package_agents_dir / agent_type / "manifest.yaml"
        if not manifest_path.exists():
            available = self.list_available_agents()
            raise ValueError(
                f"Unknown agent type: {agent_type}. " f"Available agents: {', '.join(available)}"
            )

        manifest = AgentManifest.load(manifest_path)
        self._manifest_cache[agent_type] = manifest
        return manifest

    def get_agent_commands_dir(self, agent_type: str) -> Path:
        """Get native commands directory for an agent.

        Args:
            agent_type: Agent type name (e.g., "claude", "copilot")

        Returns:
            Path to agent's native commands directory

        Examples:
            - claude: project_root/.claude/commands/
            - copilot: project_root/.github/agents/
            - cursor: project_root/.cursor/commands/
        """
        manifest = self.get_agent_manifest(agent_type)
        return self.project_root / manifest.get_commands_dir()

    def get_agents_from_config(self) -> list[str]:
        """Get configured agents from project config.

        Returns:
            List of configured agent names
        """
        config = self.config_service.load_config()
        return config.agents

    def is_agent_configured(self, agent_type: str | None = None) -> bool:
        """Check if an agent (or any agent) is configured.

        Args:
            agent_type: Specific agent type to check (optional)

        Returns:
            True if agent(s) configured, False otherwise
        """
        agents = self.get_agents_from_config()
        if agent_type:
            return agent_type.lower() in [a.lower() for a in agents]
        return len(agents) > 0

    def get_agent_context(self, agent_type: str) -> dict:
        """Get template context for agent-aware command rendering.

        This context is used when installing commands to conditionally render
        agent-specific sections based on each agent's capabilities (web search,
        background agents, MCP tools, etc.).

        Capabilities are resolved in order of precedence:
        1. User config overrides (from .oak/config.yaml agent_capabilities)
        2. Manifest defaults (from agents/{agent}/manifest.yaml)

        Args:
            agent_type: Agent type name (e.g., "claude", "copilot")

        Returns:
            Dictionary with agent context for Jinja2 template rendering

        Examples:
            >>> service = AgentService()
            >>> context = service.get_agent_context('claude')
            >>> context['has_native_web']
            True
            >>> context = service.get_agent_context('codex')
            >>> context['has_native_web']
            False
        """
        manifest = self.get_agent_manifest(agent_type)
        context = manifest.get_template_context()

        # Apply config overrides if present
        config = self.config_service.load_config()
        agent_key = agent_type.lower()

        if agent_key in config.agent_capabilities:
            overrides = config.agent_capabilities[agent_key]
            # Only override non-None values
            if overrides.has_background_agents is not None:
                context["has_background_agents"] = overrides.has_background_agents
            if overrides.has_native_web is not None:
                context["has_native_web"] = overrides.has_native_web
            if overrides.has_mcp is not None:
                context["has_mcp"] = overrides.has_mcp
            if overrides.research_strategy is not None:
                context["research_strategy"] = overrides.research_strategy
            # Check for background_agent_instructions override
            if (
                hasattr(overrides, "background_agent_instructions")
                and overrides.background_agent_instructions is not None
            ):
                context["background_agent_instructions"] = overrides.background_agent_instructions
            # Add any custom capabilities
            if overrides.custom:
                context.update(overrides.custom)

        return context

    def get_capabilities_config(self, agent_type: str) -> dict:
        """Get capabilities from manifest as config-ready dict.

        Used by oak init to populate agent_capabilities in config.yaml with
        manifest defaults, making them visible and editable by users.

        Args:
            agent_type: Agent type name (e.g., "claude", "copilot")

        Returns:
            Dictionary with capability values suitable for config.yaml
        """
        manifest = self.get_agent_manifest(agent_type)
        caps = manifest.capabilities
        return {
            "has_background_agents": caps.has_background_agents,
            "background_agent_instructions": caps.background_agent_instructions,
            "has_native_web": caps.has_native_web,
            "has_mcp": caps.has_mcp,
            "research_strategy": caps.research_strategy,
        }

    def get_command_filename(self, agent_type: str, command_name: str) -> str:
        """Get the full command filename for an agent.

        Args:
            agent_type: Agent type name
            command_name: Command name (e.g., "rfc-create")

        Returns:
            Command filename with proper extension

        Examples:
            - claude: oak.rfc-create.md
            - copilot: oak.rfc-create.agent.md
        """
        manifest = self.get_agent_manifest(agent_type)
        return manifest.get_command_filename(command_name)

    def get_agent_display_name(self, agent_type: str) -> str:
        """Get display name for an agent.

        Args:
            agent_type: Agent type name

        Returns:
            Human-readable display name
        """
        manifest = self.get_agent_manifest(agent_type)
        return manifest.display_name

    def get_agent_instruction_file(self, agent_type: str) -> Path | None:
        """Get path to agent's instruction file.

        Args:
            agent_type: Agent type (claude, copilot, etc.)

        Returns:
            Path to instruction file, or None if not defined

        Examples:
            claude -> .claude/CLAUDE.md
            copilot -> .github/copilot-instructions.md
            cursor -> .cursor/rules.md
        """
        manifest = self.get_agent_manifest(agent_type)
        instruction_path = manifest.get_instruction_file_path()
        if instruction_path:
            return self.project_root / instruction_path
        return None

    def create_agent_commands_dir(self, agent_type: str) -> Path:
        """Create native commands directory for an agent.

        Args:
            agent_type: Agent type name

        Returns:
            Path to agent's native commands directory
        """
        commands_dir = self.get_agent_commands_dir(agent_type)
        ensure_dir(commands_dir)
        return commands_dir

    def list_agent_commands(self, agent_type: str) -> list[Path]:
        """List command files for an agent.

        Args:
            agent_type: Agent type name

        Returns:
            List of command file paths
        """
        commands_dir = self.get_agent_commands_dir(agent_type)

        if not commands_dir.exists():
            return []

        # Get file extension pattern for this agent
        manifest = self.get_agent_manifest(agent_type)
        extension = manifest.installation.file_extension
        pattern = f"oak.*{extension}"

        return list_files(commands_dir, pattern, recursive=False)

    def create_default_commands(
        self, agent_type: str, features: list[str] | None = None
    ) -> list[Path]:
        """Create command templates for an agent based on installed features.

        Args:
            agent_type: Agent type name
            features: List of feature names to install commands for.
                     If None, installs all default features.

        Returns:
            List of created command file paths
        """
        commands_dir = self.create_agent_commands_dir(agent_type)

        # Get features to install commands for
        if features is None:
            from open_agent_kit.constants import DEFAULT_FEATURES

            features = DEFAULT_FEATURES

        created_files = []

        for feature_name in features:
            # Get commands directory for this feature
            feature_commands_dir = self.package_features_dir / feature_name / "commands"
            if not feature_commands_dir.exists():
                continue

            # Get command names from feature config
            from typing import cast

            from open_agent_kit.constants import FEATURE_CONFIG

            feature_config = FEATURE_CONFIG.get(feature_name, {})
            command_names = cast(list[str], feature_config.get("commands", []))

            for command_name in command_names:
                # Read template from feature's commands directory
                template_file = feature_commands_dir / f"oak.{command_name}.md"
                if not template_file.exists():
                    continue

                content = read_file(template_file)

                # Write to agent-specific directory with proper extension
                filename = self.get_command_filename(agent_type, command_name)
                file_path = commands_dir / filename
                if not file_path.exists():
                    write_file(file_path, content)
                    created_files.append(file_path)

        return created_files

    def validate_agent_setup(self, agent_type: str) -> tuple[bool, list[str]]:
        """Validate agent setup and configuration.

        Args:
            agent_type: Agent type name

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        try:
            manifest = self.get_agent_manifest(agent_type)
        except ValueError as e:
            return (False, [str(e)])

        return manifest.validate_installation(self.project_root)

    def remove_agent_commands(self, agent_type: str) -> int:
        """Remove open-agent-kit command files for an agent.

        Only removes files that start with 'oak.' to avoid deleting
        user's custom commands.

        Args:
            agent_type: Agent type name

        Returns:
            Number of files removed
        """
        commands_dir = self.get_agent_commands_dir(agent_type)
        if not commands_dir.exists():
            return 0

        removed_count = 0
        oak_commands = self.list_agent_commands(agent_type)

        for command_file in oak_commands:
            try:
                command_file.unlink()
                removed_count += 1
            except Exception:
                pass

        # Clean up empty directories
        cleanup_empty_directories(commands_dir, self.project_root)

        return removed_count

    def remove_feature_commands(self, agent_type: str, feature_name: str) -> int:
        """Remove commands for a specific feature from an agent.

        Args:
            agent_type: Agent type name
            feature_name: Feature name to remove commands for

        Returns:
            Number of files removed
        """
        from typing import cast

        from open_agent_kit.constants import FEATURE_CONFIG

        commands_dir = self.get_agent_commands_dir(agent_type)
        if not commands_dir.exists():
            return 0

        feature_config = FEATURE_CONFIG.get(feature_name, {})
        command_names = cast(list[str], feature_config.get("commands", []))

        removed_count = 0
        for command_name in command_names:
            filename = self.get_command_filename(agent_type, command_name)
            file_path = commands_dir / filename

            if file_path.exists():
                try:
                    file_path.unlink()
                    removed_count += 1
                except Exception:
                    pass

        cleanup_empty_directories(commands_dir, self.project_root)

        return removed_count

    def get_all_command_names(self) -> list[str]:
        """Get all available command names across all features.

        Returns:
            List of command names (e.g., ['rfc-create', 'constitution-validate'])
        """
        from typing import cast

        from open_agent_kit.constants import FEATURE_CONFIG, SUPPORTED_FEATURES

        all_commands: list[str] = []
        for feature_name in SUPPORTED_FEATURES:
            feature_config = FEATURE_CONFIG.get(feature_name, {})
            command_names = cast(list[str], feature_config.get("commands", []))
            all_commands.extend(command_names)
        return all_commands

    def detect_existing_agent_instructions(self) -> dict[str, dict]:
        """Detect existing agent instruction files for all configured agents.

        Returns:
            Dictionary mapping agent_type to detection info
        """
        configured_agents = self.get_agents_from_config()
        detection_results = {}

        for agent_type in configured_agents:
            agent_type = agent_type.lower()

            try:
                instruction_path = self.get_agent_instruction_file(agent_type)
                if instruction_path is None:
                    continue

                exists = instruction_path.exists()

                content = None
                has_constitution_ref = False
                if exists:
                    try:
                        content = read_file(instruction_path)
                        has_constitution_ref = self._has_constitution_reference(instruction_path)
                    except Exception:
                        content = None

                detection_results[agent_type] = {
                    "exists": exists,
                    "path": instruction_path,
                    "content": content,
                    "has_constitution_ref": has_constitution_ref,
                }

            except ValueError:
                continue

        return detection_results

    def _has_constitution_reference(self, file_path: Path) -> bool:
        """Check if instruction file already references constitution."""
        if not file_path.exists():
            return False

        try:
            content = read_file(file_path)

            constitution_markers = [
                "## Project Constitution",
                "# Project Constitution",
                "### Project Constitution",
                "oak/constitution.md",
                ".oak/constitution.md",
                "See constitution:",
                "Constitution file:",
                "[constitution]",
                "[Constitution]",
            ]

            content_lower = content.lower()
            for marker in constitution_markers:
                if marker.lower() in content_lower:
                    return True

            return False

        except Exception:
            return False

    def update_agent_instructions_from_constitution(
        self, constitution_path: Path, mode: str = "additive"
    ) -> dict[str, list[str]]:
        """Update agent instruction files to reference constitution.

        Args:
            constitution_path: Path to constitution.md file
            mode: Update mode - "additive" (default) or "skip"

        Returns:
            Dictionary with results (updated, created, skipped, backed_up, errors)
        """
        results: dict[str, list[str]] = {
            "updated": [],
            "created": [],
            "skipped": [],
            "backed_up": [],
            "errors": [],
        }

        if not constitution_path.exists():
            results["errors"].append(f"Constitution file not found: {constitution_path}")
            return results

        detection = self.detect_existing_agent_instructions()

        files_to_process = {}
        for agent_type, info in detection.items():
            file_path = info["path"]
            file_key = str(file_path)

            if file_key not in files_to_process:
                files_to_process[file_key] = {
                    "path": file_path,
                    "agents": [],
                    "exists": info["exists"],
                    "has_constitution_ref": info["has_constitution_ref"],
                }

            files_to_process[file_key]["agents"].append(agent_type)

        for file_info in files_to_process.values():
            file_path = file_info["path"]
            agents = file_info["agents"]
            exists = file_info["exists"]
            has_ref = file_info["has_constitution_ref"]

            try:
                if has_ref:
                    for agent in agents:
                        results["skipped"].append(agent)
                    continue

                if mode == "skip" and exists:
                    for agent in agents:
                        results["skipped"].append(agent)
                    continue

                if exists:
                    backup_path = self._append_constitution_reference(file_path, constitution_path)
                    results["backed_up"].append(str(backup_path))
                    for agent in agents:
                        results["updated"].append(agent)
                else:
                    self._create_agent_instruction_file(file_path, constitution_path, agents)
                    for agent in agents:
                        results["created"].append(agent)

            except Exception as e:
                error_msg = f"Failed to process {file_path} for {', '.join(agents)}: {e}"
                results["errors"].append(error_msg)

        return results

    def _append_constitution_reference(self, file_path: Path, constitution_path: Path) -> Path:
        """Append constitution reference to existing file."""
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        shutil.copy2(file_path, backup_path)

        existing_content = read_file(file_path)

        try:
            relative_path = os.path.relpath(constitution_path, file_path.parent)
            relative_path = relative_path.replace("\\", "/")
        except ValueError:
            relative_path = str(constitution_path).replace("\\", "/")

        reference_text = self._get_constitution_reference_template(relative_path)
        updated_content = existing_content.rstrip() + "\n\n" + reference_text

        write_file(file_path, updated_content)

        # Record that we modified this file (existed before oak)
        self.state_service.record_modified_file(
            file_path,
            modification_type="appended",
            marker="## Project Constitution",
        )

        return backup_path

    def _create_agent_instruction_file(
        self, file_path: Path, constitution_path: Path, agent_types: list[str]
    ) -> None:
        """Create new agent instruction file with constitution reference."""
        ensure_dir(file_path.parent)

        try:
            relative_path = os.path.relpath(constitution_path, file_path.parent)
            relative_path = relative_path.replace("\\", "/")
        except ValueError:
            relative_path = str(constitution_path).replace("\\", "/")

        if len(agent_types) == 1:
            agent_name = self.get_agent_display_name(agent_types[0])
            header = f"# {agent_name} Instructions\n\n"
            intro = f"This file contains instructions for {agent_name} when working with this project.\n\n"
        else:
            agent_names = [self.get_agent_display_name(a) for a in agent_types]
            header = "# AI Assistant Instructions\n\n"
            intro = f"This file contains instructions for AI assistants ({', '.join(agent_names)}) when working with this project.\n\n"

        reference_text = self._get_constitution_reference_template(relative_path)
        content = header + intro + reference_text

        write_file(file_path, content)

        # Record that we created this file (can safely remove later)
        self.state_service.record_created_file(file_path, content)

    def _get_constitution_reference_template(self, constitution_relative_path: str) -> str:
        """Get template text for constitution reference."""
        template = f"""---

## Project Constitution

This project follows engineering standards and conventions defined in the project constitution.

**Read the constitution first:** [{constitution_relative_path}]({constitution_relative_path})

The constitution defines:
- Architecture principles and patterns
- Code standards and best practices
- Testing requirements
- Documentation standards
- Governance and decision-making processes

All suggestions and code generated must align with the constitution.
"""
        return template


def get_agent_service(project_root: Path | None = None) -> AgentService:
    """Get an AgentService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        AgentService instance
    """
    return AgentService(project_root)
