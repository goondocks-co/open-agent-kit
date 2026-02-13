"""Core ActivityProcessor class and orchestration.

Main class that coordinates all processing, scheduling, and recovery.
"""

import asyncio
import json
import logging
import sqlite3
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.activity.processor.classification import (
    classify_heuristic,
    classify_session,
    select_template_by_classification,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.handlers import (
    get_batch_handler,
    process_user_batch,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.indexing import (
    embed_pending_observations,
    index_pending_plans,
    rebuild_chromadb_from_sqlite,
    rebuild_plan_index,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.llm import (
    call_llm,
    get_oak_ci_context,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.models import (
    ContextBudget,
    ProcessingResult,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.observation import (
    store_observation,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
    process_session_summary,
)
from open_agent_kit.features.codebase_intelligence.activity.processor.titles import (
    generate_pending_titles,
    generate_session_title,
    generate_title_from_summary,
)
from open_agent_kit.features.codebase_intelligence.activity.prompts import (
    PromptTemplateConfig,
    render_prompt,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_RUN_RECOVERY_BUFFER_SECONDS,
    DEFAULT_AGENT_TIMEOUT_SECONDS,
    INJECTION_MAX_SESSION_SUMMARIES,
    PROMPT_SOURCE_PLAN,
    PROMPT_SOURCE_USER,
    SESSION_STATUS_ACTIVE,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from open_agent_kit.features.codebase_intelligence.activity.store import (
        ActivityStore,
    )
    from open_agent_kit.features.codebase_intelligence.config import (
        CIConfig,
        SessionQualityConfig,
        SummarizationConfig,
    )
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.summarization.base import (
        BaseSummarizer,
    )

logger = logging.getLogger(__name__)

# Exception types caught by background processing phases.
# Each phase has its own error boundary so failures are isolated.
# Exception types caught by background processing phases.
# Each phase has its own error boundary so failures are isolated —
# a bug in one phase must not crash the entire processor loop.
# TypeError/KeyError/AttributeError are intentionally included:
# while they often indicate programming errors, in this context
# phase isolation is more important than fail-fast behavior.
# All caught exceptions are logged with exc_info=True for debugging.
_BG_EXCEPTIONS = (
    OSError,
    sqlite3.OperationalError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
)


class ActivityProcessor:
    """Background processor for activity → observation extraction.

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
        """Initialize the processor.

        Args:
            activity_store: SQLite store for activities.
            vector_store: ChromaDB store for observations.
            summarizer: Static summarizer fallback (used when config_accessor
                is not provided, e.g. in tests).
            prompt_config: Prompt template configuration.
            project_root: Project root for oak ci commands.
            context_tokens: Static context_tokens fallback (used when
                config_accessor is not provided).
            session_quality_config: Static session quality fallback.
            config_accessor: Callable returning the current CIConfig. When
                provided, summarizer/context_budget/session_quality are read
                from live config instead of the static init values. This
                ensures config changes via the UI take effect immediately
                without a daemon restart.
        """
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
                                from open_agent_kit.features.codebase_intelligence.summarization import (
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
    def min_session_activities(self) -> int:
        """Get minimum activities threshold from config or constant."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            MIN_SESSION_ACTIVITIES,
        )

        sqc = self.session_quality_config
        if sqc:
            return sqc.min_activities
        return MIN_SESSION_ACTIVITIES

    @property
    def stale_timeout_seconds(self) -> int:
        """Get stale timeout from config or constant."""
        from open_agent_kit.features.codebase_intelligence.constants import (
            SESSION_INACTIVE_TIMEOUT_SECONDS,
        )

        sqc = self.session_quality_config
        if sqc:
            return sqc.stale_timeout_seconds
        return SESSION_INACTIVE_TIMEOUT_SECONDS

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        """Call LLM for observation extraction.

        Args:
            prompt: Rendered prompt.

        Returns:
            Dictionary with success, observations, summary, and raw_response.
        """
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
        """Classify session type using LLM."""
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
        """Fallback heuristic classification."""
        return classify_heuristic(tool_names, has_errors, files_modified, files_created)

    def _select_template_by_classification(self, classification: str) -> Any:
        """Select extraction template based on LLM classification."""
        return select_template_by_classification(classification, self.prompt_config)

    def _get_oak_ci_context(
        self,
        files_read: list[str],
        files_modified: list[str],
        files_created: list[str],
        classification: str,
    ) -> str:
        """Get relevant context from oak ci for the prompt."""
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
    ) -> str | None:
        """Store an observation using dual-write: SQLite + ChromaDB."""
        return store_observation(
            session_id=session_id,
            observation=observation,
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            classification=classification,
            prompt_batch_id=prompt_batch_id,
            project_root=self.project_root,
        )

    def process_session(self, session_id: str) -> ProcessingResult:
        """Process all unprocessed activities for a session.

        Two-stage approach:
        1. Classify session type via LLM
        2. Extract observations with activity-specific prompt + oak ci context

        Args:
            session_id: Session to process.

        Returns:
            ProcessingResult with extraction statistics.
        """
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

            # Store observations
            observations = result.get("observations", [])
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
                f"Processed session {session_id}: {len(activities)} activities → "
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
        """Process activities for a single prompt batch.

        This is the preferred processing unit - activities from one user prompt.
        Dispatches to appropriate handler based on batch source_type.

        Args:
            batch_id: Prompt batch ID to process.

        Returns:
            ProcessingResult with extraction statistics.
        """
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

    def process_pending_batches(self, max_batches: int = 10) -> list[ProcessingResult]:
        """Process all pending prompt batches.

        Args:
            max_batches: Maximum batches to process in one run.

        Returns:
            List of ProcessingResult for each batch.
        """
        with self._processing_lock:
            if self._is_processing:
                logger.debug("Processing already in progress, skipping")
                return []

            self._is_processing = True

        try:
            batches = self.activity_store.get_unprocessed_prompt_batches(limit=max_batches)

            if not batches:
                # Debug: check why no batches - query all recent batches
                try:
                    conn = self.activity_store._get_connection()
                    cursor = conn.execute(
                        "SELECT id, status, processed, classification FROM prompt_batches "
                        "ORDER BY created_at_epoch DESC LIMIT 5"
                    )
                    recent = cursor.fetchall()
                    if recent:
                        batch_info = [
                            f"id={r[0]} status={r[1]} processed={r[2]} class={r[3]}" for r in recent
                        ]
                        logger.debug(f"Recent batches: {batch_info}")
                except sqlite3.OperationalError as e:
                    logger.debug(f"Could not query batch state: {e}")

                logger.debug("No pending prompt batches to process")
                return []

            logger.info(f"Processing {len(batches)} pending prompt batches")

            results = []
            for batch in batches:
                if batch.id is not None:
                    result = self.process_prompt_batch(batch.id)
                    results.append(result)

            self._last_process_time = datetime.now()
            return results

        finally:
            with self._processing_lock:
                self._is_processing = False

    def _process_user_batch(
        self,
        batch_id: int,
        batch: Any,
        activities: list[Any],
        start_time: datetime,
    ) -> ProcessingResult:
        """Process a user-initiated batch with full LLM extraction.

        This is a wrapper for the handlers.process_user_batch function.
        Used by promote_agent_batch.
        """
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
        )

    def generate_session_title(self, session_id: str) -> str | None:
        """Generate a short title for a session based on its prompts."""
        return generate_session_title(
            session_id=session_id,
            activity_store=self.activity_store,
            prompt_config=self.prompt_config,
            call_llm=self._call_llm,
            min_activities=self.min_session_activities,
        )

    def generate_pending_titles(self, limit: int = 5) -> int:
        """Generate titles for sessions that don't have them."""
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
        """Generate and store a session summary and title.

        Args:
            session_id: Session to summarize.
            regenerate_title: If True, force regenerate title even if one exists.

        Returns:
            Tuple of (summary text, title text) if generated, (None, None) otherwise.
        """
        if not self.summarizer:
            logger.info("Session summary skipped: summarizer not configured")
            return None, None

        # Create a wrapper for generate_title_from_summary that binds store and config
        def _generate_title_from_summary(sid: str, summary: str) -> str | None:
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
            generate_title_from_summary=_generate_title_from_summary,
        )

    def complete_session(self, session_id: str) -> tuple[str | None, str | None]:
        """Mark an active session as completed and run post-completion processing.

        This is the same chain the background job runs for stale sessions:
        1. Mark session status as 'completed' (via end_session)
        2. Generate summary (if summarizer configured)
        3. Generate title (if missing)

        Args:
            session_id: Session to complete.

        Returns:
            Tuple of (summary text, title text) if generated.

        Raises:
            ValueError: If session not found or not active.
        """
        session = self.activity_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.status != SESSION_STATUS_ACTIVE:
            raise ValueError(
                f"Session {session_id} is already '{session.status}', only active sessions can be completed"
            )

        # Step 1: Mark as completed — same SQL path as recover_stale_sessions
        self.activity_store.end_session(session_id)
        logger.info(f"Manually completed session {session_id[:8]}")

        # Step 2: Generate summary — same path as background job
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
        """Process all pending sessions.

        Args:
            max_sessions: Maximum sessions to process in one batch.

        Returns:
            List of ProcessingResult for each session.
        """
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
    # Background processing phases
    #
    # Each phase has its own error boundary so a failure in one phase
    # does not skip subsequent phases.  This decomposition also makes
    # each phase independently testable and sets the groundwork for
    # future parallelization (W5.6).
    # ------------------------------------------------------------------

    def _bg_recover_stuck_data(self) -> None:
        """Phase 1: Recover stuck batches, stale runs, and orphaned activities."""
        try:
            from open_agent_kit.features.codebase_intelligence.constants import (
                BATCH_ACTIVE_TIMEOUT_SECONDS,
            )

            # Auto-end batches stuck in 'active' too long
            stuck_count = self.activity_store.recover_stuck_batches(
                timeout_seconds=BATCH_ACTIVE_TIMEOUT_SECONDS,
                project_root=self.project_root,
            )
            if stuck_count:
                logger.info(f"Recovered {stuck_count} stuck batches")

            # Mark stale agent runs as failed
            stale_run_ids = self.activity_store.recover_stale_runs(
                buffer_seconds=AGENT_RUN_RECOVERY_BUFFER_SECONDS,
                default_timeout_seconds=DEFAULT_AGENT_TIMEOUT_SECONDS,
            )
            if stale_run_ids:
                logger.info(
                    f"Recovered {len(stale_run_ids)} stale agent runs: "
                    f"{[r[:8] for r in stale_run_ids]}"
                )

            # Associate orphaned activities with batches
            orphan_count = self.activity_store.recover_orphaned_activities()
            if orphan_count:
                logger.info(f"Recovered {orphan_count} orphaned activities")
        except _BG_EXCEPTIONS as e:
            logger.error(f"Background recovery error: {e}", exc_info=True)

    def _bg_recover_stale_sessions(self) -> None:
        """Phase 2: End/delete stale sessions and summarize recovered ones."""
        try:
            recovered_ids, deleted_ids = self.activity_store.recover_stale_sessions(
                timeout_seconds=self.stale_timeout_seconds,
                min_activities=self.min_session_activities,
                vector_store=self.vector_store,
            )
            if deleted_ids:
                logger.info(
                    f"Deleted {len(deleted_ids)} empty stale sessions: "
                    f"{[s[:8] for s in deleted_ids]}"
                )
            if recovered_ids:
                logger.info(f"Recovered {len(recovered_ids)} stale sessions")
                for session_id in recovered_ids:
                    try:
                        summary, _title = self.process_session_summary_with_title(session_id)
                        if summary:
                            logger.info(
                                f"Generated summary for recovered session "
                                f"{session_id[:8]}: {summary[:50]}..."
                            )
                    except (OSError, ValueError, TypeError, RuntimeError) as e:
                        logger.warning(
                            f"Failed to summarize recovered session {session_id[:8]}: {e}"
                        )
        except _BG_EXCEPTIONS as e:
            logger.error(f"Background stale-session recovery error: {e}", exc_info=True)

    def _bg_cleanup_and_summarize(self) -> None:
        """Phase 3: Clean up low-quality sessions and generate missing summaries.

        Cleanup runs first to avoid wasting LLM calls on sessions that
        will be deleted.
        """
        try:
            cleanup_ids = self.activity_store.cleanup_low_quality_sessions(
                vector_store=self.vector_store,
                min_activities=self.min_session_activities,
            )
            if cleanup_ids:
                logger.info(
                    f"Cleaned up {len(cleanup_ids)} low-quality completed sessions: "
                    f"{[s[:8] for s in cleanup_ids]}"
                )

            if self.summarizer:
                missing = self.activity_store.get_sessions_missing_summaries(
                    limit=INJECTION_MAX_SESSION_SUMMARIES,
                    min_activities=self.min_session_activities,
                )
                for session in missing:
                    try:
                        summary, _title = self.process_session_summary_with_title(session.id)
                        if summary:
                            logger.info(
                                f"Generated summary for session {session.id[:8]}: "
                                f"{summary[:50]}..."
                            )
                    except (OSError, ValueError, TypeError, RuntimeError) as e:
                        logger.warning(f"Failed to summarize session {session.id[:8]}: {e}")
        except _BG_EXCEPTIONS as e:
            logger.error(f"Background cleanup/summarize error: {e}", exc_info=True)

    def _bg_process_pending(self) -> None:
        """Phase 4: Process pending batches and fallback sessions."""
        try:
            batch_results = self.process_pending_batches()
            if batch_results:
                logger.info(f"Background processed {len(batch_results)} prompt batches")

            self.process_pending()
        except _BG_EXCEPTIONS as e:
            logger.error(f"Background batch processing error: {e}", exc_info=True)

    def _bg_index_and_title(self) -> None:
        """Phase 5: Index pending plans and generate missing titles."""
        try:
            plan_stats = self.index_pending_plans()
            if plan_stats.get("indexed", 0) > 0:
                logger.info(f"Background indexed {plan_stats['indexed']} plans")

            title_count = self.generate_pending_titles()
            if title_count > 0:
                logger.info(f"Background generated {title_count} session titles")
        except _BG_EXCEPTIONS as e:
            logger.error(f"Background indexing/title error: {e}", exc_info=True)

    def run_background_cycle(self) -> None:
        """Execute one full background processing cycle.

        Runs all phases sequentially.  Each phase has its own error
        boundary so a failure in one does not skip the rest.

        Phase ordering:
        1. Recover stuck data (batches, runs, orphans)
        2. Recover stale sessions
        3. Cleanup low-quality sessions + generate summaries
        4. Process pending batches/sessions
        5. Index plans + generate titles
        """
        self._bg_recover_stuck_data()
        self._bg_recover_stale_sessions()
        self._bg_cleanup_and_summarize()
        self._bg_process_pending()
        self._bg_index_and_title()

    def schedule_background_processing(
        self,
        interval_seconds: int = 60,
    ) -> threading.Timer:
        """Schedule periodic background processing.

        Args:
            interval_seconds: Interval between processing runs.

        Returns:
            Timer object (can be cancelled).
        """

        def run_and_reschedule() -> None:
            try:
                self.run_background_cycle()
            finally:
                timer = threading.Timer(interval_seconds, run_and_reschedule)
                timer.daemon = True
                timer.start()

        timer = threading.Timer(interval_seconds, run_and_reschedule)
        timer.daemon = True
        timer.start()

        logger.info(f"Scheduled background activity processing every {interval_seconds}s")
        return timer

    def rebuild_chromadb_from_sqlite(
        self,
        batch_size: int = 50,
        reset_embedded_flags: bool = True,
        clear_chromadb_first: bool = False,
    ) -> dict[str, int]:
        """Rebuild ChromaDB memory index from SQLite source of truth.

        Args:
            batch_size: Number of observations to process per batch.
            reset_embedded_flags: If True, marks ALL observations as unembedded first.
            clear_chromadb_first: If True, clears ChromaDB memory collection first
                to remove orphaned entries before rebuilding.
        """
        return rebuild_chromadb_from_sqlite(
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            batch_size=batch_size,
            reset_embedded_flags=reset_embedded_flags,
            clear_chromadb_first=clear_chromadb_first,
        )

    def embed_pending_observations(self, batch_size: int = 50) -> dict[str, int]:
        """Embed observations that are in SQLite but not yet in ChromaDB."""
        return embed_pending_observations(
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            batch_size=batch_size,
        )

    def index_pending_plans(self, batch_size: int = 10) -> dict[str, int]:
        """Index plans that haven't been embedded in ChromaDB yet."""
        return index_pending_plans(
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            batch_size=batch_size,
        )

    def _extract_plan_title(self, batch: Any) -> str:
        """Extract plan title from filename or first heading."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.indexing import (
            extract_plan_title,
        )

        return extract_plan_title(batch)

    def rebuild_plan_index(self, batch_size: int = 50) -> dict[str, int]:
        """Rebuild ChromaDB plan index from SQLite source of truth."""
        return rebuild_plan_index(
            activity_store=self.activity_store,
            vector_store=self.vector_store,
            batch_size=batch_size,
        )

    def promote_agent_batch(self, batch_id: int) -> ProcessingResult:
        """Promote an agent batch to extract memories using user-style processing.

        This forces full LLM extraction on batches that were previously skipped
        (agent_notification, system). Useful for manually promoting valuable
        findings from background agent work to the memory store.

        Args:
            batch_id: Prompt batch ID to promote.

        Returns:
            ProcessingResult with extracted observations.
        """
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


# Async wrappers for use with FastAPI


async def process_session_async(
    processor: ActivityProcessor,
    session_id: str,
) -> ProcessingResult:
    """Process a session asynchronously.

    Args:
        processor: Activity processor instance.
        session_id: Session to process.

    Returns:
        ProcessingResult.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, processor.process_session, session_id)


async def process_prompt_batch_async(
    processor: ActivityProcessor,
    batch_id: int,
) -> ProcessingResult:
    """Process a prompt batch asynchronously.

    This is the preferred processing method - processes activities from a
    single user prompt as one coherent unit.

    Args:
        processor: Activity processor instance.
        batch_id: Prompt batch ID to process.

    Returns:
        ProcessingResult.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, processor.process_prompt_batch, batch_id)


async def promote_agent_batch_async(
    processor: ActivityProcessor,
    batch_id: int,
) -> ProcessingResult:
    """Promote an agent batch to extract memories asynchronously.

    This forces user-style LLM extraction on batches that were previously
    skipped (agent_notification, system). Useful for promoting valuable
    findings from background agent work.

    Args:
        processor: Activity processor instance.
        batch_id: Prompt batch ID to promote.

    Returns:
        ProcessingResult with extracted observations.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, processor.promote_agent_batch, batch_id)
