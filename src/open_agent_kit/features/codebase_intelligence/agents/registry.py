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
    ScheduleDefinition,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_DEFINITION_FILENAME,
    AGENT_INSTANCE_NAME_PATTERN,
    AGENT_INSTANCE_SCHEMA_VERSION,
    AGENT_PROJECT_CONFIG_DIR,
    AGENT_PROJECT_CONFIG_EXTENSION,
    AGENT_PROMPTS_DIR,
    AGENT_SYSTEM_PROMPT_FILENAME,
    AGENT_TASK_TEMPLATE_FILENAME,
    AGENTS_DEFINITIONS_DIR,
    AGENTS_DIR,
    AGENTS_TASKS_SUBDIR,
    MAX_AGENT_MAX_TURNS,
    MAX_AGENT_TIMEOUT_SECONDS,
    MIN_AGENT_TIMEOUT_SECONDS,
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
    - Built-in tasks from the package's tasks directory
    - User tasks from the project's agent config directory

    Templates define capabilities; instances define tasks.
    Only instances can be executed.
    User tasks override built-in tasks with the same name.

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
                         If None, user instances are not loaded.
        """
        self._definitions_dir = definitions_dir or _AGENTS_DIR
        self._project_root = project_root
        self._agents: dict[str, AgentDefinition] = {}  # Legacy: templates only
        self._templates: dict[str, AgentDefinition] = {}
        self._builtin_tasks: dict[str, AgentInstance] = {}  # Built-in tasks from package
        self._instances: dict[str, AgentInstance] = {}  # All instances (built-in + user)
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
        Built-in tasks are loaded from agents/tasks/ in the package.
        User instances are loaded from the project's agent config directory.
        User instances override built-in tasks with the same name.

        Returns:
            Number of templates successfully loaded.
        """
        self._agents.clear()
        self._templates.clear()
        self._builtin_tasks.clear()
        self._instances.clear()

        # Load templates from definitions directory
        template_count = self._load_templates()

        # Load built-in tasks from package
        builtin_count = self._load_builtin_tasks()

        # Load user instances from project root (overrides built-ins)
        user_count = self._load_user_instances()

        # Merge: built-ins first, then user instances override
        for name, task in self._builtin_tasks.items():
            if name not in self._instances:
                self._instances[name] = task

        self._loaded = True
        total_instances = len(self._instances)
        logger.info(
            f"Agent registry loaded {template_count} templates, "
            f"{builtin_count} built-in tasks, {user_count} user tasks "
            f"({total_instances} total instances)"
        )
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

    def _load_builtin_tasks(self) -> int:
        """Load all built-in tasks from each agent definition's tasks/ subdirectory.

        Built-in tasks are stored in definitions/{agent_name}/tasks/*.yaml
        This keeps tasks organized with their parent agent template.

        Returns:
            Number of built-in tasks successfully loaded.
        """
        count = 0

        # Iterate through each loaded template and check for tasks/ subdirectory
        for template_name, template in self._templates.items():
            if not template.definition_path:
                continue

            # Tasks are in the same directory as the agent.yaml, under tasks/
            template_dir = Path(template.definition_path).parent
            tasks_dir = template_dir / AGENTS_TASKS_SUBDIR

            if not tasks_dir.exists():
                logger.debug(f"No tasks directory for template '{template_name}': {tasks_dir}")
                continue

            for yaml_file in tasks_dir.glob(f"*{AGENT_PROJECT_CONFIG_EXTENSION}"):
                try:
                    instance = self._load_instance(yaml_file, is_builtin=True)
                    if instance:
                        # Validate template matches the parent directory
                        if instance.agent_type != template_name:
                            logger.warning(
                                f"Built-in task '{instance.name}' in {template_name}/tasks/ "
                                f"references different template '{instance.agent_type}', skipping"
                            )
                            continue

                        self._builtin_tasks[instance.name] = instance
                        count += 1
                        logger.info(
                            f"Loaded built-in task: {instance.name} ({instance.display_name})"
                        )
                except (OSError, ValueError, yaml.YAMLError) as e:
                    logger.warning(f"Failed to load built-in task from {yaml_file}: {e}")

        return count

    def _load_user_instances(self) -> int:
        """Load all user instances from the project's agent config directory.

        User instances override built-in tasks with the same name.

        Returns:
            Number of user instances successfully loaded.
        """
        if self._project_root is None:
            logger.debug("No project root - skipping user instance loading")
            return 0

        instances_dir = self._project_root / AGENT_PROJECT_CONFIG_DIR
        if not instances_dir.exists():
            logger.debug(f"User instances directory not found: {instances_dir}")
            return 0

        count = 0
        for yaml_file in instances_dir.glob(f"*{AGENT_PROJECT_CONFIG_EXTENSION}"):
            try:
                instance = self._load_instance(yaml_file, is_builtin=False)
                if instance:
                    # Validate template exists
                    if instance.agent_type not in self._templates:
                        logger.warning(
                            f"Instance '{instance.name}' references unknown template "
                            f"'{instance.agent_type}', skipping"
                        )
                        continue

                    # Check if overriding a built-in
                    if instance.name in self._builtin_tasks:
                        logger.info(f"User instance '{instance.name}' overrides built-in task")

                    self._instances[instance.name] = instance
                    count += 1
                    logger.info(f"Loaded user instance: {instance.name} ({instance.display_name})")
            except (OSError, ValueError, yaml.YAMLError) as e:
                logger.warning(f"Failed to load instance from {yaml_file}: {e}")

        return count

    def _load_instance(self, yaml_file: Path, is_builtin: bool = False) -> AgentInstance | None:
        """Load a single instance from a YAML file.

        Args:
            yaml_file: Path to instance YAML file.
            is_builtin: True if this is a built-in task from the package.

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

        # Parse execution config (optional override of template defaults)
        execution = None
        execution_data = data.get("execution")
        if execution_data and isinstance(execution_data, dict):
            # Build execution config with validation
            timeout_seconds = execution_data.get("timeout_seconds")
            max_turns = execution_data.get("max_turns")
            permission_mode_str = execution_data.get("permission_mode")

            # Validate timeout bounds if provided
            if timeout_seconds is not None:
                timeout_seconds = max(
                    MIN_AGENT_TIMEOUT_SECONDS,
                    min(MAX_AGENT_TIMEOUT_SECONDS, int(timeout_seconds)),
                )

            # Validate max_turns bounds if provided
            if max_turns is not None:
                max_turns = max(1, min(MAX_AGENT_MAX_TURNS, int(max_turns)))

            # Parse permission mode if provided
            permission_mode = None
            if permission_mode_str:
                try:
                    permission_mode = AgentPermissionMode(permission_mode_str)
                except ValueError:
                    logger.warning(
                        f"Invalid permission_mode '{permission_mode_str}' in '{name}', ignoring"
                    )

            execution = AgentExecution(
                timeout_seconds=timeout_seconds or 600,  # Default if not specified
                max_turns=max_turns or 50,
                permission_mode=permission_mode or AgentPermissionMode.ACCEPT_EDITS,
            )

        # Parse schedule
        schedule = None
        schedule_data = data.get("schedule")
        if schedule_data and isinstance(schedule_data, dict) and "cron" in schedule_data:
            schedule = ScheduleDefinition(
                cron=schedule_data["cron"],
                description=schedule_data.get("description", ""),
            )

        return AgentInstance(
            name=name,
            display_name=data.get("display_name", name),
            agent_type=data["agent_type"],
            description=data.get("description", ""),
            default_task=data["default_task"],
            execution=execution,
            schedule=schedule,
            maintained_files=maintained_files,
            ci_queries=ci_queries,
            output_requirements=data.get("output_requirements", {}),
            style=data.get("style", {}),
            extra=data.get("extra", {}),
            instance_path=str(yaml_file),
            is_builtin=is_builtin,
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

    def is_builtin(self, name: str) -> bool:
        """Check if an instance is a built-in task.

        Args:
            name: Instance name.

        Returns:
            True if the instance is a built-in task shipped with OAK.
        """
        if not self._loaded:
            self.load_all()
        instance = self._instances.get(name)
        return instance.is_builtin if instance else False

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

        # Generate YAML content using Jinja2 template
        from jinja2 import Environment, FileSystemLoader

        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(template_dir), keep_trailing_newline=True)
        jinja_template = env.get_template(AGENT_TASK_TEMPLATE_FILENAME)

        yaml_content = jinja_template.render(
            name=name,
            display_name=display_name,
            agent_type=template_name,
            description=description,
            default_task=default_task,
            schema_version=AGENT_INSTANCE_SCHEMA_VERSION,
        )

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

    def copy_task(self, task_name: str, new_name: str | None = None) -> AgentInstance:
        """Copy a built-in task to the user's instances directory for customization.

        Args:
            task_name: Name of the task to copy (usually a built-in).
            new_name: Optional new name for the copy. If None, uses original name.

        Returns:
            Newly created AgentInstance.

        Raises:
            ValueError: If task doesn't exist or target already exists.
            OSError: If file cannot be written.
        """
        if not self._loaded:
            self.load_all()

        # Get the source task
        source = self._instances.get(task_name)
        if not source:
            raise ValueError(f"Task '{task_name}' not found")

        # Determine target name
        target_name = new_name or task_name

        # Validate name format
        if not re.match(AGENT_INSTANCE_NAME_PATTERN, target_name):
            raise ValueError(
                f"Invalid task name '{target_name}'. Must be lowercase letters, numbers, and hyphens."
            )

        # Ensure project root is configured
        if self._project_root is None:
            raise ValueError("Cannot copy task - no project root configured")

        instances_dir = self._project_root / AGENT_PROJECT_CONFIG_DIR
        target_path = instances_dir / f"{target_name}{AGENT_PROJECT_CONFIG_EXTENSION}"

        # Check if target already exists as a user file
        if target_path.exists():
            raise ValueError(f"User task '{target_name}' already exists at {target_path}")

        # Ensure directory exists
        instances_dir.mkdir(parents=True, exist_ok=True)

        # Read source YAML and write to target
        if source.instance_path:
            source_path = Path(source.instance_path)
            with open(source_path, encoding="utf-8") as f:
                content = f.read()

            # If renaming, update the name field in the content
            if new_name and new_name != task_name:
                content = re.sub(
                    r"^name:\s*\S+",
                    f"name: {new_name}",
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Copied task '{task_name}' to {target_path}")

            # Load and register the new instance
            instance = self._load_instance(target_path, is_builtin=False)
            if instance:
                self._instances[instance.name] = instance
                return instance

        raise ValueError(f"Failed to copy task '{task_name}'")

    def install_builtin_tasks(self, force: bool = False) -> dict[str, str]:
        """Install built-in tasks to the project's agents directory.

        Copies built-in task YAML files to oak/ci/agents/ so users can
        customize them. By default, only installs tasks that don't already
        exist (won't overwrite user customizations).

        Args:
            force: If True, overwrite existing tasks with built-in versions.

        Returns:
            Dictionary mapping task name to status: 'installed', 'skipped', 'updated', 'error'.
        """
        import shutil

        if not self._loaded:
            self.load_all()

        if self._project_root is None:
            logger.warning("Cannot install built-in tasks - no project root configured")
            return {}

        # Ensure target directory exists
        target_dir = self._project_root / AGENT_PROJECT_CONFIG_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        results: dict[str, str] = {}

        for task_name, task in self._builtin_tasks.items():
            if not task.instance_path:
                results[task_name] = "error"
                continue

            source_path = Path(task.instance_path)
            target_path = target_dir / f"{task_name}{AGENT_PROJECT_CONFIG_EXTENSION}"

            try:
                if target_path.exists():
                    if force:
                        shutil.copy2(source_path, target_path)
                        results[task_name] = "updated"
                        logger.info(f"Updated task '{task_name}' from built-in")
                    else:
                        results[task_name] = "skipped"
                        logger.debug(f"Skipped task '{task_name}' - user version exists")
                else:
                    shutil.copy2(source_path, target_path)
                    results[task_name] = "installed"
                    logger.info(f"Installed built-in task '{task_name}'")
            except OSError as e:
                results[task_name] = "error"
                logger.warning(f"Failed to install task '{task_name}': {e}")

        # Reload to pick up newly installed tasks as user tasks
        if any(r in ("installed", "updated") for r in results.values()):
            self.reload()

        return results

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
