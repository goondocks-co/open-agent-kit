"""Core ActivityProcessor class and orchestration.

Main class that coordinates all processing, scheduling, and recovery.
Background phases, scheduling, power management, and async wrappers
live in their own modules -- see background_phases.py, scheduler.py,
power.py, and async_api.py.
"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.team.activity.processor.classification import (
    classify_heuristic,
    classify_session,
    compute_session_origin_type,
    select_template_by_classification,
)
from open_agent_kit.features.team.activity.processor.handlers import (
    get_batch_handler,
    process_user_batch,
)
from open_agent_kit.features.team.activity.processor.indexing import (
    embed_pending_observations,
    index_pending_plans,
    rebuild_chromadb_from_sqlite,
    rebuild_plan_index,
)
from open_agent_kit.features.team.activity.processor.llm import (
    call_llm,
    get_oak_ci_context,
)
from open_agent_kit.features.team.activity.processor.models import (
    ContextBudget,
    ProcessingResult,
)
from open_agent_kit.features.team.activity.processor.observation import (
    store_observation,
)
from open_agent_kit.features.team.activity.processor.summaries import (
    process_session_summary,
)
from open_agent_kit.features.team.activity.processor.titles import (
    generate_pending_titles,
    generate_session_title,
    generate_title_from_summary,
)
from open_agent_kit.features.team.activity.prompts import (
    PromptTemplateConfig,
    render_prompt,
)
from open_agent_kit.features.team.constants import (
    DEFAULT_BACKGROUND_PROCESSING_BATCH_SIZE,
    DEFAULT_BACKGROUND_PROCESSING_WORKERS,
    PROMPT_SOURCE_PLAN,
    PROMPT_SOURCE_USER,
    SESSION_STATUS_ACTIVE,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from open_agent_kit.features.team.activity.store import (
        ActivityStore,
    )
    from open_agent_kit.features.team.config import (
        CIConfig,
        SessionQualityConfig,
        SummarizationConfig,
    )
    from open_agent_kit.features.team.daemon.state import DaemonState
    from open_agent_kit.features.team.memory.store import VectorStore
    from open_agent_kit.features.team.summarization.base import (
        BaseSummarizer,
    )

logger = logging.getLogger(__name__)


class ActivityProcessor:
    """Background processor for activity -> observation extraction.

    Two-stage approach:
    1. LLM classifies session type
    2. Activity-specific prompt with oak ci context injection
    """

    def __init__(
        self,
        activity_store: "ActivityStore",
        vector_store: "VectorStore",
        summarizer: "BaseSummarizer | None" = None,
        prompt_config: PromptTemplateConfig | None = None,
        project_root: str | None = None,
        context_tokens: int = 4096,
        session_quality_config: "SessionQualityConfig | None" = None,
        config_accessor: "Callable[[], CIConfig | None] | None" = None,
    ):
        self.activity_store = activity_store
        self.vector_store = vector_store
        self.prompt_config = prompt_config or PromptTemplateConfig.load_from_directory()
        self.project_root = project_root

        # Config accessor for live config reads (production path).
        # When set, properties below read from it instead of static fallbacks.
        self._config_accessor = config_accessor

        # Static fallbacks (used by tests and when no accessor is provided)
        self._fallback_summarizer = summarizer
        self._fallback_context_budget = ContextBudget.from_context_tokens(context_tokens)
        self._fallback_session_quality_config = session_quality_config

        # Summarizer cache: recreated when config fingerprint changes
        self._cached_summarizer: BaseSummarizer | None = None
        self._summarizer_config_key: tuple[str, str, str, str | None, float, bool] | None = None
        self._summarizer_lock = threading.Lock()

        self._processing_lock = threading.Lock()
        self._is_processing = False
        self._last_process_time: datetime | None = None
        self._pollution_cleanup_done = False

    # ------------------------------------------------------------------
    # Property accessors (live config or static fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def _summarizer_fingerprint(
        sc: "SummarizationConfig",
    ) -> "tuple[str, str, str, str | None, float, bool]":
        """Build a cache key from all fields that affect summarizer construction."""
        return (sc.provider, sc.model, sc.base_url, sc.api_key, sc.timeout, sc.enabled)

    @property
    def summarizer(self) -> "BaseSummarizer | None":
        """Get the current summarizer, recreating if config changed."""
        if self._config_accessor is not None:
            config = self._config_accessor()
            if config is not None:
                sc = config.summarization
                key = self._summarizer_fingerprint(sc)
                if key != self._summarizer_config_key:
                    with self._summarizer_lock:
                        # Double-check after acquiring lock
                        if key != self._summarizer_config_key:
                            if sc.enabled:
                                from open_agent_kit.features.team.summarization import (
                                    create_summarizer_from_config,
                                )

                                self._cached_summarizer = create_summarizer_from_config(sc)
                            else:
                                self._cached_summarizer = None
                            self._summarizer_config_key = key
                return self._cached_summarizer
        return self._fallback_summarizer

    @property
    def context_budget(self) -> ContextBudget:
        """Get context budget from live config or static fallback."""
        if self._config_accessor is not None:
            config = self._config_accessor()
            if config is not None:
                return ContextBudget.from_context_tokens(config.summarization.get_context_tokens())
        return self._fallback_context_budget

    @property
    def session_quality_config(self) -> "SessionQualityConfig | None":
        """Get session quality config from live config or static fallback."""
        if self._config_accessor is not None:
            config = self._config_accessor()
            if config is not None:
                return config.session_quality
        return self._fallback_session_quality_config

    @property
    def processing_workers(self) -> int:
        """Get number of parallel processing workers from live config or constant."""
        if self._config_accessor is not None:
            config = self._config_accessor()
            if config is not None:
                return config.agents.background_processing_workers
        return DEFAULT_BACKGROUND_PROCESSING_WORKERS

    @property
    def min_session_activities(self) -> int:
        """Get minimum activities threshold from config or constant."""
        from open_agent_kit.features.team.constants import (
            MIN_SESSION_ACTIVITIES,
        )

        sqc = self.session_quality_config
        if sqc:
            return sqc.min_activities
        return MIN_SESSION_ACTIVITIES

    @property
    def stale_timeout_seconds(self) -> int:
        """Get stale timeout from config or constant."""
        from open_agent_kit.features.team.constants import (
            SESSION_INACTIVE_TIMEOUT_SECONDS,
        )

        sqc = self.session_quality_config
        if sqc:
            return sqc.stale_timeout_seconds
        return SESSION_INACTIVE_TIMEOUT_SECONDS

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        if not self.summarizer:
            return {"success": False, "error": "No summarizer configured"}
        return call_llm(prompt, self.summarizer, self.context_budget)

    def _classify_session(
        self,
        activities: list[dict[str, Any]],
        tool_names: list[str],
        files_read: list[str],
        files_modified: list[str],
        files_created: list[str],
        has_errors: bool,
        duration_minutes: float,
    ) -> str:
        return classify_session(
            activities=activities,
            tool_names=tool_names,
            files_read=files_read,
            files_modified=files_modified,
            files_created=files_created,
            has_errors=has_errors,
            duration_minutes=duration_minutes,
            prompt_config=self.prompt_config,
            call_llm=self._call_llm,
        )

    def _classify_heuristic(
        self,
        tool_names: list[str],
        has_errors: bool,
        files_modified: list[str],
        files_created: list[str],
    ) -> str:
        return classify_heuristic(tool_names, has_errors, files_modified, files_created)

    def _select_template_by_classification(self, classification: str) -> Any:
        return select_template_by_classification(classification, self.prompt_config)

    def _get_oak_ci_context(
        self,
        files_read: list[str],
        files_modified: list[str],
        files_created: list[str],
        classification: str,
    ) -> str:
        return get_oak_ci_context(
            files_read=files_read,
            files_modified=files_modified,
            files_created=files_created,
            classification=classification,
            project_root=self.project_root,
        )

    def _store_observation(
        self,
        session_id: str,
        observation: dict[str, Any],
        classification: str | None = None,
        prompt_batch_id: int | None = None,
        session_origin_type: str | None = None,
    ) -> str | None:
        auto_resolve_config = None
        if self._config_accessor is not None:
            config = self._config_accessor()
            if config is not None:
                auto_resolve_config = config.auto_resolve
        return store_observation(
            session_id=session_id,
            observation=observation,
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            classification=classification,
            prompt_batch_id=prompt_batch_id,
            project_root=self.project_root,
            session_origin_type=session_origin_type,
            auto_resolve_config=auto_resolve_config,
        )

    # ------------------------------------------------------------------
    # Core processing methods
    # ------------------------------------------------------------------

    def process_session(self, session_id: str) -> ProcessingResult:
        """Process all unprocessed activities for a session."""
        start_time = datetime.now()

        if not self.summarizer:
            logger.warning("No summarizer configured, skipping activity processing")
            return ProcessingResult(
                session_id=session_id,
                activities_processed=0,
                observations_extracted=0,
                success=False,
                error="No summarizer configured",
            )

        # Get unprocessed activities
        activities = self.activity_store.get_unprocessed_activities(session_id=session_id)

        if not activities:
            logger.debug(f"No unprocessed activities for session {session_id}")
            self.activity_store.mark_session_processed(session_id)
            return ProcessingResult(
                session_id=session_id,
                activities_processed=0,
                observations_extracted=0,
                success=True,
            )

        logger.info(f"Processing {len(activities)} activities for session {session_id}")

        try:
            # Extract session statistics
            tool_names = [a.tool_name for a in activities]
            files_read = list(
                {a.file_path for a in activities if a.tool_name == "Read" and a.file_path}
            )
            files_modified = list(
                {a.file_path for a in activities if a.tool_name == "Edit" and a.file_path}
            )
            files_created = list(
                {a.file_path for a in activities if a.tool_name == "Write" and a.file_path}
            )
            errors = [a.error_message for a in activities if a.error_message]

            # Calculate session duration
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

            # Stage 1: Classify session type via LLM
            classification = self._classify_session(
                activities=activity_dicts,
                tool_names=tool_names,
                files_read=files_read,
                files_modified=files_modified,
                files_created=files_created,
                has_errors=bool(errors),
                duration_minutes=duration_minutes,
            )
            logger.info(f"Session classified as: {classification}")

            # Stage 2: Select prompt based on classification
            template = self._select_template_by_classification(classification)
            logger.debug(f"Using prompt template: {template.name}")

            # Inject oak ci context for relevant files
            oak_ci_context = self._get_oak_ci_context(
                files_read=files_read,
                files_modified=files_modified,
                files_created=files_created,
                classification=classification,
            )

            # Render extraction prompt with dynamic context budget
            budget = self.context_budget
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

            # Inject oak ci context into prompt (trimmed to budget)
            if oak_ci_context:
                oak_context_trimmed = oak_ci_context[: budget.max_oak_context_chars]
                prompt = f"{prompt}\n\n## Related Code Context\n\n{oak_context_trimmed}"

            # Call LLM for extraction
            result = self._call_llm(prompt)

            if not result.get("success"):
                logger.warning(f"LLM extraction failed: {result.get('error')}")
                return ProcessingResult(
                    session_id=session_id,
                    activities_processed=len(activities),
                    observations_extracted=0,
                    success=False,
                    error=result.get("error"),
                    duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                    classification=classification,
                )

            # Store observations (truncated to hard cap)
            from open_agent_kit.features.team.activity.processor.observation import (
                truncate_observations,
            )

            observations = truncate_observations(result.get("observations", []))
            stored_count = 0

            for obs in observations:
                try:
                    obs_id = self._store_observation(
                        session_id=session_id,
                        observation=obs,
                        classification=classification,
                    )
                    if obs_id:
                        stored_count += 1
                except (ValueError, KeyError, AttributeError, TypeError) as e:
                    logger.warning(f"Failed to store observation: {e}")

            # Mark activities as processed
            activity_ids = [a.id for a in activities if a.id is not None]
            if activity_ids:
                self.activity_store.mark_activities_processed(activity_ids)

            # Mark session as processed
            self.activity_store.mark_session_processed(session_id)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            logger.info(
                f"Processed session {session_id}: {len(activities)} activities -> "
                f"{stored_count} observations ({duration_ms}ms, type={classification})"
            )

            return ProcessingResult(
                session_id=session_id,
                activities_processed=len(activities),
                observations_extracted=stored_count,
                success=True,
                duration_ms=duration_ms,
                classification=classification,
            )

        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as e:
            logger.error(f"Error processing session {session_id}: {e}", exc_info=True)
            return ProcessingResult(
                session_id=session_id,
                activities_processed=len(activities),
                observations_extracted=0,
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
            )

    def process_prompt_batch(self, batch_id: int) -> ProcessingResult:
        """Process activities for a single prompt batch."""
        start_time = datetime.now()

        batch = self.activity_store.get_prompt_batch(batch_id)
        if not batch:
            return ProcessingResult(
                session_id="",
                activities_processed=0,
                observations_extracted=0,
                success=False,
                error=f"Prompt batch {batch_id} not found",
                prompt_batch_id=batch_id,
            )

        # Get activities for this batch
        activities = self.activity_store.get_prompt_batch_activities(batch_id)

        if not activities:
            logger.debug(f"No activities for prompt batch {batch_id}")
            # Mark as processed even if empty
            self.activity_store.mark_prompt_batch_processed(batch_id)
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=0,
                observations_extracted=0,
                success=True,
                prompt_batch_id=batch_id,
            )

        # Log batch info with source type
        source_type = batch.source_type or PROMPT_SOURCE_USER
        logger.info(
            f"Processing prompt batch {batch_id} (prompt #{batch.prompt_number}, "
            f"source={source_type}): {len(activities)} activities"
        )

        # For user batches, require a summarizer for LLM extraction
        if source_type == PROMPT_SOURCE_USER and not self.summarizer:
            logger.warning("No summarizer configured, skipping prompt batch processing")
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=0,
                observations_extracted=0,
                success=False,
                error="No summarizer configured",
                prompt_batch_id=batch_id,
            )

        try:
            # Clean up any existing observations from a previous processing run.
            # Without this, reprocessing a batch creates NEW observations (new UUIDs)
            # while leaving the old ones in place, causing unbounded duplication.
            old_obs_ids = self.activity_store.delete_batch_observations(batch_id)
            if old_obs_ids:
                try:
                    self.vector_store.delete_memories(old_obs_ids)
                    logger.info(
                        f"Cleaned up {len(old_obs_ids)} old observations for batch {batch_id} "
                        f"before reprocessing"
                    )
                except (ValueError, RuntimeError, KeyError, AttributeError) as e:
                    # SQLite cleanup succeeded; ChromaDB will be stale but not duplicated
                    logger.warning(f"ChromaDB cleanup failed for batch {batch_id}: {e}")

            # Compute session origin type from activity stats
            session_stats = self.activity_store.get_session_stats(batch.session_id)
            all_batches = self.activity_store.get_session_prompt_batches(
                batch.session_id, limit=100
            )
            has_plan_batches = any(
                b.source_type in (PROMPT_SOURCE_PLAN, "derived_plan") for b in all_batches
            )
            session_origin_type = compute_session_origin_type(
                stats=session_stats, has_plan_batches=has_plan_batches
            )

            # Dispatch to appropriate handler based on source type
            handler = get_batch_handler(source_type)

            # Build handler kwargs
            handler_kwargs = {
                "batch_id": batch_id,
                "batch": batch,
                "activities": activities,
                "start_time": start_time,
                "activity_store": self.activity_store,
                "vector_store": self.vector_store,
                "prompt_config": self.prompt_config,
                "context_budget": self.context_budget,
                "project_root": self.project_root,
                "call_llm": self._call_llm,
                "store_observation": store_observation,
                "classify_session": classify_session,
                "select_template_by_classification": select_template_by_classification,
                "get_oak_ci_context": get_oak_ci_context,
                "session_origin_type": session_origin_type,
            }

            return handler(**handler_kwargs)

        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as e:
            logger.error(f"Error processing prompt batch {batch_id}: {e}", exc_info=True)
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=len(activities),
                observations_extracted=0,
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                prompt_batch_id=batch_id,
            )

    def process_pending_batches(
        self, max_batches: int = DEFAULT_BACKGROUND_PROCESSING_BATCH_SIZE
    ) -> list[ProcessingResult]:
        """Process all pending prompt batches."""
        with self._processing_lock:
            if self._is_processing:
                logger.debug("Processing already in progress, skipping")
                return []

            self._is_processing = True

        try:
            batches = self.activity_store.get_unprocessed_prompt_batches(limit=max_batches)

            if not batches:
                logger.debug("No pending prompt batches to process")
                return []

            logger.info(f"Processing {len(batches)} pending prompt batches")

            batch_ids = [b.id for b in batches if b.id is not None]
            workers = min(self.processing_workers, len(batch_ids))

            results = []
            if workers <= 1:
                # Single batch -- no thread pool overhead
                for bid in batch_ids:
                    results.append(self.process_prompt_batch(bid))
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {
                        pool.submit(self.process_prompt_batch, bid): bid for bid in batch_ids
                    }
                    for future in as_completed(futures):
                        try:
                            results.append(future.result())
                        except Exception as e:
                            bid = futures[future]
                            logger.error(f"Batch {bid} failed in thread pool: {e}")
                            results.append(
                                ProcessingResult(
                                    session_id="",
                                    activities_processed=0,
                                    observations_extracted=0,
                                    success=False,
                                    error=str(e),
                                    prompt_batch_id=bid,
                                )
                            )

            self._last_process_time = datetime.now()
            return results

        finally:
            with self._processing_lock:
                self._is_processing = False

    def _process_user_batch(
        self, batch_id: int, batch: Any, activities: list[Any], start_time: datetime
    ) -> ProcessingResult:
        """Wrapper for handlers.process_user_batch. Used by promote_agent_batch."""
        session_stats = self.activity_store.get_session_stats(batch.session_id)
        all_batches = self.activity_store.get_session_prompt_batches(batch.session_id, limit=100)
        has_plan_batches = any(
            b.source_type in (PROMPT_SOURCE_PLAN, "derived_plan") for b in all_batches
        )
        return process_user_batch(
            batch_id=batch_id,
            batch=batch,
            activities=activities,
            start_time=start_time,
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            prompt_config=self.prompt_config,
            context_budget=self.context_budget,
            project_root=self.project_root,
            call_llm=self._call_llm,
            store_observation=store_observation,
            classify_session=classify_session,
            select_template_by_classification=select_template_by_classification,
            get_oak_ci_context=get_oak_ci_context,
            session_origin_type=compute_session_origin_type(
                stats=session_stats, has_plan_batches=has_plan_batches
            ),
        )

    # ------------------------------------------------------------------
    # Title and summary generation
    # ------------------------------------------------------------------

    def generate_session_title(self, session_id: str) -> str | None:
        return generate_session_title(
            session_id=session_id,
            activity_store=self.activity_store,
            prompt_config=self.prompt_config,
            call_llm=self._call_llm,
            min_activities=self.min_session_activities,
        )

    def generate_pending_titles(self, limit: int = 5) -> int:
        return generate_pending_titles(
            activity_store=self.activity_store,
            prompt_config=self.prompt_config,
            call_llm=self._call_llm,
            limit=limit,
            min_activities=self.min_session_activities,
        )

    def process_session_summary_with_title(
        self, session_id: str, regenerate_title: bool = False
    ) -> tuple[str | None, str | None]:
        if not self.summarizer:
            logger.info("Session summary skipped: summarizer not configured")
            return None, None

        def _gen_title(sid: str, summary: str) -> str | None:
            return generate_title_from_summary(
                session_id=sid,
                summary=summary,
                activity_store=self.activity_store,
                prompt_config=self.prompt_config,
                call_llm=self._call_llm,
            )

        return process_session_summary(
            session_id=session_id,
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            prompt_config=self.prompt_config,
            call_llm=self._call_llm,
            generate_title=self.generate_session_title,
            regenerate_title=regenerate_title,
            generate_title_from_summary=_gen_title,
        )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def complete_session(self, session_id: str) -> tuple[str | None, str | None]:
        """Mark an active session as completed and run post-completion processing."""
        session = self.activity_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.status != SESSION_STATUS_ACTIVE:
            raise ValueError(
                f"Session {session_id} is already '{session.status}', only active sessions can be completed"
            )

        # Step 1: Mark as completed -- same SQL path as recover_stale_sessions
        self.activity_store.end_session(session_id)
        logger.info(f"Manually completed session {session_id[:8]}")

        # Step 2: Generate summary -- same path as background job
        summary, title = self.process_session_summary_with_title(session_id, regenerate_title=True)

        # Step 3: Generate title if summary didn't produce one
        if not title:
            count = self.generate_pending_titles()
            if count > 0:
                logger.info(f"Generated {count} pending titles after completing session")
            # Re-fetch to get the title that was generated
            updated = self.activity_store.get_session(session_id)
            if updated and updated.title:
                title = updated.title

        return summary, title

    def process_pending(self, max_sessions: int = 5) -> list[ProcessingResult]:
        """Process all pending sessions."""
        with self._processing_lock:
            if self._is_processing:
                logger.debug("Processing already in progress, skipping")
                return []

            self._is_processing = True

        try:
            sessions = self.activity_store.get_unprocessed_sessions(limit=max_sessions)

            if not sessions:
                logger.debug("No pending sessions to process")
                return []

            logger.info(f"Processing {len(sessions)} pending sessions")

            results = []
            for session in sessions:
                result = self.process_session(session.id)
                results.append(result)

            self._last_process_time = datetime.now()
            return results

        finally:
            with self._processing_lock:
                self._is_processing = False

    # ------------------------------------------------------------------
    # Background processing (delegates to background_phases module)
    # ------------------------------------------------------------------

    def _bg_cleanup_pollution(self) -> None:
        from open_agent_kit.features.team.activity.processor.background_phases import (
            bg_cleanup_pollution as _fn,
        )  # noqa: E501

        _fn(self)

    def _bg_recover_stuck_data(self) -> None:
        from open_agent_kit.features.team.activity.processor.background_phases import (
            bg_recover_stuck_data as _fn,
        )  # noqa: E501

        _fn(self)

    def _bg_recover_stale_sessions(self) -> None:
        from open_agent_kit.features.team.activity.processor.background_phases import (
            bg_recover_stale_sessions as _fn,
        )  # noqa: E501

        _fn(self)

    def _bg_cleanup_and_summarize(self) -> None:
        from open_agent_kit.features.team.activity.processor.background_phases import (
            bg_cleanup_and_summarize as _fn,
        )  # noqa: E501

        _fn(self)

    def _bg_process_pending(self) -> None:
        from open_agent_kit.features.team.activity.processor.background_phases import (
            bg_process_pending as _fn,
        )  # noqa: E501

        _fn(self)

    def _bg_index_and_title(self) -> None:
        from open_agent_kit.features.team.activity.processor.background_phases import (
            bg_index_and_title as _fn,
        )  # noqa: E501

        _fn(self)

    def run_background_cycle(self) -> None:
        """Execute one full background processing cycle (phases 0-5)."""
        self._bg_cleanup_pollution()
        self._bg_recover_stuck_data()
        self._bg_recover_stale_sessions()
        self._bg_cleanup_and_summarize()
        self._bg_process_pending()
        self._bg_index_and_title()

    # ------------------------------------------------------------------
    # Scheduling and power (delegates to scheduler/power modules)
    # ------------------------------------------------------------------

    def schedule_background_processing(
        self,
        interval_seconds: int = 60,
        state_accessor: "Callable[[], DaemonState] | None" = None,
    ) -> threading.Timer:
        """Schedule periodic background processing with power-state awareness."""
        from open_agent_kit.features.team.activity.processor.scheduler import (
            schedule_background_processing as _fn,
        )  # noqa: E501

        return _fn(self, interval_seconds, state_accessor)

    def _evaluate_and_run_cycle(
        self,
        state_accessor: "Callable[[], DaemonState] | None",
        base_interval: int,
    ) -> tuple[str, int]:
        """Evaluate power state, run appropriate phases, return (state, interval)."""
        from open_agent_kit.features.team.activity.processor.scheduler import (
            evaluate_and_run_cycle as _fn,
        )  # noqa: E501

        return _fn(self, state_accessor, base_interval)

    def _on_power_transition(
        self, daemon_state: "DaemonState", old_state: str, new_state: str
    ) -> None:
        from open_agent_kit.features.team.activity.processor.power import (
            on_power_transition as _fn,
        )  # noqa: E501

        _fn(self, daemon_state, old_state, new_state)

    def _trigger_transition_backup(self, daemon_state: "DaemonState") -> None:
        from open_agent_kit.features.team.activity.processor.power import (
            _trigger_transition_backup as _fn,
        )  # noqa: E501

        _fn(self, daemon_state)

    def _trigger_governance_prune(self, daemon_state: "DaemonState") -> None:
        from open_agent_kit.features.team.activity.processor.power import (
            _trigger_governance_prune as _fn,
        )  # noqa: E501

        _fn(self, daemon_state)

    # ------------------------------------------------------------------
    # Indexing and rebuild (delegates to indexing module)
    # ------------------------------------------------------------------

    def rebuild_chromadb_from_sqlite(
        self,
        batch_size: int = 50,
        reset_embedded_flags: bool = True,
        clear_chromadb_first: bool = False,
    ) -> dict[str, int]:
        return rebuild_chromadb_from_sqlite(
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            batch_size=batch_size,
            reset_embedded_flags=reset_embedded_flags,
            clear_chromadb_first=clear_chromadb_first,
        )

    def embed_pending_observations(self, batch_size: int = 50) -> dict[str, int]:
        return embed_pending_observations(
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            batch_size=batch_size,
        )

    def index_pending_plans(self, batch_size: int = 10) -> dict[str, int]:
        return index_pending_plans(
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            batch_size=batch_size,
        )

    def _extract_plan_title(self, batch: Any) -> str:
        from open_agent_kit.features.team.activity.processor.indexing import (
            extract_plan_title,
        )  # noqa: E501

        return extract_plan_title(batch)

    def rebuild_plan_index(self, batch_size: int = 50) -> dict[str, int]:
        return rebuild_plan_index(
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            batch_size=batch_size,
        )

    # ------------------------------------------------------------------
    # Agent batch promotion
    # ------------------------------------------------------------------

    def promote_agent_batch(self, batch_id: int) -> ProcessingResult:
        """Promote an agent batch to extract memories using user-style LLM extraction."""
        start_time = datetime.now()

        # Get the batch
        batch = self.activity_store.get_prompt_batch(batch_id)
        if not batch:
            return ProcessingResult(
                session_id="",
                activities_processed=0,
                observations_extracted=0,
                success=False,
                error=f"Prompt batch {batch_id} not found",
                prompt_batch_id=batch_id,
            )

        # Check if batch is promotable (agent_notification or system)
        source_type = batch.source_type or PROMPT_SOURCE_USER
        if source_type == PROMPT_SOURCE_USER:
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=0,
                observations_extracted=0,
                success=False,
                error="User batches don't need promotion - already processed with LLM extraction",
                prompt_batch_id=batch_id,
            )

        if source_type == PROMPT_SOURCE_PLAN:
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=0,
                observations_extracted=0,
                success=False,
                error="Plan batches have specialized processing - use reprocess instead",
                prompt_batch_id=batch_id,
            )

        # Check if summarizer is available
        if not self.summarizer:
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=0,
                observations_extracted=0,
                success=False,
                error="No summarizer configured for memory extraction",
                prompt_batch_id=batch_id,
            )

        # Get activities for this batch
        activities = self.activity_store.get_prompt_batch_activities(batch_id)
        if not activities:
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=0,
                observations_extracted=0,
                success=True,
                error="No activities to process",
                prompt_batch_id=batch_id,
            )

        logger.info(
            f"Promoting agent batch {batch_id} (source={source_type}): "
            f"{len(activities)} activities for LLM extraction"
        )

        try:
            # Force user-style processing (full LLM extraction)
            result = self._process_user_batch(batch_id, batch, activities, start_time)

            # Update classification to indicate promotion
            if result.success:
                promoted_classification = f"promoted_{result.classification or 'unknown'}"
                self.activity_store.mark_prompt_batch_processed(
                    batch_id, classification=promoted_classification
                )
                result.classification = promoted_classification

                logger.info(
                    f"Promoted agent batch {batch_id}: {result.observations_extracted} "
                    f"observations extracted ({result.duration_ms}ms)"
                )

            return result

        except (
            OSError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as e:
            logger.error(f"Error promoting agent batch {batch_id}: {e}", exc_info=True)
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=len(activities),
                observations_extracted=0,
                success=False,
                error=str(e),
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                prompt_batch_id=batch_id,
            )
