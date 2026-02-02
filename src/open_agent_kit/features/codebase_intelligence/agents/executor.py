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
    AgentInstance,
    AgentPermissionMode,
    AgentRun,
    AgentRunStatus,
)
from open_agent_kit.features.codebase_intelligence.agents.tools import create_ci_mcp_server
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_FORBIDDEN_TOOLS,
    AGENT_INTERRUPT_GRACE_SECONDS,
    CI_MCP_SERVER_NAME,
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

        # MCP server for CI tools (lazy initialization)
        self._ci_mcp_server: McpSdkServerConfig | None = None

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

    def _get_ci_mcp_server(self) -> "McpSdkServerConfig | None":
        """Get or create the CI MCP server.

        Returns:
            SDKMCPServer instance, or None if unavailable.
        """
        if self._ci_mcp_server is not None:
            return self._ci_mcp_server

        if self._retrieval_engine is None:
            logger.warning("Cannot create CI MCP server - no retrieval engine")
            return None

        self._ci_mcp_server = create_ci_mcp_server(
            retrieval_engine=self._retrieval_engine,
            activity_store=self._activity_store,
            vector_store=self._vector_store,
        )
        return self._ci_mcp_server

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
        instance: AgentInstance | None = None,
    ) -> AgentExecution:
        """Get effective execution config, preferring instance overrides.

        Instance config takes precedence over template defaults for timeout_seconds,
        max_turns, and permission_mode. This allows per-instance tuning of resource
        limits based on task complexity.

        Args:
            agent: Agent definition (template) with default execution config.
            instance: Optional instance with execution overrides.

        Returns:
            AgentExecution with merged settings.
        """
        base = agent.execution

        if instance and instance.execution:
            inst_exec = instance.execution
            return AgentExecution(
                timeout_seconds=inst_exec.timeout_seconds or base.timeout_seconds,
                max_turns=inst_exec.max_turns or base.max_turns,
                permission_mode=inst_exec.permission_mode or base.permission_mode,
            )

        return base

    def _build_options(
        self,
        agent: AgentDefinition,
        execution: AgentExecution | None = None,
    ) -> Any:
        """Build ClaudeAgentOptions from agent definition.

        Args:
            agent: Agent definition with configuration.
            execution: Optional execution config override (from instance).

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

        # Add CI MCP tools if agent has CI access
        mcp_servers: dict[str, Any] = {}
        if agent.ci_access.code_search or agent.ci_access.memory_search:
            ci_server = self._get_ci_mcp_server()
            if ci_server:
                mcp_servers[CI_MCP_SERVER_NAME] = ci_server
                # Add CI tool names to allowed list
                if agent.ci_access.code_search:
                    allowed_tools.append(f"mcp__{CI_MCP_SERVER_NAME}__ci_search")
                if agent.ci_access.memory_search:
                    allowed_tools.append(f"mcp__{CI_MCP_SERVER_NAME}__ci_memories")
                if agent.ci_access.session_history:
                    allowed_tools.append(f"mcp__{CI_MCP_SERVER_NAME}__ci_sessions")
                if agent.ci_access.project_stats:
                    allowed_tools.append(f"mcp__{CI_MCP_SERVER_NAME}__ci_project_stats")

        # Map permission mode
        permission_mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"] = "default"
        if effective_execution.permission_mode == AgentPermissionMode.ACCEPT_EDITS:
            permission_mode = "acceptEdits"
        elif effective_execution.permission_mode == AgentPermissionMode.BYPASS_PERMISSIONS:
            permission_mode = "bypassPermissions"

        options = ClaudeAgentOptions(
            system_prompt=agent.system_prompt,
            allowed_tools=allowed_tools,
            disallowed_tools=list(AGENT_FORBIDDEN_TOOLS),
            max_turns=effective_execution.max_turns,
            permission_mode=permission_mode,
            cwd=str(self._project_root),
        )

        # Add MCP servers if any
        if mcp_servers:
            options.mcp_servers = mcp_servers

        return options

    def _build_task_prompt(
        self,
        agent: AgentDefinition,
        task: str,
        instance: AgentInstance | None = None,
    ) -> str:
        """Build the task prompt, optionally injecting instance configuration.

        If an instance is provided, its configuration (maintained_files, ci_queries,
        output_requirements, style) is appended to the task as YAML.

        Also injects runtime context like daemon_url for linking to sessions.

        Args:
            agent: Agent definition (template).
            task: Task description (usually instance.default_task).
            instance: Optional instance with configuration.

        Returns:
            Task prompt with config injected if available.
        """
        # Get daemon port for this project
        from open_agent_kit.features.codebase_intelligence.daemon.manager import (
            get_project_port,
        )

        daemon_port = get_project_port(self._project_root)
        daemon_url = f"http://localhost:{daemon_port}"

        if instance:
            # Build instance configuration block
            config: dict[str, Any] = {}

            # CRITICAL: Inject project_root so the agent knows where it's working
            # Without this, the agent may hallucinate paths or get confused
            project_root_str = str(self._project_root)
            config["project_root"] = project_root_str

            # Inject daemon URL for session/memory links
            config["daemon_url"] = daemon_url

            if instance.maintained_files:
                # Resolve {project_root} placeholder in paths
                config["maintained_files"] = [
                    {
                        **mf.model_dump(exclude_none=True),
                        "path": mf.path.replace("{project_root}", project_root_str),
                    }
                    for mf in instance.maintained_files
                ]

            if instance.ci_queries:
                config["ci_queries"] = {
                    phase: [q.model_dump(exclude_none=True) for q in queries]
                    for phase, queries in instance.ci_queries.items()
                }

            if instance.output_requirements:
                config["output_requirements"] = instance.output_requirements

            if instance.style:
                config["style"] = instance.style

            if instance.extra:
                config["extra"] = instance.extra

            config_yaml = yaml.dump(config, default_flow_style=False, sort_keys=False)
            return f"{task}\n\n## Instance Configuration\n```yaml\n{config_yaml}```"

        # No instance - inject project_root and daemon URL as runtime context
        runtime_context = f"project_root: {self._project_root}\ndaemon_url: {daemon_url}"
        return f"{task}\n\n## Runtime Context\n```yaml\n{runtime_context}\n```"

        # Legacy: use project_config if no instance
        if agent.project_config:
            config_yaml = yaml.dump(agent.project_config, default_flow_style=False, sort_keys=False)
            return f"{task}\n\n## Project Configuration\n```yaml\n{config_yaml}```"

        return task

    def create_run(
        self,
        agent: AgentDefinition,
        task: str,
        instance: AgentInstance | None = None,
    ) -> AgentRun:
        """Create a new run record.

        Persists to SQLite if ActivityStore is available, and caches in memory.

        Args:
            agent: Agent definition (template).
            task: Task description.
            instance: Optional instance being run.

        Returns:
            New AgentRun instance.
        """
        import hashlib

        # Use instance name if running an instance, otherwise template name
        agent_name = instance.name if instance else agent.name

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

            # Build config from instance or legacy project_config
            project_config = None
            if instance:
                project_config = {
                    "instance_name": instance.name,
                    "agent_type": instance.agent_type,
                    "maintained_files": [
                        mf.model_dump(exclude_none=True) for mf in instance.maintained_files
                    ],
                    "ci_queries": {
                        phase: [q.model_dump(exclude_none=True) for q in queries]
                        for phase, queries in instance.ci_queries.items()
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
    ) -> tuple[list[AgentRun], int]:
        """List runs with optional filtering.

        Uses SQLite if available (for durability), falls back to in-memory.

        Args:
            limit: Maximum runs to return.
            offset: Pagination offset.
            agent_name: Filter by agent name.
            status: Filter by status.

        Returns:
            Tuple of (runs list, total count).
        """
        # Use SQLite if available
        if self._activity_store:
            status_str = status.value if status else None
            data_list, total = self._activity_store.list_agent_runs(
                limit=limit,
                offset=offset,
                agent_name=agent_name,
                status=status_str,
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

            runs.sort(key=lambda r: r.created_at, reverse=True)
            total = len(runs)
            runs = runs[offset : offset + limit]

            return runs, total

    async def execute(
        self,
        agent: AgentDefinition,
        task: str,
        run: AgentRun | None = None,
        instance: AgentInstance | None = None,
    ) -> AgentRun:
        """Execute an agent with the given task.

        This is the main entry point for running an agent. It:
        1. Creates a run record if not provided
        2. Builds SDK options from agent definition (with instance overrides)
        3. Runs the agent with timeout and graceful interrupt support
        4. Tracks results and handles errors

        Args:
            agent: Agent definition (template).
            task: Task description for the agent.
            run: Optional existing run record.
            instance: Optional instance being executed.

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
            run = self.create_run(agent, task, instance)

        # Get effective execution config (instance overrides template)
        execution = self._get_effective_execution(agent, instance)

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

        try:
            # Build options with effective execution config
            options = self._build_options(agent, execution)

            # Build task prompt with config injection
            task_prompt = self._build_task_prompt(agent, task, instance)

            result_text_parts: list[str] = []
            turns_count = 0

            logger.debug(
                f"Agent run {run.id}: Starting query with prompt length {len(task_prompt)}, "
                f"timeout={execution.timeout_seconds}s, max_turns={execution.max_turns}"
            )

            # Use ClaudeSDKClient for bidirectional communication with MCP servers
            # The query() function doesn't support MCP servers properly
            try:
                async with asyncio.timeout(execution.timeout_seconds):
                    async with ClaudeSDKClient(options=options) as client:
                        # Track active client for interrupt support
                        with self._clients_lock:
                            self._active_clients[run.id] = client

                        try:
                            await client.query(task_prompt)
                            async for msg in client.receive_response():
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
                        finally:
                            # Always untrack client
                            with self._clients_lock:
                                self._active_clients.pop(run.id, None)

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
                logger.warning(f"Agent run {run.id} timed out")

            # Update run with results
            run.turns_used = turns_count
            if result_text_parts:
                run.result = "\n".join(result_text_parts)

            # Mark completed if not already terminal
            if not run.is_terminal():
                run.status = AgentRunStatus.COMPLETED

            run.completed_at = datetime.now()

            logger.info(
                f"Agent run {run.id} completed: status={run.status}, "
                f"turns={run.turns_used}, cost=${run.cost_usd or 0:.4f}"
            )

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
            files_created=run.files_created if run.files_created else None,
            files_modified=run.files_modified if run.files_modified else None,
            files_deleted=run.files_deleted if run.files_deleted else None,
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
