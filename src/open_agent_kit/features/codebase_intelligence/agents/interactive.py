"""Interactive Session Manager for ACP multi-turn conversations.

This module provides the InteractiveSessionManager that manages long-lived
Claude SDK sessions for ACP (Agent Client Protocol) conversations. Unlike
the AgentExecutor which runs single tasks to completion, this manager keeps
sessions alive across multiple prompt() calls for multi-turn interaction.

Each session tracks its own state (cwd, permission_mode, cancellation,
pending plan) and streams ExecutionEvents back to the caller via
async iterators.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

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
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)

# Agent name used for ACP sessions in the activity store
ACP_AGENT_NAME = "acp"

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
        cancelled: Whether the session has been cancelled.
        pending_plan: Whether a plan is awaiting approval.
        pending_plan_content: Content of the pending plan.
    """

    session_id: str
    cwd: Path
    permission_mode: Literal["default", "acceptEdits", "plan", "bypassPermissions"] = "default"
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
    ) -> None:
        """Initialize the interactive session manager.

        Args:
            project_root: Project root directory.
            activity_store: ActivityStore for session/batch tracking.
            retrieval_engine: RetrievalEngine for CI tools.
            vector_store: VectorStore for CI tools.
            agent_registry: AgentRegistry for loading agent definitions.
        """
        self._project_root = project_root
        self._activity_store = activity_store
        self._retrieval_engine = retrieval_engine
        self._vector_store = vector_store
        self._agent_registry = agent_registry
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

    def _build_options(
        self,
        session: InteractiveSession,
    ) -> Any:
        """Build ClaudeAgentOptions for a session.

        Follows the same pattern as AgentExecutor._build_options() but
        sources configuration from the ACP agent definition and session state.

        Args:
            session: Interactive session with current state.

        Returns:
            ClaudeAgentOptions instance.
        """
        try:
            from claude_agent_sdk import ClaudeAgentOptions
        except ImportError as e:
            raise RuntimeError("claude-agent-sdk not installed") from e

        # Load agent definition from registry
        agent_def = None
        if self._agent_registry is not None:
            agent_def = self._agent_registry.get(ACP_AGENT_NAME)

        # Determine system prompt
        system_prompt = ACP_DEFAULT_SYSTEM_PROMPT
        if agent_def and agent_def.system_prompt:
            system_prompt = agent_def.system_prompt

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

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            permission_mode=session.permission_mode,
            cwd=str(session.cwd),
        )

        if mcp_servers:
            options.mcp_servers = mcp_servers

        return options

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

        try:
            # Lazy imports for SDK types
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeSDKClient,
                ResultMessage,
                TextBlock,
                ToolUseBlock,
            )

            options = self._build_options(session)

            async with ClaudeSDKClient(options=options) as client:
                await client.query(user_text)

                async for msg in client.receive_response():
                    # Check for cancellation between messages
                    if session.cancelled:
                        yield CancelledEvent()
                        return

                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                yield TextEvent(text=block.text)
                            elif isinstance(block, ToolUseBlock):
                                if block.name == "ExitPlanMode":
                                    # Plan proposed - needs user approval
                                    plan_content = ""
                                    if isinstance(block.input, dict):
                                        plan_content = block.input.get("plan", "")
                                    session.pending_plan = True
                                    session.pending_plan_content = plan_content
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
        finally:
            if batch.id is not None:
                self._activity_store.end_prompt_batch(batch.id)

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

        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeSDKClient,
                ResultMessage,
                TextBlock,
                ToolUseBlock,
            )

            # Build options with acceptEdits for plan execution
            options = self._build_options(session)
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
        finally:
            if batch.id is not None:
                self._activity_store.end_prompt_batch(batch.id)

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

    def close_session(self, session_id: str) -> None:
        """Close a session and clean up resources.

        Args:
            session_id: Session to close.
        """
        session = self._sessions.pop(session_id, None)
        if session is not None:
            self._activity_store.end_session(session_id)
            logger.info(f"ACP interactive session closed: {session_id}")
        else:
            logger.warning(f"Cannot close unknown session: {session_id}")
