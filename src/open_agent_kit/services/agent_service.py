"""Agent service for managing AI agent configurations."""

import os
import shutil
from pathlib import Path

from open_agent_kit.constants import AGENT_CONFIG, AGENT_INSTRUCTION_PATTERNS
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.utils import (
    cleanup_empty_directories,
    ensure_dir,
    list_files,
    read_file,
    write_file,
)


class AgentService:
    """Service for managing AI agent configurations and commands.

    Following each agents pattern: installs commands in each agent's native directory
    (.claude/commands/, .github/agents/, etc.) instead of requiring API keys.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize agent service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)

        # Package templates directory (where command templates are stored)
        self.package_templates_dir = (
            Path(__file__).parent.parent.parent.parent / "templates" / "commands"
        )

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
        agent_config = AGENT_CONFIG.get(agent_type.lower())
        if not agent_config:
            raise ValueError(f"Unknown agent type: {agent_type}")

        folder = str(agent_config["folder"])
        subfolder = str(agent_config["commands_subfolder"])
        return self.project_root / folder / subfolder

    def get_agents_from_config(self) -> list[str]:
        """Get configured agents from config.

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

    def get_agent_config(self, agent_type: str) -> dict:
        """Get configuration for an agent type.

        Args:
            agent_type: Agent type name (e.g., "claude", "copilot")

        Returns:
            Agent configuration dictionary
        """
        return AGENT_CONFIG.get(agent_type.lower(), {})

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
        agent_config = self.get_agent_config(agent_type)
        if not agent_config:
            raise ValueError(f"Unknown agent type: {agent_type}")

        extension = agent_config["file_extension"]
        return f"oak.{command_name}{extension}"

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
        agent_config = self.get_agent_config(agent_type)
        extension = agent_config.get("file_extension", ".md")
        pattern = f"oak.*{extension}"

        return list_files(commands_dir, pattern, recursive=False)

    def create_default_commands(self, agent_type: str) -> list[Path]:
        """Create default command templates for an agent in native directory.

        Args:
            agent_type: Agent type name

        Returns:
            List of created command file paths

        Examples:
            For claude: Creates .claude/commands/oak.rfc-create.md
            For copilot: Creates .github/agents/oak.rfc-create.agent.md
        """
        commands_dir = self.create_agent_commands_dir(agent_type)

        # Default command templates to copy
        command_names = [
            "rfc-create",
            "rfc-list",
            "rfc-validate",
            "issue-plan",
            "issue-implement",
            "issue-validate",
            "constitution-create",
            "constitution-validate",
            "constitution-amend",
        ]

        created_files = []
        for command_name in command_names:
            # Read template from package
            template_file = self.package_templates_dir / f"oak.{command_name}.md"
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
        issues = []

        # Check if agent is supported
        if agent_type.lower() not in AGENT_CONFIG:
            issues.append(f"Unsupported agent type: {agent_type}")
            return (False, issues)

        # Check if native commands directory exists
        commands_dir = self.get_agent_commands_dir(agent_type)
        if not commands_dir.exists():
            agent_config = self.get_agent_config(agent_type)
            folder = agent_config["folder"]
            issues.append(
                f"Commands directory not found: {commands_dir}. "
                f"Run 'oak init --agent {agent_type}' to create {folder} structure."
            )

        # Check if any commands exist
        if commands_dir.exists():
            commands = self.list_agent_commands(agent_type)
            if not commands:
                issues.append(
                    f"No oak commands found in {commands_dir}. "
                    "Run 'oak init' to install default commands."
                )

        return (len(issues) == 0, issues)

    def remove_agent_commands(self, agent_type: str) -> int:
        """Remove open-agent-kit command files for an agent.

        Only removes files that start with 'oak.' to avoid deleting
        user's custom commands. Also removes empty directories if we
        created them.

        Args:
            agent_type: Agent type name

        Returns:
            Number of files removed

        Examples:
            Removes: oak.rfc-create.md, oak.issue-plan.md
            Keeps: custom-command.md, user-prompt.md
            Cleans: .codex/prompts/ if empty after cleanup
        """
        commands_dir = self.get_agent_commands_dir(agent_type)
        if not commands_dir.exists():
            return 0

        removed_count = 0
        # List all open-agent-kit commands (files starting with 'oak.')
        oak_commands = self.list_agent_commands(agent_type)

        for command_file in oak_commands:
            try:
                command_file.unlink()
                removed_count += 1
            except Exception:
                # Continue removing other files even if one fails
                pass

        # Clean up empty directories if we emptied them
        cleanup_empty_directories(commands_dir, self.project_root)

        return removed_count

    def get_agent_display_name(self, agent_type: str) -> str:
        """Get display name for an agent.

        Args:
            agent_type: Agent type name

        Returns:
            Display name
        """
        agent_config = self.get_agent_config(agent_type)
        return str(agent_config.get("name", agent_type.capitalize()))

    def get_agent_instruction_file(self, agent_type: str) -> Path:
        """Get path to agent's instruction file.

        Args:
            agent_type: Agent type (claude, copilot, etc.)

        Returns:
            Path to instruction file

        Examples:
            claude → .claude/CLAUDE.md
            copilot → .github/copilot-instructions.md
            cursor → AGENTS.md (root)
        """
        agent_type = agent_type.lower()

        # Get the instruction pattern for this agent
        if agent_type not in AGENT_INSTRUCTION_PATTERNS:
            raise ValueError(f"Unknown agent type: {agent_type}")

        pattern = AGENT_INSTRUCTION_PATTERNS[agent_type]

        # Replace {agent_folder} placeholder if present
        if "{agent_folder}" in pattern:
            agent_config = self.get_agent_config(agent_type)
            if not agent_config:
                raise ValueError(f"No configuration for agent: {agent_type}")
            agent_folder = agent_config["folder"]
            pattern = pattern.replace("{agent_folder}", agent_folder)

        # Return path relative to project root
        return self.project_root / pattern

    def detect_existing_agent_instructions(self) -> dict[str, dict]:
        """Detect existing agent instruction files for all configured agents.

        Returns:
            Dictionary mapping agent_type to detection info:
            {
                'copilot': {
                    'exists': True,
                    'path': Path('.github/copilot-instructions.md'),
                    'content': '...',
                    'has_constitution_ref': False
                },
                'claude': {
                    'exists': False,
                    'path': Path('.claude/CLAUDE.md'),
                    'content': None,
                    'has_constitution_ref': False
                }
            }
        """
        # Get configured agents from config
        configured_agents = self.get_agents_from_config()

        detection_results = {}

        for agent_type in configured_agents:
            agent_type = agent_type.lower()

            try:
                # Get instruction file path
                instruction_path = self.get_agent_instruction_file(agent_type)

                # Check if file exists
                exists = instruction_path.exists()

                # Read content if file exists
                content = None
                has_constitution_ref = False
                if exists:
                    try:
                        content = read_file(instruction_path)
                        has_constitution_ref = self._has_constitution_reference(instruction_path)
                    except Exception:
                        # File might exist but be unreadable
                        content = None

                detection_results[agent_type] = {
                    "exists": exists,
                    "path": instruction_path,
                    "content": content,
                    "has_constitution_ref": has_constitution_ref,
                }

            except ValueError:
                # Unknown agent type - skip
                continue

        # Handle shared files (cursor and codex both use AGENTS.md)
        # If both are configured and use the same file, they'll have identical results
        # This is intentional as they share the same instruction file

        return detection_results

    def _has_constitution_reference(self, file_path: Path) -> bool:
        """Check if instruction file already references constitution.

        Looks for markers:
        - "## Project Constitution"
        - "oak/constitution.md"

        Args:
            file_path: Path to instruction file

        Returns:
            True if already has reference
        """
        if not file_path.exists():
            return False

        try:
            content = read_file(file_path)

            # Check for various constitution reference markers
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

            # Case-insensitive check for any of the markers
            content_lower = content.lower()
            for marker in constitution_markers:
                if marker.lower() in content_lower:
                    return True

            return False

        except Exception:
            # If we can't read the file, assume no reference
            return False

    def update_agent_instructions_from_constitution(
        self, constitution_path: Path, mode: str = "additive"
    ) -> dict[str, list[str]]:
        """Update agent instruction files to reference constitution.

        Strategy:
        - Existing file WITHOUT ref → Append constitution section + backup
        - Existing file WITH ref → Skip (idempotent)
        - No file → Create new with constitution reference
        - Shared files (AGENTS.md) → Update once, affects multiple agents

        Args:
            constitution_path: Path to constitution.md file
            mode: Update mode - "additive" (default) or "skip"

        Returns:
            Dictionary with results:
            {
                'updated': ['copilot'],  # Files appended to
                'created': ['claude'],   # New files created
                'skipped': ['cursor'],   # Already had reference
                'backed_up': ['.github/copilot-instructions.md.backup'],
                'errors': []
            }

        Examples:
            >>> service = AgentService()
            >>> results = service.update_agent_instructions_from_constitution(
            ...     Path("oak/constitution.md")
            ... )
            >>> print(f"Updated: {results['updated']}")
            >>> print(f"Created: {results['created']}")
        """
        results: dict[str, list[str]] = {
            "updated": [],
            "created": [],
            "skipped": [],
            "backed_up": [],
            "errors": [],
        }

        # Validate constitution file exists
        if not constitution_path.exists():
            results["errors"].append(f"Constitution file not found: {constitution_path}")
            return results

        # Get detection results for all configured agents
        detection = self.detect_existing_agent_instructions()

        # Group agents by file path to handle shared files
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

        # Process each unique file
        for _file_key, file_info in files_to_process.items():
            file_path = file_info["path"]
            agents = file_info["agents"]
            exists = file_info["exists"]
            has_ref = file_info["has_constitution_ref"]

            try:
                # Skip if already has constitution reference
                if has_ref:
                    for agent in agents:
                        results["skipped"].append(agent)
                    continue

                # Skip mode - don't modify existing files
                if mode == "skip" and exists:
                    for agent in agents:
                        results["skipped"].append(agent)
                    continue

                # Process the file
                if exists:
                    # Append to existing file
                    backup_path = self._append_constitution_reference(file_path, constitution_path)
                    results["backed_up"].append(str(backup_path))
                    for agent in agents:
                        results["updated"].append(agent)
                else:
                    # Create new file
                    self._create_agent_instruction_file(file_path, constitution_path, agents)
                    for agent in agents:
                        results["created"].append(agent)

            except Exception as e:
                error_msg = f"Failed to process {file_path} for {', '.join(agents)}: {e}"
                results["errors"].append(error_msg)

        return results

    def _append_constitution_reference(self, file_path: Path, constitution_path: Path) -> Path:
        """Append constitution reference to existing file.

        Safety:
        - Creates backup with .backup extension
        - Adds separator line before reference
        - Uses relative path from file location

        Args:
            file_path: Path to existing instruction file
            constitution_path: Path to constitution.md

        Returns:
            Path to backup file

        Raises:
            IOError: If file operations fail

        Examples:
            >>> service = AgentService()
            >>> backup = service._append_constitution_reference(
            ...     Path(".github/copilot-instructions.md"),
            ...     Path("oak/constitution.md")
            ... )
            >>> print(f"Backup created: {backup}")
        """
        # Create backup
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        shutil.copy2(file_path, backup_path)

        # Read existing content
        existing_content = read_file(file_path)

        # Calculate relative path from file location to constitution
        try:
            relative_path = os.path.relpath(constitution_path, file_path.parent)
            # Normalize path separators for markdown links
            relative_path = relative_path.replace("\\", "/")
        except ValueError:
            # If on different drives (Windows), use absolute path
            relative_path = str(constitution_path).replace("\\", "/")

        # Get constitution reference template
        reference_text = self._get_constitution_reference_template(relative_path)

        # Append with proper separator
        updated_content = existing_content.rstrip() + "\n\n" + reference_text

        # Write updated content
        write_file(file_path, updated_content)

        return backup_path

    def _create_agent_instruction_file(
        self, file_path: Path, constitution_path: Path, agent_types: list[str]
    ) -> None:
        """Create new agent instruction file with constitution reference.

        Args:
            file_path: Path where file should be created
            constitution_path: Path to constitution.md
            agent_types: List of agents using this file (for shared files)

        Raises:
            IOError: If file operations fail

        Examples:
            >>> service = AgentService()
            >>> service._create_agent_instruction_file(
            ...     Path(".claude/CLAUDE.md"),
            ...     Path("oak/constitution.md"),
            ...     ["claude"]
            ... )
        """
        # Ensure parent directory exists
        ensure_dir(file_path.parent)

        # Calculate relative path from file location to constitution
        try:
            relative_path = os.path.relpath(constitution_path, file_path.parent)
            # Normalize path separators for markdown links
            relative_path = relative_path.replace("\\", "/")
        except ValueError:
            # If on different drives (Windows), use absolute path
            relative_path = str(constitution_path).replace("\\", "/")

        # Create header based on agent types
        if len(agent_types) == 1:
            agent_name = self.get_agent_display_name(agent_types[0])
            header = f"# {agent_name} Instructions\n\n"
            intro = f"This file contains instructions for {agent_name} when working with this project.\n\n"
        else:
            agent_names = [self.get_agent_display_name(a) for a in agent_types]
            header = "# AI Assistant Instructions\n\n"
            intro = f"This file contains instructions for AI assistants ({', '.join(agent_names)}) when working with this project.\n\n"

        # Get constitution reference template
        reference_text = self._get_constitution_reference_template(relative_path)

        # Combine header, intro, and constitution reference
        content = header + intro + reference_text

        # Write the file
        write_file(file_path, content)

    def _get_constitution_reference_template(self, constitution_relative_path: str) -> str:
        """Get template text for constitution reference.

        Args:
            constitution_relative_path: Relative path to constitution

        Returns:
            Markdown template text to append/insert

        Examples:
            >>> service = AgentService()
            >>> template = service._get_constitution_reference_template(
            ...     "../oak/constitution.md"
            ... )
            >>> print(template[:50])  # First 50 chars
        """
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
