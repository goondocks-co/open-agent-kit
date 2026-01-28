"""Agent Executor for running agents via claude-code-sdk.

This module provides the AgentExecutor class that manages agent execution
lifecycle including:
- Building claude-code-sdk options from agent definitions
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
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDefinition,
    AgentPermissionMode,
    AgentRun,
    AgentRunStatus,
)
from open_agent_kit.features.codebase_intelligence.agents.tools import create_ci_mcp_server
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_FORBIDDEN_TOOLS,
    AGENT_RUNS_CLEANUP_THRESHOLD,
    AGENT_RUNS_MAX_HISTORY,
    CI_MCP_SERVER_NAME,
)

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeSDKClient, SDKMCPServer

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Executor for running CI agents via claude-code-sdk.

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
        retrieval_engine: "RetrievalEngine | None" = None,
        activity_store: "ActivityStore | None" = None,
        vector_store: "VectorStore | None" = None,
    ):
        """Initialize the executor.

        Args:
            project_root: Project root directory for agent operations.
            retrieval_engine: RetrievalEngine for CI tools (optional).
            activity_store: ActivityStore for CI tools (optional).
            vector_store: VectorStore for CI tools (optional).
        """
        self._project_root = project_root
        self._retrieval_engine = retrieval_engine
        self._activity_store = activity_store
        self._vector_store = vector_store

        # Run tracking
        self._runs: OrderedDict[str, AgentRun] = OrderedDict()
        self._runs_lock = RLock()

        # Active client tracking for cancellation
        self._active_clients: dict[str, ClaudeSDKClient] = {}
        self._clients_lock = RLock()

        # MCP server for CI tools (lazy initialization)
        self._ci_mcp_server: SDKMCPServer | None = None

    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return self._project_root

    @property
    def runs(self) -> dict[str, AgentRun]:
        """Get all run records (copy for thread safety)."""
        with self._runs_lock:
            return dict(self._runs)

    def _get_ci_mcp_server(self) -> "SDKMCPServer | None":
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
        """Remove old runs when history exceeds threshold."""
        with self._runs_lock:
            if len(self._runs) <= AGENT_RUNS_CLEANUP_THRESHOLD:
                return

            # Keep only the most recent runs
            items = list(self._runs.items())
            to_remove = len(items) - AGENT_RUNS_MAX_HISTORY

            for i in range(to_remove):
                run_id = items[i][0]
                del self._runs[run_id]
                logger.debug(f"Cleaned up old run: {run_id}")

    def _build_options(
        self,
        agent: AgentDefinition,
    ) -> Any:
        """Build ClaudeAgentOptions from agent definition.

        Args:
            agent: Agent definition with configuration.

        Returns:
            ClaudeAgentOptions instance.
        """
        try:
            from claude_agent_sdk import ClaudeAgentOptions
        except ImportError as e:
            raise RuntimeError("claude-code-sdk not installed") from e

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
        permission_mode = "default"
        if agent.execution.permission_mode == AgentPermissionMode.ACCEPT_EDITS:
            permission_mode = "acceptEdits"
        elif agent.execution.permission_mode == AgentPermissionMode.BYPASS_PERMISSIONS:
            permission_mode = "bypassPermissions"

        options = ClaudeAgentOptions(
            system_prompt=agent.system_prompt,
            allowed_tools=allowed_tools,
            disallowed_tools=list(AGENT_FORBIDDEN_TOOLS),
            max_turns=agent.execution.max_turns,
            permission_mode=permission_mode,
            cwd=str(self._project_root),
        )

        # Add MCP servers if any
        if mcp_servers:
            options.mcp_servers = mcp_servers

        return options

    def create_run(self, agent: AgentDefinition, task: str) -> AgentRun:
        """Create a new run record.

        Args:
            agent: Agent definition.
            task: Task description.

        Returns:
            New AgentRun instance.
        """
        run = AgentRun(
            id=str(uuid4()),
            agent_name=agent.name,
            task=task,
            status=AgentRunStatus.PENDING,
            created_at=datetime.now(),
        )

        with self._runs_lock:
            self._runs[run.id] = run
            self._cleanup_old_runs()

        return run

    def get_run(self, run_id: str) -> AgentRun | None:
        """Get a run by ID.

        Args:
            run_id: Run identifier.

        Returns:
            AgentRun if found, None otherwise.
        """
        with self._runs_lock:
            return self._runs.get(run_id)

    def list_runs(
        self,
        limit: int = 20,
        offset: int = 0,
        agent_name: str | None = None,
        status: AgentRunStatus | None = None,
    ) -> tuple[list[AgentRun], int]:
        """List runs with optional filtering.

        Args:
            limit: Maximum runs to return.
            offset: Pagination offset.
            agent_name: Filter by agent name.
            status: Filter by status.

        Returns:
            Tuple of (runs list, total count).
        """
        with self._runs_lock:
            # Filter
            runs = list(self._runs.values())
            if agent_name:
                runs = [r for r in runs if r.agent_name == agent_name]
            if status:
                runs = [r for r in runs if r.status == status]

            # Sort by created_at descending (most recent first)
            runs.sort(key=lambda r: r.created_at, reverse=True)

            total = len(runs)
            runs = runs[offset : offset + limit]

            return runs, total

    async def execute(
        self,
        agent: AgentDefinition,
        task: str,
        run: AgentRun | None = None,
    ) -> AgentRun:
        """Execute an agent with the given task.

        This is the main entry point for running an agent. It:
        1. Creates a run record if not provided
        2. Builds SDK options from agent definition
        3. Runs the agent with timeout
        4. Tracks results and handles errors

        Args:
            agent: Agent definition.
            task: Task description for the agent.
            run: Optional existing run record.

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
                run.error = "claude-code-sdk not installed"
                run.completed_at = datetime.now()
            raise RuntimeError("claude-code-sdk not installed") from e

        # Create run record if not provided
        if run is None:
            run = self.create_run(agent, task)

        # Mark as running
        run.status = AgentRunStatus.RUNNING
        run.started_at = datetime.now()

        try:
            # Build options
            options = self._build_options(agent)

            # Create client and track for cancellation
            client = ClaudeSDKClient(options=options)
            with self._clients_lock:
                self._active_clients[run.id] = client

            result_text_parts: list[str] = []
            turns_count = 0

            try:
                async with client:
                    # Send the task prompt
                    await client.query(task)

                    # Process responses with timeout
                    try:
                        async with asyncio.timeout(agent.execution.timeout_seconds):
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

                    except TimeoutError:
                        run.status = AgentRunStatus.TIMEOUT
                        run.error = f"Execution timed out after {agent.execution.timeout_seconds}s"
                        logger.warning(f"Agent run {run.id} timed out")

            finally:
                # Remove from active clients
                with self._clients_lock:
                    self._active_clients.pop(run.id, None)

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
            run.status = AgentRunStatus.CANCELLED
            run.error = "Execution cancelled"
            run.completed_at = datetime.now()
            logger.info(f"Agent run {run.id} was cancelled")

        except (OSError, RuntimeError, ValueError) as e:
            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now()
            logger.error(f"Agent run {run.id} failed: {e}")

        return run

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

        # Close the client if active
        with self._clients_lock:
            client = self._active_clients.pop(run_id, None)
            if client:
                try:
                    # The context manager will handle cleanup
                    pass
                except (OSError, RuntimeError) as e:
                    logger.warning(f"Error closing client for {run_id}: {e}")

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
