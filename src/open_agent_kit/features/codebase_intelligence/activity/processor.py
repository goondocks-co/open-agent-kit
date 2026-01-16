"""Background processor for extracting observations from activities.

Two-stage LLM approach:
1. Classify session type (exploration, debugging, implementation, refactoring)
2. Use activity-specific prompt with oak ci context injection

The processor runs in the background without blocking hook responses.
"""

import asyncio
import json
import logging
import re
import sqlite3
import subprocess
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from open_agent_kit.features.codebase_intelligence.activity.prompts import (
    PromptTemplate,
    PromptTemplateConfig,
    render_prompt,
)
from open_agent_kit.features.codebase_intelligence.activity.store import (
    ActivityStore,
    StoredObservation,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.summarization.base import BaseSummarizer


@dataclass
class ContextBudget:
    """Dynamic context budget based on model's context window.

    Allocates the model's context tokens across different parts of the prompt.
    """

    context_tokens: int = 4096  # Original context token limit
    max_user_prompt_chars: int = 3000
    max_activities: int = 30
    max_activity_summary_chars: int = 150
    max_oak_context_chars: int = 2000

    @classmethod
    def from_context_tokens(cls, context_tokens: int) -> "ContextBudget":
        """Calculate budget based on model's context token limit.

        Args:
            context_tokens: Model's max context tokens.

        Returns:
            ContextBudget scaled to the model.
        """
        # Reserve ~30% for model response, allocate rest to input
        available_tokens = int(context_tokens * 0.7)

        # Rough estimate: 1 token ≈ 3-4 chars for mixed content
        available_chars = available_tokens * 3

        # Allocation percentages:
        # - User prompt: 25%
        # - Activities: 50%
        # - Oak context: 15%
        # - Template overhead: 10%

        if context_tokens >= 32000:
            # Large context models (qwen2.5, llama3.1, gpt-4o)
            return cls(
                context_tokens=context_tokens,
                max_user_prompt_chars=min(10000, int(available_chars * 0.25)),
                max_activities=50,
                max_activity_summary_chars=200,
                max_oak_context_chars=min(5000, int(available_chars * 0.15)),
            )
        elif context_tokens >= 8000:
            # Medium context models (llama3.2, mistral, gpt-3.5)
            return cls(
                context_tokens=context_tokens,
                max_user_prompt_chars=min(5000, int(available_chars * 0.25)),
                max_activities=30,
                max_activity_summary_chars=150,
                max_oak_context_chars=min(2000, int(available_chars * 0.15)),
            )
        else:
            # Small context models (phi3:mini, 4K context)
            return cls(
                context_tokens=context_tokens,
                max_user_prompt_chars=min(2000, int(available_chars * 0.25)),
                max_activities=15,
                max_activity_summary_chars=100,
                max_oak_context_chars=min(1000, int(available_chars * 0.15)),
            )


logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a batch of activities."""

    session_id: str
    activities_processed: int
    observations_extracted: int
    success: bool
    error: str | None = None
    duration_ms: int = 0
    classification: str | None = None
    prompt_batch_id: int | None = None  # If processing a specific prompt batch


class ActivityProcessor:
    """Background processor for activity → observation extraction.

    Two-stage approach:
    1. LLM classifies session type
    2. Activity-specific prompt with oak ci context injection
    """

    def __init__(
        self,
        activity_store: ActivityStore,
        vector_store: "VectorStore",
        summarizer: "BaseSummarizer | None",
        prompt_config: PromptTemplateConfig | None = None,
        project_root: str | None = None,
        context_tokens: int = 4096,
    ):
        """Initialize the processor.

        Args:
            activity_store: SQLite store for activities.
            vector_store: ChromaDB store for observations.
            summarizer: LLM summarizer for extraction.
            prompt_config: Prompt template configuration.
            project_root: Project root for oak ci commands.
            context_tokens: Model's context window size (from config).
        """
        self.activity_store = activity_store
        self.vector_store = vector_store
        self.summarizer = summarizer
        self.prompt_config = prompt_config or PromptTemplateConfig.load_from_directory()
        self.project_root = project_root
        self.context_budget = ContextBudget.from_context_tokens(context_tokens)

        self._processing_lock = threading.Lock()
        self._is_processing = False
        self._last_process_time: datetime | None = None

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

        Two-stage approach:
        1. Classify batch type via LLM
        2. Extract observations with activity-specific prompt + oak ci context

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

        if not self.summarizer:
            logger.warning("No summarizer configured, skipping prompt batch processing")
            return ProcessingResult(
                session_id=batch.session_id,
                activities_processed=0,
                observations_extracted=0,
                success=False,
                error="No summarizer configured",
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

        logger.info(
            f"Processing prompt batch {batch_id} (prompt #{batch.prompt_number}): "
            f"{len(activities)} activities"
        )

        try:
            # Extract batch statistics
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
            classification = self._classify_session(
                activities=activity_dicts,
                tool_names=tool_names,
                files_read=files_read,
                files_modified=files_modified,
                files_created=files_created,
                has_errors=bool(errors),
                duration_minutes=duration_minutes,
            )
            logger.info(f"Prompt batch classified as: {classification}")

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

            # Inject oak ci context and user prompt
            # Context budget dynamically scales based on model's context window
            # (full prompt is stored in SQLite for reference)
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
            result = self._call_llm(prompt)

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

            # Store observations
            observations = result.get("observations", [])
            stored_count = 0

            for obs in observations:
                try:
                    obs_id = self._store_observation(
                        session_id=batch.session_id,
                        observation=obs,
                        classification=classification,
                        prompt_batch_id=batch_id,
                    )
                    if obs_id:
                        stored_count += 1
                except (ValueError, KeyError, AttributeError, TypeError) as e:
                    logger.warning(f"Failed to store observation: {e}")

            # Mark activities as processed
            activity_ids = [a.id for a in activities if a.id is not None]
            if activity_ids:
                self.activity_store.mark_activities_processed(activity_ids)

            # Mark batch as processed
            self.activity_store.mark_prompt_batch_processed(batch_id, classification=classification)

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
        """Classify session type using LLM.

        Args:
            activities: Activity dictionaries.
            tool_names: List of tool names used.
            files_read: Files that were read.
            files_modified: Files that were modified.
            files_created: Files that were created.
            has_errors: Whether errors occurred.
            duration_minutes: Session duration.

        Returns:
            Classification from schema (e.g., exploration, debugging, implementation, refactoring).
        """
        from open_agent_kit.features.codebase_intelligence.activity.prompts import get_schema

        classify_template = self.prompt_config.get_template("classify")
        if not classify_template:
            # Fallback to heuristic if no classify template
            return self._classify_heuristic(tool_names, has_errors, files_modified, files_created)

        # Get schema for classification types
        schema = get_schema()
        valid_classifications = schema.get_classification_type_names()

        # Build tool summary
        tool_counts = Counter(tool_names)
        tool_summary = ", ".join(f"{tool}:{count}" for tool, count in tool_counts.most_common(5))

        # Format activities briefly
        activity_lines = []
        for i, act in enumerate(activities[:20], 1):  # Limit to first 20
            tool = act.get("tool_name", "Unknown")
            file_path = act.get("file_path", "")
            line = f"{i}. {tool}"
            if file_path:
                line += f" - {file_path}"
            activity_lines.append(line)
        activities_text = "\n".join(activity_lines)

        # Build classification prompt with schema-driven types
        prompt = classify_template.prompt
        prompt = prompt.replace("{{session_duration}}", f"{duration_minutes:.1f}")
        prompt = prompt.replace("{{tool_summary}}", tool_summary)
        prompt = prompt.replace("{{files_read_count}}", str(len(files_read)))
        prompt = prompt.replace("{{files_modified_count}}", str(len(files_modified)))
        prompt = prompt.replace("{{files_created_count}}", str(len(files_created)))
        prompt = prompt.replace("{{has_errors}}", "yes" if has_errors else "no")
        prompt = prompt.replace("{{activities}}", activities_text)
        # Inject schema-driven classification types
        prompt = prompt.replace(
            "{{classification_types}}", schema.format_classification_types_for_prompt()
        )

        # Call LLM
        result = self._call_llm(prompt)

        if result.get("success"):
            # Parse classification from response using schema-defined types
            raw = result.get("raw_response", "").strip().lower()
            for cls in valid_classifications:
                if cls in raw:
                    return cls

        # Fallback to heuristic
        return self._classify_heuristic(tool_names, has_errors, files_modified, files_created)

    def _classify_heuristic(
        self,
        tool_names: list[str],
        has_errors: bool,
        files_modified: list[str],
        files_created: list[str],
    ) -> str:
        """Fallback heuristic classification.

        Args:
            tool_names: Tools used in session.
            has_errors: Whether errors occurred.
            files_modified: Modified files.
            files_created: Created files.

        Returns:
            Classification string.
        """
        if has_errors:
            return "debugging"

        edit_count = sum(1 for t in tool_names if t in ("Write", "Edit"))
        if files_created:
            return "implementation"
        if edit_count > len(tool_names) * 0.3:
            return "refactoring" if not files_created else "implementation"

        explore_count = sum(1 for t in tool_names if t in ("Read", "Grep", "Glob"))
        if explore_count > len(tool_names) * 0.5:
            return "exploration"

        return "exploration"

    def _select_template_by_classification(self, classification: str) -> PromptTemplate:
        """Select extraction template based on LLM classification.

        Args:
            classification: Session classification.

        Returns:
            Appropriate PromptTemplate.
        """
        # Map classifications to template names
        template_map = {
            "exploration": "exploration",
            "debugging": "debugging",
            "implementation": "implementation",
            "refactoring": "implementation",  # Use implementation for refactoring
        }

        template_name = template_map.get(classification, "extraction")
        template = self.prompt_config.get_template(template_name)

        if template:
            return template

        # Fallback to extraction
        return self.prompt_config.get_template("extraction") or self.prompt_config.templates[0]

    def _get_oak_ci_context(
        self,
        files_read: list[str],
        files_modified: list[str],
        files_created: list[str],
        classification: str,
    ) -> str:
        """Get relevant context from oak ci for the prompt.

        Calls oak ci search/context to inject related code into the prompt.

        Args:
            files_read: Files that were read.
            files_modified: Files that were modified.
            files_created: Files that were created.
            classification: Session classification.

        Returns:
            Context string to inject into prompt, or empty string.
        """
        if not self.project_root:
            return ""

        context_parts = []

        try:
            # For modified files, get related code context
            key_files = files_modified[:3] or files_created[:3] or files_read[:3]

            for file_path in key_files:
                # Use oak ci search to find related code
                query = f"code related to {file_path}"
                result = self._run_oak_ci_command(["search", query, "--limit", "3"])
                if result:
                    context_parts.append(f"### Related to {file_path}\n{result[:1000]}")

            # For debugging sessions, search for error patterns
            if classification == "debugging":
                result = self._run_oak_ci_command(
                    ["search", "error handling", "--type", "memory", "--limit", "3"]
                )
                if result:
                    context_parts.append(f"### Previous error learnings\n{result[:500]}")

        except (OSError, subprocess.TimeoutExpired) as e:
            logger.debug(f"Failed to get oak ci context: {e}")

        return "\n\n".join(context_parts)

    def _run_oak_ci_command(self, args: list[str]) -> str | None:
        """Run an oak ci command and return output.

        Args:
            args: Command arguments (e.g., ["search", "query"]).

        Returns:
            Command output or None on error.
        """
        if not self.project_root:
            return None

        try:
            result = subprocess.run(
                ["oak", "ci"] + args,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (OSError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"oak ci command failed: {e}")
            return None

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        """Call LLM for observation extraction.

        Args:
            prompt: Rendered prompt.

        Returns:
            Dictionary with success, observations, summary, and raw_response.
        """
        import re

        logger.debug("[LLM] _call_llm invoked")

        if not self.summarizer:
            logger.debug("[LLM] No summarizer configured")
            return {"success": False, "error": "No summarizer configured"}

        try:
            # Use the summarizer's API directly
            from open_agent_kit.features.codebase_intelligence.summarization import (
                OpenAICompatSummarizer,
            )

            if not isinstance(self.summarizer, OpenAICompatSummarizer):
                logger.debug("[LLM] Unsupported summarizer type")
                return {"success": False, "error": "Unsupported summarizer type"}

            # Determine if this is an extraction prompt (expects JSON)
            is_extraction = "observations" in prompt.lower()

            # Calculate max_tokens based on context budget
            # Reserve ~25% of context for output, minimum 2000 tokens
            max_output_tokens = max(2000, self.context_budget.context_tokens // 4)

            request_body: dict[str, Any] = {
                "model": self.summarizer._resolved_model or self.summarizer.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": max_output_tokens,
            }

            # Request JSON format for extraction prompts (Ollama/OpenAI compatible)
            if is_extraction:
                request_body["response_format"] = {"type": "json_object"}

            # Use warmup-aware post method to handle model loading timeouts
            logger.debug(
                f"[LLM] Making request to {self.summarizer.base_url} "
                f"model={request_body.get('model')} is_extraction={is_extraction}"
            )
            response = self.summarizer.post_chat_completion(request_body)
            logger.debug(f"[LLM] Response status: {response.status_code}")

            if response.status_code != 200:
                logger.warning(f"[LLM] API error: {response.status_code} - {response.text[:500]}")
                return {"success": False, "error": f"API returned {response.status_code}"}

            data = response.json()
            raw_response = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not raw_response:
                return {"success": False, "error": "Empty LLM response"}

            logger.debug(f"LLM response ({len(raw_response)} chars): {raw_response[:300]}")

            # For classification prompts, just return raw response
            if not is_extraction:
                return {
                    "success": True,
                    "raw_response": raw_response,
                    "observations": [],
                }

            # Try to extract JSON for extraction prompts
            json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                json_match = re.search(r"\{[\s\S]*\}", raw_response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = raw_response.strip()

            result = json.loads(json_str)

            return {
                "success": True,
                "observations": result.get("observations", []),
                "summary": result.get("summary", ""),
                "raw_response": raw_response,
            }

        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse error: {e}")

            # Attempt to repair truncated JSON from LLM
            observations = self._extract_observations_fallback(
                json_str if "json_str" in dir() else raw_response
            )
            if observations:
                logger.info(f"Recovered {len(observations)} observations via fallback parsing")
                return {
                    "success": True,
                    "observations": observations,
                    "raw_response": raw_response if "raw_response" in dir() else "",
                }

            return {
                "success": True,
                "observations": [],
                "raw_response": raw_response if "raw_response" in dir() else "",
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _extract_observations_fallback(self, raw_text: str) -> list[dict[str, Any]]:
        """Extract observations from malformed/truncated JSON using regex.

        LLMs sometimes produce truncated JSON. This attempts to extract
        individual observation objects that are complete.

        Args:
            raw_text: Raw LLM response text.

        Returns:
            List of observation dicts that could be parsed.
        """
        observations = []

        # Pattern to match individual observation objects
        # Looking for: {"type": "...", "observation": "...", ...}
        obs_pattern = re.compile(
            r'\{\s*"type"\s*:\s*"([^"]+)"\s*,\s*"observation"\s*:\s*"((?:[^"\\]|\\.)*)"\s*'
            r'(?:,\s*"importance"\s*:\s*"([^"]+)")?\s*'
            r'(?:,\s*"context"\s*:\s*"((?:[^"\\]|\\.)*)")?\s*\}',
            re.DOTALL,
        )

        for match in obs_pattern.finditer(raw_text):
            try:
                obs_type = match.group(1)
                obs_text = match.group(2)
                importance = match.group(3) or "medium"
                context = match.group(4)

                # Unescape JSON string escapes
                obs_text = obs_text.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
                if context:
                    context = context.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")

                observations.append(
                    {
                        "type": obs_type,
                        "observation": obs_text,
                        "importance": importance,
                        "context": context,
                    }
                )
            except (ValueError, KeyError, AttributeError, TypeError, IndexError) as e:
                logger.debug(f"Failed to parse observation match: {e}")
                continue

        return observations

    def _store_observation(
        self,
        session_id: str,
        observation: dict[str, Any],
        classification: str | None = None,
        prompt_batch_id: int | None = None,
    ) -> str | None:
        """Store an observation using dual-write: SQLite (source of truth) + ChromaDB (search index).

        SQLite is the authoritative storage. ChromaDB can be rebuilt from SQLite if needed.

        Args:
            session_id: Source session ID.
            observation: Observation data from LLM.
            classification: Session classification for tagging.
            prompt_batch_id: Optional prompt batch ID for linking.

        Returns:
            Observation ID if stored, None otherwise.
        """
        from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType
        from open_agent_kit.features.codebase_intelligence.memory.store import (
            MemoryObservation,
        )

        obs_text = observation.get("observation", "")
        if not obs_text:
            return None

        # Map observation type
        type_map = {
            "gotcha": MemoryType.GOTCHA,
            "bug_fix": MemoryType.BUG_FIX,
            "decision": MemoryType.DECISION,
            "discovery": MemoryType.DISCOVERY,
        }
        obs_type = observation.get("type", "discovery")
        memory_type = type_map.get(obs_type, MemoryType.DISCOVERY)

        # Map importance string to integer (1-10 scale)
        importance_str = observation.get("importance", "medium")
        importance_map = {"low": 3, "medium": 5, "high": 8, "critical": 10}
        importance_int = importance_map.get(importance_str, 5)

        # Build tags
        tags = ["auto-extracted", f"importance:{importance_str}"]
        if classification:
            tags.append(f"session:{classification}")

        obs_id = str(uuid4())
        created_at = datetime.now()

        # Step 1: Store to SQLite (source of truth) - MUST succeed
        stored_obs = StoredObservation(
            id=obs_id,
            session_id=session_id,
            prompt_batch_id=prompt_batch_id,
            observation=obs_text,
            memory_type=memory_type.value,
            context=observation.get("context"),
            tags=tags,
            importance=importance_int,
            created_at=created_at,
            embedded=False,  # Not yet in ChromaDB
        )

        try:
            self.activity_store.store_observation(stored_obs)
            logger.debug(f"Stored observation to SQLite [{obs_type}]: {obs_text[:50]}...")
        except (OSError, ValueError, TypeError) as e:
            logger.error(f"Failed to store observation to SQLite: {e}", exc_info=True)
            return None

        # Step 2: Embed and store in ChromaDB (search index)
        memory = MemoryObservation(
            id=obs_id,
            observation=obs_text,
            memory_type=memory_type.value,
            context=observation.get("context"),
            tags=tags,
            created_at=created_at,
        )

        try:
            self.vector_store.add_memory(memory)
            # Step 3: Mark as embedded in SQLite
            self.activity_store.mark_observation_embedded(obs_id)
            logger.debug(f"Stored observation to ChromaDB [{obs_type}]: {obs_text[:50]}...")
            return obs_id
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            # ChromaDB failed, but SQLite has the data - it can be retried later
            logger.warning(f"Failed to embed observation in ChromaDB (will retry later): {e}")
            # Return the ID anyway - SQLite storage succeeded
            return obs_id

    def process_session_summary(self, session_id: str) -> str | None:
        """Generate and store a session summary.

        Called at session end to create a high-level summary of what was accomplished.
        Stored as a session_summary memory for injection into future sessions.

        Args:
            session_id: Session ID to summarize.

        Returns:
            Summary text if generated, None otherwise.
        """
        if not self.summarizer:
            logger.debug("No summarizer configured, skipping session summary")
            return None

        # Get session from activity store
        session = self.activity_store.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for summary")
            return None

        # Get prompt batches for this session
        batches = self.activity_store.get_session_prompt_batches(session_id, limit=100)
        if not batches:
            logger.debug(f"No prompt batches for session {session_id}, skipping summary")
            return None

        # Get session stats
        stats = self.activity_store.get_session_stats(session_id)

        # Check if session has enough substance to summarize
        tool_calls = stats.get("total_activities", 0)
        if tool_calls < 3:
            logger.debug(f"Session {session_id} too short ({tool_calls} tools), skipping summary")
            return None

        # Get summary template
        summary_template = self.prompt_config.get_template("session-summary")
        if not summary_template:
            logger.warning("No session-summary prompt template found")
            return None

        # Calculate duration
        duration_minutes = 0.0
        if session.started_at and session.ended_at:
            duration_minutes = (session.ended_at - session.started_at).total_seconds() / 60

        # Format prompt batches for context
        batch_lines = []
        for i, batch in enumerate(batches[:20], 1):  # Limit to 20 batches
            classification = batch.classification or "unknown"
            user_prompt = batch.user_prompt or "(no prompt captured)"
            # Truncate long prompts
            if len(user_prompt) > 150:
                user_prompt = user_prompt[:147] + "..."
            batch_lines.append(f"{i}. [{classification}] {user_prompt}")

        prompt_batches_text = "\n".join(batch_lines) if batch_lines else "(no batches)"

        # Build prompt
        prompt = summary_template.prompt
        prompt = prompt.replace("{{session_duration}}", f"{duration_minutes:.1f}")
        prompt = prompt.replace("{{prompt_batch_count}}", str(len(batches)))
        prompt = prompt.replace("{{files_read_count}}", str(len(stats.get("files_read", []))))
        prompt = prompt.replace(
            "{{files_modified_count}}", str(len(stats.get("files_modified", [])))
        )
        prompt = prompt.replace("{{files_created_count}}", str(len(stats.get("files_created", []))))
        prompt = prompt.replace("{{tool_calls}}", str(tool_calls))
        prompt = prompt.replace("{{prompt_batches}}", prompt_batches_text)

        # Call LLM
        result = self._call_llm(prompt)

        if not result.get("success"):
            logger.warning(f"Session summary LLM call failed: {result.get('error')}")
            return None

        # Extract summary text (raw response, not JSON)
        raw_response = result.get("raw_response", "")
        summary: str = str(raw_response).strip() if raw_response else ""
        if not summary or len(summary) < 10:
            logger.debug("Session summary too short or empty")
            return None

        # Clean up common LLM artifacts
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1]

        # Store as session_summary memory using dual-write: SQLite + ChromaDB
        from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType
        from open_agent_kit.features.codebase_intelligence.memory.store import (
            MemoryObservation,
        )

        obs_id = str(uuid4())
        created_at = datetime.now()
        tags = ["session-summary", session.agent or "unknown"]

        # Step 1: Store to SQLite (source of truth)
        stored_obs = StoredObservation(
            id=obs_id,
            session_id=session_id,
            observation=summary,
            memory_type=MemoryType.SESSION_SUMMARY.value,
            context=f"session:{session_id}",
            tags=tags,
            importance=7,  # Session summaries are moderately important
            created_at=created_at,
            embedded=False,
        )

        try:
            self.activity_store.store_observation(stored_obs)
        except (OSError, ValueError, TypeError) as e:
            logger.error(f"Failed to store session summary to SQLite: {e}", exc_info=True)
            return None

        # Step 2: Embed and store in ChromaDB
        memory = MemoryObservation(
            id=obs_id,
            observation=summary,
            memory_type=MemoryType.SESSION_SUMMARY.value,
            context=f"session:{session_id}",
            tags=tags,
            created_at=created_at,
        )

        try:
            self.vector_store.add_memory(memory)
            self.activity_store.mark_observation_embedded(obs_id)
            logger.info(f"Stored session summary for {session_id}: {summary[:80]}...")
            return summary
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            # ChromaDB failed but SQLite has the data - can retry later
            logger.warning(f"Failed to embed session summary in ChromaDB: {e}")
            return summary  # Return summary anyway since SQLite storage succeeded

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
                from open_agent_kit.features.codebase_intelligence.constants import (
                    BATCH_ACTIVE_TIMEOUT_SECONDS,
                )

                # Recovery: Auto-end batches stuck in 'active' too long
                stuck_count = self.activity_store.recover_stuck_batches(
                    timeout_seconds=BATCH_ACTIVE_TIMEOUT_SECONDS
                )
                if stuck_count:
                    logger.info(f"Recovered {stuck_count} stuck batches")

                # Recovery: Associate orphaned activities with batches
                orphan_count = self.activity_store.recover_orphaned_activities()
                if orphan_count:
                    logger.info(f"Recovered {orphan_count} orphaned activities")

                # Process pending prompt batches (preferred - processes by user prompt)
                batch_results = self.process_pending_batches()
                if batch_results:
                    logger.info(f"Background processed {len(batch_results)} prompt batches")

                # Also process any sessions with unprocessed activities
                # (fallback for activities not associated with a batch)
                self.process_pending()
            except (
                OSError,
                sqlite3.OperationalError,
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
            ) as e:
                logger.error(f"Background processing error: {e}", exc_info=True)
            finally:
                # Reschedule
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
    ) -> dict[str, int]:
        """Rebuild ChromaDB memory index from SQLite source of truth.

        Call this when ChromaDB is empty/wiped but SQLite has observations,
        or when there's a dimension mismatch requiring full re-indexing.

        Args:
            batch_size: Number of observations to process per batch.
            reset_embedded_flags: If True, marks ALL observations as unembedded
                first (for full rebuild). If False, only processes observations
                already marked as unembedded.

        Returns:
            Dictionary with rebuild statistics:
            - total: Total observations in SQLite
            - embedded: Successfully embedded count
            - failed: Failed embedding count
            - skipped: Already embedded (if reset_embedded_flags=False)
        """
        from open_agent_kit.features.codebase_intelligence.memory.store import (
            MemoryObservation,
        )

        stats = {"total": 0, "embedded": 0, "failed": 0, "skipped": 0}

        # Get total count
        stats["total"] = self.activity_store.count_observations()

        if stats["total"] == 0:
            logger.info("No observations in SQLite to rebuild")
            return stats

        # Step 1: Reset embedded flags if doing full rebuild
        if reset_embedded_flags:
            already_embedded = self.activity_store.count_embedded_observations()
            if already_embedded > 0:
                logger.info(f"Resetting {already_embedded} embedded flags for full rebuild")
                self.activity_store.mark_all_observations_unembedded()

        # Step 2: Process unembedded observations in batches
        processed = 0
        while True:
            observations = self.activity_store.get_unembedded_observations(limit=batch_size)

            if not observations:
                break

            logger.info(
                f"Rebuilding ChromaDB: processing batch of {len(observations)} "
                f"({processed}/{stats['total']} done)"
            )

            for stored_obs in observations:
                try:
                    # Create MemoryObservation for ChromaDB
                    memory = MemoryObservation(
                        id=stored_obs.id,
                        observation=stored_obs.observation,
                        memory_type=stored_obs.memory_type,
                        context=stored_obs.context,
                        tags=stored_obs.tags or [],
                        created_at=stored_obs.created_at,
                    )

                    # Embed and store
                    self.vector_store.add_memory(memory)
                    self.activity_store.mark_observation_embedded(stored_obs.id)
                    stats["embedded"] += 1

                except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
                    logger.warning(f"Failed to embed observation {stored_obs.id}: {e}")
                    stats["failed"] += 1

            processed += len(observations)

        logger.info(
            f"ChromaDB rebuild complete: {stats['embedded']} embedded, "
            f"{stats['failed']} failed, {stats['total']} total"
        )
        return stats

    def embed_pending_observations(self, batch_size: int = 50) -> dict[str, int]:
        """Embed observations that are in SQLite but not yet in ChromaDB.

        This is the incremental version - only processes observations with
        embedded=FALSE. Use rebuild_chromadb_from_sqlite for full rebuilds.

        Args:
            batch_size: Number of observations to process per batch.

        Returns:
            Dictionary with processing statistics.
        """
        return self.rebuild_chromadb_from_sqlite(
            batch_size=batch_size,
            reset_embedded_flags=False,
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
