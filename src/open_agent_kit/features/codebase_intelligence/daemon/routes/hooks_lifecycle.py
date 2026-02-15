"""Lifecycle hook handlers: stop, subagent, agent-thought, pre-compact.

These handlers track agent lifecycle events that are not directly tied to
prompt submission or tool execution.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Request

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_UNKNOWN,
    HOOK_DEDUP_CACHE_MAX,
    HOOK_DROP_LOG_TAG,
    HOOK_EVENT_AGENT_THOUGHT,
    HOOK_EVENT_PRE_COMPACT,
    HOOK_EVENT_STOP,
    HOOK_EVENT_SUBAGENT_START,
    HOOK_EVENT_SUBAGENT_STOP,
    HOOK_FIELD_AGENT,
    HOOK_FIELD_AGENT_ID,
    HOOK_FIELD_AGENT_TRANSCRIPT_PATH,
    HOOK_FIELD_AGENT_TYPE,
    HOOK_FIELD_CONVERSATION_ID,
    HOOK_FIELD_GENERATION_ID,
    HOOK_FIELD_HOOK_ORIGIN,
    HOOK_FIELD_SESSION_ID,
    HOOK_FIELD_STOP_HOOK_ACTIVE,
    PROMPT_SOURCE_PLAN,
    RESPONSE_SUMMARY_MAX_LENGTH,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_common import (
    HOOK_STORE_EXCEPTIONS,
    OAK_CI_PREFIX,
    build_dedupe_key,
    get_active_batch_id,
    hash_value,
    hooks_logger,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hooks"])


# =============================================================================
# Stop handler
# =============================================================================


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
    transcript_path = body.get("transcript_path", "")
    agent = body.get(HOOK_FIELD_AGENT, AGENT_UNKNOWN)

    # Debug logging to trace transcript_path flow
    logger.debug(
        "[STOP] session=%s agent=%s transcript_path=%s body_keys=%s",
        session_id,
        agent,
        transcript_path[:100] if transcript_path else "(empty)",
        list(body.keys()),
    )

    result: dict[str, Any] = {"status": "ok"}
    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped stop hook: missing session_id")
        return result

    if not state.activity_store:
        return result

    # Persist transcript_path early — before any dedup or batch logic.
    # In a dual-fire scenario (e.g. Claude cloud hooks fire first without
    # transcript_path, then Cursor/VS Code local hooks fire with it), the
    # second fire may not find an active batch.  Storing the path here
    # ensures it is always captured for future recovery.
    if transcript_path:
        try:
            state.activity_store.update_session_transcript_path(session_id, transcript_path)
        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"[STOP] Failed to store transcript_path: {e}")

    # Flush any buffered activities before ending the batch
    try:
        flushed_ids = state.activity_store.flush_activity_buffer()
        if flushed_ids:
            logger.debug(f"Flushed {len(flushed_ids)} buffered activities before batch end")
    except HOOK_STORE_EXCEPTIONS as e:
        logger.debug(f"Failed to flush activity buffer: {e}")

    state.record_hook_activity()

    # End current prompt batch and queue for processing (get batch from SQLite)
    active_batch = state.activity_store.get_active_prompt_batch(session_id)
    prompt_batch_id = active_batch.id if active_batch else None
    if prompt_batch_id:
        dedupe_key = build_dedupe_key(
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
            response_summary = _extract_response_summary(transcript_path, body)

            # Heuristic plan detection: check if response matches plan patterns
            # This is the 4th detection mechanism, only runs if no deterministic
            # mechanism already promoted the batch to plan.
            if response_summary and active_batch and active_batch.source_type != PROMPT_SOURCE_PLAN:
                _try_promote_to_plan(
                    state, prompt_batch_id, response_summary, transcript_path, body, agent
                )

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
            logger.info(
                "[STOP] Ended prompt batch %s (has_summary=%s)",
                prompt_batch_id,
                response_summary is not None,
            )

            # Note: batch status is tracked in SQLite, no in-memory cleanup needed

        except HOOK_STORE_EXCEPTIONS as e:
            logger.warning(f"Failed to end prompt batch: {e}")

    elif transcript_path or body.get("response_summary"):
        # -----------------------------------------------------------
        # Dual-fire late arrival: the first stop (e.g. --agent claude)
        # already finalized the active batch, so no active batch exists.
        # The second stop (e.g. --agent cursor) carries the transcript.
        # Find the just-completed batch and backfill its response.
        # -----------------------------------------------------------
        try:
            response_summary = _extract_response_summary(transcript_path, body)
            if response_summary:
                recent_batch = state.activity_store.get_latest_prompt_batch(session_id)
                if recent_batch and recent_batch.id:
                    # Only backfill if the batch has no response yet
                    if not recent_batch.response_summary:
                        state.activity_store.update_prompt_batch_response(
                            recent_batch.id, response_summary
                        )
                        logger.info(
                            "[STOP] Late transcript capture: updated batch %s with response (%d chars)",
                            recent_batch.id,
                            len(response_summary),
                        )
                        result["prompt_batch_id"] = recent_batch.id
                        result["late_capture"] = True

                        # Also run plan detection on the backfilled response
                        if recent_batch.source_type != PROMPT_SOURCE_PLAN:
                            _try_promote_to_plan(
                                state,
                                recent_batch.id,
                                response_summary,
                                transcript_path,
                                body,
                                agent,
                            )
                    else:
                        logger.debug(
                            "[STOP] Batch %s already has response, skipping late capture",
                            recent_batch.id,
                        )
        except HOOK_STORE_EXCEPTIONS as e:
            logger.warning(f"[STOP] Failed to capture late transcript: {e}")

    return result


def _extract_response_summary(transcript_path: str, body: dict) -> str | None:
    """Extract response summary from transcript file or request body.

    Tries transcript_path first (Claude, Cursor, VS Code Copilot), then
    falls back to the ``response_summary`` field in the body (Gemini,
    Windsurf, OpenCode).
    """
    response_summary = None

    if transcript_path:
        from open_agent_kit.features.codebase_intelligence.transcript import (
            parse_transcript_response,
        )

        response_summary = parse_transcript_response(transcript_path)
        logger.debug(
            "[STOP] Parsed transcript: path=%s summary_len=%s preview=%s",
            transcript_path,
            len(response_summary) if response_summary else 0,
            response_summary[:80] if response_summary else "(none)",
        )

    # Fallback: accept response_summary directly from body
    # (for agents that provide the summary inline instead of via transcript)
    if not response_summary:
        body_summary = body.get("response_summary", "")
        if body_summary:
            response_summary = body_summary[:RESPONSE_SUMMARY_MAX_LENGTH]
            logger.debug(
                "[STOP] Using body response_summary (%d chars)",
                len(response_summary),
            )

    if not response_summary:
        logger.debug("[STOP] No response_summary available")

    return response_summary


def _try_promote_to_plan(
    state: Any,
    batch_id: int,
    response_summary: str,
    transcript_path: str,
    body: dict,
    agent: str,
) -> None:
    """Check if a response looks like a plan and promote the batch if so."""
    from open_agent_kit.features.codebase_intelligence.plan_detector import (
        detect_plan_in_response,
    )

    if not detect_plan_in_response(response_summary, agent):
        return

    logger.info(
        "[STOP] Heuristic plan detected in response for batch %s (agent=%s)",
        batch_id,
        agent,
    )
    # Re-fetch the full response at PLAN_CONTENT_MAX_LENGTH.
    # response_summary is capped at RESPONSE_SUMMARY_MAX_LENGTH (5K)
    # which is too short for plans. Re-parse from transcript or body
    # at the higher limit to capture the complete plan.
    from open_agent_kit.features.codebase_intelligence.constants import (
        PLAN_CONTENT_MAX_LENGTH,
    )
    from open_agent_kit.features.codebase_intelligence.transcript import (
        parse_transcript_response,
    )

    full_plan_content = None
    if transcript_path:
        full_plan_content = parse_transcript_response(
            transcript_path, max_length=PLAN_CONTENT_MAX_LENGTH
        )
    if not full_plan_content:
        body_summary = body.get("response_summary", "")
        if body_summary:
            full_plan_content = body_summary[:PLAN_CONTENT_MAX_LENGTH]
    # Fall back to the (truncated) response_summary if re-fetch failed
    plan_content = full_plan_content or response_summary

    try:
        state.activity_store.update_prompt_batch_source_type(
            batch_id,
            PROMPT_SOURCE_PLAN,
            plan_content=plan_content,
        )
    except HOOK_STORE_EXCEPTIONS as e:
        logger.debug(f"[STOP] Failed to promote batch to plan: {e}")


# =============================================================================
# Subagent handlers
# =============================================================================


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
    agent_type = body.get(HOOK_FIELD_AGENT_TYPE, AGENT_UNKNOWN)
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped subagent-start: missing session_id")
        return {"status": "ok"}

    # Dedupe by agent_id
    if agent_id:
        dedupe_key = build_dedupe_key(
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

    # VS Code Copilot gives each subagent its own session_id, unlike Claude Code
    # where subagents share the parent's session_id.  When a SubagentStart arrives
    # with an unknown session_id, find the parent session and pre-create the
    # subagent session with parent_session_id linked.
    #
    # Parent detection strategy (handles concurrent sessions):
    #   1. Filter by same agent type (vscode-copilot subagent -> vscode-copilot parent)
    #   2. Use most recent tool activity, not session start time -- the parent will
    #      have had a PreToolUse just moments before SubagentStart fires
    #   3. Fall back to most recently started session of the same agent if no
    #      activity data matches
    if state.activity_store and state.project_root and session_id:
        agent_name = body.get(HOOK_FIELD_AGENT, AGENT_UNKNOWN)
        existing = state.activity_store.get_session(session_id)
        if not existing:
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store import sessions

                parent_id = sessions.find_active_parent_for_subagent(
                    state.activity_store,
                    subagent_session_id=session_id,
                    agent=agent_name,
                )

                sessions.create_session(
                    state.activity_store,
                    session_id=session_id,
                    agent=agent_name,
                    project_root=str(state.project_root),
                    parent_session_id=parent_id,
                    parent_session_reason="subagent",
                )
                logger.info(
                    f"[SUBAGENT-START] Created session {session_id[:8]} "
                    f"with parent={parent_id[:8] if parent_id else 'none'}"
                )
            except HOOK_STORE_EXCEPTIONS as e:
                logger.debug(f"Failed to pre-create subagent session: {e}")

    # Store as activity to track subagent spawn
    if state.activity_store and session_id:
        try:
            from open_agent_kit.features.codebase_intelligence.activity import Activity

            prompt_batch_id = get_active_batch_id(state.activity_store, session_id)

            activity = Activity(
                session_id=session_id,
                prompt_batch_id=prompt_batch_id,
                tool_name="SubagentStart",
                tool_input={"agent_id": agent_id, "agent_type": agent_type},
                tool_output_summary=f"Started subagent: {agent_type}",
                success=True,
            )
            state.activity_store.add_activity_buffered(activity)
            state.record_hook_activity()
            logger.debug(f"Stored subagent-start: {agent_type} (batch={prompt_batch_id})")

        except HOOK_STORE_EXCEPTIONS as e:
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
    agent_type = body.get(HOOK_FIELD_AGENT_TYPE, AGENT_UNKNOWN)
    agent_transcript_path = body.get(HOOK_FIELD_AGENT_TRANSCRIPT_PATH, "")
    stop_hook_active = body.get(HOOK_FIELD_STOP_HOOK_ACTIVE, False)
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped subagent-stop: missing session_id")
        return {"status": "ok"}

    # Dedupe by agent_id
    if agent_id:
        dedupe_key = build_dedupe_key(
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

            prompt_batch_id = get_active_batch_id(state.activity_store, session_id)

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
            state.record_hook_activity()
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

        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"Failed to store subagent-stop: {e}")

    return {
        "status": "ok",
        "agent_id": agent_id,
        "agent_type": agent_type,
        "transcript_path": agent_transcript_path,
    }


# =============================================================================
# Agent thought handler
# =============================================================================


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
    thought_hash = hash_value(thought_text[:500])  # Hash first 500 chars
    dedupe_parts = [generation_id, thought_hash] if generation_id else [thought_hash]
    dedupe_key = build_dedupe_key(HOOK_EVENT_AGENT_THOUGHT, session_id, dedupe_parts)
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

            prompt_batch_id = get_active_batch_id(state.activity_store, session_id)

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
            state.record_hook_activity()
            logger.debug(
                f"Stored agent-thought: {len(thought_text)} chars (batch={prompt_batch_id})"
            )

        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"Failed to store agent-thought: {e}")

    return {"status": "ok", "thought_length": len(thought_text), "duration_ms": duration_ms}


# =============================================================================
# Pre-compact handler
# =============================================================================


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
    dedupe_key = build_dedupe_key(HOOK_EVENT_PRE_COMPACT, session_id, dedupe_parts)
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

            prompt_batch_id = get_active_batch_id(state.activity_store, session_id)

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
            state.record_hook_activity()
            logger.debug(
                f"Stored pre-compact: {context_usage_percent}% usage (batch={prompt_batch_id})"
            )

        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"Failed to store pre-compact: {e}")

    return {
        "status": "ok",
        "trigger": trigger,
        "context_usage_percent": context_usage_percent,
    }


# =============================================================================
# Generic catch-all handler
# =============================================================================


@router.post(f"{OAK_CI_PREFIX}/{{event}}")
async def handle_hook_generic(event: str) -> dict:
    """Handle other hook events."""
    logger.info(f"Hook event: {event}")
    return {"status": "ok", "event": event}
