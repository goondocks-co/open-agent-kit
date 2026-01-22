"""AI agent integration hooks for the CI daemon (claude-mem inspired)."""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request

from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hooks"])

# Route prefix - uses /api/oak/ci/ to avoid conflicts with other integrations
OAK_CI_PREFIX = "/api/oak/ci"


def _parse_tool_output(tool_output: str) -> dict[str, Any] | None:
    """Parse JSON tool output, return None if not valid JSON."""
    if not tool_output:
        return None
    try:
        import json

        result = json.loads(tool_output)
        if isinstance(result, dict):
            return result
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def _format_memories_for_injection(memories: list[dict], max_items: int = 10) -> str:
    """Format memories as a concise string for context injection.

    Args:
        memories: List of memory dicts with observation, memory_type, context.
        max_items: Maximum number of items to include.

    Returns:
        Formatted string for Claude's context.
    """
    if not memories:
        return ""

    emoji_map = {
        "gotcha": "⚠️",
        "bug_fix": "🐛",
        "decision": "📋",
        "discovery": "💡",
        "trade_off": "⚖️",
    }

    lines = ["## Recent Project Memories\n"]
    for mem in memories[:max_items]:
        mem_type = mem.get("memory_type", "note")
        emoji = emoji_map.get(mem_type, "📝")
        obs = mem.get("observation", "")
        ctx = mem.get("context", "")

        line = f"- {emoji} **{mem_type}**: {obs}"
        if ctx:
            line += f" _(context: {ctx})_"
        lines.append(line)

    return "\n".join(lines)


def _format_session_summaries(summaries: list[dict], max_items: int = 5) -> str:
    """Format session summaries for context injection.

    Args:
        summaries: List of session summary memory dicts.
        max_items: Maximum number of summaries to include.

    Returns:
        Formatted string with recent session context.
    """
    if not summaries:
        return ""

    lines = ["## Recent Session History\n"]
    for i, summary in enumerate(summaries[:max_items], 1):
        obs = summary.get("observation", "")
        tags = summary.get("tags", [])

        # Extract agent from tags (filter out system tags)
        system_tags = {"session-summary", "session", "llm-summarized", "auto-extracted"}
        agent = next((t for t in tags if t not in system_tags), "unknown")

        # Truncate long summaries
        if len(obs) > 200:
            obs = obs[:197] + "..."

        lines.append(f"**Session {i}** ({agent}): {obs}\n")

    return "\n".join(lines)


def _build_session_context(state: Any, include_memories: bool = True) -> str:
    """Build context string for session injection.

    Args:
        state: Daemon state object.
        include_memories: Whether to include recent memories.

    Returns:
        Formatted context string for Claude.
    """
    parts = []

    # Add CI status summary
    if state.vector_store:
        stats = state.vector_store.get_stats()
        code_chunks = stats.get("code_chunks", 0)
        memory_count = stats.get("memory_observations", 0)

        if code_chunks > 0 or memory_count > 0:
            parts.append(
                f"**Codebase Intelligence Active**: {code_chunks} code chunks indexed, "
                f"{memory_count} memories stored.\n\n"
                "**PREFER** `oak ci` over grep/read for code discovery:\n"
                "- `oak ci search '<query>'` - Semantic search (finds by meaning, not just keywords)\n"
                "- `oak ci context '<task>'` - Get relevant code + memories before implementing\n"
                "- `oak ci remember '<observation>' -t <type>` - Store learnings for future sessions"
            )

        # Include recent session summaries (provides continuity across sessions)
        if include_memories and state.retrieval_engine:
            try:
                session_summaries, _ = state.retrieval_engine.list_memories(
                    limit=5,
                    memory_types=["session_summary"],
                )
                if session_summaries:
                    session_text = _format_session_summaries(session_summaries)
                    if session_text:
                        parts.append(session_text)
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.debug(f"Failed to fetch session summaries for injection: {e}")

        # Include recent memories (gotchas, decisions, etc.) - excluding session summaries
        if include_memories and memory_count > 0 and state.retrieval_engine:
            try:
                # Search with base threshold, then filter by confidence
                # For session start, include high and medium confidence (broader context)
                result = state.retrieval_engine.search(
                    query="important gotchas decisions bugs",
                    search_type="memory",
                    limit=15,  # Fetch more, filter by confidence
                )
                # Filter to high and medium confidence, exclude session summaries
                confident_memories = RetrievalEngine.filter_by_confidence(
                    result.memory, min_confidence="medium"
                )
                recent = [
                    m for m in confident_memories if m.get("memory_type") != "session_summary"
                ]
                if recent:
                    mem_text = _format_memories_for_injection(recent[:10])  # Cap at 10
                    if mem_text:
                        parts.append(mem_text)
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.debug(f"Failed to fetch memories for injection: {e}")

    return "\n\n".join(parts) if parts else ""


