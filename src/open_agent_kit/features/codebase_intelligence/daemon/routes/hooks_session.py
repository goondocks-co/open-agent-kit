"""Session hook handlers: session-start, session-end.

These handlers manage session lifecycle -- creating/resuming sessions,
injecting context, finalizing batches, and generating summaries.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request

from open_agent_kit.features.codebase_intelligence.constants import (
    HOOK_DEDUP_CACHE_MAX,
    HOOK_DROP_LOG_TAG,
    HOOK_EVENT_SESSION_END,
    HOOK_EVENT_SESSION_START,
    HOOK_FIELD_CONVERSATION_ID,
    HOOK_FIELD_SESSION_ID,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_common import (
    HOOK_STORE_EXCEPTIONS,
    OAK_CI_PREFIX,
    build_dedupe_key,
    get_continuation_label,
    get_continuation_sources,
    hooks_logger,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
    build_session_context,
    format_hook_output,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hooks"])


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

    dedupe_key = build_dedupe_key(
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
    # Parent linking: prefer explicit parent_session_id from body, fall back to heuristic
    parent_session_id = body.get("parent_session_id") or None
    parent_session_reason = None

    if parent_session_id:
        parent_session_reason = source  # e.g., "resume", "clear"
        hooks_logger.info(
            f"[SESSION-LINK] session={session_id} parent={parent_session_id[:8]}... "
            f"reason={parent_session_reason} (explicit)"
        )

    if state.activity_store and state.project_root:
        # When source="clear" and no explicit parent, find one heuristically:
        # 1. Session that just ended (within SESSION_LINK_IMMEDIATE_GAP_SECONDS) - normal flow
        # 2. Active session (race condition - SessionEnd not processed yet)
        # 3. Most recent completed session within SESSION_LINK_FALLBACK_MAX_HOURS (stale/next-day)
        if source == "clear" and not parent_session_id:
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
                        f"reason={parent_session_reason} (heuristic)"
                    )
            except HOOK_STORE_EXCEPTIONS as e:
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
                    except HOOK_STORE_EXCEPTIONS as e:
                        logger.debug(f"Failed to update session parent: {e}")

                # For continuation sources, create a batch immediately
                # Agents may start executing tools before UserPromptSubmit fires
                # Use manifest configuration to determine which sources trigger this
                continuation_sources = get_continuation_sources(agent)

                if source in continuation_sources:
                    try:
                        batch_label = get_continuation_label(source)
                        batch = state.activity_store.create_prompt_batch(
                            session_id=session_id,
                            user_prompt=batch_label,
                            source_type="system",
                        )
                        if batch:
                            hooks_logger.info(
                                f"[BATCH-CREATE-CONTINUATION] batch={batch.id} "
                                f"session={session_id} source={source} agent={agent}"
                            )
                    except HOOK_STORE_EXCEPTIONS as e:
                        logger.warning(f"Failed to create continuation batch: {e}")
            else:
                logger.debug(f"Resumed activity session: {session_id}")
        except HOOK_STORE_EXCEPTIONS as e:
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

    hook_event_name = body.get("hook_event_name", "SessionStart")
    response = {"status": "ok", "session_id": session_id, "context": context}
    response["hook_output"] = format_hook_output(response, agent, hook_event_name)
    return response


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
        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"Failed to flush activity buffer on session end: {e}")

    result: dict[str, Any] = {"status": "ok"}
    if not session_id:
        return result

    dedupe_key = build_dedupe_key(HOOK_EVENT_SESSION_END, session_id, [])
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

        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"Failed to end final prompt batch: {e}")

    # Ensure transcript_path is stored (fallback if Stop hook didn't provide it)
    if state.activity_store and session_id:
        try:
            db_session = state.activity_store.get_session(session_id)
            if db_session and not getattr(db_session, "transcript_path", None):
                from open_agent_kit.features.codebase_intelligence.transcript_resolver import (
                    resolve_transcript_path,
                )

                resolved = resolve_transcript_path(session_id, agent, db_session.project_root)
                if resolved and resolved.exists():
                    state.activity_store.update_session_transcript_path(session_id, str(resolved))
                    logger.debug(f"[SESSION-END] Resolved transcript_path fallback: {resolved}")
        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"[SESSION-END] Transcript resolution fallback failed: {e}")

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

            # Generate session summary and title in background
            if state.activity_processor:
                processor = state.activity_processor
                sid = session_id

                async def _generate_session_summary_and_title() -> None:
                    try:
                        loop = asyncio.get_event_loop()
                        summary, title = await loop.run_in_executor(
                            None,
                            processor.process_session_summary_with_title,
                            sid,
                            True,  # regenerate_title from summary for better accuracy
                        )
                        if summary:
                            logger.info(f"Session summary generated: {summary[:80]}...")
                        if title:
                            logger.info(f"Session title generated: {title}")
                    except (RuntimeError, OSError, ValueError) as e:
                        logger.warning(f"Session summary/title generation error: {e}")

                asyncio.create_task(_generate_session_summary_and_title())

        except HOOK_STORE_EXCEPTIONS as e:
            logger.warning(f"Failed to end activity session: {e}")

    # Session stats come from activity_stats (SQLite) - no in-memory tracking
    result["duration_minutes"] = round(duration_minutes, 1)

    return result
