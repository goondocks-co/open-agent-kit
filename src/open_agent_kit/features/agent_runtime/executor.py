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
import os
import shutil
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal

import yaml

from open_agent_kit.features.acp_server.constants import ACP_MODE_BYPASS_PERMISSIONS
from open_agent_kit.features.agent_runtime.constants import (
    AGENT_FORBIDDEN_TOOLS,
    AGENT_INTERRUPT_GRACE_SECONDS,
    AGENT_RETRY_BASE_DELAY,
    AGENT_RETRY_MAX_ATTEMPTS,
    OAK_MCP_SERVER_NAME,
    TOOL_NAME_BASH,
    TOOL_NAME_EDIT,
    TOOL_NAME_WRITE,
)
from open_agent_kit.features.agent_runtime.mcp_cache import OakMcpServerCache
from open_agent_kit.features.agent_runtime.models import (
    AgentDefinition,
    AgentExecution,
    AgentPermissionMode,
    AgentProvider,
    AgentRun,
    AgentRunStatus,
    AgentTask,
)
from open_agent_kit.features.agent_runtime.run_store import RunStore
from open_agent_kit.features.agent_runtime.tools import build_oak_tools_from_access

if TYPE_CHECKING:
    from collections.abc import Callable

    from open_agent_kit.features.team.activity.store import ActivityStore
    from open_agent_kit.features.team.config import AgentConfig, CIConfig
    from open_agent_kit.features.team.memory.store import VectorStore
    from open_agent_kit.features.team.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Executor for running OAK agents via claude-agent-sdk."""

    def __init__(
        self,
        project_root: Path,
        agent_config: "AgentConfig",
        retrieval_engine: "RetrievalEngine | None" = None,
        activity_store: "ActivityStore | None" = None,
        vector_store: "VectorStore | None" = None,
        config_accessor: "Callable[[], CIConfig | None] | None" = None,
    ):
        self._project_root = project_root
        self._config_accessor = config_accessor
        self._fallback_agent_config = agent_config
        self._retrieval_engine = retrieval_engine
        self._activity_store = activity_store
        self._vector_store = vector_store

        # Run tracking (delegated to RunStore)
        self._run_store = RunStore(activity_store=activity_store)

        # Active SDK clients for interrupt support (run_id -> client)
        self._active_clients: dict[str, Any] = {}
        self._clients_lock = RLock()

        # MCP server cache
        self._oak_mcp_cache = OakMcpServerCache(
            retrieval_engine=retrieval_engine,
            activity_store=activity_store,
            vector_store=vector_store,
        )

        # Additional MCP servers injected at runtime (name -> server config)
        self._additional_mcp_servers: dict[str, Any] = {}

    @property
    def _agent_config(self) -> "AgentConfig":
        """Get agent config from live config accessor or static fallback."""
        if self._config_accessor is not None:
            config = self._config_accessor()
            if config is not None:
                return config.agents
        return self._fallback_agent_config

    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return self._project_root

    @property
    def runs(self) -> dict[str, AgentRun]:
        """Get all run records (copy for thread safety)."""
        return self._run_store.runs

    @property
    def max_cache_size(self) -> int:
        """Get the maximum in-memory cache size from config."""
        return self._agent_config.executor_cache_size

    def add_mcp_server(self, name: str, server: Any) -> None:
        """Register an additional MCP server to be injected into all agent runs.

        Args:
            name: Server name (used as key in mcp_servers dict).
            server: McpSdkServerConfig instance from create_sdk_mcp_server().
        """
        self._additional_mcp_servers[name] = server

    def _get_external_mcp_servers(self, agent: AgentDefinition) -> dict[str, Any]:
        """Phase 2 injection point for SDLC provider MCP servers. Returns empty dict."""
        return {}

    def _get_effective_execution(
        self,
        agent: AgentDefinition,
        task: AgentTask | None = None,
    ) -> AgentExecution:
        """Get effective execution config, preferring task overrides over template defaults."""
        base = agent.execution

        if task and task.execution:
            task_exec = task.execution
            overrides: dict[str, Any] = {
                "model": task_exec.model,
                "provider": task_exec.provider,
            }
            if task_exec.timeout_seconds:
                overrides["timeout_seconds"] = task_exec.timeout_seconds
            if task_exec.max_turns:
                overrides["max_turns"] = task_exec.max_turns
            if task_exec.permission_mode:
                overrides["permission_mode"] = task_exec.permission_mode
            return base.model_copy(update=overrides)

        return base

    def _apply_provider_env(self, provider: AgentProvider | None) -> dict[str, str | None]:
        """Apply provider env vars, returning originals for restoration."""
        if provider is None:
            return {}

        original_values: dict[str, str | None] = {}
        for key, value in provider.env_vars.items():
            original_values[key] = os.environ.get(key)
            os.environ[key] = value
            logger.debug(f"Set {key} for provider {provider.type}")

        return original_values

    def _restore_provider_env(self, original_values: dict[str, str | None]) -> None:
        """Restore original environment variables after provider execution."""
        for key, original_value in original_values.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

    def _build_options(
        self,
        agent: AgentDefinition,
        execution: AgentExecution | None = None,
        additional_tools: list[str] | None = None,
    ) -> Any:
        """Build ClaudeAgentOptions from agent definition."""
        try:
            from claude_agent_sdk import ClaudeAgentOptions
        except ImportError as e:
            raise RuntimeError("claude-agent-sdk not installed") from e

        # Use provided execution config or template default
        effective_execution = execution or agent.execution

        # Check if additional_tools contains a Bash override pattern.
        # When a task declares additional_tools: ["Bash"] or ["Bash(git *)"],
        # the Bash restriction is lifted for that execution only.
        # Task remains permanently forbidden regardless.
        has_bash_override = any(
            t == TOOL_NAME_BASH or t.startswith(TOOL_NAME_BASH + "(")
            for t in (additional_tools or [])
        )
        forbidden = AGENT_FORBIDDEN_TOOLS
        if has_bash_override:
            forbidden = tuple(t for t in AGENT_FORBIDDEN_TOOLS if t != TOOL_NAME_BASH)

        # Build allowed tools list, filtering forbidden tools
        allowed_tools = [t for t in agent.get_effective_tools() if t not in forbidden]

        # Merge task-level additional tools (e.g., scoped Bash patterns)
        if additional_tools:
            for tool in additional_tools:
                if tool not in forbidden and tool not in allowed_tools:
                    allowed_tools.append(tool)

        # Inject external MCP servers declared by the agent (Phase 2 hook)
        mcp_servers: dict[str, Any] = {}
        external_servers = self._get_external_mcp_servers(agent)
        mcp_servers.update(external_servers)

        # Inject additional MCP servers registered via add_mcp_server()
        mcp_servers.update(self._additional_mcp_servers)

        # Build enabled OAK tools set from tool_access flags
        enabled_oak_tools = build_oak_tools_from_access(agent.tool_access)
        if enabled_oak_tools is not None:
            oak_server = self._oak_mcp_cache.get(enabled_oak_tools)
            if oak_server:
                mcp_servers[OAK_MCP_SERVER_NAME] = oak_server
                # Add OAK tool names to allowed list
                for tool_name in enabled_oak_tools:
                    allowed_tools.append(f"mcp__{OAK_MCP_SERVER_NAME}__{tool_name}")
            else:
                logger.warning(
                    f"OAK MCP server unavailable for agent '{agent.name}' - OAK tools will not work"
                )

        # Map permission mode
        permission_mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"] = "default"
        if effective_execution.permission_mode == AgentPermissionMode.ACCEPT_EDITS:
            permission_mode = "acceptEdits"
        elif effective_execution.permission_mode == AgentPermissionMode.BYPASS_PERMISSIONS:
            permission_mode = ACP_MODE_BYPASS_PERMISSIONS

        # Determine model to use (execution config or provider fallback)
        model = effective_execution.model
        if model is None and effective_execution.provider:
            model = effective_execution.provider.model

        # Build a clean env for the SDK subprocess.
        # The SDK merges os.environ with options.env (user env wins on overlap),
        # so we must explicitly blank CLAUDECODE rather than just omitting it —
        # otherwise the daemon's value leaks through from os.environ.
        clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        clean_env["CLAUDECODE"] = ""

        # Prefer the system-installed claude binary over the SDK's bundled one.
        # The user authenticates via `/login` against the system binary; the
        # bundled binary may be a different version with incompatible auth state.
        system_cli = shutil.which("claude")

        options = ClaudeAgentOptions(
            system_prompt=agent.system_prompt,
            allowed_tools=allowed_tools,
            max_turns=effective_execution.max_turns,
            permission_mode=permission_mode,
            cwd=str(self._project_root),
            env=clean_env,
        )
        if system_cli:
            options.cli_path = system_cli

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
        """Build the task prompt, injecting task config and runtime context as YAML."""
        # Get daemon port for this project
        from open_agent_kit.features.team.daemon.manager import (
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

            if agent_task.oak_queries:
                config["oak_queries"] = {
                    phase: [q.model_dump(exclude_none=True) for q in queries]
                    for phase, queries in agent_task.oak_queries.items()
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

    def _is_transient_error(self, error: Exception) -> bool:
        """Check if an error is transient (connection, rate-limit) and worth retrying."""
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
        """Create a new run record (delegates to RunStore)."""
        self._run_store.max_cache_size = self.max_cache_size
        return self._run_store.create(agent, task, agent_task)

    def get_run(self, run_id: str) -> AgentRun | None:
        """Get a run by ID (delegates to RunStore)."""
        return self._run_store.get(run_id)

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
        """List runs with optional filtering and sorting (delegates to RunStore)."""
        return self._run_store.list(
            limit=limit,
            offset=offset,
            agent_name=agent_name,
            status=status,
            created_after=created_after,
            created_before=created_before,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def _do_execute_with_retry(
        self,
        run: AgentRun,
        options: Any,
        task_prompt: str,
        execution: AgentExecution,
    ) -> tuple[list[str], int]:
        """Run the SDK client with retry logic for transient failures."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeSDKClient,
            ResultMessage,
            TextBlock,
            ToolUseBlock,
        )

        result_text_parts: list[str] = []
        turns_count = 0
        last_error: Exception | None = None

        for attempt in range(AGENT_RETRY_MAX_ATTEMPTS):
            try:
                async with asyncio.timeout(execution.timeout_seconds):
                    async with ClaudeSDKClient(options=options) as client:
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
                                            self._track_file_operation(run, block)

                                elif isinstance(msg, ResultMessage):
                                    self._capture_result_metrics(run, msg)

                            logger.debug(
                                f"Agent run {run.id}: Response loop finished - "
                                f"messages={msg_count}, turns={turns_count}"
                            )
                            if msg_count == 0:
                                warning_msg = (
                                    "No response from provider - the provider may not support "
                                    "Claude Code's API format (e.g., ?beta=true query parameter)"
                                )
                                run.warnings.append(warning_msg)
                                logger.warning(f"Agent run {run.id}: {warning_msg}")
                        finally:
                            with self._clients_lock:
                                self._active_clients.pop(run.id, None)

                last_error = None
                break

            except TimeoutError:
                raise

            except Exception as e:  # broad catch intentional: SDK may raise any error type
                last_error = e
                if not self._is_transient_error(e) or attempt == AGENT_RETRY_MAX_ATTEMPTS - 1:
                    raise

                wait_time = AGENT_RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    f"Agent run {run.id}: Transient error on attempt {attempt + 1}/"
                    f"{AGENT_RETRY_MAX_ATTEMPTS}, retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)

                result_text_parts.clear()
                turns_count = 0

        if last_error is not None:
            raise last_error

        return result_text_parts, turns_count

    @staticmethod
    def _track_file_operation(run: AgentRun, block: Any) -> None:
        """Record file create/modify from a ToolUseBlock on the run."""
        tool_name = block.name
        tool_input = block.input or {}

        if tool_name == TOOL_NAME_WRITE:
            file_path = tool_input.get("file_path", "")
            if file_path:
                run.files_created.append(file_path)
        elif tool_name == TOOL_NAME_EDIT:
            file_path = tool_input.get("file_path", "")
            if file_path and file_path not in run.files_modified:
                run.files_modified.append(file_path)

    @staticmethod
    def _capture_result_metrics(run: AgentRun, msg: Any) -> None:
        """Capture cost and token metrics from a ResultMessage."""
        if msg.total_cost_usd:
            run.cost_usd = msg.total_cost_usd
        if hasattr(msg, "input_tokens") and msg.input_tokens:
            run.input_tokens = msg.input_tokens
        if hasattr(msg, "output_tokens") and msg.output_tokens:
            run.output_tokens = msg.output_tokens

    async def execute(
        self,
        agent: AgentDefinition,
        task: str,
        run: AgentRun | None = None,
        agent_task: AgentTask | None = None,
    ) -> AgentRun:
        """Execute an agent: create run, build options, run with timeout, track results."""
        try:
            from claude_agent_sdk import ClaudeSDKClient  # noqa: F401 — verify installed
        except ImportError as e:
            if run:
                run.status = AgentRunStatus.FAILED
                run.error = "claude-agent-sdk not installed"
                run.completed_at = datetime.now()
            raise RuntimeError("claude-agent-sdk not installed") from e

        if run is None:
            run = self.create_run(agent, task, agent_task)

        execution = self._get_effective_execution(agent, agent_task)

        run.status = AgentRunStatus.RUNNING
        run.started_at = datetime.now()

        if self._activity_store:
            self._activity_store.update_agent_run(
                run_id=run.id,
                status=run.status.value,
                started_at=run.started_at,
                timeout_seconds=execution.timeout_seconds,
            )

        # Determine effective provider: task override > global config > None (cloud default)
        effective_provider = execution.provider
        if effective_provider is None and self._agent_config.provider_type != "cloud":
            effective_provider = AgentProvider(
                type=self._agent_config.provider_type,  # type: ignore[arg-type]
                base_url=self._agent_config.provider_base_url,
                api_key=None,
                model=self._agent_config.provider_model,
            )
            logger.info(
                f"Using global provider config: type={effective_provider.type}, "
                f"base_url={effective_provider.base_url}, model={effective_provider.model}"
            )

        original_env = self._apply_provider_env(effective_provider)

        try:
            options = self._build_options(
                agent,
                execution,
                additional_tools=agent_task.additional_tools if agent_task else None,
            )

            if effective_provider and effective_provider.model:
                options.model = effective_provider.model

            task_prompt = self._build_task_prompt(agent, task, agent_task)

            self._log_execution_start(run, task_prompt, execution, effective_provider)

            result_text_parts, turns_count = await self._do_execute_with_retry(
                run, options, task_prompt, execution
            )

        except TimeoutError:
            await self._handle_timeout(run, execution)

        except asyncio.CancelledError:
            with self._clients_lock:
                self._active_clients.pop(run.id, None)
            run.status = AgentRunStatus.CANCELLED
            run.error = "Execution cancelled"
            run.completed_at = datetime.now()
            logger.info(f"Agent run {run.id} was cancelled")

        except Exception as e:  # broad catch intentional: top-level run handler must update status
            with self._clients_lock:
                self._active_clients.pop(run.id, None)
            import traceback

            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now()
            logger.error(f"Agent run {run.id} failed: {e}\n{traceback.format_exc()}")

        else:
            run.turns_used = turns_count
            if result_text_parts:
                run.result = "\n".join(result_text_parts)

            if self._is_auth_failure(run.result, run.cost_usd, turns_count):
                run.status = AgentRunStatus.FAILED
                run.error = (
                    "Authentication failed: the Claude Code subprocess is not logged in. "
                    "Try restarting the daemon after running /login, or check that the "
                    "claude binary is accessible in the daemon's PATH."
                )
                run.completed_at = datetime.now()
                logger.warning(
                    f"Agent run {run.id} detected as auth failure: "
                    f"result={run.result!r}, cost={run.cost_usd}, turns={turns_count}"
                )
            else:
                run.status = AgentRunStatus.COMPLETED
                run.completed_at = datetime.now()
                logger.info(
                    f"Agent run {run.id} completed: status={run.status}, "
                    f"turns={run.turns_used}, cost=${run.cost_usd or 0:.4f}"
                )

        finally:
            self._restore_provider_env(original_env)

        self._persist_run_completion(run)
        return run

    @staticmethod
    def _is_auth_failure(
        result: str | None,
        cost: float | None,
        turns: int,
    ) -> bool:
        """Detect Claude Code auth failures that masquerade as successful completions.

        When the subprocess can't authenticate (e.g. missing OAuth tokens after daemon
        restart), it returns a short "Not logged in" message with zero cost in one turn.
        """
        if turns > 1:
            return False
        if cost is not None and cost > 0:
            return False
        if not result:
            return False
        return "not logged in" in result.lower()

    def _log_execution_start(
        self,
        run: AgentRun,
        task_prompt: str,
        execution: AgentExecution,
        provider: AgentProvider | None,
    ) -> None:
        """Log execution start with provider and model info."""
        provider_info = f", provider={provider.type}" if provider else ""
        effective_model = None
        if provider and provider.model:
            effective_model = provider.model
        elif execution.model:
            effective_model = execution.model
        model_info = f", model={effective_model}" if effective_model else ""
        logger.debug(
            f"Agent run {run.id}: Starting query with prompt length {len(task_prompt)}, "
            f"timeout={execution.timeout_seconds}s, max_turns={execution.max_turns}"
            f"{model_info}{provider_info}"
        )

    async def _handle_timeout(self, run: AgentRun, execution: AgentExecution) -> None:
        """Handle timeout: attempt graceful interrupt, update run status."""
        with self._clients_lock:
            active_client = self._active_clients.pop(run.id, None)

        if active_client:
            try:
                logger.info(f"Agent run {run.id}: Attempting graceful interrupt")
                await active_client.interrupt()
                await asyncio.sleep(AGENT_INTERRUPT_GRACE_SECONDS)
            except (RuntimeError, OSError, AttributeError) as interrupt_err:
                logger.debug(f"Interrupt failed (expected): {interrupt_err}")

        run.status = AgentRunStatus.TIMEOUT
        run.error = f"Execution timed out after {execution.timeout_seconds}s"
        run.completed_at = datetime.now()
        logger.warning(f"Agent run {run.id} timed out")

    def persist_completion(self, run: AgentRun) -> None:
        """Persist run completion state to SQLite (delegates to RunStore)."""
        self._run_store.persist_completion(run)

    def _persist_run_completion(self, run: AgentRun) -> None:
        """Backward-compatible alias — prefer ``persist_completion``."""
        self.persist_completion(run)

    async def cancel(self, run_id: str) -> bool:
        """Cancel a running agent (delegates to RunStore)."""
        return self._run_store.cancel(run_id)

    def to_dict(self) -> dict[str, Any]:
        """Convert executor state to dictionary for API responses."""
        all_runs = self._run_store.runs
        return {
            "project_root": str(self._project_root),
            "total_runs": len(all_runs),
            "active_runs": sum(1 for r in all_runs.values() if r.status == AgentRunStatus.RUNNING),
            "oak_tools_available": self._retrieval_engine is not None,
        }