@router.post(f"{OAK_CI_PREFIX}/session-start")
async def hook_session_start(request: Request) -> dict:
    """Handle session start - create session and inject context.

    Returns context that gets injected into Claude's conversation via
    the additionalContext mechanism in the hook output.
    """
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body")
        body = {}

    agent = body.get("agent", "unknown")
    session_id = body.get("session_id") or str(uuid4())
    source = body.get("source", "startup")  # startup, resume, clear, compact

    # Prominent logging for session-start lifecycle tracking
    logger.info("[SESSION-START] ========== Session starting ==========")
    logger.info(f"[SESSION-START] session_id={session_id}, agent={agent}, source={source}")
    logger.debug(f"[SESSION-START] Raw request body: {body}")

    # Create session tracking (in-memory)
    state.create_session(session_id, agent)

    # Create or resume session in activity store (persistent SQLite)
    if state.activity_store and state.project_root:
        try:
            _, created = state.activity_store.get_or_create_session(
                session_id=session_id,
                agent=agent,
                project_root=str(state.project_root),
            )
            if created:
                logger.debug(f"Created activity session: {session_id}")
            else:
                logger.debug(f"Resumed activity session: {session_id}")
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to create/resume activity session: {e}")

    # Build context response with injected_context for Claude
    context: dict[str, Any] = {
        "session_id": session_id,
        "agent": agent,
    }

    # Only inject full context on fresh starts, not resume/compact
    inject_full_context = source in ("startup", "clear")

    # Build the context string that will be injected into Claude
    injected = _build_session_context(state, include_memories=inject_full_context)
    if injected:
        context["injected_context"] = injected
        logger.debug(f"[INJECT:session-start] Content:\n{injected}")

    # Add metadata (not injected, just for reference)
    if state.project_root:
        context["project_root"] = str(state.project_root)

    if state.vector_store:
        stats = state.vector_store.get_stats()
        context["index"] = {
            "code_chunks": stats.get("code_chunks", 0),
            "memory_observations": stats.get("memory_observations", 0),
            "status": state.index_status.status,
        }

    return {"status": "ok", "session_id": session_id, "context": context}


