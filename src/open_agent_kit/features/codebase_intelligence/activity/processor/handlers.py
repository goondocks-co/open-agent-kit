"""Batch handlers by source type.

Dispatches processing to appropriate handler based on batch source_type:
- user: Full LLM extraction
- agent_notification: Skip extraction, preserve for analysis
- plan: Extract plan file as decision memory
- system: Skip extraction
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.activity.processor.models import (
    ContextBudget,
    ProcessingResult,
)
from open_agent_kit.features.codebase_intelligence.activity.prompts import (
    render_prompt,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    PROMPT_SOURCE_AGENT,
    PROMPT_SOURCE_DERIVED_PLAN,
    PROMPT_SOURCE_PLAN,
    PROMPT_SOURCE_SYSTEM,
    PROMPT_SOURCE_USER,
)
from open_agent_kit.features.codebase_intelligence.plan_detector import detect_plan

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.prompts import (
        PromptTemplateConfig,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        Activity,
        ActivityStore,
        PromptBatch,
    )
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


def get_batch_handler(
    source_type: str,
) -> Callable[..., ProcessingResult]:
    """Get the appropriate handler for a batch source type.

    Uses a dispatch pattern for extensibility - new source types
    just need a new handler method.

    Args:
        source_type: The batch's source type (user, agent_notification, plan, system, derived_plan).

    Returns:
        Handler function for the source type.
    """
    handlers: dict[str, Callable[..., ProcessingResult]] = {
        PROMPT_SOURCE_USER: process_user_batch,
        PROMPT_SOURCE_AGENT: process_agent_batch,
        PROMPT_SOURCE_PLAN: process_plan_batch,
        PROMPT_SOURCE_SYSTEM: process_system_batch,
        PROMPT_SOURCE_DERIVED_PLAN: process_derived_plan_batch,
    }
    return handlers.get(source_type, process_user_batch)


def process_agent_batch(
    batch_id: int,
    batch: "PromptBatch",
    activities: list["Activity"],
    start_time: datetime,
    activity_store: "ActivityStore",
    **kwargs: Any,
) -> ProcessingResult:
    """Skip memory extraction for agent notifications but preserve activities.

    Background agent work (task notifications) is captured for audit/analysis
    but doesn't pollute the memory store with auto-extracted observations.

    Args:
        batch_id: Prompt batch ID.
        batch: The prompt batch object.
        activities: Activities in this batch.
        start_time: When processing started.
        activity_store: Activity store.
        **kwargs: Additional arguments (ignored).

    Returns:
        ProcessingResult with no observations extracted.
    """
    logger.info(
        f"Skipping memory extraction for agent batch {batch_id}",
        extra={"batch_id": batch_id, "source_type": PROMPT_SOURCE_AGENT},
    )

    # Mark activities as processed (they're still stored for analysis)
    activity_ids = [a.id for a in activities if a.id is not None]
    if activity_ids:
        activity_store.mark_activities_processed(activity_ids)

    # Mark batch as processed with agent_work classification
    activity_store.mark_prompt_batch_processed(batch_id, classification="agent_work")

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    return ProcessingResult(
        session_id=batch.session_id,
        activities_processed=len(activities),
        observations_extracted=0,
        success=True,
        duration_ms=duration_ms,
        classification="agent_work",
        prompt_batch_id=batch_id,
    )


def process_system_batch(
    batch_id: int,
    batch: "PromptBatch",
    activities: list["Activity"],
    start_time: datetime,
    activity_store: "ActivityStore",
    **kwargs: Any,
) -> ProcessingResult:
    """Skip memory extraction for system messages.

    System messages are internal to the agent and don't contain
    user-relevant learnings.

    Args:
        batch_id: Prompt batch ID.
        batch: The prompt batch object.
        activities: Activities in this batch.
        start_time: When processing started.
        activity_store: Activity store.
        **kwargs: Additional arguments (ignored).

    Returns:
        ProcessingResult with no observations extracted.
    """
    logger.info(
        f"Skipping memory extraction for system batch {batch_id}",
        extra={"batch_id": batch_id, "source_type": PROMPT_SOURCE_SYSTEM},
    )

    # Mark activities as processed
    activity_ids = [a.id for a in activities if a.id is not None]
    if activity_ids:
        activity_store.mark_activities_processed(activity_ids)

    # Mark batch as processed
    activity_store.mark_prompt_batch_processed(batch_id, classification="system")

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    return ProcessingResult(
        session_id=batch.session_id,
        activities_processed=len(activities),
        observations_extracted=0,
        success=True,
        duration_ms=duration_ms,
        classification="system",
        prompt_batch_id=batch_id,
    )


def process_derived_plan_batch(
    batch_id: int,
    batch: "PromptBatch",
    activities: list["Activity"],
    start_time: datetime,
    activity_store: "ActivityStore",
    **kwargs: Any,
) -> ProcessingResult:
    """Process a derived plan batch - already has synthesized plan content.

    Derived plans are created when a batch has TaskCreate activities but
    no explicit plan file. The plan content is already synthesized and stored
    by the plan_synthesis module.

    Args:
        batch_id: Prompt batch ID.
        batch: The prompt batch object.
        activities: Activities in this batch.
        start_time: When processing started.
        activity_store: Activity store.
        **kwargs: Additional arguments (ignored).

    Returns:
        ProcessingResult indicating batch was processed.
    """
    # Mark activities as processed
    activity_ids = [a.id for a in activities if a.id is not None]
    if activity_ids:
        activity_store.mark_activities_processed(activity_ids)

    # Mark batch as processed
    activity_store.mark_prompt_batch_processed(batch_id, classification="derived_plan")

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    logger.info(
        f"Processed derived plan batch {batch_id}: {len(activities)} activities "
        f"(plan content already stored) ({duration_ms}ms)",
        extra={"batch_id": batch_id, "source_type": PROMPT_SOURCE_DERIVED_PLAN},
    )

    return ProcessingResult(
        session_id=batch.session_id,
        activities_processed=len(activities),
        observations_extracted=0,
        success=True,
        duration_ms=duration_ms,
        classification="derived_plan",
        prompt_batch_id=batch_id,
    )


def process_plan_batch(
    batch_id: int,
    batch: "PromptBatch",
    activities: list["Activity"],
    start_time: datetime,
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    **kwargs: Any,
) -> ProcessingResult:
    """Process a plan batch - mark activities as processed.

    Plan indexing for semantic search is handled separately by index_pending_plans()
    in indexing.py, which reads plan_content from prompt_batches and indexes with
    memory_type='plan'. This handler only marks activities as processed to avoid
    duplicate memory entries.

    Args:
        batch_id: Prompt batch ID.
        batch: The prompt batch object.
        activities: Activities in this batch.
        start_time: When processing started.
        activity_store: Activity store.
        vector_store: Vector store (unused, kept for interface compatibility).
        **kwargs: Additional arguments (ignored).

    Returns:
        ProcessingResult indicating batch was processed.
    """
    # Find Write activities to any agent's plans directory (for logging)
    plan_path = None
    detected_agent = None
    for activity in activities:
        if activity.tool_name == "Write" and activity.file_path:
            detection = detect_plan(activity.file_path)
            if detection.is_plan:
                plan_path = activity.file_path
                detected_agent = detection.agent_type

    # Mark activities as processed
    activity_ids = [a.id for a in activities if a.id is not None]
    if activity_ids:
        activity_store.mark_activities_processed(activity_ids)

    # Mark batch as processed
    # Note: Plan indexing happens via index_pending_plans() in the background cycle
    activity_store.mark_prompt_batch_processed(batch_id, classification="plan")

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    logger.info(
        f"Processed plan batch {batch_id}: {len(activities)} activities "
        f"(plan indexing deferred to background cycle) ({duration_ms}ms)",
        extra={
            "batch_id": batch_id,
            "agent_type": detected_agent,
            "plan_path": plan_path,
        },
    )

    return ProcessingResult(
        session_id=batch.session_id,
        activities_processed=len(activities),
        observations_extracted=0,  # Plans indexed separately via index_pending_plans()
        success=True,
        duration_ms=duration_ms,
        classification="plan",
        prompt_batch_id=batch_id,
    )


def process_user_batch(
    batch_id: int,
    batch: "PromptBatch",
    activities: list["Activity"],
    start_time: datetime,
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    prompt_config: "PromptTemplateConfig",
    context_budget: ContextBudget,
    project_root: str | None,
    call_llm: Callable[[str], dict[str, Any]],
    store_observation: Callable[..., str | None],
    classify_session: Callable[..., str],
    select_template_by_classification: Callable[..., Any],
    get_oak_ci_context: Callable[..., str],
    session_origin_type: str | None = None,
) -> ProcessingResult:
    """Process a user-initiated batch with full LLM extraction.

    This is the standard processing path for user prompts - classifies
    the batch type and extracts observations using the appropriate template.

    Also checks for TaskCreate activities and synthesizes a derived plan
    if the batch has significant task planning but no explicit plan file.

    Args:
        batch_id: Prompt batch ID.
        batch: The prompt batch object.
        activities: Activities in this batch.
        start_time: When processing started.
        activity_store: Activity store.
        vector_store: Vector store.
        prompt_config: Prompt template configuration.
        context_budget: Context budget for token limits.
        project_root: Project root for oak ci commands.
        call_llm: Function to call LLM.
        store_observation: Function to store observations.
        classify_session: Function to classify sessions.
        select_template_by_classification: Function to select templates.
        get_oak_ci_context: Function to get oak ci context.

    Returns:
        ProcessingResult with extracted observations.
    """
    # Check if we should synthesize a derived plan from TaskCreate activities
    # This captures implementation intent when no explicit plan file was written
    try:
        from open_agent_kit.features.codebase_intelligence.activity.processor.plan_synthesis import (
            should_synthesize_plan,
            store_derived_plan,
            synthesize_derived_plan,
        )

        if should_synthesize_plan(batch, activities):
            derived_plan = synthesize_derived_plan(batch.session_id, activities)
            if derived_plan and derived_plan.tasks:
                store_derived_plan(activity_store, batch_id, derived_plan)
                logger.info(
                    f"Synthesized derived plan for batch {batch_id}: "
                    f"{len(derived_plan.tasks)} tasks"
                )
                # Continue processing as normal - the derived plan is stored
                # but we still extract observations from the activities
    except (ImportError, RuntimeError, ValueError) as e:
        logger.debug(f"Plan synthesis check failed (non-fatal): {e}")

    # Extract batch statistics
    tool_names = [a.tool_name for a in activities]
    files_read = list({a.file_path for a in activities if a.tool_name == "Read" and a.file_path})
    files_modified = list(
        {a.file_path for a in activities if a.tool_name == "Edit" and a.file_path}
    )
    files_created = list(
        {a.file_path for a in activities if a.tool_name == "Write" and a.file_path}
    )
    errors = [a.error_message for a in activities if a.error_message]

    # Calculate batch duration
    if activities:
        first_ts = activities[0].timestamp
        last_ts = activities[-1].timestamp
        duration_minutes = (last_ts - first_ts).total_seconds() / 60
    else:
        duration_minutes = 0

    # Build activity dicts for prompts
    activity_dicts = [
        {
            "tool_name": a.tool_name,
            "file_path": a.file_path,
            "tool_output_summary": a.tool_output_summary,
            "error_message": a.error_message,
        }
        for a in activities
    ]

    # Stage 1: Classify batch type via LLM
    classification = classify_session(
        activities=activity_dicts,
        tool_names=tool_names,
        files_read=files_read,
        files_modified=files_modified,
        files_created=files_created,
        has_errors=bool(errors),
        duration_minutes=duration_minutes,
        prompt_config=prompt_config,
        call_llm=call_llm,
    )
    logger.info(f"Prompt batch classified as: {classification}")

    # Stage 2: Select prompt based on classification
    template = select_template_by_classification(classification, prompt_config)
    logger.debug(f"Using prompt template: {template.name}")

    # Inject oak ci context for relevant files
    oak_ci_context = get_oak_ci_context(
        files_read=files_read,
        files_modified=files_modified,
        files_created=files_created,
        classification=classification,
        project_root=project_root,
    )

    # Render extraction prompt with dynamic context budget
    budget = context_budget
    prompt = render_prompt(
        template=template,
        activities=activity_dicts,
        session_duration=duration_minutes,
        files_read=files_read,
        files_modified=files_modified,
        files_created=files_created,
        errors=errors,
        max_activities=budget.max_activities,
    )

    # Inject oak ci context and user prompt
    context_parts = []
    if batch.user_prompt:
        prompt_for_llm = batch.user_prompt[: budget.max_user_prompt_chars]
        if len(batch.user_prompt) > budget.max_user_prompt_chars:
            prompt_for_llm += "\n... (prompt truncated for context budget)"
        context_parts.append(f"## User Request\n\n{prompt_for_llm}")
    if oak_ci_context:
        oak_context_trimmed = oak_ci_context[: budget.max_oak_context_chars]
        context_parts.append(f"## Related Code Context\n\n{oak_context_trimmed}")

    if context_parts:
        prompt = f"{prompt}\n\n{''.join(context_parts)}"

    # Call LLM for extraction
    result = call_llm(prompt)

    if not result.get("success"):
        logger.warning(f"LLM extraction failed: {result.get('error')}")
        return ProcessingResult(
            session_id=batch.session_id,
            activities_processed=len(activities),
            observations_extracted=0,
            success=False,
            error=result.get("error"),
            duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            classification=classification,
            prompt_batch_id=batch_id,
        )

    # Store observations (truncated to hard cap)
    from open_agent_kit.features.codebase_intelligence.activity.processor.observation import (
        truncate_observations,
    )

    observations = truncate_observations(result.get("observations", []))
    stored_count = 0

    for obs in observations:
        try:
            obs_id = store_observation(
                session_id=batch.session_id,
                observation=obs,
                activity_store=activity_store,
                vector_store=vector_store,
                classification=classification,
                prompt_batch_id=batch_id,
                project_root=project_root,
                session_origin_type=session_origin_type,
            )
            if obs_id:
                stored_count += 1
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            logger.warning(f"Failed to store observation: {e}")

    # Mark activities as processed
    activity_ids = [a.id for a in activities if a.id is not None]
    if activity_ids:
        activity_store.mark_activities_processed(activity_ids)

    # Mark batch as processed
    activity_store.mark_prompt_batch_processed(batch_id, classification=classification)

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

    logger.info(
        f"Processed prompt batch {batch_id}: {len(activities)} activities → "
        f"{stored_count} observations ({duration_ms}ms, type={classification})"
    )

    return ProcessingResult(
        session_id=batch.session_id,
        activities_processed=len(activities),
        observations_extracted=stored_count,
        success=True,
        duration_ms=duration_ms,
        classification=classification,
        prompt_batch_id=batch_id,
    )
