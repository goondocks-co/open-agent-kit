"""Interactive Session Manager for ACP multi-turn conversations.

This module provides the InteractiveSessionManager that manages long-lived
Claude SDK sessions for ACP (Agent Client Protocol) conversations. Unlike
the AgentExecutor which runs single tasks to completion, this manager keeps
sessions alive across multiple prompt() calls for multi-turn interaction.

Each session tracks its own state (cwd, permission_mode, cancellation,
pending plan) and streams ExecutionEvents back to the caller via
async iterators.

Intelligence pipeline integration:
- Session-start context injection (CI status, session summaries)
- SDK hooks for activity recording (PostToolUse, PostToolUseFailure)
- Context search on prompt submit (code + memories)
- Proper batch finalization with response summaries + async observation extraction
- Session summary generation on close
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from open_agent_kit.features.acp_server.constants import ACP_AGENT_NAME
from open_agent_kit.features.codebase_intelligence.agents.tools import create_ci_mcp_server
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_MCP_SERVER_NAME,
    CI_TOOL_ARCHIVE,
    CI_TOOL_MEMORIES,
    CI_TOOL_PROJECT_STATS,
    CI_TOOL_QUERY,
    CI_TOOL_REMEMBER,
    CI_TOOL_RESOLVE,
    CI_TOOL_SEARCH,
    CI_TOOL_SESSIONS,
    INJECTION_MAX_SESSION_SUMMARIES,
    INJECTION_SESSION_START_REMINDER_BLOCK,
    PROMPT_SOURCE_PLAN,
)
from open_agent_kit.features.codebase_intelligence.daemon.models_acp import (
    CancelledEvent,
    CostEvent,
    DoneEvent,
    ErrorEvent,
    ExecutionEvent,
    PlanProposedEvent,
    TextEvent,
    ToolStartEvent,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.processor import (
        ActivityProcessor,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)

# Default system prompt when no ACP agent definition is registered
ACP_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI coding assistant with access to the project's "
    "codebase intelligence. Use the available tools to search code, "
    "access project memories, and understand the codebase."
)

# Maximum length for sanitized tool input string values
_SANITIZED_INPUT_MAX_LENGTH = 500

# Fields in tool_input that contain large content (file bodies, diffs)
_LARGE_CONTENT_FIELDS = frozenset({"content", "new_source", "old_string", "new_string"})


@dataclass
class InteractiveSession:
    """State for a single interactive ACP session.

    Attributes:
        session_id: Unique session identifier.
        cwd: Working directory for agent operations.
        permission_mode: Current SDK permission mode.
        focus: Agent template name controlling specialization.
        cancelled: Whether the session has been cancelled.
        pending_plan: Whether a plan is awaiting approval.
        pending_plan_content: Content of the pending plan.
    """

    session_id: str
    cwd: Path
    permission_mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"] = "default"
    focus: str = "oak"
    cancelled: bool = False
    pending_plan: bool = False
    pending_plan_content: str | None = None


class InteractiveSessionManager:
    """Manages long-lived Claude SDK sessions for ACP multi-turn conversations.

    Unlike AgentExecutor which runs a single task to completion, this manager
    keeps sessions alive across multiple prompt() calls. Each session maintains
    its own state (permission mode, pending plans, cancellation).

    Attributes:
        project_root: Root directory for agent operations.
    """

    def __init__(
        self,
        project_root: Path,
        activity_store: "ActivityStore",
        retrieval_engine: "RetrievalEngine | None",
        vector_store: "VectorStore | None",
        agent_registry: "AgentRegistry | None",
        activity_processor: "ActivityProcessor | None" = None,
    ) -> None:
        """Initialize the interactive session manager.

        Args:
            project_root: Project root directory.
            activity_store: ActivityStore for session/batch tracking.
            retrieval_engine: RetrievalEngine for CI tools.
            vector_store: VectorStore for CI tools.
            agent_registry: AgentRegistry for loading agent definitions.
            activity_processor: ActivityProcessor for batch processing and summaries.
        """
        self._project_root = project_root
        self._activity_store = activity_store
        self._retrieval_engine = retrieval_engine
        self._vector_store = vector_store
        self._agent_registry = agent_registry
        self._activity_processor = activity_processor
        self._sessions: dict[str, InteractiveSession] = {}

        # MCP server cache keyed by frozenset of enabled tools
        self._ci_mcp_servers: dict[frozenset[str], Any] = {}

    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return self._project_root

    def _get_ci_mcp_server(self, enabled_tools: set[str] | None = None) -> Any:
        """Get or create a CI MCP server for the given tool set.

        Caches servers by the set of enabled tools.

        Args:
            enabled_tools: Set of tool names to include.

        Returns:
            McpSdkServerConfig instance, or None if unavailable.
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

    # =====================================================================
    # Context injection
    # =====================================================================

    def _build_session_context(self, session_id: str) -> str:
        """Build context string for session-start injection.

        Mirrors injection.py:build_session_context() but uses injected
        dependencies instead of DaemonState.

        Args:
            session_id: Current session ID for tool call linking.

        Returns:
            Formatted context string (may be empty).
        """
        parts: list[str] = []

        try:
            if self._vector_store:
                stats = self._vector_store.get_stats()
                code_chunks = stats.get("code_chunks", 0)
                memory_count = stats.get("memory_observations", 0)

                if code_chunks > 0 or memory_count > 0:
                    parts.append(
                        f"**Codebase Intelligence Active**: {code_chunks} code chunks indexed, "
                        f"{memory_count} memories stored."
                    )

                    reminder = INJECTION_SESSION_START_REMINDER_BLOCK
                    reminder += f"\n- Current session: `session_id={session_id}`"
                    parts.append(reminder)

                    # Include recent session summaries for continuity
                    if self._activity_store:
                        try:
                            from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
                                format_session_summaries,
                            )

                            recent_sessions = self._activity_store.list_sessions_with_summaries(
                                limit=INJECTION_MAX_SESSION_SUMMARIES
                            )
                            if recent_sessions:
                                session_summaries = [
                                    {
                                        "observation": s.summary,
                                        "tags": [s.agent],
                                    }
                                    for s in recent_sessions
                                ]
                                session_text = format_session_summaries(session_summaries)
                                if session_text:
                                    parts.append(session_text)
                        except (OSError, ValueError, RuntimeError, AttributeError) as e:
                            logger.debug(
                                f"Failed to fetch session summaries for ACP injection: {e}"
                            )
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to build session context: {e}")

        return "\n\n".join(parts) if parts else ""

    def _search_prompt_context(self, user_text: str, session_id: str) -> str | None:
        """Search for relevant code and memories based on user prompt.

        Args:
            user_text: The user's prompt text.
            session_id: Current session ID.

        Returns:
            Formatted context string, or None if nothing relevant found.
        """
        if not self._retrieval_engine:
            return None

        try:
            from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
                format_code_for_injection,
                format_memories_for_injection,
            )
            from open_agent_kit.features.codebase_intelligence.retrieval.engine import (
                RetrievalEngine,
            )

            search_res = self._retrieval_engine.search(
                query=user_text,
                search_type="all",
                limit=10,
            )

            parts: list[str] = []

            # Filter code by high confidence
            if search_res.code:
                confident_code = RetrievalEngine.filter_by_combined_score(
                    search_res.code, min_combined="high"
                )
                if confident_code:
                    code_text = format_code_for_injection(confident_code[:3])
                    if code_text:
                        parts.append(code_text)

            # Filter memories by high combined score
            if search_res.memory:
                confident_memories = RetrievalEngine.filter_by_combined_score(
                    search_res.memory, min_combined="high"
                )
                if confident_memories:
                    mem_text = format_memories_for_injection(confident_memories[:5])
                    if mem_text:
                        parts.append(mem_text)

            if parts:
                return "\n\n".join(parts)

        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to search prompt context: {e}")

        return None

    # =====================================================================
    # SDK hooks for activity recording
    # =====================================================================

    def _build_sdk_hooks(
        self,
        session: InteractiveSession,
        batch_id_ref: list[int | None],
        response_text_parts: list[str],
    ) -> dict[str, list[Any]]:
        """Build SDK hooks dict for activity recording.

        Creates PostToolUse and PostToolUseFailure callbacks that record
        tool activities in the activity store, mirroring hooks_tool.py.

        Args:
            session: Current interactive session.
            batch_id_ref: Mutable reference [batch_id] so hooks see current batch.
            response_text_parts: Mutable list to accumulate response text.

        Returns:
            Dict suitable for ClaudeAgentOptions.hooks.
        """
        try:
            from claude_agent_sdk import (
                HookJSONOutput,
                HookMatcher,
            )
        except ImportError:
            return {}

        activity_store = self._activity_store
        project_root = self._project_root

        async def _post_tool_use(
            input_data: Any,
            tool_use_id: str | None,
            context: Any,
        ) -> HookJSONOutput:
            """Record successful tool execution as an activity."""
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store.models import (
                    Activity,
                )

                tool_name = input_data.get("tool_name", "")
                tool_input = input_data.get("tool_input", {})
                tool_response = input_data.get("tool_response", "")

                # Sanitize tool_input (remove large content fields)
                sanitized_input = _sanitize_tool_input(tool_input)

                # Build output summary
                output_summary = _build_output_summary(tool_name, tool_response)

                activity = Activity(
                    session_id=session.session_id,
                    prompt_batch_id=batch_id_ref[0],
                    tool_name=tool_name,
                    tool_input=sanitized_input,
                    tool_output_summary=output_summary,
                    file_path=(
                        tool_input.get("file_path") if isinstance(tool_input, dict) else None
                    ),
                    success=True,
                )
                activity_store.add_activity_buffered(activity)
                logger.debug(f"ACP hook: stored activity {tool_name} (batch={batch_id_ref[0]})")

                # Plan detection for Write tool
                if tool_name == "Write" and batch_id_ref[0] is not None:
                    _handle_plan_detection(
                        activity_store,
                        session.session_id,
                        batch_id_ref[0],
                        tool_input,
                        project_root,
                    )

                # Plan capture for ExitPlanMode
                if tool_name == "ExitPlanMode" and batch_id_ref[0] is not None:
                    _handle_exit_plan_mode(
                        activity_store,
                        session.session_id,
                        project_root,
                    )

            except Exception as e:
                logger.debug(f"ACP post-tool-use hook error: {e}")

            return {}

        async def _post_tool_use_failure(
            input_data: Any,
            tool_use_id: str | None,
            context: Any,
        ) -> HookJSONOutput:
            """Record failed tool execution as an activity."""
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store.models import (
                    Activity,
                )

                tool_name = input_data.get("tool_name", "unknown")
                tool_input = input_data.get("tool_input", {})
                error_message = str(input_data.get("tool_response", "Tool execution failed"))

                sanitized_input = _sanitize_tool_input(tool_input)

                activity = Activity(
                    session_id=session.session_id,
                    prompt_batch_id=batch_id_ref[0],
                    tool_name=tool_name,
                    tool_input=sanitized_input,
                    tool_output_summary=error_message[:_SANITIZED_INPUT_MAX_LENGTH],
                    file_path=(
                        tool_input.get("file_path") if isinstance(tool_input, dict) else None
                    ),
                    success=False,
                    error_message=error_message[:_SANITIZED_INPUT_MAX_LENGTH],
                )
                activity_store.add_activity_buffered(activity)
                logger.debug(
                    f"ACP hook: stored failed activity {tool_name} (batch={batch_id_ref[0]})"
                )

            except Exception as e:
                logger.debug(f"ACP post-tool-use-failure hook error: {e}")

            return {}

        return {
            "PostToolUse": [
                HookMatcher(matcher=None, hooks=[_post_tool_use]),
            ],
            "PostToolUseFailure": [
                HookMatcher(matcher=None, hooks=[_post_tool_use_failure]),
            ],
        }

    # =====================================================================
    # Batch finalization
    # =====================================================================

    def _finalize_batch(
        self,
        batch_id: int,
        response_text_parts: list[str],
    ) -> None:
        """Finalize a prompt batch with response summary and async processing.

        Uses activity.batches.finalize_prompt_batch when activity_processor is
        available, otherwise falls back to bare end_prompt_batch.

        Args:
            batch_id: Prompt batch ID to finalize.
            response_text_parts: Accumulated response text blocks.
        """
        # Flush any buffered activities first
        try:
            self._activity_store.flush_activity_buffer()
        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to flush activity buffer: {e}")

        # Build response summary from accumulated text
        response_summary = "".join(response_text_parts).strip() or None

        if self._activity_processor:
            try:
                from open_agent_kit.features.codebase_intelligence.activity.batches import (
                    finalize_prompt_batch,
                )

                finalize_prompt_batch(
                    activity_store=self._activity_store,
                    activity_processor=self._activity_processor,
                    prompt_batch_id=batch_id,
                    response_summary=response_summary,
                )
                return
            except (OSError, ValueError, RuntimeError) as e:
                logger.warning(f"finalize_prompt_batch failed, falling back: {e}")

        # Fallback: bare end_prompt_batch
        try:
            if response_summary:
                self._activity_store.update_prompt_batch_response(batch_id, response_summary)
        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to store response summary: {e}")

        try:
            self._activity_store.end_prompt_batch(batch_id)
        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to end prompt batch: {e}")

    # =====================================================================
    # Options building
    # =====================================================================

    def _build_task_context(self, focus: str) -> str:
        """Build a task-awareness section for the system prompt.

        When a non-default focus is active, finds all tasks that use that
        template and produces a concise reference the agent can use to
        apply the right guardrails when the user's request matches a task.

        Args:
            focus: Current agent focus (template name).

        Returns:
            Markdown block describing available tasks, or empty string.
        """
        if self._agent_registry is None:
            return ""

        tasks = [t for t in self._agent_registry.list_tasks() if t.agent_type == focus]
        if not tasks:
            return ""

        lines = [
            "## Available Tasks",
            "",
            (
                "The following pre-configured tasks exist for this focus. When the "
                "user's request aligns with a task, follow its conventions — maintained "
                "files, style, and output requirements."
            ),
            "",
        ]

        for task in tasks:
            lines.append(f"### {task.display_name} (`{task.name}`)")
            if task.description:
                lines.append(f"{task.description.strip()}")
            lines.append("")

            if task.maintained_files:
                lines.append("**Maintained files:**")
                for mf in task.maintained_files:
                    path = mf.path.replace("{project_root}/", "")
                    purpose = f" — {mf.purpose}" if mf.purpose else ""
                    lines.append(f"- `{path}`{purpose}")
                lines.append("")

            if task.output_requirements:
                sections = task.output_requirements.get("required_sections", [])
                if sections:
                    lines.append("**Required sections:**")
                    for section in sections:
                        if isinstance(section, dict):
                            name = section.get("name", "")
                            desc = section.get("description", "")
                            lines.append(f"- {name}: {desc}" if desc else f"- {name}")
                    lines.append("")

            if task.style:
                conventions = task.style.get("conventions", [])
                if conventions:
                    lines.append("**Conventions:**")
                    for conv in conventions:
                        lines.append(f"- {conv}")
                    lines.append("")

        return "\n".join(lines)

    def _build_options(
        self,
        session: InteractiveSession,
        batch_id_ref: list[int | None] | None = None,
        response_text_parts: list[str] | None = None,
    ) -> Any:
        """Build ClaudeAgentOptions for a session.

        Follows the same pattern as AgentExecutor._build_options() but
        sources configuration from the ACP agent definition and session state.

        Args:
            session: Interactive session with current state.
            batch_id_ref: Mutable reference for SDK hooks (optional).
            response_text_parts: Mutable list for SDK hooks (optional).

        Returns:
            ClaudeAgentOptions instance.
        """
        try:
            from claude_agent_sdk import ClaudeAgentOptions
        except ImportError as e:
            raise RuntimeError("claude-agent-sdk not installed") from e

        # Load agent definition based on current focus
        agent_def = None
        if self._agent_registry is not None:
            agent_def = self._agent_registry.get_template(session.focus)
            if agent_def is None:
                # Fallback to the default ACP agent
                agent_def = self._agent_registry.get(ACP_AGENT_NAME)

        # Determine system prompt
        system_prompt = ACP_DEFAULT_SYSTEM_PROMPT
        if agent_def and agent_def.system_prompt:
            system_prompt = agent_def.system_prompt

        # Inject task awareness for non-default focuses
        task_context = self._build_task_context(session.focus)
        if task_context:
            system_prompt = f"{system_prompt}\n\n{task_context}"

        # Append session context (CI status, summaries)
        session_context = self._build_session_context(session.session_id)
        if session_context:
            system_prompt = f"{system_prompt}\n\n{session_context}"

        # Determine allowed tools
        allowed_tools: list[str] = []
        if agent_def:
            from open_agent_kit.features.codebase_intelligence.constants import (
                AGENT_FORBIDDEN_TOOLS,
            )

            allowed_tools = [
                t for t in agent_def.get_effective_tools() if t not in AGENT_FORBIDDEN_TOOLS
            ]

        # Build enabled CI tools set from agent ci_access flags
        mcp_servers: dict[str, Any] = {}
        if agent_def:
            ci_access = agent_def.ci_access
            has_any_ci_access = (
                ci_access.code_search
                or ci_access.memory_search
                or ci_access.session_history
                or ci_access.project_stats
                or ci_access.sql_query
                or ci_access.memory_write
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
                if ci_access.memory_write:
                    enabled_ci_tools.add(CI_TOOL_REMEMBER)
                    enabled_ci_tools.add(CI_TOOL_RESOLVE)
                    enabled_ci_tools.add(CI_TOOL_ARCHIVE)

                ci_server = self._get_ci_mcp_server(enabled_ci_tools)
                if ci_server:
                    mcp_servers[CI_MCP_SERVER_NAME] = ci_server
                    for tool_name in enabled_ci_tools:
                        allowed_tools.append(f"mcp__{CI_MCP_SERVER_NAME}__{tool_name}")
                else:
                    logger.warning(
                        "CI MCP server unavailable for ACP session - CI tools will not work"
                    )
        else:
            # No agent definition: provide default CI tools (read-only)
            default_ci_tools = {
                CI_TOOL_SEARCH,
                CI_TOOL_MEMORIES,
                CI_TOOL_SESSIONS,
                CI_TOOL_PROJECT_STATS,
            }
            ci_server = self._get_ci_mcp_server(default_ci_tools)
            if ci_server:
                mcp_servers[CI_MCP_SERVER_NAME] = ci_server
                for tool_name in default_ci_tools:
                    allowed_tools.append(f"mcp__{CI_MCP_SERVER_NAME}__{tool_name}")

        # Build a clean env for the SDK subprocess.
        # Strip CLAUDECODE so the child process doesn't refuse to start
        # with "cannot be launched inside another Claude Code session".
        clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            permission_mode=session.permission_mode,
            cwd=str(session.cwd),
            env=clean_env,
        )

        if mcp_servers:
            options.mcp_servers = mcp_servers

        # Wire SDK hooks for activity recording
        if batch_id_ref is not None and response_text_parts is not None:
            hooks = self._build_sdk_hooks(session, batch_id_ref, response_text_parts)
            if hooks:
                options.hooks = hooks  # type: ignore[assignment]

        return options

    # =====================================================================
    # Session lifecycle
    # =====================================================================

    def create_session(self, session_id: str | None = None, cwd: Path | None = None) -> dict:
        """Create a new interactive session.

        Args:
            session_id: Optional session ID (generated if not provided).
            cwd: Working directory for the session (defaults to project_root).

        Returns:
            Dictionary with session_id.
        """
        if session_id is None:
            session_id = str(uuid4())

        effective_cwd = cwd or self._project_root

        # Record in activity store
        self._activity_store.create_session(
            session_id, agent=ACP_AGENT_NAME, project_root=str(effective_cwd)
        )

        # Store session metadata
        session = InteractiveSession(
            session_id=session_id,
            cwd=effective_cwd,
        )
        self._sessions[session_id] = session

        logger.info(f"ACP interactive session created: {session_id}")
        return {"session_id": session_id}

    async def prompt(self, session_id: str, user_text: str) -> AsyncIterator[ExecutionEvent]:
        """Send a prompt to a session and stream execution events.

        Args:
            session_id: Session to prompt.
            user_text: User's message text.

        Yields:
            ExecutionEvent instances as the agent processes the prompt.
        """
        # Look up session
        session = self._sessions.get(session_id)
        if session is None:
            yield ErrorEvent(message=f"Session not found: {session_id}")
            return

        # Reset cancellation flag for new prompt
        session.cancelled = False
        session.pending_plan = False
        session.pending_plan_content = None

        # Create prompt batch
        batch = self._activity_store.create_prompt_batch(
            session_id, user_text, source_type=ACP_AGENT_NAME
        )

        # Mutable references for SDK hooks
        batch_id_ref: list[int | None] = [batch.id]
        response_text_parts: list[str] = []

        try:
            # Lazy imports for SDK types
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeSDKClient,
                ResultMessage,
                TextBlock,
                ToolUseBlock,
            )

            options = self._build_options(session, batch_id_ref, response_text_parts)

            # Search for relevant context based on user prompt
            prompt_context = self._search_prompt_context(user_text, session_id)
            effective_text = user_text
            if prompt_context:
                effective_text = f"{user_text}\n\n---\n**Relevant context:**\n{prompt_context}"

            async with ClaudeSDKClient(options=options) as client:
                logger.debug(f"ACP session {session_id}: SDK client connected, sending query")
                await client.query(effective_text)

                msg_count = 0
                async for msg in client.receive_response():
                    msg_count += 1
                    logger.debug(
                        f"ACP session {session_id}: message {msg_count} "
                        f"type={type(msg).__name__}"
                    )
                    # Check for cancellation between messages
                    if session.cancelled:
                        yield CancelledEvent()
                        return

                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                response_text_parts.append(block.text)
                                yield TextEvent(text=block.text)
                            elif isinstance(block, ToolUseBlock):
                                if block.name == "ExitPlanMode":
                                    # Plan proposed - needs user approval
                                    plan_content = ""
                                    if isinstance(block.input, dict):
                                        plan_content = block.input.get("plan", "")
                                    session.pending_plan = True
                                    session.pending_plan_content = plan_content

                                    # Store plan in batch metadata
                                    if batch.id is not None:
                                        try:
                                            self._activity_store.update_prompt_batch_source_type(
                                                batch.id,
                                                PROMPT_SOURCE_PLAN,
                                                plan_content=plan_content,
                                            )
                                        except (OSError, ValueError, RuntimeError) as e:
                                            logger.debug(f"Failed to store plan metadata: {e}")

                                    yield PlanProposedEvent(plan=plan_content)
                                else:
                                    yield ToolStartEvent(
                                        tool_id=block.id,
                                        tool_name=block.name,
                                        tool_input=(
                                            block.input if isinstance(block.input, dict) else {}
                                        ),
                                    )

                    elif isinstance(msg, ResultMessage):
                        if msg.total_cost_usd:
                            cost_event = CostEvent(
                                total_cost_usd=msg.total_cost_usd,
                            )
                            if hasattr(msg, "input_tokens") and msg.input_tokens:
                                cost_event.input_tokens = msg.input_tokens
                            if hasattr(msg, "output_tokens") and msg.output_tokens:
                                cost_event.output_tokens = msg.output_tokens
                            yield cost_event

        except ImportError as e:
            yield ErrorEvent(message=f"claude-agent-sdk not installed: {e}")
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"ACP session {session_id} prompt failed: {e}")
            yield ErrorEvent(message=str(e))
        except Exception as e:
            # Catch SDK-specific errors (ProcessError, ClaudeSDKError, etc.)
            logger.error(f"ACP session {session_id} prompt failed: {type(e).__name__}: {e}")
            yield ErrorEvent(message=f"{type(e).__name__}: {e}")
        finally:
            if batch.id is not None:
                self._finalize_batch(batch.id, response_text_parts)

        yield DoneEvent(
            session_id=session_id,
            needs_plan_approval=session.pending_plan,
        )

    def set_mode(
        self,
        session_id: str,
        mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"],
    ) -> None:
        """Update the permission mode for a session.

        Args:
            session_id: Session to update.
            mode: New permission mode.

        Raises:
            KeyError: If session not found.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        session.permission_mode = mode
        logger.debug(f"ACP session {session_id} mode set to {mode}")

    def set_focus(self, session_id: str, focus: str) -> None:
        """Update the agent focus for a session.

        Switches the agent template used by subsequent prompt() calls.
        Conversation history is preserved across focus changes.

        Args:
            session_id: Session to update.
            focus: Agent template name (e.g. "oak", "documentation", "analysis").

        Raises:
            KeyError: If session not found.
            ValueError: If focus is not a valid template name.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")

        # Validate focus against registry if available
        if self._agent_registry is not None:
            template = self._agent_registry.get_template(focus)
            if template is None:
                raise ValueError(f"Unknown agent focus: {focus}")

        session.focus = focus
        logger.info(f"ACP session {session_id} focus set to {focus}")

    async def approve_plan(self, session_id: str) -> AsyncIterator[ExecutionEvent]:
        """Approve a pending plan and continue execution.

        Similar to prompt() but continues the existing conversation with
        acceptEdits permission mode to execute the approved plan.

        Args:
            session_id: Session with pending plan.

        Yields:
            ExecutionEvent instances as the plan is executed.
        """
        session = self._sessions.get(session_id)
        if session is None:
            yield ErrorEvent(message=f"Session not found: {session_id}")
            return

        if not session.pending_plan:
            yield ErrorEvent(message="No pending plan to approve")
            return

        # Clear pending plan state
        session.pending_plan = False
        plan_content = session.pending_plan_content or ""
        session.pending_plan_content = None

        # Create a prompt batch for the approval continuation
        batch = self._activity_store.create_prompt_batch(
            session_id, "[plan approved]", source_type=ACP_AGENT_NAME
        )

        # Mutable references for SDK hooks
        batch_id_ref: list[int | None] = [batch.id]
        response_text_parts: list[str] = []

        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeSDKClient,
                ResultMessage,
                TextBlock,
                ToolUseBlock,
            )

            # Build options with acceptEdits for plan execution
            options = self._build_options(session, batch_id_ref, response_text_parts)
            options.permission_mode = "acceptEdits"

            async with ClaudeSDKClient(options=options) as client:
                # Continue conversation with plan approval
                await client.query(
                    f"The plan has been approved. Please proceed with the implementation.\n\n{plan_content}",
                )

                async for msg in client.receive_response():
                    if session.cancelled:
                        yield CancelledEvent()
                        return

                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                response_text_parts.append(block.text)
                                yield TextEvent(text=block.text)
                            elif isinstance(block, ToolUseBlock):
                                yield ToolStartEvent(
                                    tool_id=block.id,
                                    tool_name=block.name,
                                    tool_input=block.input if isinstance(block.input, dict) else {},
                                )

                    elif isinstance(msg, ResultMessage):
                        if msg.total_cost_usd:
                            cost_event = CostEvent(
                                total_cost_usd=msg.total_cost_usd,
                            )
                            if hasattr(msg, "input_tokens") and msg.input_tokens:
                                cost_event.input_tokens = msg.input_tokens
                            if hasattr(msg, "output_tokens") and msg.output_tokens:
                                cost_event.output_tokens = msg.output_tokens
                            yield cost_event

        except ImportError as e:
            yield ErrorEvent(message=f"claude-agent-sdk not installed: {e}")
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"ACP session {session_id} plan approval failed: {e}")
            yield ErrorEvent(message=str(e))
        except Exception as e:
            logger.error(f"ACP session {session_id} plan approval failed: {type(e).__name__}: {e}")
            yield ErrorEvent(message=f"{type(e).__name__}: {e}")
        finally:
            if batch.id is not None:
                self._finalize_batch(batch.id, response_text_parts)

        yield DoneEvent(session_id=session_id, needs_plan_approval=False)

    def cancel(self, session_id: str) -> None:
        """Cancel an in-progress prompt for a session.

        Args:
            session_id: Session to cancel.

        Raises:
            KeyError: If session not found.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        session.cancelled = True
        logger.info(f"ACP session {session_id} cancelled")

    async def close_session(self, session_id: str) -> None:
        """Close a session and clean up resources.

        Flushes buffered activities, finalizes any remaining batch,
        ends the session, and schedules async summary generation.

        Args:
            session_id: Session to close.
        """
        session = self._sessions.pop(session_id, None)
        if session is None:
            logger.warning(f"Cannot close unknown session: {session_id}")
            return

        # Flush any remaining buffered activities
        try:
            self._activity_store.flush_activity_buffer()
        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to flush activity buffer on close: {e}")

        # Finalize any active batch
        try:
            active_batch = self._activity_store.get_active_prompt_batch(session_id)
            if active_batch and active_batch.id is not None:
                self._finalize_batch(active_batch.id, [])
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to finalize active batch on close: {e}")

        # End the session in the activity store
        self._activity_store.end_session(session_id)
        logger.info(f"ACP interactive session closed: {session_id}")

        # Schedule async summary generation
        if self._activity_processor:
            processor = self._activity_processor
            sid = session_id

            async def _generate_summary() -> None:
                try:
                    summary, title = processor.process_session_summary_with_title(sid)
                    if summary:
                        logger.info(
                            f"ACP session summary generated for {sid}: "
                            f"{len(summary)} chars, title={title!r}"
                        )
                except (OSError, ValueError, RuntimeError) as e:
                    logger.warning(f"Failed to generate session summary for {sid}: {e}")

            asyncio.create_task(_generate_summary())


# =========================================================================
# Module-level helper functions (used by SDK hooks)
# =========================================================================


def _sanitize_tool_input(tool_input: Any) -> dict[str, Any] | None:
    """Sanitize tool input by truncating large content fields.

    Mirrors the sanitization pattern from hooks_tool.py.

    Args:
        tool_input: Raw tool input (dict or other).

    Returns:
        Sanitized dict, or None.
    """
    if not isinstance(tool_input, dict):
        return None

    sanitized: dict[str, Any] = {}
    for k, v in tool_input.items():
        if k in _LARGE_CONTENT_FIELDS:
            sanitized[k] = f"<{len(str(v))} chars>"
        elif isinstance(v, str) and len(v) > _SANITIZED_INPUT_MAX_LENGTH:
            sanitized[k] = v[:_SANITIZED_INPUT_MAX_LENGTH] + "..."
        else:
            sanitized[k] = v
    return sanitized


def _build_output_summary(tool_name: str, tool_response: Any) -> str:
    """Build a concise output summary from tool response.

    Args:
        tool_name: Name of the tool.
        tool_response: Raw tool response.

    Returns:
        Truncated summary string.
    """
    if not tool_response:
        return ""

    response_str = str(tool_response)

    # For file reads, just note the length
    if tool_name == "Read" and len(response_str) > 200:
        return f"Read {len(response_str)} chars"

    return response_str[:_SANITIZED_INPUT_MAX_LENGTH]


def _handle_plan_detection(
    activity_store: "ActivityStore",
    session_id: str,
    batch_id: int,
    tool_input: Any,
    project_root: Path,
) -> None:
    """Detect and record plan file writes.

    Args:
        activity_store: Store for batch updates.
        session_id: Current session.
        batch_id: Current batch ID.
        tool_input: Tool input dict from Write tool.
        project_root: Project root for path resolution.
    """
    if not isinstance(tool_input, dict):
        return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    try:
        from open_agent_kit.features.codebase_intelligence.plan_detector import detect_plan

        detection = detect_plan(file_path)
        if not detection.is_plan:
            return

        # Read plan content from disk (source of truth)
        plan_content = ""
        plan_path = Path(file_path)
        if not plan_path.is_absolute():
            plan_path = project_root / plan_path

        try:
            if plan_path.exists():
                plan_content = plan_path.read_text(encoding="utf-8")
            else:
                plan_content = tool_input.get("content", "")
        except (OSError, ValueError) as e:
            logger.debug(f"Failed to read plan file {plan_path}: {e}")
            plan_content = tool_input.get("content", "")

        activity_store.update_prompt_batch_source_type(
            batch_id,
            PROMPT_SOURCE_PLAN,
            plan_file_path=file_path,
            plan_content=plan_content,
        )
        logger.info(
            f"ACP: detected plan in Write to {file_path}, "
            f"batch {batch_id} ({len(plan_content)} chars)"
        )

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.debug(f"Plan detection failed: {e}")


def _handle_exit_plan_mode(
    activity_store: "ActivityStore",
    session_id: str,
    project_root: Path,
) -> None:
    """Re-read and update plan content on ExitPlanMode.

    Args:
        activity_store: Store for batch updates.
        session_id: Current session.
        project_root: Project root for path resolution.
    """
    try:
        plan_batch = activity_store.get_session_plan_batch(session_id)
        if not (plan_batch and plan_batch.plan_file_path and plan_batch.id):
            return

        plan_path = Path(plan_batch.plan_file_path)
        if not plan_path.is_absolute():
            plan_path = project_root / plan_path

        if plan_path.exists():
            final_content = plan_path.read_text(encoding="utf-8")
            activity_store.update_prompt_batch_source_type(
                plan_batch.id,
                PROMPT_SOURCE_PLAN,
                plan_file_path=plan_batch.plan_file_path,
                plan_content=final_content,
            )
            activity_store.mark_plan_unembedded(plan_batch.id)
            logger.info(
                f"ACP ExitPlanMode: updated plan {plan_batch.id} ({len(final_content)} chars)"
            )
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.debug(f"ExitPlanMode handling failed: {e}")
