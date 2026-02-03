"""AI agent integration hooks for the CI daemon (claude-mem inspired)."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from open_agent_kit.features.codebase_intelligence.constants import (
    HOOK_DEDUP_CACHE_MAX,
    HOOK_DEDUP_HASH_ALGORITHM,
    HOOK_DROP_LOG_TAG,
    HOOK_EVENT_AGENT_THOUGHT,
    HOOK_EVENT_POST_TOOL_USE,
    HOOK_EVENT_POST_TOOL_USE_FAILURE,
    HOOK_EVENT_PRE_COMPACT,
    HOOK_EVENT_PROMPT_SUBMIT,
    HOOK_EVENT_SESSION_END,
    HOOK_EVENT_SESSION_START,
    HOOK_EVENT_STOP,
    HOOK_EVENT_SUBAGENT_START,
    HOOK_EVENT_SUBAGENT_STOP,
    HOOK_FIELD_AGENT_ID,
    HOOK_FIELD_AGENT_TRANSCRIPT_PATH,
    HOOK_FIELD_AGENT_TYPE,
    HOOK_FIELD_CONVERSATION_ID,
    HOOK_FIELD_ERROR_MESSAGE,
    HOOK_FIELD_GENERATION_ID,
    HOOK_FIELD_HOOK_ORIGIN,
    HOOK_FIELD_PROMPT,
    HOOK_FIELD_SESSION_ID,
    HOOK_FIELD_STOP_HOOK_ACTIVE,
    HOOK_FIELD_TOOL_INPUT,
    HOOK_FIELD_TOOL_NAME,
    HOOK_FIELD_TOOL_OUTPUT_B64,
    HOOK_FIELD_TOOL_USE_ID,
    MEMORY_EMBED_LINE_SEPARATOR,
    PROMPT_SOURCE_PLAN,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
    build_rich_search_query,
    build_session_context,
    format_code_for_injection,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.plan_detector import detect_plan
from open_agent_kit.features.codebase_intelligence.prompt_classifier import classify_prompt
from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine
from open_agent_kit.utils.file_utils import get_relative_path

logger = logging.getLogger(__name__)

# Dedicated hooks logger for lifecycle events (writes to hooks.log)
# This provides a clean, focused view of hook activity separate from daemon.log
hooks_logger = logging.getLogger("oak.ci.hooks")

router = APIRouter(tags=["hooks"])

# Route prefix - uses /api/oak/ci/ to avoid conflicts with other integrations
OAK_CI_PREFIX = "/api/oak/ci"

# ==========================================================================
# Exit Plan Tool Detection (for final plan capture)
# ==========================================================================

# Cached mapping of exit plan tool names from agent manifests
_exit_plan_tools: dict[str, str] | None = None


def _get_exit_plan_tools() -> dict[str, str]:
    """Get exit plan tool names from agent manifests (cached).

    Returns:
        Dict mapping agent_type to exit_plan_tool name.
        Example: {'claude': 'ExitPlanMode'}
    """
    global _exit_plan_tools
    if _exit_plan_tools is None:
        try:
            from open_agent_kit.services.agent_service import AgentService

            agent_service = AgentService()
            _exit_plan_tools = agent_service.get_all_exit_plan_tools()
            logger.debug(f"Loaded exit_plan_tools: {_exit_plan_tools}")
        except Exception as e:
            logger.warning(f"Failed to load exit_plan_tools: {e}")
            _exit_plan_tools = {}
    return _exit_plan_tools


def _is_exit_plan_tool(tool_name: str) -> bool:
    """Check if a tool name is an exit plan tool for any agent.

    Args:
        tool_name: The tool name to check (e.g., 'ExitPlanMode').

    Returns:
        True if this tool signals plan mode exit for any agent.
    """
    return tool_name in _get_exit_plan_tools().values()


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


def _hash_value(value: str) -> str:
    """Create a stable hash for dedupe keys."""
    hasher = hashlib.new(HOOK_DEDUP_HASH_ALGORITHM)
    hasher.update(value.encode("utf-8"))
    return hasher.hexdigest()


def _build_dedupe_key(event_name: str, session_id: str, parts: list[str]) -> str:
    """Build a dedupe key for hook events."""
    return "|".join([event_name, session_id, *parts])


def _normalize_file_path(file_path: str, project_root: Path | None) -> str:
    """Normalize file path to project-relative when possible."""
    if not file_path:
        return file_path
    if not project_root:
        return file_path

    path_value = Path(file_path)

    try:
        if not path_value.is_absolute():
            path_value = project_root / path_value
        path_value = path_value.resolve()
        root_path = project_root.resolve()
        if path_value == root_path or root_path in path_value.parents:
            return get_relative_path(path_value, root_path).as_posix()
    except (OSError, RuntimeError, ValueError):
        return file_path

    return file_path


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
    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    source = body.get("source", "startup")  # startup, resume, clear, compact

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped session-start: missing session_id")
        return {"status": "ok", "context": {}}

    dedupe_key = _build_dedupe_key(
        HOOK_EVENT_SESSION_START,
        session_id,
        [agent, source],
    )
    if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
        logger.debug(
            "Deduped session-start session=%s agent=%s source=%s",
            session_id,
            agent,
            source,
        )
        return {"status": "ok", "session_id": session_id, "context": {}}

    # Lifecycle logging to dedicated hooks.log
    hooks_logger.info(f"[SESSION-START] session={session_id} agent={agent} source={source}")
    # Detailed logging to daemon.log (debug mode only)
    logger.debug(f"[SESSION-START] Raw request body: {body}")

    # Create or resume session in activity store (SQLite) - idempotent
    # For source="clear", find the session that just ended and link as parent
    parent_session_id = None
    parent_session_reason = None

    if state.activity_store and state.project_root:
        # When source="clear", find a session to link as parent using tiered approach:
        # 1. Session that just ended (within SESSION_LINK_IMMEDIATE_GAP_SECONDS) - normal flow
        # 2. Active session (race condition - SessionEnd not processed yet)
        # 3. Most recent completed session within SESSION_LINK_FALLBACK_MAX_HOURS (stale/next-day)
        if source == "clear":
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
                    find_linkable_parent_session,
                )

                link_result = find_linkable_parent_session(
                    store=state.activity_store,
                    agent=agent,
                    project_root=str(state.project_root),
                    exclude_session_id=session_id,
                    new_session_started_at=datetime.now(),
                    # Use defaults from constants (SESSION_LINK_IMMEDIATE_GAP_SECONDS,
                    # SESSION_LINK_FALLBACK_MAX_HOURS)
                )
                if link_result:
                    parent_session_id, parent_session_reason = link_result
                    hooks_logger.info(
                        f"[SESSION-LINK] session={session_id} parent={parent_session_id[:8]}... "
                        f"reason={parent_session_reason}"
                    )
            except (OSError, ValueError, RuntimeError) as e:
                logger.debug(f"Failed to find parent session for linking: {e}")

        try:
            _, created = state.activity_store.get_or_create_session(
                session_id=session_id,
                agent=agent,
                project_root=str(state.project_root),
            )
            if created:
                logger.debug(f"Created activity session: {session_id}")
                # If we found a parent session and the session was just created,
                # update the parent link
                if parent_session_id:
                    try:
                        from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
                            update_session_parent,
                        )

                        update_session_parent(
                            store=state.activity_store,
                            session_id=session_id,
                            parent_session_id=parent_session_id,
                            reason=parent_session_reason or "clear",
                        )
                    except (OSError, ValueError, RuntimeError) as e:
                        logger.debug(f"Failed to update session parent: {e}")
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
    injected = build_session_context(state, include_memories=inject_full_context)
    if injected:
        context["injected_context"] = injected
        # Summary to hooks.log for easy visibility
        hooks_logger.info(
            f"[CONTEXT-INJECT] session_context session={session_id} "
            f"include_memories={inject_full_context} hook=session-start"
        )
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

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    prompt = body.get(HOOK_FIELD_PROMPT, "")
    agent = body.get("agent", "unknown")
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")
    generation_id = body.get(HOOK_FIELD_GENERATION_ID, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped prompt-submit: missing session_id")
        return {"status": "ok", "context": {}}

    # Skip if no prompt or very short
    if not prompt or len(prompt) < 2:
        return {"status": "ok", "context": {}}

    prompt_hash = _hash_value(prompt)

    dedupe_parts = [prompt_hash]
    if generation_id:
        dedupe_parts = [generation_id, prompt_hash]
    dedupe_key = _build_dedupe_key(HOOK_EVENT_PROMPT_SUBMIT, session_id, dedupe_parts)
    if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
        logger.debug(
            "Deduped prompt-submit session=%s origin=%s key=%s",
            session_id,
            hook_origin,
            dedupe_key,
        )
        return {"status": "ok", "context": {}}

    logger.debug(f"Prompt submit: {prompt[:50]}...")

    # Create new prompt batch in activity store (SQLite handles all session/batch tracking)
    prompt_batch_id = None
    if state.activity_store and session_id:
        try:
            # End previous prompt batch if exists (query SQLite for active batch)
            active_batch = state.activity_store.get_active_prompt_batch(session_id)
            if active_batch and active_batch.id:
                previous_batch_id = active_batch.id
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

            # Detect prompt source type for categorization using PromptClassifier
            # This handles: internal messages (task-notification, system) and
            # plan execution prompts (auto-injected by plan mode)
            classification = classify_prompt(prompt)
            source_type = classification.source_type

            # Extract plan content if this is a plan prompt (plan embedded in prompt)
            # The plan content is after the prefix (e.g., "Implement the following plan:\n\n")
            plan_content = None
            if source_type == PROMPT_SOURCE_PLAN and classification.matched_prefix:
                # Strip the prefix and any leading whitespace to get the actual plan
                prefix_len = len(classification.matched_prefix)
                plan_content = prompt[prefix_len:].lstrip()
                logger.debug(f"Extracted plan content from prompt ({len(plan_content)} chars)")

            # Create new prompt batch with full user prompt and source type
            batch = state.activity_store.create_prompt_batch(
                session_id=session_id,
                user_prompt=prompt,  # Full prompt, truncated to 10K in store
                source_type=source_type,
                plan_content=plan_content,  # Plan content if extracted from prompt
                agent=agent,  # For session recreation if previously deleted
            )
            prompt_batch_id = batch.id

            # Lifecycle logging to dedicated hooks.log
            hooks_logger.info(
                f"[PROMPT-SUBMIT] session={session_id} batch={prompt_batch_id} "
                f"source={source_type}"
            )

            # Detailed logging to daemon.log
            if classification.agent_type:
                logger.debug(
                    f"Created prompt batch {prompt_batch_id} (source={source_type}, "
                    f"agent={classification.agent_type}) for session {session_id}"
                )
            else:
                logger.debug(
                    f"Created prompt batch {prompt_batch_id} (source={source_type}) "
                    f"for session {session_id}"
                )

            # Note: batch ID is tracked in SQLite, no in-memory state needed

        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to create prompt batch: {e}")

    context: dict[str, Any] = {}
    search_query = prompt
    if state.activity_store:
        session_record = state.activity_store.get_session(session_id)
        if session_record and session_record.title:
            search_query = MEMORY_EMBED_LINE_SEPARATOR.join([session_record.title, prompt])

    # Search for relevant memories based on prompt
    if state.retrieval_engine:
        try:
            # Debug logging for search queries (trace mode)
            logger.debug(f"[SEARCH:memory] query={search_query[:200]}")

            # Search with base threshold, then filter by confidence
            # For prompt injection, only include HIGH confidence (precision over recall)
            result = state.retrieval_engine.search(
                query=search_query,
                search_type="memory",
                limit=10,  # Fetch more, filter by confidence
            )

            # Filter by combined score (confidence + importance) for prompt injection
            # High threshold ensures only highly relevant AND important memories are injected
            high_confidence_memories = RetrievalEngine.filter_by_combined_score(
                result.memory, min_combined="high"
            )

            # Debug logging for search results (trace mode)
            logger.debug(
                f"[SEARCH:memory:results] found={len(result.memory)} "
                f"high_combined={len(high_confidence_memories)}"
            )
            if result.memory:
                scores_preview = [
                    (round(m.get("relevance", 0), 3), m.get("confidence"))
                    for m in result.memory[:5]
                ]
                logger.debug(f"[SEARCH:memory:scores] {scores_preview}")

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
                    num_memories = len(high_confidence_memories[:5])
                    logger.info(f"Injecting {num_memories} high-confidence " f"memories for prompt")
                    # Summary to hooks.log for easy visibility
                    hooks_logger.info(
                        f"[CONTEXT-INJECT] memories={num_memories} session={session_id} "
                        f"hook=prompt-submit"
                    )
                    logger.debug(f"[INJECT:prompt-submit] Content:\n{injected_text}")

        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to search memories for prompt: {e}")

    # Search for relevant code based on prompt
    if state.retrieval_engine:
        try:
            # Debug logging for search queries (trace mode)
            logger.debug(f"[SEARCH:code] query={search_query[:200]}")

            code_result = state.retrieval_engine.search(
                query=search_query,
                search_type="code",
                limit=10,
            )
            # For code, stick with confidence-only filtering (no importance metadata)
            high_confidence_code = RetrievalEngine.filter_by_confidence(
                code_result.code, min_confidence="high"
            )

            # Debug logging for search results (trace mode)
            logger.debug(
                f"[SEARCH:code:results] found={len(code_result.code)} "
                f"high_confidence={len(high_confidence_code)}"
            )

            if high_confidence_code:
                code_text = format_code_for_injection(high_confidence_code[:3])
                if code_text:
                    if "injected_context" in context:
                        context["injected_context"] = (
                            f"{code_text}\n\n{context['injected_context']}"
                        )
                    else:
                        context["injected_context"] = code_text
                    num_code = min(3, len(high_confidence_code))
                    logger.info(f"Injecting {num_code} code chunks for prompt")
                    # Summary to hooks.log for easy visibility
                    hooks_logger.info(
                        f"[CONTEXT-INJECT] code={num_code} session={session_id} "
                        f"hook=prompt-submit"
                    )
                    logger.debug(f"[INJECT:prompt-submit-code] Content:\n{code_text}")
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to search code for prompt: {e}")

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

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    tool_name = body.get(HOOK_FIELD_TOOL_NAME, "")
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")
    tool_use_id = body.get(HOOK_FIELD_TOOL_USE_ID, "")
    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped post-tool-use: missing session_id")
        return {"status": "ok", "observations_captured": 0}

    # Handle tool_input - could be dict (from JSON) or string
    tool_input = body.get(HOOK_FIELD_TOOL_INPUT, {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (ValueError, json.JSONDecodeError):
            tool_input = {"raw": tool_input}
    elif tool_input is None:
        tool_input = {}

    # Handle tool_output - check for base64-encoded version first
    tool_output_b64 = body.get(HOOK_FIELD_TOOL_OUTPUT_B64, "")
    if tool_output_b64:
        try:
            tool_output = base64.b64decode(tool_output_b64).decode("utf-8", errors="replace")
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to decode base64 output: {e}")
            tool_output = ""
    else:
        tool_output = body.get("tool_output", body.get("output", ""))

    # Log detailed info about what was received (daemon.log debug only)
    has_input = bool(tool_input and tool_input != {})
    has_output = bool(tool_output)
    output_len = len(tool_output) if tool_output else 0
    logger.debug(
        f"Post-tool-use: {tool_name} | "
        f"input={has_input} | output={has_output} ({output_len} chars) | "
        f"session={session_id or 'none'}"
    )
    if session_id and tool_use_id:
        dedupe_key = _build_dedupe_key(
            HOOK_EVENT_POST_TOOL_USE,
            session_id,
            [tool_use_id],
        )
        if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
            logger.debug(
                "Deduped post-tool-use session=%s origin=%s token=%s",
                session_id,
                hook_origin,
                tool_use_id,
            )
            return {"status": "ok", "observations_captured": 0}
    elif session_id:
        signature_payload = {
            HOOK_FIELD_TOOL_NAME: tool_name,
            HOOK_FIELD_TOOL_INPUT: tool_input,
            HOOK_FIELD_TOOL_OUTPUT_B64: tool_output_b64 or tool_output,
        }
        signature = json.dumps(signature_payload, sort_keys=True, default=str)
        dedupe_token = _hash_value(signature)
        dedupe_key = _build_dedupe_key(
            HOOK_EVENT_POST_TOOL_USE,
            session_id,
            [dedupe_token],
        )
        if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
            logger.debug(
                "Deduped post-tool-use session=%s origin=%s token=%s",
                session_id,
                hook_origin,
                dedupe_token,
            )
            return {"status": "ok", "observations_captured": 0}

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

            # Get current prompt batch ID from SQLite
            prompt_batch_id = None
            active_batch = state.activity_store.get_active_prompt_batch(session_id)
            if active_batch:
                prompt_batch_id = active_batch.id

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
            # Use buffered insert for better performance (auto-flushes at batch size)
            state.activity_store.add_activity_buffered(activity)
            logger.debug(f"Stored activity: {tool_name} (batch={prompt_batch_id})")

            # Lifecycle logging to dedicated hooks.log
            hooks_logger.info(f"[TOOL-USE] {tool_name} session={session_id} success={not is_error}")

            # Detect plan mode: if Write to a plan directory, mark batch as plan
            # and capture plan content for self-contained CI storage
            if tool_name == "Write" and prompt_batch_id:
                file_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
                if file_path:
                    detection = detect_plan(file_path)
                    if detection.is_plan:
                        # Read plan content from the file that was just written.
                        # This is more reliable than tool_input because:
                        # 1. tool_input in stored activities is sanitized (<N chars>)
                        # 2. The file is the source of truth
                        plan_content = ""
                        plan_path = Path(file_path)
                        if not plan_path.is_absolute() and state.project_root:
                            plan_path = state.project_root / plan_path

                        try:
                            if plan_path.exists():
                                plan_content = plan_path.read_text(encoding="utf-8")
                            else:
                                # Fallback to tool_input if file doesn't exist yet
                                plan_content = (
                                    tool_input.get("content", "")
                                    if isinstance(tool_input, dict)
                                    else ""
                                )
                        except (OSError, ValueError) as e:
                            logger.warning(f"Failed to read plan file {plan_path}: {e}")
                            # Fallback to tool_input
                            plan_content = (
                                tool_input.get("content", "")
                                if isinstance(tool_input, dict)
                                else ""
                            )

                        state.activity_store.update_prompt_batch_source_type(
                            prompt_batch_id,
                            PROMPT_SOURCE_PLAN,
                            plan_file_path=file_path,
                            plan_content=plan_content,
                        )
                        location = "global" if detection.is_global else "project"
                        content_len = len(plan_content) if plan_content else 0
                        logger.info(
                            f"Detected {location} plan mode for {detection.agent_type}, "
                            f"batch {prompt_batch_id} marked as plan with file {file_path} "
                            f"({content_len} chars stored)"
                        )

            # Detect ExitPlanMode: re-read plan file and update stored content
            # Plans iterate during development - the final approved version (when user
            # exits plan mode) may differ from the initial write. Re-reading ensures
            # we capture the final content.
            if _is_exit_plan_tool(tool_name) and session_id:
                try:
                    plan_batch = state.activity_store.get_session_plan_batch(session_id)

                    if plan_batch and plan_batch.plan_file_path and plan_batch.id:
                        plan_path = Path(plan_batch.plan_file_path)
                        if not plan_path.is_absolute() and state.project_root:
                            plan_path = state.project_root / plan_path

                        if plan_path.exists():
                            final_content = plan_path.read_text(encoding="utf-8")
                            state.activity_store.update_prompt_batch_source_type(
                                plan_batch.id,
                                PROMPT_SOURCE_PLAN,
                                plan_file_path=plan_batch.plan_file_path,
                                plan_content=final_content,
                            )
                            state.activity_store.mark_plan_unembedded(plan_batch.id)
                            hooks_logger.info(
                                f"[EXIT-PLAN-MODE] Updated plan {plan_batch.id} "
                                f"({len(final_content)} chars)"
                            )
                            logger.info(
                                f"ExitPlanMode detected: re-read plan {plan_batch.plan_file_path} "
                                f"and updated batch {plan_batch.id} ({len(final_content)} chars)"
                            )
                        else:
                            logger.warning(
                                f"[EXIT-PLAN-MODE] Plan file not found: {plan_batch.plan_file_path}"
                            )
                    else:
                        logger.debug(
                            "[EXIT-PLAN-MODE] No plan batch in session "
                            "(plan may have been cancelled or not created)"
                        )
                except Exception as e:
                    logger.warning(f"[EXIT-PLAN-MODE] Failed to update plan content: {e}")

            # Detect plan file reads - may signal plan execution is starting
            # This helps discover patterns for agents without known plan execution prefixes
            if tool_name == "Read" and prompt_batch_id:
                file_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
                if file_path:
                    detection = detect_plan(file_path)
                    if detection.is_plan:
                        location = "global" if detection.is_global else "project"
                        hooks_logger.info(
                            f"[PLAN-READ] {detection.agent_type} plan read: {file_path} "
                            f"location={location} session={session_id}"
                        )
                        logger.info(
                            f"Detected {location} plan file read for {detection.agent_type}: "
                            f"{file_path} (may signal plan execution)"
                        )

        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to store activity: {e}")

    # NOTE: Observation extraction is now handled by the background ActivityProcessor
    # which uses LLM-based classification via schema.yaml instead of pattern matching.
    # Activities are stored above; the processor extracts observations when batches complete.

    # Inject relevant context for file operations
    injected_context = None
    if tool_name in ("Read", "Edit", "Write") and state.retrieval_engine:
        file_path = tool_input.get("file_path", "")
        if file_path and state.activity_store:
            try:
                normalized_path = _normalize_file_path(file_path, state.project_root)

                # Get user prompt for richer context from active batch
                user_prompt = None
                active_batch = state.activity_store.get_active_prompt_batch(session_id)
                if active_batch:
                    user_prompt = active_batch.user_prompt

                    # Build rich query (not just file path) for better semantic matching
                    search_query = build_rich_search_query(
                        normalized_path=normalized_path,
                        tool_output=tool_output if tool_name != "Read" else None,
                        user_prompt=user_prompt,
                    )

                    # Debug logging for file context search (trace mode)
                    logger.debug(
                        f"[SEARCH:file-context] query={search_query[:150]} file={normalized_path}"
                    )

                    # Search for memories about this file, filter by combined score
                    # For file operations, include medium+ combined score
                    search_res = state.retrieval_engine.search(
                        query=search_query,
                        search_type="memory",
                        limit=8,  # Fetch more, filter by combined score
                    )
                    # Filter by combined score (confidence + importance)
                    confident_memories = RetrievalEngine.filter_by_combined_score(
                        search_res.memory, min_combined="medium"
                    )

                    # Debug logging for file context results (trace mode)
                    logger.debug(
                        f"[SEARCH:file-context:results] found={len(search_res.memory)} "
                        f"kept_combined={len(confident_memories)}"
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
                            injected_context = (
                                f"**Memories about {normalized_path}:**\n" + "\n".join(mem_lines)
                            )
                            num_file_memories = len(confident_memories[:3])
                            logger.debug(
                                f"Injecting {num_file_memories} confident memories "
                                f"for {normalized_path}"
                            )
                            # Summary to hooks.log for easy visibility
                            hooks_logger.info(
                                f"[CONTEXT-INJECT] file_memories={num_file_memories} "
                                f"file={normalized_path} session={session_id} hook=post-tool-use"
                            )
                            logger.debug(f"[INJECT:post-tool-use] Content:\n{injected_context}")

            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.debug(f"Failed to search memories for file context: {e}")

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
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in stop hook")
        body = {}

    session_id = body.get("session_id") or body.get("conversation_id")

    result: dict[str, Any] = {"status": "ok"}
    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped stop hook: missing session_id")
        return result

    if not state.activity_store:
        return result

    # Flush any buffered activities before ending the batch
    try:
        flushed_ids = state.activity_store.flush_activity_buffer()
        if flushed_ids:
            logger.debug(f"Flushed {len(flushed_ids)} buffered activities before batch end")
    except (OSError, ValueError, RuntimeError) as e:
        logger.debug(f"Failed to flush activity buffer: {e}")

    # End current prompt batch and queue for processing (get batch from SQLite)
    active_batch = state.activity_store.get_active_prompt_batch(session_id)
    prompt_batch_id = active_batch.id if active_batch else None
    if prompt_batch_id:
        dedupe_key = _build_dedupe_key(
            HOOK_EVENT_STOP,
            session_id,
            [str(prompt_batch_id)],
        )
        if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
            logger.debug(
                "Deduped stop hook session=%s batch=%s",
                session_id,
                prompt_batch_id,
            )
            result["prompt_batch_id"] = prompt_batch_id
            return result
        try:
            response_summary = None
            transcript_path = body.get("transcript_path", "")
            if transcript_path:
                from open_agent_kit.features.codebase_intelligence.transcript import (
                    parse_transcript_response,
                )

                response_summary = parse_transcript_response(transcript_path)

            from open_agent_kit.features.codebase_intelligence.activity import (
                finalize_prompt_batch,
            )

            finalize_result = finalize_prompt_batch(
                activity_store=state.activity_store,
                activity_processor=state.activity_processor,
                prompt_batch_id=prompt_batch_id,
                response_summary=response_summary,
            )
            result.update(finalize_result)
            logger.info(f"Ended prompt batch {prompt_batch_id}")

            # Note: batch status is tracked in SQLite, no in-memory cleanup needed

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

    session_id = body.get("session_id") or body.get("conversation_id")
    agent = body.get("agent", "unknown")
    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped session-end: missing session_id")
        return {"status": "ok"}

    # Lifecycle logging to dedicated hooks.log
    hooks_logger.info(f"[SESSION-END] session={session_id} agent={agent}")
    # Detailed logging to daemon.log (debug mode only)
    logger.debug(f"[SESSION-END] Raw request body: {body}")

    # Flush any buffered activities before ending the session
    if state.activity_store:
        try:
            flushed_ids = state.activity_store.flush_activity_buffer()
            if flushed_ids:
                logger.debug(f"Flushed {len(flushed_ids)} buffered activities on session end")
        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to flush activity buffer on session end: {e}")

    result: dict[str, Any] = {"status": "ok"}
    if not session_id:
        return result

    dedupe_key = _build_dedupe_key(HOOK_EVENT_SESSION_END, session_id, [])
    if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
        logger.debug("Deduped session-end session=%s agent=%s", session_id, agent)
        return result

    if not state.activity_store:
        return result

    # Calculate session duration from SQLite session record
    duration_minutes = 0.0
    db_session = state.activity_store.get_session(session_id)
    if db_session and db_session.started_at:
        duration_minutes = (datetime.now() - db_session.started_at).total_seconds() / 60

    # End any remaining prompt batch (query SQLite for active batch)
    active_batch = state.activity_store.get_active_prompt_batch(session_id)
    prompt_batch_id = active_batch.id if active_batch else None
    if prompt_batch_id:
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

    # Session stats come from activity_stats (SQLite) - no in-memory tracking
    result["duration_minutes"] = round(duration_minutes, 1)

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
    search_query = prompt_preview
    if state.activity_store:
        session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
        if session_id:
            session_record = state.activity_store.get_session(session_id)
            if session_record and session_record.title:
                search_query = MEMORY_EMBED_LINE_SEPARATOR.join(
                    [session_record.title, prompt_preview]
                )

    # Search for relevant context based on prompt
    if search_query and state.retrieval_engine:
        try:
            # Search for both code and memories, filter by confidence
            # For notify context, only include HIGH confidence (precision over recall)
            result = state.retrieval_engine.search(
                query=search_query,
                search_type="all",
                limit=10,  # Fetch more, filter by confidence
            )

            # Filter to high confidence for notify context
            # Code uses confidence-only (no importance metadata)
            high_confidence_code = RetrievalEngine.filter_by_confidence(
                result.code, min_confidence="high"
            )
            # Memories use combined score (confidence + importance)
            high_confidence_memories = RetrievalEngine.filter_by_combined_score(
                result.memory, min_combined="high"
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


@router.post(f"{OAK_CI_PREFIX}/post-tool-use-failure")
async def hook_post_tool_use_failure(request: Request) -> dict:
    """Handle post-tool-use-failure - capture failed tool executions.

    This is called when a tool execution fails. Similar to post-tool-use
    but always marks success=False and captures error details.
    """
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in post-tool-use-failure")
        body = {}

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    tool_name = body.get(HOOK_FIELD_TOOL_NAME, "unknown")
    error_message = body.get(HOOK_FIELD_ERROR_MESSAGE, "")
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")
    tool_use_id = body.get(HOOK_FIELD_TOOL_USE_ID, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped post-tool-use-failure: missing session_id")
        return {"status": "ok"}

    # Dedupe by tool_use_id if available
    if tool_use_id:
        dedupe_key = _build_dedupe_key(
            HOOK_EVENT_POST_TOOL_USE_FAILURE,
            session_id,
            [tool_use_id],
        )
        if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
            logger.debug(
                "Deduped post-tool-use-failure session=%s origin=%s token=%s",
                session_id,
                hook_origin,
                tool_use_id,
            )
            return {"status": "ok"}

    # Prominent logging for tool failures
    logger.warning(
        f"[TOOL-FAILURE] {tool_name} | session={session_id} | error={error_message[:100]}"
    )

    # Handle tool_input - could be dict (from JSON) or string
    tool_input = body.get(HOOK_FIELD_TOOL_INPUT, {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (ValueError, json.JSONDecodeError):
            tool_input = {"raw": tool_input}
    elif tool_input is None:
        tool_input = {}

    # Store activity in SQLite with success=False
    if state.activity_store and session_id:
        try:
            from open_agent_kit.features.codebase_intelligence.activity import Activity

            # Get current prompt batch ID from SQLite
            prompt_batch_id = None
            active_batch = state.activity_store.get_active_prompt_batch(session_id)
            if active_batch:
                prompt_batch_id = active_batch.id

            activity = Activity(
                session_id=session_id,
                prompt_batch_id=prompt_batch_id,
                tool_name=tool_name,
                tool_input=tool_input if isinstance(tool_input, dict) else None,
                tool_output_summary=(
                    error_message[:500] if error_message else "Tool execution failed"
                ),
                file_path=tool_input.get("file_path") if isinstance(tool_input, dict) else None,
                success=False,
                error_message=error_message[:500] if error_message else None,
            )
            state.activity_store.add_activity_buffered(activity)
            logger.debug(f"Stored failed activity: {tool_name} (batch={prompt_batch_id})")

        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to store failed activity: {e}")

    return {"status": "ok", "tool_name": tool_name, "recorded": True}


@router.post(f"{OAK_CI_PREFIX}/subagent-start")
async def hook_subagent_start(request: Request) -> dict:
    """Handle subagent-start - track when a subagent is spawned.

    This is called when a parent agent spawns a subagent (e.g., Task tool).
    Tracks agent_id and agent_type for correlation with subagent-stop.
    """
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in subagent-start")
        body = {}

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    agent_id = body.get(HOOK_FIELD_AGENT_ID, "")
    agent_type = body.get(HOOK_FIELD_AGENT_TYPE, "unknown")
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped subagent-start: missing session_id")
        return {"status": "ok"}

    # Dedupe by agent_id
    if agent_id:
        dedupe_key = _build_dedupe_key(
            HOOK_EVENT_SUBAGENT_START,
            session_id,
            [agent_id],
        )
        if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
            logger.debug(
                "Deduped subagent-start session=%s origin=%s agent_id=%s",
                session_id,
                hook_origin,
                agent_id,
            )
            return {"status": "ok"}

    # Lifecycle logging to dedicated hooks.log
    hooks_logger.info(f"[SUBAGENT-START] type={agent_type} id={agent_id} session={session_id}")

    # Store as activity to track subagent spawn
    if state.activity_store and session_id:
        try:
            from open_agent_kit.features.codebase_intelligence.activity import Activity

            # Get current prompt batch ID from SQLite
            prompt_batch_id = None
            active_batch = state.activity_store.get_active_prompt_batch(session_id)
            if active_batch:
                prompt_batch_id = active_batch.id

            activity = Activity(
                session_id=session_id,
                prompt_batch_id=prompt_batch_id,
                tool_name="SubagentStart",
                tool_input={"agent_id": agent_id, "agent_type": agent_type},
                tool_output_summary=f"Started subagent: {agent_type}",
                success=True,
            )
            state.activity_store.add_activity_buffered(activity)
            logger.debug(f"Stored subagent-start: {agent_type} (batch={prompt_batch_id})")

        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to store subagent-start: {e}")

    return {"status": "ok", "agent_id": agent_id, "agent_type": agent_type}


@router.post(f"{OAK_CI_PREFIX}/subagent-stop")
async def hook_subagent_stop(request: Request) -> dict:
    """Handle subagent-stop - track when a subagent completes.

    This is called when a subagent finishes executing. Includes the
    agent_transcript_path if available for potential future parsing.
    """
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in subagent-stop")
        body = {}

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    agent_id = body.get(HOOK_FIELD_AGENT_ID, "")
    agent_type = body.get(HOOK_FIELD_AGENT_TYPE, "unknown")
    agent_transcript_path = body.get(HOOK_FIELD_AGENT_TRANSCRIPT_PATH, "")
    stop_hook_active = body.get(HOOK_FIELD_STOP_HOOK_ACTIVE, False)
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped subagent-stop: missing session_id")
        return {"status": "ok"}

    # Dedupe by agent_id
    if agent_id:
        dedupe_key = _build_dedupe_key(
            HOOK_EVENT_SUBAGENT_STOP,
            session_id,
            [agent_id],
        )
        if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
            logger.debug(
                "Deduped subagent-stop session=%s origin=%s agent_id=%s",
                session_id,
                hook_origin,
                agent_id,
            )
            return {"status": "ok"}

    # Lifecycle logging to dedicated hooks.log
    hooks_logger.info(f"[SUBAGENT-STOP] type={agent_type} id={agent_id} session={session_id}")

    # Store as activity to track subagent completion
    if state.activity_store and session_id:
        try:
            from open_agent_kit.features.codebase_intelligence.activity import Activity

            # Get current prompt batch ID from SQLite
            prompt_batch_id = None
            active_batch = state.activity_store.get_active_prompt_batch(session_id)
            if active_batch:
                prompt_batch_id = active_batch.id

            activity = Activity(
                session_id=session_id,
                prompt_batch_id=prompt_batch_id,
                tool_name="SubagentStop",
                tool_input={
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "has_transcript": bool(agent_transcript_path),
                    "stop_hook_active": stop_hook_active,
                },
                tool_output_summary=f"Completed subagent: {agent_type}",
                file_path=agent_transcript_path if agent_transcript_path else None,
                success=True,
            )
            state.activity_store.add_activity_buffered(activity)
            logger.debug(f"Stored subagent-stop: {agent_type} (batch={prompt_batch_id})")

            # Capture subagent response summary from transcript
            if agent_transcript_path and prompt_batch_id:
                from open_agent_kit.features.codebase_intelligence.transcript import (
                    parse_transcript_response,
                )

                response_summary = parse_transcript_response(agent_transcript_path)
                if response_summary:
                    state.activity_store.update_prompt_batch_response(
                        prompt_batch_id, response_summary
                    )
                    logger.debug(f"Captured subagent response for batch {prompt_batch_id}")

        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to store subagent-stop: {e}")

    return {
        "status": "ok",
        "agent_id": agent_id,
        "agent_type": agent_type,
        "transcript_path": agent_transcript_path,
    }


@router.post(f"{OAK_CI_PREFIX}/agent-thought")
async def hook_agent_thought(request: Request) -> dict:
    """Handle agent-thought - capture agent reasoning/thinking blocks.

    This is called when the agent completes a thinking block. Stores the
    thinking text as an activity for potential analysis of agent reasoning.
    """
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in agent-thought")
        body = {}

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    thought_text = body.get("text", "")
    duration_ms = body.get("duration_ms", 0)
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")
    generation_id = body.get(HOOK_FIELD_GENERATION_ID, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped agent-thought: missing session_id")
        return {"status": "ok"}

    # Skip empty thinking blocks
    if not thought_text or len(thought_text) < 10:
        return {"status": "ok"}

    # Create dedupe key based on thought content hash
    thought_hash = _hash_value(thought_text[:500])  # Hash first 500 chars
    dedupe_parts = [generation_id, thought_hash] if generation_id else [thought_hash]
    dedupe_key = _build_dedupe_key(HOOK_EVENT_AGENT_THOUGHT, session_id, dedupe_parts)
    if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
        logger.debug(
            "Deduped agent-thought session=%s origin=%s",
            session_id,
            hook_origin,
        )
        return {"status": "ok"}

    # Lifecycle logging to dedicated hooks.log
    hooks_logger.info(
        f"[AGENT-THOUGHT] session={session_id} duration_ms={duration_ms} "
        f"length={len(thought_text)}"
    )

    # Store as activity for analysis
    if state.activity_store and session_id:
        try:
            from open_agent_kit.features.codebase_intelligence.activity import Activity

            # Get current prompt batch ID from SQLite
            prompt_batch_id = None
            active_batch = state.activity_store.get_active_prompt_batch(session_id)
            if active_batch:
                prompt_batch_id = active_batch.id

            # Truncate thought text if too long (keep first 2000 chars for summary)
            summary = thought_text[:2000] if len(thought_text) > 2000 else thought_text

            activity = Activity(
                session_id=session_id,
                prompt_batch_id=prompt_batch_id,
                tool_name="AgentThought",
                tool_input={"duration_ms": duration_ms},
                tool_output_summary=summary,
                success=True,
            )
            state.activity_store.add_activity_buffered(activity)
            logger.debug(
                f"Stored agent-thought: {len(thought_text)} chars (batch={prompt_batch_id})"
            )

        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to store agent-thought: {e}")

    return {"status": "ok", "thought_length": len(thought_text), "duration_ms": duration_ms}


@router.post(f"{OAK_CI_PREFIX}/pre-compact")
async def hook_pre_compact(request: Request) -> dict:
    """Handle pre-compact - track context window compaction events.

    This is called before context window compaction/summarization occurs.
    Useful for understanding context pressure and debugging memory issues.
    """
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in pre-compact")
        body = {}

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    trigger = body.get("trigger", "auto")
    context_usage_percent = body.get("context_usage_percent", 0)
    context_tokens = body.get("context_tokens", 0)
    context_window_size = body.get("context_window_size", 0)
    message_count = body.get("message_count", 0)
    messages_to_compact = body.get("messages_to_compact", 0)
    is_first_compaction = body.get("is_first_compaction", False)
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")
    generation_id = body.get(HOOK_FIELD_GENERATION_ID, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped pre-compact: missing session_id")
        return {"status": "ok"}

    # Dedupe by generation_id if available, else by context_tokens
    dedupe_parts = [generation_id] if generation_id else [str(context_tokens)]
    dedupe_key = _build_dedupe_key(HOOK_EVENT_PRE_COMPACT, session_id, dedupe_parts)
    if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
        logger.debug(
            "Deduped pre-compact session=%s origin=%s",
            session_id,
            hook_origin,
        )
        return {"status": "ok"}

    # Lifecycle logging to dedicated hooks.log
    hooks_logger.info(
        f"[PRE-COMPACT] session={session_id} trigger={trigger} "
        f"usage={context_usage_percent}% tokens={context_tokens} messages={message_count}"
    )

    # Store as activity for debugging context pressure
    if state.activity_store and session_id:
        try:
            from open_agent_kit.features.codebase_intelligence.activity import Activity

            # Get current prompt batch ID from SQLite
            prompt_batch_id = None
            active_batch = state.activity_store.get_active_prompt_batch(session_id)
            if active_batch:
                prompt_batch_id = active_batch.id

            activity = Activity(
                session_id=session_id,
                prompt_batch_id=prompt_batch_id,
                tool_name="ContextCompact",
                tool_input={
                    "trigger": trigger,
                    "context_usage_percent": context_usage_percent,
                    "context_tokens": context_tokens,
                    "context_window_size": context_window_size,
                    "message_count": message_count,
                    "messages_to_compact": messages_to_compact,
                    "is_first_compaction": is_first_compaction,
                },
                tool_output_summary=(
                    f"Context compaction ({trigger}): {context_usage_percent}% used, "
                    f"{messages_to_compact}/{message_count} messages"
                ),
                success=True,
            )
            state.activity_store.add_activity_buffered(activity)
            logger.debug(
                f"Stored pre-compact: {context_usage_percent}% usage (batch={prompt_batch_id})"
            )

        except (OSError, ValueError, RuntimeError) as e:
            logger.debug(f"Failed to store pre-compact: {e}")

    return {
        "status": "ok",
        "trigger": trigger,
        "context_usage_percent": context_usage_percent,
    }


@router.post(f"{OAK_CI_PREFIX}/{{event}}")
async def handle_hook_generic(event: str) -> dict:
    """Handle other hook events."""
    logger.info(f"Hook event: {event}")
    return {"status": "ok", "event": event}