@router.post(f"{OAK_CI_PREFIX}/prompt-submit")
async def hook_prompt_submit(request: Request) -> dict:
    """Handle user prompt submission - create prompt batch and search for context.

    This is called when a user sends a prompt. We:
    1. End any previous prompt batch (if exists)
    2. Create a new prompt batch for this prompt
    3. Search for relevant context to inject

    The prompt batch tracks all activities until the agent finishes responding.
    """
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in prompt-submit")
        body = {}

    session_id = body.get("session_id")
    prompt = body.get("prompt", "")
    agent = body.get("agent", "unknown")

    # Skip if no prompt or very short
    if not prompt or len(prompt) < 2:
        return {"status": "ok", "context": {}}

    logger.debug(f"Prompt submit: {prompt[:50]}...")

    # Get or create session tracking
    # Auto-create session if it doesn't exist (e.g., after daemon restart)
    session = state.get_session(session_id) if session_id else None
    if session_id and not session:
        logger.info(f"Auto-creating session {session_id} (daemon may have restarted)")
        session = state.create_session(session_id, agent)

    # Create new prompt batch in activity store
    prompt_batch_id = None
    if state.activity_store and session_id:
        try:
            # End previous prompt batch if exists
            if session and session.current_prompt_batch_id:
                previous_batch_id = session.current_prompt_batch_id
                state.activity_store.end_prompt_batch(previous_batch_id)
                logger.debug(f"Ended previous prompt batch: {previous_batch_id}")

                # Queue previous batch for processing
                if state.activity_processor:
                    import asyncio

                    from open_agent_kit.features.codebase_intelligence.activity import (
                        process_prompt_batch_async,
                    )

                    # Capture processor reference to avoid type narrowing issues
                    processor = state.activity_processor
                    batch_id = previous_batch_id

                    async def _process_previous() -> None:
                        logger.debug(
                            f"[REALTIME] Starting async processing for previous batch {batch_id}"
                        )
                        try:
                            result = await process_prompt_batch_async(processor, batch_id)
                            if result.success:
                                logger.info(
                                    f"[REALTIME] Processed previous batch {batch_id}: "
                                    f"{result.observations_extracted} observations"
                                )
                            else:
                                logger.warning(
                                    f"[REALTIME] Previous batch {batch_id} failed: {result.error}"
                                )
                        except (RuntimeError, OSError, ValueError) as e:
                            logger.warning(f"[REALTIME] Failed to process previous batch: {e}")

                    logger.debug(f"[REALTIME] Scheduling async task for previous batch {batch_id}")
                    asyncio.create_task(_process_previous())

            # Create new prompt batch with full user prompt
            batch = state.activity_store.create_prompt_batch(
                session_id=session_id,
                user_prompt=prompt,  # Full prompt, truncated to 10K in store
            )
            prompt_batch_id = batch.id
            logger.info(f"Created prompt batch {prompt_batch_id} for session {session_id}")

            # Update session with current batch ID
            if session:
                session.current_prompt_batch_id = prompt_batch_id

        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to create prompt batch: {e}")

    context: dict[str, Any] = {}

    # Search for relevant memories based on prompt
    if state.retrieval_engine:
        try:
            # Search with base threshold, then filter by confidence
            # For prompt injection, only include HIGH confidence (precision over recall)
            result = state.retrieval_engine.search(
                query=prompt,
                search_type="memory",
                limit=10,  # Fetch more, filter by confidence
            )

            # Filter to high confidence only for prompt injection (avoid noise)
            high_confidence_memories = RetrievalEngine.filter_by_confidence(
                result.memory, min_confidence="high"
            )

            if high_confidence_memories:
                # Format as injection context
                mem_lines = []
                for mem in high_confidence_memories[:5]:  # Cap at 5
                    mem_type = mem.get("memory_type", "note")
                    obs = mem.get("observation", "")
                    mem_lines.append(f"- [{mem_type}] {obs}")

                if mem_lines:
                    injected_text = "**Relevant memories for this task:**\n" + "\n".join(mem_lines)
                    context["injected_context"] = injected_text
                    logger.info(
                        f"Injecting {len(high_confidence_memories[:5])} high-confidence "
                        f"memories for prompt"
                    )
                    logger.debug(f"[INJECT:prompt-submit] Content:\n{injected_text}")

        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to search memories for prompt: {e}")

    return {"status": "ok", "context": context, "prompt_batch_id": prompt_batch_id}


