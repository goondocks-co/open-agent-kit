"""Agent Registry for loading and managing agent definitions.

The registry loads agent definitions from YAML files located in:
  agents/definitions/{name}/agent.yaml

Each agent can have optional prompt files in:
  agents/definitions/{name}/prompts/system.md
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentCIAccess,
    AgentDefinition,
    AgentExecution,
    AgentPermissionMode,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_DEFINITION_FILENAME,
    AGENT_PROMPTS_DIR,
    AGENT_SYSTEM_PROMPT_FILENAME,
    AGENTS_DEFINITIONS_DIR,
    AGENTS_DIR,
)

logger = logging.getLogger(__name__)

# Path to the agents directory within the CI feature
# Path: agents/registry.py -> agents/ -> codebase_intelligence/
_FEATURE_ROOT = Path(__file__).parent.parent
_AGENTS_DIR = _FEATURE_ROOT / AGENTS_DIR / AGENTS_DEFINITIONS_DIR


class AgentRegistry:
    """Registry for loading and managing agent definitions.

    The registry discovers agent definitions from the built-in definitions
    directory and provides access to them by name.

    Attributes:
        agents: Dictionary of loaded agent definitions by name.
    """

    def __init__(self, definitions_dir: Path | None = None):
        """Initialize the registry.

        Args:
            definitions_dir: Optional custom directory for agent definitions.
                           Defaults to the built-in definitions directory.
        """
        self._definitions_dir = definitions_dir or _AGENTS_DIR
        self._agents: dict[str, AgentDefinition] = {}
        self._loaded = False

    @property
    def agents(self) -> dict[str, AgentDefinition]:
        """Get all loaded agents."""
        if not self._loaded:
            self.load_all()
        return self._agents

    def load_all(self) -> int:
        """Load all agent definitions from the definitions directory.

        Returns:
            Number of agents successfully loaded.
        """
        self._agents.clear()

        if not self._definitions_dir.exists():
            logger.warning(f"Agent definitions directory not found: {self._definitions_dir}")
            self._loaded = True
            return 0

        count = 0
        for agent_dir in self._definitions_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            definition_file = agent_dir / AGENT_DEFINITION_FILENAME
            if not definition_file.exists():
                logger.debug(f"No {AGENT_DEFINITION_FILENAME} in {agent_dir.name}, skipping")
                continue

            try:
                agent = self._load_agent(definition_file)
                if agent:
                    self._agents[agent.name] = agent
                    count += 1
                    logger.info(f"Loaded agent: {agent.name} ({agent.display_name})")
            except (OSError, ValueError, yaml.YAMLError) as e:
                logger.warning(f"Failed to load agent from {definition_file}: {e}")

        self._loaded = True
        logger.info(f"Agent registry loaded {count} agents")
        return count

    def _load_agent(self, definition_file: Path) -> AgentDefinition | None:
        """Load a single agent definition from a YAML file.

        Args:
            definition_file: Path to agent.yaml file.

        Returns:
            AgentDefinition if successful, None otherwise.
        """
        with open(definition_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning(f"Empty agent definition: {definition_file}")
            return None

        # Load system prompt from file if not inline
        system_prompt = data.get("system_prompt")
        if not system_prompt:
            prompt_file = definition_file.parent / AGENT_PROMPTS_DIR / AGENT_SYSTEM_PROMPT_FILENAME
            if prompt_file.exists():
                system_prompt = prompt_file.read_text(encoding="utf-8").strip()

        # Parse nested configurations
        execution_data = data.get("execution", {})
        execution = AgentExecution(
            max_turns=execution_data.get("max_turns", 50),
            timeout_seconds=execution_data.get("timeout_seconds", 600),
            permission_mode=AgentPermissionMode(
                execution_data.get("permission_mode", "acceptEdits")
            ),
        )

        ci_access_data = data.get("ci_access", {})
        ci_access = AgentCIAccess(
            code_search=ci_access_data.get("code_search", True),
            memory_search=ci_access_data.get("memory_search", True),
            session_history=ci_access_data.get("session_history", True),
            project_stats=ci_access_data.get("project_stats", True),
        )

        return AgentDefinition(
            name=data.get("name", definition_file.parent.name),
            display_name=data.get("display_name", data.get("name", definition_file.parent.name)),
            description=data.get("description", ""),
            execution=execution,
            allowed_tools=data.get("allowed_tools", ["Read", "Write", "Edit", "Glob", "Grep"]),
            disallowed_tools=data.get("disallowed_tools", []),
            allowed_paths=data.get("allowed_paths", []),
            disallowed_paths=data.get("disallowed_paths", [".env", ".env.*", "*.pem", "*.key"]),
            ci_access=ci_access,
            system_prompt=system_prompt,
            definition_path=str(definition_file),
        )

    def get(self, name: str) -> AgentDefinition | None:
        """Get an agent definition by name.

        Args:
            name: Agent name.

        Returns:
            AgentDefinition if found, None otherwise.
        """
        if not self._loaded:
            self.load_all()
        return self._agents.get(name)

    def list_agents(self) -> list[AgentDefinition]:
        """Get all registered agents.

        Returns:
            List of all agent definitions.
        """
        if not self._loaded:
            self.load_all()
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        """Get names of all registered agents.

        Returns:
            List of agent names.
        """
        if not self._loaded:
            self.load_all()
        return list(self._agents.keys())

    def reload(self) -> int:
        """Reload all agent definitions.

        Returns:
            Number of agents loaded.
        """
        self._loaded = False
        return self.load_all()

    def to_dict(self) -> dict[str, Any]:
        """Convert registry state to dictionary for API responses.

        Returns:
            Dictionary with agent count and names.
        """
        if not self._loaded:
            self.load_all()
        return {
            "count": len(self._agents),
            "agents": self.list_names(),
            "definitions_dir": str(self._definitions_dir),
        }
