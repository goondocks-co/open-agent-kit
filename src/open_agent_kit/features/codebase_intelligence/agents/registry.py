"""Agent Registry for loading and managing agent definitions and instances.

The registry loads:
- Agent templates (definitions) from agents/definitions/{name}/agent.yaml
- Agent instances from the project's agent config directory (AGENT_PROJECT_CONFIG_DIR)

Templates define capabilities (tools, permissions, system prompt).
Instances define tasks (default_task, maintained_files, ci_queries).
Only instances can be executed - templates are used to create instances.
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentCIAccess,
    AgentDefinition,
    AgentExecution,
    AgentInstance,
    AgentPermissionMode,
    CIQueryTemplate,
    MaintainedFile,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_DEFINITION_FILENAME,
    AGENT_INSTANCE_NAME_PATTERN,
    AGENT_INSTANCE_SCHEMA_VERSION,
    AGENT_PROJECT_CONFIG_DIR,
    AGENT_PROJECT_CONFIG_EXTENSION,
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
    """Registry for loading and managing agent templates and instances.

    The registry discovers:
    - Agent templates (definitions) from the built-in definitions directory
    - Agent instances from the project's agent config directory

    Templates define capabilities; instances define tasks.
    Only instances can be executed.

    Attributes:
        agents: Dictionary of loaded agent definitions by name (legacy).
        templates: Dictionary of loaded templates by name.
        instances: Dictionary of loaded instances by name.
    """

    def __init__(
        self,
        definitions_dir: Path | None = None,
        project_root: Path | None = None,
    ):
        """Initialize the registry.

        Args:
            definitions_dir: Optional custom directory for agent definitions.
                           Defaults to the built-in definitions directory.
            project_root: Project root for loading instances from agent config directory.
                         If None, instances are not loaded.
        """
        self._definitions_dir = definitions_dir or _AGENTS_DIR
        self._project_root = project_root
        self._agents: dict[str, AgentDefinition] = {}  # Legacy: templates only
        self._templates: dict[str, AgentDefinition] = {}
        self._instances: dict[str, AgentInstance] = {}
        self._loaded = False

    @property
    def agents(self) -> dict[str, AgentDefinition]:
        """Get all loaded agents (legacy - returns templates only)."""
        if not self._loaded:
            self.load_all()
        return self._agents

    @property
    def templates(self) -> dict[str, AgentDefinition]:
        """Get all loaded templates."""
        if not self._loaded:
            self.load_all()
        return self._templates

    def load_all(self) -> int:
        """Load all agent templates and instances.

        Templates are loaded from agents/definitions/{name}/agent.yaml.
        Instances are loaded from the project's agent config directory.

        Returns:
            Number of templates successfully loaded.
        """
        self._agents.clear()
        self._templates.clear()
        self._instances.clear()

        # Load templates from definitions directory
        template_count = self._load_templates()

        # Load instances from project root
        instance_count = self._load_instances()

        self._loaded = True
        logger.info(f"Agent registry loaded {template_count} templates, {instance_count} instances")
        return template_count

    def _load_templates(self) -> int:
        """Load all agent templates from the definitions directory.

        Returns:
            Number of templates successfully loaded.
        """
        if not self._definitions_dir.exists():
            logger.warning(f"Agent definitions directory not found: {self._definitions_dir}")
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
                    self._agents[agent.name] = agent  # Legacy
                    self._templates[agent.name] = agent
                    count += 1
                    logger.info(f"Loaded template: {agent.name} ({agent.display_name})")
            except (OSError, ValueError, yaml.YAMLError) as e:
                logger.warning(f"Failed to load template from {definition_file}: {e}")

        return count

    def _load_instances(self) -> int:
        """Load all agent instances from the project's agent config directory.

        Returns:
            Number of instances successfully loaded.
        """
        if self._project_root is None:
            logger.debug("No project root - skipping instance loading")
            return 0

        instances_dir = self._project_root / AGENT_PROJECT_CONFIG_DIR
        if not instances_dir.exists():
            logger.debug(f"Instances directory not found: {instances_dir}")
            return 0

        count = 0
        for yaml_file in instances_dir.glob(f"*{AGENT_PROJECT_CONFIG_EXTENSION}"):
            try:
                instance = self._load_instance(yaml_file)
                if instance:
                    # Validate template exists
                    if instance.agent_type not in self._templates:
                        logger.warning(
                            f"Instance '{instance.name}' references unknown template "
                            f"'{instance.agent_type}', skipping"
                        )
                        continue

                    self._instances[instance.name] = instance
                    count += 1
                    logger.info(f"Loaded instance: {instance.name} ({instance.display_name})")
            except (OSError, ValueError, yaml.YAMLError) as e:
                logger.warning(f"Failed to load instance from {yaml_file}: {e}")

        return count

    def _load_instance(self, yaml_file: Path) -> AgentInstance | None:
        """Load a single instance from a YAML file.

        Args:
            yaml_file: Path to instance YAML file.

        Returns:
            AgentInstance if successful, None otherwise.
        """
        with open(yaml_file, encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse instance YAML from {yaml_file}: {e}")
                return None

        if not data:
            logger.warning(f"Empty instance file: {yaml_file}")
            return None

        # Instance name defaults to filename without extension
        name = data.get("name", yaml_file.stem)

        # Validate required fields
        if "default_task" not in data:
            logger.warning(f"Instance '{name}' missing required 'default_task', skipping")
            return None

        if "agent_type" not in data:
            logger.warning(f"Instance '{name}' missing required 'agent_type', skipping")
            return None

        # Parse maintained_files
        maintained_files = []
        for mf_data in data.get("maintained_files", []):
            if isinstance(mf_data, dict):
                maintained_files.append(MaintainedFile(**mf_data))
            elif isinstance(mf_data, str):
                maintained_files.append(MaintainedFile(path=mf_data))

        # Parse ci_queries
        ci_queries: dict[str, list[CIQueryTemplate]] = {}
        for phase, queries in data.get("ci_queries", {}).items():
            ci_queries[phase] = []
            for q_data in queries:
                if isinstance(q_data, dict):
                    ci_queries[phase].append(CIQueryTemplate(**q_data))

        return AgentInstance(
            name=name,
            display_name=data.get("display_name", name),
            agent_type=data["agent_type"],
            description=data.get("description", ""),
            default_task=data["default_task"],
            maintained_files=maintained_files,
            ci_queries=ci_queries,
            output_requirements=data.get("output_requirements", {}),
            style=data.get("style", {}),
            extra=data.get("extra", {}),
            instance_path=str(yaml_file),
            schema_version=data.get("schema_version", AGENT_INSTANCE_SCHEMA_VERSION),
        )

    def load_project_config(self, agent_name: str) -> dict[str, Any] | None:
        """Load project-specific config for an agent.

        Project configs are stored in the agent config directory within the
        project root. These are optional, git-tracked configurations that
        customize agent behavior for a specific project.

        Args:
            agent_name: Name of the agent.

        Returns:
            Configuration dictionary if found, None otherwise.
        """
        if self._project_root is None:
            return None

        config_path = (
            self._project_root
            / AGENT_PROJECT_CONFIG_DIR
            / f"{agent_name}{AGENT_PROJECT_CONFIG_EXTENSION}"
        )

        if not config_path.exists():
            logger.debug(f"No project config for agent '{agent_name}' at {config_path}")
            return None

        try:
            with open(config_path, encoding="utf-8") as f:
                config: dict[str, Any] | None = yaml.safe_load(f)
            if config:
                logger.info(f"Loaded project config for agent '{agent_name}' from {config_path}")
            return config
        except (OSError, yaml.YAMLError) as e:
            logger.warning(f"Failed to load project config from {config_path}: {e}")
            return None

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

        # Get agent name for project config lookup
        agent_name = data.get("name", definition_file.parent.name)

        # Load project-specific config if available
        project_config = self.load_project_config(agent_name)

        return AgentDefinition(
            name=agent_name,
            display_name=data.get("display_name", agent_name),
            description=data.get("description", ""),
            execution=execution,
            allowed_tools=data.get("allowed_tools", ["Read", "Write", "Edit", "Glob", "Grep"]),
            disallowed_tools=data.get("disallowed_tools", []),
            allowed_paths=data.get("allowed_paths", []),
            disallowed_paths=data.get("disallowed_paths", [".env", ".env.*", "*.pem", "*.key"]),
            ci_access=ci_access,
            system_prompt=system_prompt,
            definition_path=str(definition_file),
            project_config=project_config,
        )

    def get(self, name: str) -> AgentDefinition | None:
        """Get an agent definition (template) by name.

        Args:
            name: Agent/template name.

        Returns:
            AgentDefinition if found, None otherwise.
        """
        if not self._loaded:
            self.load_all()
        return self._templates.get(name)

    def get_template(self, name: str) -> AgentDefinition | None:
        """Get a template by name.

        Args:
            name: Template name.

        Returns:
            AgentDefinition if found, None otherwise.
        """
        if not self._loaded:
            self.load_all()
        return self._templates.get(name)

    def get_instance(self, name: str) -> AgentInstance | None:
        """Get an instance by name.

        Args:
            name: Instance name.

        Returns:
            AgentInstance if found, None otherwise.
        """
        if not self._loaded:
            self.load_all()
        return self._instances.get(name)

    def list_agents(self) -> list[AgentDefinition]:
        """Get all registered agents (legacy - returns templates only).

        Returns:
            List of all agent definitions.
        """
        if not self._loaded:
            self.load_all()
        return list(self._templates.values())

    def list_templates(self) -> list[AgentDefinition]:
        """Get all registered templates.

        Returns:
            List of all templates.
        """
        if not self._loaded:
            self.load_all()
        return list(self._templates.values())

    def list_instances(self) -> list[AgentInstance]:
        """Get all registered instances.

        Returns:
            List of all instances.
        """
        if not self._loaded:
            self.load_all()
        return list(self._instances.values())

    def list_names(self) -> list[str]:
        """Get names of all registered agents (legacy - templates only).

        Returns:
            List of agent names.
        """
        if not self._loaded:
            self.load_all()
        return list(self._templates.keys())

    def reload(self) -> int:
        """Reload all agent templates and instances.

        Returns:
            Number of templates loaded.
        """
        self._loaded = False
        return self.load_all()

    def create_instance(
        self,
        name: str,
        template_name: str,
        display_name: str,
        description: str,
        default_task: str,
    ) -> AgentInstance:
        """Create a new instance YAML file and load it.

        Args:
            name: Instance name (becomes filename).
            template_name: Name of template to use.
            display_name: Human-readable name.
            description: What this instance does.
            default_task: Task to execute when run.

        Returns:
            Newly created AgentInstance.

        Raises:
            ValueError: If name is invalid or template doesn't exist.
            OSError: If file cannot be written.
        """
        if not self._loaded:
            self.load_all()

        # Validate name format
        if not re.match(AGENT_INSTANCE_NAME_PATTERN, name):
            raise ValueError(
                f"Invalid instance name '{name}'. Must be lowercase letters, numbers, and hyphens."
            )

        # Check template exists
        template = self._templates.get(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")

        # Check instance doesn't already exist
        if name in self._instances:
            raise ValueError(f"Instance '{name}' already exists")

        # Ensure instances directory exists
        if self._project_root is None:
            raise ValueError("Cannot create instance - no project root configured")

        instances_dir = self._project_root / AGENT_PROJECT_CONFIG_DIR
        instances_dir.mkdir(parents=True, exist_ok=True)

        # Generate YAML content with scaffolding
        yaml_content = f"""# Agent Instance: {display_name}
