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
from open_agent_kit.features.codebase_intelligence.agents.activity_recorder import (
    ActivityRecorder,
)
from open_agent_kit.features.codebase_intelligence.agents.ci_tools import (
    build_ci_tools_from_access,
)
from open_agent_kit.features.codebase_intelligence.agents.context_injection import (
    build_session_context as build_session_context_impl,
)
from open_agent_kit.features.codebase_intelligence.agents.context_injection import (
    build_task_context as build_task_context_impl,
)
from open_agent_kit.features.codebase_intelligence.agents.context_injection import (
    search_prompt_context as search_prompt_context_impl,
)
from open_agent_kit.features.codebase_intelligence.agents.mcp_cache import CiMcpServerCache
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_MCP_SERVER_NAME,
    CI_TOOL_MEMORIES,
    CI_TOOL_PROJECT_STATS,
    CI_TOOL_SEARCH,
    CI_TOOL_SESSIONS,
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

        # MCP server cache
        self._ci_mcp_cache = CiMcpServerCache(
            retrieval_engine=retrieval_engine,
            activity_store=activity_store,
            vector_store=vector_store,
        )

    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return self._project_root

    # =====================================================================
    # Context injection (delegated to context_injection module)
    # =====================================================================

    def _build_session_context(self, session_id: str) -> str:
        """Build context string for session-start injection."""
        return build_session_context_impl(session_id, self._vector_store, self._activity_store)

    def _search_prompt_context(self, user_text: str, session_id: str) -> str | None:
        """Search for relevant code and memories based on user prompt."""
        return search_prompt_context_impl(user_text, self._retrieval_engine)

    # =====================================================================
    # SDK hooks for activity recording (delegated to ActivityRecorder)
    # =====================================================================

    def _build_sdk_hooks(
        self,
        session: InteractiveSession,
        batch_id_ref: list[int | None],
        response_text_parts: list[str],
    ) -> dict[str, list[Any]]:
        """Build SDK hooks dict for activity recording."""
        recorder = ActivityRecorder(
            activity_store=self._activity_store,
            project_root=self._project_root,
        )
        return recorder.build_hooks(session.session_id, batch_id_ref, response_text_parts)

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
        """Build a task-awareness section for the system prompt."""
        return build_task_context_impl(focus, self._agent_registry)

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
            enabled_ci_tools = build_ci_tools_from_access(agent_def.ci_access)
            if enabled_ci_tools is not None:
                ci_server = self._ci_mcp_cache.get(enabled_ci_tools)
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
            ci_server = self._ci_mcp_cache.get(default_ci_tools)
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
    # SDK turn execution (shared by prompt() and approve_plan())
    # =====================================================================

    async def _run_sdk_turn(
        self,
        session: InteractiveSession,
        query_text: str,
        batch_id_ref: list[int | None],
        response_text_parts: list[str],
        options: Any,
        *,
        detect_plans: bool = False,
    ) -> AsyncIterator[ExecutionEvent]:
        """Run a single SDK turn: send query, stream response events.

        Shared loop used by both ``prompt()`` and ``approve_plan()`` to
        avoid duplicating the message-processing logic.

        Args:
            session: Current interactive session.
            query_text: Text to send to the SDK client.
            batch_id_ref: Mutable reference for batch ID.
            response_text_parts: Mutable list accumulating text blocks.
            options: ClaudeAgentOptions instance.
            detect_plans: If True, handle ExitPlanMode tool events.

        Yields:
            ExecutionEvent instances.
        """
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeSDKClient,
            ResultMessage,
            TextBlock,
            ToolUseBlock,
        )

        async with ClaudeSDKClient(options=options) as client:
            logger.debug(f"ACP session {session.session_id}: SDK client connected, sending query")
            await client.query(query_text)

            msg_count = 0
            async for msg in client.receive_response():
                msg_count += 1
                logger.debug(
                    f"ACP session {session.session_id}: message {msg_count} "
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
                            if detect_plans and block.name == "ExitPlanMode":
                                # Plan proposed - needs user approval
                                plan_content = ""
                                if isinstance(block.input, dict):
                                    plan_content = block.input.get("plan", "")
                                session.pending_plan = True
                                session.pending_plan_content = plan_content

                                # Store plan in batch metadata
                                if batch_id_ref[0] is not None:
                                    try:
                                        self._activity_store.update_prompt_batch_source_type(
                                            batch_id_ref[0],
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
            options = self._build_options(session, batch_id_ref, response_text_parts)

            # Search for relevant context based on user prompt
            prompt_context = self._search_prompt_context(user_text, session_id)
            effective_text = user_text
            if prompt_context:
                effective_text = f"{user_text}\n\n---\n**Relevant context:**\n{prompt_context}"

            async for event in self._run_sdk_turn(
                session,
                effective_text,
                batch_id_ref,
                response_text_parts,
                options,
                detect_plans=True,
            ):
                yield event

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
            # Build options with acceptEdits for plan execution
            options = self._build_options(session, batch_id_ref, response_text_parts)
            options.permission_mode = "acceptEdits"

            query_text = (
                f"The plan has been approved. Please proceed with the "
                f"implementation.\n\n{plan_content}"
            )

            async for event in self._run_sdk_turn(
                session,
                query_text,
                batch_id_ref,
                response_text_parts,
                options,
                detect_plans=False,
            ):
                yield event

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
