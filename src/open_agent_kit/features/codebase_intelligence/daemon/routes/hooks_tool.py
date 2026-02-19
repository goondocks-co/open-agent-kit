"""Tool-use hook handlers: pre-tool-use, post-tool-use, post-tool-use-failure.

These handlers track tool invocations and their results, store activities
in SQLite for background processing, and inject relevant file context.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from open_agent_kit.features.codebase_intelligence.constants import (
    BATCH_LABEL_SESSION_CONTINUATION,
    BATCH_REACTIVATION_TIMEOUT_SECONDS,
    HOOK_DEDUP_CACHE_MAX,
    HOOK_DROP_LOG_TAG,
    HOOK_EVENT_POST_TOOL_USE,
    HOOK_EVENT_POST_TOOL_USE_FAILURE,
    HOOK_EVENT_PRE_TOOL_USE,
    HOOK_FIELD_CONVERSATION_ID,
    HOOK_FIELD_ERROR_MESSAGE,
    HOOK_FIELD_HOOK_ORIGIN,
    HOOK_FIELD_SESSION_ID,
    HOOK_FIELD_TOOL_INPUT,
    HOOK_FIELD_TOOL_NAME,
    HOOK_FIELD_TOOL_OUTPUT_B64,
    HOOK_FIELD_TOOL_USE_ID,
    PROMPT_SOURCE_PLAN,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_common import (
    HOOK_STORE_EXCEPTIONS,
    OAK_CI_PREFIX,
    build_dedupe_key,
    get_active_batch_id,
    hash_value,
    hooks_logger,
    is_exit_plan_tool,
    normalize_file_path,
    parse_tool_output,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
    build_rich_search_query,
    format_hook_output,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.plan_detector import detect_plan
from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hooks"])


@router.post(f"{OAK_CI_PREFIX}/pre-tool-use")
async def hook_pre_tool_use(request: Request) -> dict:
    """Handle pre-tool-use - track tool invocations before execution.

    This is called before a tool is executed. We store the activity for tracking
    but make no permission decisions (always returns ok).
    """
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in pre-tool-use")
        body = {}

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    agent = body.get("agent", "unknown")
    tool_name = body.get(HOOK_FIELD_TOOL_NAME, "")
    hook_origin = body.get(HOOK_FIELD_HOOK_ORIGIN, "")
    tool_use_id = body.get(HOOK_FIELD_TOOL_USE_ID, "")

    if not session_id:
        logger.info(f"{HOOK_DROP_LOG_TAG} Dropped pre-tool-use: missing session_id")
        return {"status": "ok", "context": {}}

    # Dedupe by tool_use_id (same pattern as post-tool-use)
    if tool_use_id:
        dedupe_key = build_dedupe_key(
            HOOK_EVENT_PRE_TOOL_USE,
            session_id,
            [tool_use_id],
        )
        if state.should_dedupe_hook_event(dedupe_key, HOOK_DEDUP_CACHE_MAX):
            logger.debug(
                "Deduped pre-tool-use session=%s origin=%s token=%s",
                session_id,
                hook_origin,
                tool_use_id,
            )
            return {"status": "ok", "context": {}}

    # Handle tool_input - could be dict (from JSON) or string
    tool_input = body.get(HOOK_FIELD_TOOL_INPUT, {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (ValueError, json.JSONDecodeError):
            tool_input = {"raw": tool_input}
    elif tool_input is None:
        tool_input = {}

    # Lifecycle logging to dedicated hooks.log
    hooks_logger.info(f"[PRE-TOOL-USE] {tool_name} session={session_id}")
    state.record_hook_activity()

    hook_event_name = body.get("hook_event_name", "PreToolUse")
    result: dict[str, Any] = {"status": "ok", "context": {}}
    result["hook_output"] = format_hook_output(result, agent, hook_event_name)

    # --- Governance evaluation ---
    engine = state.governance_engine
    if engine is not None:
        import time as _time

        t0 = _time.monotonic()
        governance_decision = engine.evaluate(tool_name, tool_input)
        eval_ms = int((_time.monotonic() - t0) * 1000)

        # Record audit event (fire-and-forget)
        if state.activity_store:
            try:
                from open_agent_kit.features.codebase_intelligence.governance.audit import (
                    GovernanceAuditWriter,
                )

                writer = GovernanceAuditWriter(state.activity_store)
                input_summary = json.dumps(tool_input, default=str)[:500]
                writer.record(
                    session_id=session_id,
                    agent=agent,
                    tool_name=tool_name,
                    tool_use_id=tool_use_id,
                    decision=governance_decision,
                    enforcement_mode=engine._config.enforcement_mode,
                    evaluation_ms=eval_ms,
                    tool_input_summary=input_summary,
                )
            except HOOK_STORE_EXCEPTIONS as e:
                logger.debug("Failed to record governance audit: %s", e)

        # Merge deny fields into hook_output (governance module owns the format)
        from open_agent_kit.features.codebase_intelligence.governance.output import (
            apply_governance_decision,
        )

        result["hook_output"] = apply_governance_decision(
            result["hook_output"],
            governance_decision,
            agent,
            hook_event_name,
        )

    return result


@router.post(f"{OAK_CI_PREFIX}/post-tool-use")
async def hook_post_tool_use(request: Request) -> dict:
    """Handle post-tool-use - auto-capture observations from tool output."""
    state = get_state()

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON body in post-tool-use")
        body = {}

    session_id = body.get(HOOK_FIELD_SESSION_ID) or body.get(HOOK_FIELD_CONVERSATION_ID)
    agent = body.get("agent", "unknown")
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
        dedupe_key = build_dedupe_key(
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
        dedupe_token = hash_value(signature)
        dedupe_key = build_dedupe_key(
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
        logger.debug(f"  Agent: {agent}")
        if tool_input:
            try:
                input_str = json.dumps(tool_input, indent=2)
                # Truncate very long inputs
                if len(input_str) > 500:
                    input_str = input_str[:500] + "... (truncated)"
                logger.debug(f"  Tool input:\n{input_str}")
            except (ValueError, TypeError):
                logger.debug(f"  Tool input: {tool_input}")
        if tool_output:
            preview = tool_output[:300].replace("\n", "\\n")
            logger.debug(f"  Tool output preview: {preview}...")

    # Cache active batch once -- reused for both activity storage and context injection.
    # The batch won't change during a single request, so this eliminates a redundant
    # SQLite query on the hottest code path (W4.2).
    cached_active_batch = None
    if state.activity_store and session_id:
        cached_active_batch = state.activity_store.get_active_prompt_batch(session_id)

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
            output_data = parse_tool_output(tool_output)
            if output_data:
                if output_data.get("stderr"):
                    is_error = True
                    error_msg = output_data.get("stderr", "")[:500]

            # Use cached batch lookup (already queried above)
            prompt_batch_id = cached_active_batch.id if cached_active_batch else None
            if prompt_batch_id is None:
                # No active batch - check if there's a recently completed batch we should use
                # This handles cases where stuck batch recovery completed a batch that's
                # still receiving tool activity
                # Use constants for universal behavior (same across all agents)
                try:
                    recent_batches = state.activity_store.get_session_prompt_batches(
                        session_id, limit=1
                    )
                    if recent_batches and BATCH_REACTIVATION_TIMEOUT_SECONDS > 0:
                        last_batch = recent_batches[0]
                        # If the last batch was completed very recently,
                        # reactivate it instead of creating a synthetic batch.
                        # This handles stuck batch recovery marking batches complete
                        # while the agent is still actively working.
                        if last_batch.ended_at and last_batch.id is not None:
                            try:
                                # ended_at is already a datetime from PromptBatch.from_row
                                ended = last_batch.ended_at
                                if ended.tzinfo is None:
                                    ended = ended.replace(tzinfo=UTC)
                                now = datetime.now(UTC)
                                seconds_since_end = (now - ended).total_seconds()

                                if seconds_since_end < BATCH_REACTIVATION_TIMEOUT_SECONDS:
                                    # Reactivate the batch - it was prematurely completed
                                    state.activity_store.reactivate_prompt_batch(last_batch.id)
                                    prompt_batch_id = last_batch.id
                                    logger.info(
                                        f"Reactivated batch {last_batch.id} for session "
                                        f"{session_id} (ended {seconds_since_end:.1f}s ago, "
                                        f"still receiving tool activity)"
                                    )
                                    hooks_logger.info(
                                        f"[BATCH-REACTIVATE] batch={last_batch.id} "
                                        f"session={session_id} seconds_since_end={seconds_since_end:.1f}"
                                    )
                            except (ValueError, TypeError) as e:
                                logger.debug(
                                    f"Failed to parse ended_at for batch reactivation: {e}"
                                )

                    # If we still don't have a batch, create a synthetic one
                    # This is for edge cases where no recent batch exists
                    if prompt_batch_id is None:
                        session = state.activity_store.get_session(session_id)
                        if session:
                            batch = state.activity_store.create_prompt_batch(
                                session_id=session_id,
                                user_prompt=BATCH_LABEL_SESSION_CONTINUATION,
                                source_type="system",
                            )
                            if batch:
                                prompt_batch_id = batch.id
                                logger.info(
                                    f"Created synthetic batch {batch.id} for session "
                                    f"{session_id} (no active batch found during tool use)"
                                )
                                hooks_logger.info(
                                    f"[BATCH-CREATE-SYNTHETIC] batch={batch.id} "
                                    f"session={session_id} trigger=post-tool-use"
                                )
                except HOOK_STORE_EXCEPTIONS as e:
                    logger.warning(f"Failed to handle missing batch: {e}")

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
            state.record_hook_activity()
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

                        # Consolidate plan iterations: if this session already has
                        # a plan batch for the same file, update that batch's content
                        # instead of tagging a new one. This prevents duplicate plan
                        # entries when Claude iterates on a plan (same file, multiple
                        # writes). The activity/prompt batches for iteration turns
                        # still exist — they just aren't tagged as plans.
                        existing_plan = (
                            state.activity_store.get_session_plan_batch(
                                session_id, plan_file_path=file_path
                            )
                            if session_id
                            else None
                        )

                        if existing_plan and existing_plan.id:
                            # Update existing plan batch with latest content
                            target_batch_id = existing_plan.id
                            state.activity_store.update_prompt_batch_source_type(
                                target_batch_id,
                                PROMPT_SOURCE_PLAN,
                                plan_file_path=file_path,
                                plan_content=plan_content,
                            )
                            # Re-embed with updated content
                            state.activity_store.mark_plan_unembedded(target_batch_id)
                            location = "global" if detection.is_global else "project"
                            content_len = len(plan_content) if plan_content else 0
                            logger.info(
                                f"Updated existing plan batch {target_batch_id} "
                                f"(iteration of {file_path}, {content_len} chars)"
                            )
                        else:
                            # First plan write in this session for this file
                            target_batch_id = prompt_batch_id
                            state.activity_store.update_prompt_batch_source_type(
                                target_batch_id,
                                PROMPT_SOURCE_PLAN,
                                plan_file_path=file_path,
                                plan_content=plan_content,
                            )
                            location = "global" if detection.is_global else "project"
                            content_len = len(plan_content) if plan_content else 0
                            logger.info(
                                f"Detected {location} plan mode for {detection.agent_type}, "
                                f"batch {target_batch_id} marked as plan with file {file_path} "
                                f"({content_len} chars stored)"
                            )

            # Detect ExitPlanMode: re-read plan file and update stored content
            # Plans iterate during development - the final approved version (when user
            # exits plan mode) may differ from the initial write. Re-reading ensures
            # we capture the final content.
            if is_exit_plan_tool(tool_name) and session_id:
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
                except HOOK_STORE_EXCEPTIONS as e:
                    logger.warning(f"[EXIT-PLAN-MODE] Failed to update plan content: {e}")

            # Detect plan file reads/edits — agents like Cursor create plan files
            # internally (IDE) and use Read/Edit to refine them. This mirrors the
            # Write handler's consolidation pattern: tag the batch with plan metadata
            # and read content from disk (source of truth).
            if tool_name in ("Read", "Edit") and prompt_batch_id:
                file_path = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
                if file_path:
                    detection = detect_plan(file_path)
                    if detection.is_plan:
                        # Read plan content from disk (source of truth)
                        plan_content = ""
                        plan_path = Path(file_path)
                        if not plan_path.is_absolute() and state.project_root:
                            plan_path = state.project_root / plan_path

                        try:
                            if plan_path.exists():
                                plan_content = plan_path.read_text(encoding="utf-8")
                            else:
                                logger.debug(f"Plan file not on disk for {tool_name}: {file_path}")
                        except (OSError, ValueError) as e:
                            logger.warning(f"Failed to read plan file {plan_path}: {e}")

                        # Only tag the batch if we got content from disk
                        if plan_content:
                            # Consolidate: if session already has a plan batch for
                            # this file, update that batch instead of tagging a new one.
                            existing_plan = (
                                state.activity_store.get_session_plan_batch(
                                    session_id, plan_file_path=file_path
                                )
                                if session_id
                                else None
                            )

                            if existing_plan and existing_plan.id:
                                target_batch_id = existing_plan.id
                                state.activity_store.update_prompt_batch_source_type(
                                    target_batch_id,
                                    PROMPT_SOURCE_PLAN,
                                    plan_file_path=file_path,
                                    plan_content=plan_content,
                                )
                                state.activity_store.mark_plan_unembedded(target_batch_id)
                                logger.info(
                                    f"Updated existing plan batch {target_batch_id} "
                                    f"via {tool_name} of {file_path} "
                                    f"({len(plan_content)} chars)"
                                )
                            else:
                                target_batch_id = prompt_batch_id
                                state.activity_store.update_prompt_batch_source_type(
                                    target_batch_id,
                                    PROMPT_SOURCE_PLAN,
                                    plan_file_path=file_path,
                                    plan_content=plan_content,
                                )
                                location = "global" if detection.is_global else "project"
                                logger.info(
                                    f"Detected {location} plan via {tool_name} for "
                                    f"{detection.agent_type}, batch {target_batch_id} "
                                    f"marked as plan with file {file_path} "
                                    f"({len(plan_content)} chars stored)"
                                )

                        hooks_logger.info(
                            f"[PLAN-{tool_name.upper()}] {detection.agent_type} plan "
                            f"{'captured' if plan_content else 'detected'}: {file_path} "
                            f"session={session_id}"
                        )

        except HOOK_STORE_EXCEPTIONS as e:
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
                normalized_path = normalize_file_path(file_path, state.project_root)

                # Get user prompt for richer context from cached active batch
                user_prompt = None
                if cached_active_batch:
                    user_prompt = cached_active_batch.user_prompt

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
                                mem_lines.append(f"\u26a0\ufe0f GOTCHA: {obs}")
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

    hook_event_name = body.get("hook_event_name", "PostToolUse")
    result["hook_output"] = format_hook_output(result, agent, hook_event_name)
    return result


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
        dedupe_key = build_dedupe_key(
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
            prompt_batch_id = get_active_batch_id(state.activity_store, session_id)

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
            state.record_hook_activity()
            logger.debug(f"Stored failed activity: {tool_name} (batch={prompt_batch_id})")

        except HOOK_STORE_EXCEPTIONS as e:
            logger.debug(f"Failed to store failed activity: {e}")

    return {"status": "ok", "tool_name": tool_name, "recorded": True}