# Auto-generated from template: {template_name}

name: {name}
display_name: "{display_name}"
agent_type: {template_name}
description: "{description}"

# Task this agent executes when run (REQUIRED)
default_task: |
  {default_task}

# Files this agent maintains (customize for your project)
maintained_files:
  - path: "TODO: add file patterns"
    purpose: "TODO: describe purpose"
    auto_create: false

# CI queries to run before executing the task
ci_queries:
  discovery:
    - tool: ci_search
      query_template: "TODO: add search query"
      search_type: all
      min_confidence: medium
      limit: 10
      purpose: "TODO: describe what this finds"

# Output requirements (optional)
output_requirements:
  required_sections: []

# Style preferences (optional)
style:
  tone: "technical"
  include_examples: true

schema_version: {AGENT_INSTANCE_SCHEMA_VERSION}
"""

        # Write YAML file
        yaml_path = instances_dir / f"{name}{AGENT_PROJECT_CONFIG_EXTENSION}"
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        logger.info(f"Created instance YAML: {yaml_path}")

        # Load and register the new instance
        instance = self._load_instance(yaml_path)
        if instance:
            self._instances[instance.name] = instance
            return instance

        raise ValueError(f"Failed to load newly created instance '{name}'")

    def to_dict(self) -> dict[str, Any]:
        """Convert registry state to dictionary for API responses.

        Returns:
            Dictionary with counts and names.
        """
        if not self._loaded:
            self.load_all()
        return {
            "count": len(self._templates),
            "templates": list(self._templates.keys()),
            "instances": list(self._instances.keys()),
            "definitions_dir": str(self._definitions_dir),
        }
