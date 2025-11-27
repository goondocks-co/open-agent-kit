"""Agent file generation service for constitution."""

from datetime import date
from pathlib import Path

import yaml

from open_agent_kit.constants import (
    AGENT_CONFIG,
    AGENT_INSTRUCTION_PATTERNS,
    CONFIG_FILE,
    OAK_DIR,
    SUPPORTED_AGENTS,
)
from open_agent_kit.models.constitution import ConstitutionDocument
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.template_service import TemplateService
from open_agent_kit.utils import ensure_dir, file_exists, read_file, write_file


class AgentFileService:
    """Service for generating and managing agent instruction files."""

    def __init__(self, project_root: Path | None = None):
        """Initialize agent file service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.template_service = TemplateService(project_root=project_root)
        self.config_path = self.project_root / OAK_DIR / CONFIG_FILE

    def detect_installed_agents(self) -> list[str]:
        """Detect which agents are installed/configured.

        Returns:
            List of installed agent names
        """
        installed_agents: list[str] = []

        # Check config file
        if file_exists(self.config_path):
            try:
                config_content = read_file(self.config_path)
                config = yaml.safe_load(config_content)
                configured_agents = config.get("agents", [])
                installed_agents.extend(configured_agents)
            except Exception:
                # If config can't be read, fall back to directory detection
                pass

        # Check for agent directories
        for agent in SUPPORTED_AGENTS:
            if agent == "none":
                continue

            if agent in AGENT_CONFIG:
                agent_folder = str(AGENT_CONFIG[agent]["folder"])
                agent_dir = self.project_root / agent_folder
                if agent_dir.exists() and agent not in installed_agents:
                    installed_agents.append(agent)

        return list(set(installed_agents))  # Remove duplicates

    def list_agent_files(self) -> dict[str, Path | None]:
        """List all agent instruction file paths.

        Returns:
            Dict mapping agent name to file path (None if file doesn't exist)
        """
        agents = self.detect_installed_agents()
        agent_files: dict[str, Path | None] = {}

        for agent in agents:
            file_path = self._get_agent_file_path(agent)
            agent_files[agent] = file_path if file_path and file_path.exists() else None

        return agent_files

    def generate_agent_files(
        self,
        constitution: ConstitutionDocument,
        agents: list[str] | None = None,
    ) -> dict[str, Path]:
        """Generate agent instruction files.

        Args:
            constitution: Constitution document
            agents: List of agents to generate for (None = all detected)

        Returns:
            Dict mapping agent name to generated file path
        """
        if agents is None:
            agents = self.detect_installed_agents()

        generated_files: dict[str, Path] = {}

        for agent in agents:
            if agent not in AGENT_CONFIG:
                continue

            try:
                file_path = self._generate_agent_file(agent, constitution)
                generated_files[agent] = file_path
            except Exception:
                # Skip agents that fail to generate
                continue

        return generated_files

    def update_agent_files(self, constitution: ConstitutionDocument) -> dict[str, Path]:
        """Update existing agent instruction files.

        Args:
            constitution: Updated constitution document

        Returns:
            Dict mapping agent name to updated file path
        """
        # Find agents with existing instruction files
        agent_files = self.list_agent_files()
        agents_to_update = [agent for agent, path in agent_files.items() if path is not None]

        return self.generate_agent_files(constitution, agents_to_update)

    def _generate_agent_file(
        self,
        agent: str,
        constitution: ConstitutionDocument,
    ) -> Path:
        """Generate instruction file for specific agent.

        Args:
            agent: Agent name
            constitution: Constitution document

        Returns:
            Path to generated file

        Raises:
            ValueError: If agent file path cannot be determined
        """
        # Get agent configuration
        agent_config = AGENT_CONFIG[agent]
        file_path = self._get_agent_file_path(agent)

        if not file_path:
            raise ValueError(f"Could not determine file path for agent: {agent}")

        # Render template
        content = self.template_service.render_template(
            "constitution/agent_instructions.md",
            {
                "agent_name": agent_config["name"],
                "project_name": constitution.metadata.project_name,
                "constitution_path": "oak/constitution.md",
                "version": constitution.metadata.version,
                "tech_stack": constitution.metadata.tech_stack or "N/A",
                "generation_date": date.today().isoformat(),
            },
        )

        # Ensure directory exists
        ensure_dir(file_path.parent)

        # Write file
        write_file(file_path, content)

        return file_path

    def _get_agent_file_path(self, agent: str) -> Path | None:
        """Get instruction file path for agent.

        Args:
            agent: Agent name

        Returns:
            File path or None if pattern not found
        """
        if agent not in AGENT_CONFIG:
            return None

        pattern = AGENT_INSTRUCTION_PATTERNS.get(agent)
        if not pattern:
            return None

        # Replace {agent_folder} template variable if present
        agent_config = AGENT_CONFIG[agent]
        if "{agent_folder}" in pattern:
            file_path_str = pattern.format(agent_folder=agent_config["folder"])
        else:
            # Pattern is absolute (like "AGENTS.md" or ".cursorrules")
            file_path_str = pattern

        return self.project_root / file_path_str

    @classmethod
    def from_config(cls, project_root: Path | None = None) -> "AgentFileService":
        """Create service from configuration.

        Args:
            project_root: Project root directory

        Returns:
            Configured AgentFileService
        """
        return cls(project_root)