@router.post(f"{OAK_CI_PREFIX}/post-tool-use")
async def hook_post_tool_use(request: Request) -> dict:
    """Handle post-tool-use - auto-capture observations from tool output."""
    import base64

    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in post-tool-use")
        body = {}

    session_id = body.get("session_id")
    tool_name = body.get("tool_name", "")

    # Handle tool_input - could be dict (from JSON) or string
    tool_input = body.get("tool_input", {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (ValueError, json.JSONDecodeError):
            tool_input = {"raw": tool_input}
    elif tool_input is None:
        tool_input = {}

    # Handle tool_output - check for base64-encoded version first
    tool_output_b64 = body.get("tool_output_b64", "")
    if tool_output_b64:
        try:
            tool_output = base64.b64decode(tool_output_b64).decode("utf-8", errors="replace")
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to decode base64 output: {e}")
            tool_output = ""
    else:
        tool_output = body.get("tool_output", body.get("output", ""))

    # Log detailed info about what was received
    has_input = bool(tool_input and tool_input != {})
    has_output = bool(tool_output)
    output_len = len(tool_output) if tool_output else 0
    logger.info(
        f"Post-tool-use: {tool_name} | "
        f"input={has_input} | output={has_output} ({output_len} chars) | "
        f"session={session_id or 'none'}"
    )

    # Debug: log full details for troubleshooting
    if logger.isEnabledFor(logging.DEBUG):
        import json as json_module

        logger.debug(f"  Agent: {body.get('agent', 'unknown')}")
        if tool_input:
            try:
                input_str = json_module.dumps(tool_input, indent=2)
                # Truncate very long inputs
                if len(input_str) > 500:
                    input_str = input_str[:500] + "... (truncated)"
                logger.debug(f"  Tool input:\n{input_str}")
            except (ValueError, TypeError):
                logger.debug(f"  Tool input: {tool_input}")
        if tool_output:
            preview = tool_output[:300].replace("\n", "\\n")
            logger.debug(f"  Tool output preview: {preview}...")

    # Update session tracking with detailed execution info
    # Auto-create session if it doesn't exist (e.g., after daemon restart)
    agent = body.get("agent", "unknown")
    session = state.get_session(session_id) if session_id else None
    if session_id and not session:
        logger.info(
            f"Auto-creating session {session_id} in post-tool-use (daemon may have restarted)"
        )
        session = state.create_session(session_id, agent)
    if session:
        # Extract file path for file operations
        file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None

        # Build execution summary
        summary = ""
        if tool_name == "Bash":
            summary = tool_input.get("command", "")[:100] if isinstance(tool_input, dict) else ""
        elif tool_name in ("Edit", "Write"):
            summary = f"Modified {file_path}" if file_path else ""
        elif tool_name == "Read":
            summary = f"Read {file_path}" if file_path else ""

        session.record_tool_execution(
            tool_name=tool_name,
            file_path=file_path,
            summary=summary,
        )

    # Store activity in SQLite for background processing (liberal capture)
    if state.activity_store and session_id:
        try:
            from open_agent_kit.features.codebase_intelligence.activity import Activity

            # Build a sanitized version of tool_input (remove large content)
            sanitized_input = None
            if isinstance(tool_input, dict):
                sanitized_input = {}
                for k, v in tool_input.items():
                    if k in ("content", "new_source", "old_string", "new_string"):
                        # For file content, just note the length
                        sanitized_input[k] = f"<{len(str(v))} chars>"
                    elif isinstance(v, str) and len(v) > 500:
                        sanitized_input[k] = v[:500] + "..."
                    else:
                        sanitized_input[k] = v

            # Build output summary (first 500 chars, excluding large content)
            output_summary = ""
            if tool_output:
                # For file reads, just note the length
                if tool_name == "Read" and len(tool_output) > 200:
                    output_summary = f"Read {len(tool_output)} chars"
                else:
                    output_summary = tool_output[:500]

            # Detect errors
            is_error = False
            error_msg = None
            output_data = _parse_tool_output(tool_output)
            if output_data:
                if output_data.get("stderr"):
                    is_error = True
                    error_msg = output_data.get("stderr", "")[:500]

            # Get current prompt batch ID from session
            prompt_batch_id = None
            if session:
                prompt_batch_id = session.current_prompt_batch_id

            activity = Activity(
                session_id=session_id,
                prompt_batch_id=prompt_batch_id,
                tool_name=tool_name,
                tool_input=sanitized_input,
                tool_output_summary=output_summary,
                file_path=tool_input.get("file_path") if isinstance(tool_input, dict) else None,
                success=not is_error,
                error_message=error_msg,
            )
            state.activity_store.add_activity(activity)
            logger.debug(f"Stored activity: {tool_name} (batch={prompt_batch_id})")

        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to store activity: {e}")

    # NOTE: Observation extraction is now handled by the background ActivityProcessor
    # which uses LLM-based classification via schema.yaml instead of pattern matching.
    # Activities are stored above; the processor extracts observations when batches complete.

    # Inject relevant context for file operations
    injected_context = None
    if tool_name in ("Read", "Edit", "Write") and state.retrieval_engine:
        file_path = tool_input.get("file_path", "")
        if file_path:
            try:
                # Search for memories about this file, filter by confidence
                # For file operations, include high and medium confidence
                search_res = state.retrieval_engine.search(
                    query=f"file:{file_path}",
                    search_type="memory",
                    limit=8,  # Fetch more, filter by confidence
                )
                # Filter to high and medium confidence
                confident_memories = RetrievalEngine.filter_by_confidence(
                    search_res.memory, min_confidence="medium"
                )

                if confident_memories:
                    mem_lines = []
                    for mem in confident_memories[:3]:  # Cap at 3
                        mem_type = mem.get("memory_type", "note")
                        obs = mem.get("observation", "")
                        if mem_type == "gotcha":
                            mem_lines.append(f"⚠️ GOTCHA: {obs}")
                        else:
                            mem_lines.append(f"[{mem_type}] {obs}")

                    if mem_lines:
                        injected_context = f"**Memories about {file_path}:**\n" + "\n".join(
                            mem_lines
                        )
                        logger.debug(
                            f"Injecting {len(confident_memories[:3])} confident memories "
                            f"for {file_path}"
                        )
                        logger.debug(f"[INJECT:post-tool-use] Content:\n{injected_context}")

            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.debug(f"Failed to search memories for file context: {e}")

    # Inject oak ci reminder when using search tools repeatedly without oak ci
    if session and tool_name in ("Grep", "Glob"):
        search_count = session.count_search_tool_uses()
        # Remind after 3+ search tool uses if oak ci hasn't been used
        if search_count >= 3 and not session.has_used_oak_ci():
            oak_ci_hint = (
                "💡 **TIP**: `oak ci search '<query>'` provides semantic code search "
                "(finds by meaning, not just keywords). Try it for more relevant results."
            )
            if injected_context:
                injected_context = f"{injected_context}\n\n{oak_ci_hint}"
            else:
                injected_context = oak_ci_hint
            logger.debug(f"Injecting oak ci reminder after {search_count} search tool uses")

    result: dict[str, Any] = {
        "status": "ok",
        # Observations are extracted by background ActivityProcessor, not in this hook
        "observations_captured": 0,
    }
    if injected_context:
        result["injected_context"] = injected_context

    return result


@router.post(f"{OAK_CI_PREFIX}/stop")
async def hook_stop(request: Request) -> dict:
    """Handle agent stop - end current prompt batch and trigger processing.

    This is called when the agent finishes responding to a user prompt.
    We end the current prompt batch and queue it for background processing.

    This is different from session-end, which is called when the user exits
    Claude Code entirely.
    """
    import asyncio

    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in stop hook")
        body = {}

    session_id = body.get("session_id")

    result: dict[str, Any] = {"status": "ok"}

    session = state.get_session(session_id) if session_id else None
    if not session:
        return result

    # End current prompt batch and queue for processing
    prompt_batch_id = session.current_prompt_batch_id
    if prompt_batch_id and state.activity_store:
        try:
            state.activity_store.end_prompt_batch(prompt_batch_id)
            logger.info(f"Ended prompt batch {prompt_batch_id}")

            # Get batch stats
            stats = state.activity_store.get_prompt_batch_stats(prompt_batch_id)
            result["prompt_batch_stats"] = stats
            result["prompt_batch_id"] = prompt_batch_id

            # Queue for background processing
            if state.activity_processor:
                from open_agent_kit.features.codebase_intelligence.activity import (
                    process_prompt_batch_async,
                )

                # Capture processor reference to avoid type narrowing issues
                processor = state.activity_processor
                batch_id = prompt_batch_id

                async def _process_batch() -> None:
                    logger.debug(f"[REALTIME] Starting async processing for batch {batch_id}")
                    try:
                        proc_result = await process_prompt_batch_async(processor, batch_id)
                        if proc_result.success:
                            logger.info(
                                f"[REALTIME] Prompt batch {batch_id} processed: "
                                f"{proc_result.observations_extracted} observations from "
                                f"{proc_result.activities_processed} activities "
                                f"(type={proc_result.classification})"
                            )
                        else:
                            logger.warning(
                                f"[REALTIME] Prompt batch processing failed: {proc_result.error}"
                            )
                    except (RuntimeError, OSError, ValueError) as e:
                        logger.warning(f"[REALTIME] Prompt batch processing error: {e}")

                logger.debug(f"[REALTIME] Scheduling async task for batch {batch_id}")
                asyncio.create_task(_process_batch())
                result["processing_scheduled"] = True

            # Clear current batch from session
            session.current_prompt_batch_id = None

        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to end prompt batch: {e}")

    return result


@router.post(f"{OAK_CI_PREFIX}/session-end")
async def hook_session_end(request: Request) -> dict:
    """Handle session end - finalize session and any remaining prompt batches.

    This is called when the user exits Claude Code entirely.
    We end any remaining prompt batch and the session itself.
    """
    import asyncio

    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in session-end hook")
        body = {}

    session_id = body.get("session_id")
    agent = body.get("agent", "unknown")

    # Prominent logging for session-end to debug if Claude Code is calling this hook
    logger.info("[SESSION-END] ========== Session ending ==========")
    logger.info(f"[SESSION-END] session_id={session_id}, agent={agent}")
    logger.debug(f"[SESSION-END] Raw request body: {body}")

    result: dict[str, Any] = {"status": "ok"}

    session = state.get_session(session_id) if session_id else None
    if not session:
        return result

    # Calculate session duration
    duration_minutes = (datetime.now() - session.started_at).total_seconds() / 60

    # End any remaining prompt batch
    prompt_batch_id = session.current_prompt_batch_id
    if prompt_batch_id and state.activity_store:
        try:
            state.activity_store.end_prompt_batch(prompt_batch_id)
            logger.debug(f"Ended final prompt batch: {prompt_batch_id}")

            # Queue for processing
            if state.activity_processor:
                from open_agent_kit.features.codebase_intelligence.activity import (
                    process_prompt_batch_async,
                )

                # Capture processor reference to avoid type narrowing issues
                processor = state.activity_processor
                batch_id = prompt_batch_id

                async def _process_final_batch() -> None:
                    logger.debug(f"[REALTIME] Starting async processing for final batch {batch_id}")
                    try:
                        proc_result = await process_prompt_batch_async(processor, batch_id)
                        if proc_result.success:
                            logger.info(
                                f"[REALTIME] Final prompt batch {batch_id} processed: "
                                f"{proc_result.observations_extracted} observations"
                            )
                        else:
                            logger.warning(
                                f"[REALTIME] Final batch {batch_id} failed: {proc_result.error}"
                            )
                    except (RuntimeError, OSError, ValueError) as e:
                        logger.warning(f"[REALTIME] Final batch processing error: {e}")

                logger.debug(f"[REALTIME] Scheduling async task for final batch {batch_id}")
                asyncio.create_task(_process_final_batch())

        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to end final prompt batch: {e}")

    # End session in activity store
    if state.activity_store and session_id:
        try:
            state.activity_store.end_session(session_id)
            logger.debug(f"Ended activity session: {session_id}")

            # Get session stats from activity store
            stats = state.activity_store.get_session_stats(session_id)
            result["activity_stats"] = stats
            logger.info(
                f"Session {session_id} ended with {stats.get('files_touched', 0)} files, "
                f"{sum(stats.get('tool_counts', {}).values())} tool calls"
            )

            # Generate session summary in background
            if state.activity_processor:
                processor = state.activity_processor
                sid = session_id

                async def _generate_session_summary() -> None:
                    try:
                        # Run in executor since it's synchronous
                        loop = asyncio.get_event_loop()
                        summary = await loop.run_in_executor(
                            None, processor.process_session_summary, sid
                        )
                        if summary:
                            logger.info(f"Session summary generated: {summary[:80]}...")
                    except (RuntimeError, OSError, ValueError) as e:
                        logger.warning(f"Session summary generation error: {e}")

                asyncio.create_task(_generate_session_summary())

        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to end activity session: {e}")

    # Include session stats from in-memory tracking
    result["observations_captured"] = len(session.observations)
    result["tool_calls"] = session.tool_calls
    result["files_modified"] = len(session.files_modified)
    result["files_created"] = len(session.files_created)
    result["duration_minutes"] = round(duration_minutes, 1)

    # Clean up in-memory session
    state.end_session(session_id)

    return result


@router.post(f"{OAK_CI_PREFIX}/before-prompt")
async def hook_before_prompt(request: Request) -> dict:
    """Handle before-prompt - inject relevant context."""
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in before-prompt hook")
        body = {}

    prompt_preview = body.get("prompt", "")[:500]  # First 500 chars of prompt

    context: dict[str, Any] = {}

    # Search for relevant context based on prompt
    if prompt_preview and state.retrieval_engine:
        try:
            # Search for both code and memories, filter by confidence
            # For notify context, only include HIGH confidence (precision over recall)
            result = state.retrieval_engine.search(
                query=prompt_preview,
                search_type="all",
                limit=10,  # Fetch more, filter by confidence
            )

            # Filter to high confidence for notify context
            high_confidence_code = RetrievalEngine.filter_by_confidence(
                result.code, min_confidence="high"
            )
            high_confidence_memories = RetrievalEngine.filter_by_confidence(
                result.memory, min_confidence="high"
            )

            if high_confidence_code:
                context["relevant_code"] = [
                    {"file": r.get("filepath", ""), "name": r.get("name", "")}
                    for r in high_confidence_code[:3]  # Cap at 3
                ]

            if high_confidence_memories:
                context["relevant_memories"] = [
                    {"observation": r.get("observation", ""), "type": r.get("memory_type", "")}
                    for r in high_confidence_memories[:3]  # Cap at 3
                ]
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.warning(f"Failed to search for context: {e}")

    return {"status": "ok", "context": context}


@router.post(f"{OAK_CI_PREFIX}/{{event}}")
async def handle_hook_generic(event: str) -> dict:
    """Handle other hook events."""
    logger.info(f"Hook event: {event}")
    return {"status": "ok", "event": event}
