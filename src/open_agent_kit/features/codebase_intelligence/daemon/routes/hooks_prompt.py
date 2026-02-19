"""Prompt hook handlers: prompt-submit, before-prompt.

These handlers manage prompt lifecycle -- creating prompt batches,
searching for relevant context to inject, and classifying prompt types.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_CURSOR,
    HOOK_DEDUP_CACHE_MAX,
    HOOK_DROP_LOG_TAG,
    HOOK_EVENT_PROMPT_SUBMIT,
    HOOK_FIELD_CONVERSATION_ID,
    HOOK_FIELD_GENERATION_ID,
    HOOK_FIELD_HOOK_ORIGIN,
    HOOK_FIELD_PROMPT,
    HOOK_FIELD_SESSION_ID,
    MEMORY_EMBED_LINE_SEPARATOR,
    PROMPT_SOURCE_PLAN,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_common import (
    HOOK_STORE_EXCEPTIONS,
    OAK_CI_PREFIX,
    build_dedupe_key,
    hash_value,
    hooks_logger,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
    format_code_for_injection,
    format_hook_output,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.prompt_classifier import classify_prompt
from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hooks"])


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

    prompt_hash = hash_value(prompt)

    dedupe_parts = [prompt_hash]
    if generation_id:
        dedupe_parts = [generation_id, prompt_hash]
    dedupe_key = build_dedupe_key(HOOK_EVENT_PROMPT_SUBMIT, session_id, dedupe_parts)
    if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
        logger.debug(
            "Deduped prompt-submit session=%s origin=%s key=%s",
            session_id,
            hook_origin,
            dedupe_key,
        )
        return {"status": "ok", "context": {}}

    logger.debug(f"Prompt submit: {prompt[:50]}...")

    # Ensure session exists for agents without a dedicated sessionStart hook
    # (e.g., Windsurf infers session lifecycle from prompt/response hooks).
    # This is idempotent — a no-op if the session already exists.
    if state.activity_store and state.project_root and session_id:
        try:
            state.activity_store.get_or_create_session(
                session_id=session_id, agent=agent, project_root=str(state.project_root)
            )
        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"Failed to ensure session in prompt-submit: {e}")

    # Create new prompt batch in activity store (SQLite handles all session/batch tracking)
    prompt_batch_id = None
    if state.activity_store and session_id:
        try:
            # End previous prompt batch if exists (query SQLite for active batch)
            active_batch = state.activity_store.get_active_prompt_batch(session_id)
            if active_batch and active_batch.id:
                previous_batch_id = active_batch.id

                # Capture response_summary as fallback if Stop hook didn't fire
                # This happens when user queues a new message while agent is responding
                if not active_batch.response_summary:
                    transcript_path = body.get("transcript_path", "")

                    # If transcript_path not in body, resolve it using TranscriptResolver
                    # Supports all agents with ci.transcript config in their manifests
                    if not transcript_path and session_id:
                        try:
                            from open_agent_kit.features.codebase_intelligence.transcript_resolver import (
                                get_transcript_resolver,
                            )

                            session = state.activity_store.get_session(session_id)
                            if session and session.project_root:
                                resolver = get_transcript_resolver(Path(session.project_root))
                                transcript_result = resolver.resolve(
                                    session_id=session_id,
                                    agent_type=(
                                        session.agent if session.agent != "unknown" else None
                                    ),
                                    project_root=session.project_root,
                                )
                                if transcript_result.path:
                                    transcript_path = str(transcript_result.path)
                                    logger.debug(
                                        f"[FALLBACK] Resolved transcript_path via {transcript_result.agent_type}: {transcript_path}"
                                    )
                        except HOOK_STORE_EXCEPTIONS as e:
                            logger.debug(f"Failed to resolve transcript_path: {e}")

                    if transcript_path:
                        try:
                            from open_agent_kit.features.codebase_intelligence.transcript import (
                                parse_transcript_response,
                            )

                            response_summary = parse_transcript_response(transcript_path)
                            if response_summary:
                                state.activity_store.update_prompt_batch_response(
                                    previous_batch_id, response_summary
                                )
                                logger.debug(
                                    f"[FALLBACK] Captured response_summary for batch {previous_batch_id} "
                                    f"(Stop hook didn't fire)"
                                )
                        except HOOK_STORE_EXCEPTIONS as e:
                            logger.debug(f"Failed to capture fallback response_summary: {e}")

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
                            batch_result = await process_prompt_batch_async(processor, batch_id)
                            if batch_result.success:
                                logger.info(
                                    f"[REALTIME] Processed previous batch {batch_id}: "
                                    f"{batch_result.observations_extracted} observations"
                                )
                            else:
                                logger.warning(
                                    f"[REALTIME] Previous batch {batch_id} failed: {batch_result.error}"
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
            plan_file_path = None
            if source_type == PROMPT_SOURCE_PLAN and classification.matched_prefix:
                # Strip the prefix and any leading whitespace to get the actual plan
                prefix_len = len(classification.matched_prefix)
                plan_content = prompt[prefix_len:].lstrip()
                logger.debug(f"Extracted plan content from prompt ({len(plan_content)} chars)")

            # Resolve plan content from disk when the execution prompt
            # is just instructions and the actual plan is in a file.
            # Delegates to resolve_plan_content() which tries:
            # known_path → candidate → transcript → filesystem.
            if source_type == PROMPT_SOURCE_PLAN and session_id:
                try:
                    from open_agent_kit.features.codebase_intelligence.plan_detector import (
                        resolve_plan_content,
                    )

                    # Get known plan file path from existing batch
                    known_plan_file_path = None
                    existing_plan = state.activity_store.get_session_plan_batch(session_id)
                    if existing_plan and existing_plan.plan_file_path:
                        known_plan_file_path = existing_plan.plan_file_path

                    # Resolve transcript_path (only needed when no known path)
                    transcript_path_for_plan = None
                    if not known_plan_file_path:
                        transcript_path_for_plan = body.get("transcript_path", "") or None
                        if not transcript_path_for_plan:
                            try:
                                from open_agent_kit.features.codebase_intelligence.transcript_resolver import (
                                    get_transcript_resolver,
                                )

                                session = state.activity_store.get_session(session_id)
                                if session and session.project_root:
                                    resolver = get_transcript_resolver(Path(session.project_root))
                                    transcript_result = resolver.resolve(
                                        session_id=session_id,
                                        agent_type=(
                                            session.agent if session.agent != "unknown" else None
                                        ),
                                        project_root=session.project_root,
                                    )
                                    if transcript_result.path:
                                        transcript_path_for_plan = str(transcript_result.path)
                            except HOOK_STORE_EXCEPTIONS as e:
                                logger.debug(f"Failed to resolve transcript_path for plan: {e}")

                    resolution = resolve_plan_content(
                        known_plan_file_path=known_plan_file_path,
                        transcript_path=transcript_path_for_plan,
                        agent_type=classification.agent_type,
                        project_root=state.project_root,
                        min_content_length=500,
                        existing_content_length=(len(plan_content) if plan_content else 0),
                    )
                    if resolution:
                        plan_file_path = resolution.file_path
                        plan_content = resolution.content
                except HOOK_STORE_EXCEPTIONS as e:
                    logger.warning(f"Failed to resolve plan content: {e}")

            # Create new prompt batch with full user prompt and source type
            batch = state.activity_store.create_prompt_batch(
                session_id=session_id,
                user_prompt=prompt,  # Full prompt, truncated to 10K in store
                source_type=source_type,
                plan_file_path=plan_file_path,  # Carry forward from Read/Edit detection
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

        except HOOK_STORE_EXCEPTIONS as e:
            logger.warning(f"Failed to create prompt batch: {e}")

    context: dict[str, Any] = {}
    search_query = prompt
    if state.activity_store:
        session_record = state.activity_store.get_session(session_id)
        if session_record and session_record.title:
            search_query = MEMORY_EMBED_LINE_SEPARATOR.join([session_record.title, prompt])

    # Search for relevant memories and code in a single call (W4.3).
    # Previously this used two separate searches (memory + code), each embedding
    # the query independently. Using search_type="all" embeds once and searches
    # both collections, saving ~5-20ms on the user-facing latency path.
    if state.retrieval_engine:
        try:
            # Debug logging for search queries (trace mode)
            logger.debug(f"[SEARCH:all] query={search_query[:200]}")

            search_result = state.retrieval_engine.search(
                query=search_query,
                search_type="all",
                limit=10,  # Fetch more, filter by confidence
            )

            # Filter memories by combined score (confidence + importance)
            # High threshold ensures only highly relevant AND important memories are injected
            high_confidence_memories = RetrievalEngine.filter_by_combined_score(
                search_result.memory, min_combined="high"
            )
            # For code, stick with confidence-only filtering (no importance metadata)
            high_confidence_code = RetrievalEngine.filter_by_confidence(
                search_result.code, min_confidence="high"
            )

            # Debug logging for search results (trace mode)
            logger.debug(
                f"[SEARCH:all:results] memories={len(search_result.memory)} "
                f"high_combined={len(high_confidence_memories)} "
                f"code={len(search_result.code)} "
                f"high_confidence={len(high_confidence_code)}"
            )
            if search_result.memory:
                scores_preview = [
                    (round(m.get("relevance", 0), 3), m.get("confidence"))
                    for m in search_result.memory[:5]
                ]
                logger.debug(f"[SEARCH:memory:scores] {scores_preview}")

            # Inject code first (appears before memories in context)
            if high_confidence_code:
                code_text = format_code_for_injection(high_confidence_code[:3])
                if code_text:
                    context["injected_context"] = code_text
                    num_code = min(3, len(high_confidence_code))
                    logger.info(f"Injecting {num_code} code chunks for prompt")
                    hooks_logger.info(
                        f"[CONTEXT-INJECT] code={num_code} session={session_id} "
                        f"hook=prompt-submit"
                    )
                    logger.debug(f"[INJECT:prompt-submit-code] Content:\n{code_text}")

            # Inject memories (appended after code if both present)
            if high_confidence_memories:
                mem_lines = []
                for mem in high_confidence_memories[:5]:  # Cap at 5
                    mem_type = mem.get("memory_type", "note")
                    obs = mem.get("observation", "")
                    mem_id = mem.get("id", "")
                    line = f"- [{mem_type}] {obs}"
                    if mem_id:
                        line += f" `[id: {mem_id}]`"
                    mem_lines.append(line)

                if mem_lines:
                    injected_text = "**Relevant memories for this task:**\n" + "\n".join(mem_lines)
                    if "injected_context" in context:
                        context["injected_context"] = (
                            f"{context['injected_context']}\n\n{injected_text}"
                        )
                    else:
                        context["injected_context"] = injected_text
                    num_memories = len(high_confidence_memories[:5])
                    logger.info(f"Injecting {num_memories} high-confidence memories for prompt")
                    hooks_logger.info(
                        f"[CONTEXT-INJECT] memories={num_memories} session={session_id} "
                        f"hook=prompt-submit"
                    )
                    logger.debug(f"[INJECT:prompt-submit] Content:\n{injected_text}")

        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.debug(f"Failed to search for prompt context: {e}")

    hook_event_name = body.get("hook_event_name", "UserPromptSubmit")
    response = {"status": "ok", "context": context, "prompt_batch_id": prompt_batch_id}
    if agent == AGENT_CURSOR:
        response["hook_output"] = {"continue": True}
    else:
        response["hook_output"] = format_hook_output(response, agent, hook_event_name)
    return response


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

    state.record_hook_activity()

    return {"status": "ok", "context": context}
