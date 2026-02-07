"""Agent Executor for running agents via claude-agent-sdk.

This module provides the AgentExecutor class that manages agent execution
lifecycle including:
- Building claude-agent-sdk options from agent definitions
- Running agents with proper timeout handling
- Tracking execution state and results
- Cancellation support
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

import yaml

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDefinition,
    AgentExecution,
    AgentPermissionMode,
    AgentProvider,
    AgentRun,
    AgentRunStatus,
    AgentTask,
)
from open_agent_kit.features.codebase_intelligence.agents.tools import create_ci_mcp_server
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_FORBIDDEN_TOOLS,
    AGENT_INTERRUPT_GRACE_SECONDS,
    AGENT_RETRY_BASE_DELAY,
    AGENT_RETRY_MAX_ATTEMPTS,
    CI_MCP_SERVER_NAME,
    CI_TOOL_MEMORIES,
    CI_TOOL_PROJECT_STATS,
    CI_TOOL_QUERY,
    CI_TOOL_SEARCH,
    CI_TOOL_SESSIONS,
)

if TYPE_CHECKING:
    from claude_agent_sdk.types import McpSdkServerConfig

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.config import AgentConfig
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Executor for running CI agents via claude-agent-sdk.

    The executor manages:
    - Agent execution lifecycle
    - Run history tracking
    - Cancellation handling
    - CI tool integration

    Attributes:
        project_root: Root directory for agent operations.
        runs: Dictionary of run records by ID.
    """

    def __init__(
        self,
        project_root: Path,
        agent_config: "AgentConfig",
        retrieval_engine: "RetrievalEngine | None" = None,
        activity_store: "ActivityStore | None" = None,
        vector_store: "VectorStore | None" = None,
    ):
        """Initialize the executor.

        Args:
            project_root: Project root directory for agent operations.
            agent_config: AgentConfig with executor settings.
            retrieval_engine: RetrievalEngine for CI tools (optional).
            activity_store: ActivityStore for CI tools (optional).
            vector_store: VectorStore for CI tools (optional).
        """
        self._project_root = project_root
        self._agent_config = agent_config
        self._retrieval_engine = retrieval_engine
        self._activity_store = activity_store
        self._vector_store = vector_store

        # Run tracking
        self._runs: OrderedDict[str, AgentRun] = OrderedDict()
        self._runs_lock = RLock()

        # Active SDK clients for interrupt support (run_id -> client)
        self._active_clients: dict[str, Any] = {}
        self._clients_lock = RLock()

        # MCP server cache keyed by frozenset of enabled tools
        self._ci_mcp_servers: dict[frozenset[str], McpSdkServerConfig | None] = {}

    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return self._project_root

    @property
    def runs(self) -> dict[str, AgentRun]:
        """Get all run records (copy for thread safety)."""
        with self._runs_lock:
            return dict(self._runs)

    @property
    def max_cache_size(self) -> int:
        """Get the maximum in-memory cache size from config."""
        return self._agent_config.executor_cache_size

    def _get_ci_mcp_server(
        self, enabled_tools: set[str] | None = None
    ) -> "McpSdkServerConfig | None":
        """Get or create a CI MCP server for the given tool set.

        Caches servers by the set of enabled tools so agents with
        different ci_access flags get different tool sets.

        Args:
            enabled_tools: Set of tool names to include.

        Returns:
            SDKMCPServer instance, or None if unavailable.
        """
        cache_key = frozenset(enabled_tools) if enabled_tools else frozenset()

        if cache_key in self._ci_mcp_servers:
            return self._ci_mcp_servers[cache_key]

        if self._retrieval_engine is None:
            logger.warning("Cannot create CI MCP server - no retrieval engine")
            return None

        server = create_ci_mcp_server(
            retrieval_engine=self._retrieval_engine,
            activity_store=self._activity_store,
            vector_store=self._vector_store,
            enabled_tools=enabled_tools,
        )
        self._ci_mcp_servers[cache_key] = server
        return server

    def _cleanup_old_runs(self) -> None:
        """Remove old runs from in-memory cache when it exceeds threshold.

        Note: SQLite storage is not cleaned up here - that should be done
        separately via maintenance jobs if needed.
        """
        with self._runs_lock:
            if len(self._runs) <= self.max_cache_size:
                return

            # Keep only the most recent runs in memory
            items = list(self._runs.items())
            to_remove = len(items) - self.max_cache_size

            for i in range(to_remove):
                run_id = items[i][0]
                del self._runs[run_id]
                logger.debug(f"Cleaned up old run from cache: {run_id}")

    def _get_effective_execution(
        self,
        agent: AgentDefinition,
        task: AgentTask | None = None,
    ) -> AgentExecution:
        """Get effective execution config, preferring task overrides.

        Task config takes precedence over template defaults for timeout_seconds,
        max_turns, and permission_mode. This allows per-task tuning of resource
        limits based on task complexity.

        Args:
            agent: Agent definition (template) with default execution config.
            task: Optional task with execution overrides.

        Returns:
            AgentExecution with merged settings.
        """
        base = agent.execution

        if task and task.execution:
            task_exec = task.execution
            return AgentExecution(
                timeout_seconds=task_exec.timeout_seconds or base.timeout_seconds,
                max_turns=task_exec.max_turns or base.max_turns,
                permission_mode=task_exec.permission_mode or base.permission_mode,
            )

        return base

    def _apply_provider_env(self, provider: AgentProvider | None) -> dict[str, str | None]:
        """Apply provider environment variables, returning original values for restoration.

        Args:
            provider: Provider configuration (None = use defaults).

        Returns:
            Dictionary of original env var values (None if not set) for restoration.
        """
        import os

        if provider is None:
            return {}

        original_values: dict[str, str | None] = {}
        for key, value in provider.env_vars.items():
            original_values[key] = os.environ.get(key)
            os.environ[key] = value
            logger.debug(f"Set {key} for provider {provider.type}")

        return original_values

    def _restore_provider_env(self, original_values: dict[str, str | None]) -> None:
        """Restore original environment variables after provider execution.

        Args:
            original_values: Dictionary from _apply_provider_env.
        """
        import os

        for key, original_value in original_values.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

    def _build_options(
        self,
        agent: AgentDefinition,
        execution: AgentExecution | None = None,
    ) -> Any:
        """Build ClaudeAgentOptions from agent definition.

        Args:
            agent: Agent definition with configuration.
            execution: Optional execution config override (from task).

        Returns:
            ClaudeAgentOptions instance.
        """
        try:
            from claude_agent_sdk import ClaudeAgentOptions
        except ImportError as e:
            raise RuntimeError("claude-agent-sdk not installed") from e

        # Use provided execution config or template default
        effective_execution = execution or agent.execution

        # Build allowed tools list, filtering forbidden tools
        allowed_tools = [t for t in agent.get_effective_tools() if t not in AGENT_FORBIDDEN_TOOLS]

        # Build enabled CI tools set from ci_access flags
        mcp_servers: dict[str, Any] = {}
        ci_access = agent.ci_access
        has_any_ci_access = (
            ci_access.code_search
            or ci_access.memory_search
            or ci_access.session_history
            or ci_access.project_stats
            or ci_access.sql_query
        )
        if has_any_ci_access:
            enabled_ci_tools: set[str] = set()
            if ci_access.code_search:
                enabled_ci_tools.add(CI_TOOL_SEARCH)
            if ci_access.memory_search:
                enabled_ci_tools.add(CI_TOOL_MEMORIES)
            if ci_access.session_history:
                enabled_ci_tools.add(CI_TOOL_SESSIONS)
            if ci_access.project_stats:
                enabled_ci_tools.add(CI_TOOL_PROJECT_STATS)
            if ci_access.sql_query:
                enabled_ci_tools.add(CI_TOOL_QUERY)

            ci_server = self._get_ci_mcp_server(enabled_ci_tools)
            if ci_server:
                mcp_servers[CI_MCP_SERVER_NAME] = ci_server
                # Add CI tool names to allowed list
                for tool_name in enabled_ci_tools:
                    allowed_tools.append(f"mcp__{CI_MCP_SERVER_NAME}__{tool_name}")
            else:
                logger.warning(
                    f"CI MCP server unavailable for agent '{agent.name}' - CI tools will not work"
                )

        # Map permission mode
        permission_mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"] = "default"
        if effective_execution.permission_mode == AgentPermissionMode.ACCEPT_EDITS:
            permission_mode = "acceptEdits"
        elif effective_execution.permission_mode == AgentPermissionMode.BYPASS_PERMISSIONS:
            permission_mode = "bypassPermissions"

        # Determine model to use (execution config or provider fallback)
        model = effective_execution.model
        if model is None and effective_execution.provider:
            model = effective_execution.provider.model

        options = ClaudeAgentOptions(
            system_prompt=agent.system_prompt,
            allowed_tools=allowed_tools,
            max_turns=effective_execution.max_turns,
            permission_mode=permission_mode,
            cwd=str(self._project_root),
        )

        # Set model if specified
        if model:
            options.model = model

        # Add MCP servers if any
        if mcp_servers:
            options.mcp_servers = mcp_servers

        return options

    def _build_task_prompt(
        self,
        agent: AgentDefinition,
        task_description: str,
        agent_task: AgentTask | None = None,
    ) -> str:
        """Build the task prompt, optionally injecting task configuration.

        If an agent_task is provided, its configuration (maintained_files, ci_queries,
        output_requirements, style) is appended to the task as YAML.

        Also injects runtime context like daemon_url for linking to sessions.

        Args:
            agent: Agent definition (template).
            task_description: Task description (usually agent_task.default_task).
            agent_task: Optional task with configuration.

        Returns:
            Task prompt with config injected if available.
        """
        # Get daemon port for this project
        from open_agent_kit.features.codebase_intelligence.daemon.manager import (
            get_project_port,
        )

        daemon_port = get_project_port(self._project_root)
        daemon_url = f"http://localhost:{daemon_port}"

        if agent_task:
            # Build task configuration block
            config: dict[str, Any] = {}

            # CRITICAL: Inject project_root so the agent knows where it's working
            # Without this, the agent may hallucinate paths or get confused
            project_root_str = str(self._project_root)
            config["project_root"] = project_root_str

            # Inject daemon URL for session/memory links
            config["daemon_url"] = daemon_url

            if agent_task.maintained_files:
                # Resolve {project_root} placeholder in paths
                config["maintained_files"] = [
                    {
                        **mf.model_dump(exclude_none=True),
                        "path": mf.path.replace("{project_root}", project_root_str),
                    }
                    for mf in agent_task.maintained_files
                ]

            if agent_task.ci_queries:
                config["ci_queries"] = {
                    phase: [q.model_dump(exclude_none=True) for q in queries]
                    for phase, queries in agent_task.ci_queries.items()
                }

            if agent_task.output_requirements:
                config["output_requirements"] = agent_task.output_requirements

            if agent_task.style:
                config["style"] = agent_task.style

            if agent_task.extra:
                config["extra"] = agent_task.extra

            config_yaml = yaml.dump(config, default_flow_style=False, sort_keys=False)
            return f"{task_description}\n\n## Task Configuration\n```yaml\n{config_yaml}```"

        # No task - inject project_root and daemon URL as runtime context
        runtime_context = f"project_root: {self._project_root}\ndaemon_url: {daemon_url}"
        return f"{task_description}\n\n## Runtime Context\n```yaml\n{runtime_context}\n```"

        # Legacy: use project_config if no task
        if agent.project_config:
            config_yaml = yaml.dump(agent.project_config, default_flow_style=False, sort_keys=False)
            return f"{task_description}\n\n## Project Configuration\n```yaml\n{config_yaml}```"

        return task_description

    def _is_transient_error(self, error: Exception) -> bool:
        """Check if an error is transient and worth retrying.

        Transient errors include:
        - Connection errors (network issues)
        - Timeout errors (temporary overload)
        - Rate limit errors (429 responses)

        Args:
            error: The exception that occurred.

        Returns:
            True if the error is transient and worth retrying.
        """
        # Connection/network errors
        if isinstance(error, (ConnectionError, ConnectionResetError, BrokenPipeError)):
            return True

        # OSError includes socket errors
        if isinstance(error, OSError):
            # Common transient errno values
            import errno

            transient_errnos = {
                errno.ECONNREFUSED,
                errno.ECONNRESET,
                errno.ETIMEDOUT,
                errno.ENETUNREACH,
                errno.EHOSTUNREACH,
            }
            if hasattr(error, "errno") and error.errno in transient_errnos:
                return True

        # Check for rate limit indicators in error message
        error_str = str(error).lower()
        if "rate limit" in error_str or "429" in error_str or "overloaded" in error_str:
            return True

        # HTTP connection errors (if wrapped)
        if "connection" in error_str and ("refused" in error_str or "reset" in error_str):
            return True

        return False

    def create_run(
        self,
        agent: AgentDefinition,
        task: str,
        agent_task: AgentTask | None = None,
    ) -> AgentRun:
        """Create a new run record.

        Persists to SQLite if ActivityStore is available, and caches in memory.

        Args:
            agent: Agent definition (template).
            task: Task description.
            agent_task: Optional task being run.

        Returns:
            New AgentRun instance.
        """
        import hashlib

        # Use task name if running a task, otherwise template name
        agent_name = agent_task.name if agent_task else agent.name

        run = AgentRun(
            id=str(uuid4()),
            agent_name=agent_name,
            task=task,
            status=AgentRunStatus.PENDING,
            created_at=datetime.now(),
        )

        # Persist to SQLite if available
        if self._activity_store:
            # Compute system prompt hash for reproducibility tracking
            system_prompt_hash = None
            if agent.system_prompt:
                system_prompt_hash = hashlib.sha256(agent.system_prompt.encode()).hexdigest()[:16]

            # Build config from task or legacy project_config
            project_config = None
            if agent_task:
                project_config = {
                    "task_name": agent_task.name,
                    "agent_type": agent_task.agent_type,
                    "maintained_files": [
                        mf.model_dump(exclude_none=True) for mf in agent_task.maintained_files
                    ],
                    "ci_queries": {
                        phase: [q.model_dump(exclude_none=True) for q in queries]
                        for phase, queries in agent_task.ci_queries.items()
                    },
                }
            elif agent.project_config:
                project_config = agent.project_config

            self._activity_store.create_agent_run(
                run_id=run.id,
                agent_name=run.agent_name,
                task=run.task,
                status=run.status.value,
                project_config=project_config,
                system_prompt_hash=system_prompt_hash,
            )

        # Cache in memory
        with self._runs_lock:
            self._runs[run.id] = run
            self._cleanup_old_runs()

        return run

    def get_run(self, run_id: str) -> AgentRun | None:
        """Get a run by ID.

        Checks in-memory cache first, then falls back to SQLite.

        Args:
            run_id: Run identifier.

        Returns:
            AgentRun if found, None otherwise.
        """
        # Check in-memory cache first
        with self._runs_lock:
            if run_id in self._runs:
                return self._runs[run_id]

        # Fall back to SQLite
        if self._activity_store:
            data = self._activity_store.get_agent_run(run_id)
            if data:
                return self._dict_to_run(data)

        return None

    def _dict_to_run(self, data: dict[str, Any]) -> AgentRun:
        """Convert a database row dict to AgentRun model.

        Args:
            data: Dictionary from SQLite.

        Returns:
            AgentRun instance.
        """
        return AgentRun(
            id=data["id"],
            agent_name=data["agent_name"],
            task=data["task"],
            status=AgentRunStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            result=data.get("result"),
            error=data.get("error"),
            turns_used=data.get("turns_used", 0),
            cost_usd=data.get("cost_usd"),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            files_created=data.get("files_created") or [],
            files_modified=data.get("files_modified") or [],
            files_deleted=data.get("files_deleted") or [],
        )

    def list_runs(
        self,
        limit: int = 20,
        offset: int = 0,
        agent_name: str | None = None,
        status: AgentRunStatus | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[AgentRun], int]:
        """List runs with optional filtering and sorting.

        Uses SQLite if available (for durability), falls back to in-memory.

        Args:
            limit: Maximum runs to return.
            offset: Pagination offset.
            agent_name: Filter by agent name.
            status: Filter by status.
            created_after: Filter by creation time (inclusive).
            created_before: Filter by creation time (exclusive).
            sort_by: Sort field (created_at, duration, cost).
            sort_order: Sort order (asc, desc).

        Returns:
            Tuple of (runs list, total count).
        """
        # Use SQLite if available
        if self._activity_store:
            status_str = status.value if status else None
            created_after_epoch = int(created_after.timestamp()) if created_after else None
            created_before_epoch = int(created_before.timestamp()) if created_before else None
            data_list, total = self._activity_store.list_agent_runs(
                limit=limit,
                offset=offset,
                agent_name=agent_name,
                status=status_str,
                created_after_epoch=created_after_epoch,
                created_before_epoch=created_before_epoch,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            runs = [self._dict_to_run(d) for d in data_list]
            return runs, total

        # Fall back to in-memory
        with self._runs_lock:
            runs = list(self._runs.values())
            if agent_name:
                runs = [r for r in runs if r.agent_name == agent_name]
            if status:
                runs = [r for r in runs if r.status == status]
            if created_after:
                runs = [r for r in runs if r.created_at >= created_after]
            if created_before:
                runs = [r for r in runs if r.created_at < created_before]

            # Sort by the requested field
            reverse = sort_order.lower() == "desc"
            if sort_by == "duration":
                runs.sort(key=lambda r: r.duration_seconds or 0, reverse=reverse)
            elif sort_by == "cost":
                runs.sort(key=lambda r: r.cost_usd or 0, reverse=reverse)
            else:
                runs.sort(key=lambda r: r.created_at, reverse=reverse)

            total = len(runs)
            runs = runs[offset : offset + limit]

            return runs, total

    async def execute(
        self,
        agent: AgentDefinition,
        task: str,
        run: AgentRun | None = None,
        agent_task: AgentTask | None = None,
    ) -> AgentRun:
        """Execute an agent with the given task.

        This is the main entry point for running an agent. It:
        1. Creates a run record if not provided
        2. Builds SDK options from agent definition (with task overrides)
        3. Runs the agent with timeout and graceful interrupt support
        4. Tracks results and handles errors

        Args:
            agent: Agent definition (template).
            task: Task description for the agent.
            run: Optional existing run record.
            agent_task: Optional task being executed.

        Returns:
            Updated AgentRun with results.
        """
        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeSDKClient,
                ResultMessage,
                TextBlock,
                ToolUseBlock,
            )
        except ImportError as e:
            if run:
                run.status = AgentRunStatus.FAILED
                run.error = "claude-agent-sdk not installed"
                run.completed_at = datetime.now()
            raise RuntimeError("claude-agent-sdk not installed") from e

        # Create run record if not provided
        if run is None:
            run = self.create_run(agent, task, agent_task)

        # Get effective execution config (task overrides template)
        execution = self._get_effective_execution(agent, agent_task)

        # Mark as running
        run.status = AgentRunStatus.RUNNING
        run.started_at = datetime.now()

        # Persist status change to SQLite
        if self._activity_store:
            self._activity_store.update_agent_run(
                run_id=run.id,
                status=run.status.value,
                started_at=run.started_at,
            )

        # Determine effective provider: task override > global config > None (cloud default)
        effective_provider = execution.provider
        if effective_provider is None and self._agent_config.provider_type != "cloud":
            # Fall back to global agent config provider settings
            from open_agent_kit.features.codebase_intelligence.agents.models import (
                AgentProvider,
            )

            effective_provider = AgentProvider(
                type=self._agent_config.provider_type,  # type: ignore[arg-type]
                base_url=self._agent_config.provider_base_url,
                api_key=None,  # Global config doesn't store API keys
                model=self._agent_config.provider_model,
            )
            logger.info(
                f"Using global provider config: type={effective_provider.type}, "
                f"base_url={effective_provider.base_url}, model={effective_provider.model}"
            )

        # Apply provider environment variables if configured
        original_env = self._apply_provider_env(effective_provider)

        try:
            # Build options with effective execution config
            options = self._build_options(agent, execution)

            # Build task prompt with config injection
            task_prompt = self._build_task_prompt(agent, task, agent_task)

            result_text_parts: list[str] = []
            turns_count = 0

            provider_info = f", provider={effective_provider.type}" if effective_provider else ""
            # Determine effective model for logging
            effective_model = None
            if effective_provider and effective_provider.model:
                effective_model = effective_provider.model
            elif execution.model:
                effective_model = execution.model
            model_info = f", model={effective_model}" if effective_model else ""
            logger.debug(
                f"Agent run {run.id}: Starting query with prompt length {len(task_prompt)}, "
                f"timeout={execution.timeout_seconds}s, max_turns={execution.max_turns}"
                f"{model_info}{provider_info}"
            )

            # Use ClaudeSDKClient for bidirectional communication with MCP servers
            # The query() function doesn't support MCP servers properly
            # Retry logic for transient failures with exponential backoff
            last_error: Exception | None = None
            for attempt in range(AGENT_RETRY_MAX_ATTEMPTS):
                try:
                    async with asyncio.timeout(execution.timeout_seconds):
                        async with ClaudeSDKClient(options=options) as client:
                            # Track active client for interrupt support
                            with self._clients_lock:
                                self._active_clients[run.id] = client

                            try:
                                await client.query(task_prompt)
                                msg_count = 0
                                async for msg in client.receive_response():
                                    msg_count += 1
                                    logger.debug(
                                        f"Agent run {run.id}: Received message {msg_count}: "
                                        f"type={type(msg).__name__}"
                                    )
                                    if isinstance(msg, AssistantMessage):
                                        turns_count += 1
                                        for block in msg.content:
                                            if isinstance(block, TextBlock):
                                                result_text_parts.append(block.text)
                                            elif isinstance(block, ToolUseBlock):
                                                # Track file operations
                                                tool_name = block.name
                                                tool_input = block.input or {}

                                                if tool_name == "Write":
                                                    file_path = tool_input.get("file_path", "")
                                                    if file_path:
                                                        run.files_created.append(file_path)
                                                elif tool_name == "Edit":
                                                    file_path = tool_input.get("file_path", "")
                                                    if (
                                                        file_path
                                                        and file_path not in run.files_modified
                                                    ):
                                                        run.files_modified.append(file_path)

                                    elif isinstance(msg, ResultMessage):
                                        # Capture cost if available
                                        if msg.total_cost_usd:
                                            run.cost_usd = msg.total_cost_usd
                                        # Capture token usage if available
                                        if hasattr(msg, "input_tokens") and msg.input_tokens:
                                            run.input_tokens = msg.input_tokens
                                        if hasattr(msg, "output_tokens") and msg.output_tokens:
                                            run.output_tokens = msg.output_tokens

                                # Log summary after response loop completes
                                logger.debug(
                                    f"Agent run {run.id}: Response loop finished - "
                                    f"messages={msg_count}, turns={turns_count}"
                                )
                                # Add warning if no messages received (provider compatibility issue)
                                if msg_count == 0:
                                    warning_msg = (
                                        "No response from provider - the provider may not support "
                                        "Claude Code's API format (e.g., ?beta=true query parameter)"
                                    )
                                    run.warnings.append(warning_msg)
                                    logger.warning(f"Agent run {run.id}: {warning_msg}")
                            finally:
                                # Always untrack client
                                with self._clients_lock:
                                    self._active_clients.pop(run.id, None)

                    # Success - break out of retry loop
                    last_error = None
                    break

                except TimeoutError:
                    # Timeout is not retried - handle below
                    raise

                except Exception as e:
                    last_error = e
                    if not self._is_transient_error(e) or attempt == AGENT_RETRY_MAX_ATTEMPTS - 1:
                        # Non-transient error or final attempt - re-raise
                        raise

                    # Transient error - retry with exponential backoff
                    wait_time = AGENT_RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Agent run {run.id}: Transient error on attempt {attempt + 1}/"
                        f"{AGENT_RETRY_MAX_ATTEMPTS}, retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)

                    # Reset state for retry (keep run record, clear partial results)
                    result_text_parts.clear()
                    turns_count = 0

            # If we exited the loop with last_error set, the final retry also failed
            if last_error is not None:
                raise last_error

            # Fall through to TimeoutError handling below if timeout occurred
            # (TimeoutError is raised, not caught by the Exception handler)

        except TimeoutError:
            # Attempt graceful interrupt before hard timeout
            with self._clients_lock:
                active_client = self._active_clients.pop(run.id, None)

            if active_client:
                try:
                    logger.info(f"Agent run {run.id}: Attempting graceful interrupt")
                    await active_client.interrupt()
                    # Give grace period for clean shutdown
                    await asyncio.sleep(AGENT_INTERRUPT_GRACE_SECONDS)
                except (RuntimeError, OSError, AttributeError) as interrupt_err:
                    logger.debug(f"Interrupt failed (expected): {interrupt_err}")

            run.status = AgentRunStatus.TIMEOUT
            run.error = f"Execution timed out after {execution.timeout_seconds}s"
            run.completed_at = datetime.now()
            logger.warning(f"Agent run {run.id} timed out")

        except asyncio.CancelledError:
            # Clean up active client tracking on cancellation
            with self._clients_lock:
                self._active_clients.pop(run.id, None)

            run.status = AgentRunStatus.CANCELLED
            run.error = "Execution cancelled"
            run.completed_at = datetime.now()
            logger.info(f"Agent run {run.id} was cancelled")

        except Exception as e:
            # Clean up active client tracking on error
            with self._clients_lock:
                self._active_clients.pop(run.id, None)

            # Catch all exceptions including SDK timeouts, connection errors, etc.
            import traceback

            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now()

            # Log full traceback for debugging
            tb_str = traceback.format_exc()
            logger.error(f"Agent run {run.id} failed: {e}\n{tb_str}")

        else:
            # Success case - update run with results
            run.turns_used = turns_count
            if result_text_parts:
                run.result = "\n".join(result_text_parts)
            run.status = AgentRunStatus.COMPLETED
            run.completed_at = datetime.now()

            logger.info(
                f"Agent run {run.id} completed: status={run.status}, "
                f"turns={run.turns_used}, cost=${run.cost_usd or 0:.4f}"
            )

        finally:
            # Always restore original environment variables
            self._restore_provider_env(original_env)

        # Persist final state to SQLite
        self._persist_run_completion(run)

        return run

    def _persist_run_completion(self, run: AgentRun) -> None:
        """Persist run completion state to SQLite.

        Args:
            run: Completed run record.
        """
        if not self._activity_store:
            return

        self._activity_store.update_agent_run(
            run_id=run.id,
            status=run.status.value,
            completed_at=run.completed_at,
            result=run.result,
            error=run.error,
            turns_used=run.turns_used,
            cost_usd=run.cost_usd,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            files_created=run.files_created if run.files_created else None,
            files_modified=run.files_modified if run.files_modified else None,
            files_deleted=run.files_deleted if run.files_deleted else None,
            warnings=run.warnings if run.warnings else None,
        )

    async def cancel(self, run_id: str) -> bool:
        """Cancel a running agent.

        Args:
            run_id: ID of the run to cancel.

        Returns:
            True if cancellation was initiated, False if run not found or not running.
        """
        run = self.get_run(run_id)
        if not run:
            return False

        if run.is_terminal():
            return False

        # Mark as cancelled
        run.status = AgentRunStatus.CANCELLED
        run.error = "Cancelled by user"
        run.completed_at = datetime.now()

        # Persist to SQLite
        self._persist_run_completion(run)

        # Note: With the query() API, we cannot cancel the subprocess directly.
        # The subprocess will continue running until completion or timeout,
        # but the run status is correctly marked as cancelled.

        logger.info(f"Agent run {run_id} cancelled")
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert executor state to dictionary for API responses.

        Returns:
            Dictionary with executor statistics.
        """
        with self._runs_lock:
            total_runs = len(self._runs)
            active_runs = sum(1 for r in self._runs.values() if r.status == AgentRunStatus.RUNNING)

        return {
            "project_root": str(self._project_root),
            "total_runs": total_runs,
            "active_runs": active_runs,
            "ci_tools_available": self._retrieval_engine is not None,
        }
