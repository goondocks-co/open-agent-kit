"""Agent Scheduler for cron-based agent execution.

This module provides the AgentScheduler class that manages scheduled agent runs:
- Reads schedule definitions from database (cron, description, trigger_type)
- Computes next run times from cron expressions
- Checks for and executes due schedules
- Background scheduling loop

IMPORTANT: Schedule definitions now live in the database only. YAML schedule
support is deprecated. Use the API/UI to create and manage schedules.
"""

import asyncio
import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any

from croniter import croniter

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentRunStatus,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    SCHEDULE_TRIGGER_CRON,
    SCHEDULER_STOP_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.config import AgentConfig, CIConfig

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Scheduler for cron-based agent execution.

    The scheduler:
    - Reads schedule definitions from ActivityStore (SQLite) - database is source of truth
    - Computes next run times using croniter
    - Periodically checks for and runs due schedules
    - Tracks run history via AgentExecutor

    YAML schedule support is deprecated. Schedules are managed via API/UI.

    Attributes:
        activity_store: ActivityStore for schedule persistence.
        agent_registry: AgentRegistry for loading task definitions.
        agent_executor: AgentExecutor for running agents.
    """

    def __init__(
        self,
        activity_store: "ActivityStore",
        agent_registry: "AgentRegistry",
        agent_executor: "AgentExecutor",
        agent_config: "AgentConfig",
        config_accessor: "Callable[[], CIConfig | None] | None" = None,
    ):
        """Initialize the scheduler.

        Args:
            activity_store: ActivityStore for schedule persistence.
            agent_registry: AgentRegistry for loading task definitions.
            agent_executor: AgentExecutor for running agents.
            agent_config: Static AgentConfig fallback (used when
                config_accessor is not provided, e.g. in tests).
            config_accessor: Callable returning the current CIConfig. When
                provided, scheduler settings are read from live config.
        """
        self._activity_store = activity_store
        self._agent_registry = agent_registry
        self._agent_executor = agent_executor
        self._config_accessor = config_accessor
        self._fallback_agent_config = agent_config

        # Background loop control
        self._running = False
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = threading.Event()

    @property
    def _agent_config(self) -> "AgentConfig":
        """Get agent config from live config accessor or static fallback."""
        if self._config_accessor is not None:
            config = self._config_accessor()
            if config is not None:
                return config.agents
        return self._fallback_agent_config

    @property
    def is_running(self) -> bool:
        """Check if the scheduler background loop is running."""
        return self._running

    @property
    def scheduler_interval_seconds(self) -> int:
        """Get the scheduler check interval from config."""
        return self._agent_config.scheduler_interval_seconds

    def compute_next_run(self, cron_expr: str, after: datetime | None = None) -> datetime:
        """Compute the next run time for a cron expression.

        Args:
            cron_expr: Cron expression (e.g., "0 0 * * MON").
            after: Base time for computation (defaults to now).

        Returns:
            Next scheduled run datetime.

        Raises:
            ValueError: If cron expression is invalid.
        """
        base_time = after or datetime.now()
        try:
            cron = croniter(cron_expr, base_time)
            next_time: datetime = cron.get_next(datetime)
            return next_time
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid cron expression '{cron_expr}': {e}") from e

    def validate_cron(self, cron_expr: str) -> bool:
        """Validate a cron expression.

        Args:
            cron_expr: Cron expression to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            croniter(cron_expr)
            return True
        except (KeyError, ValueError):
            return False

    def sync_schedules(self) -> dict[str, Any]:
        """Clean up orphaned schedules.

        YAML schedule sync is deprecated. This now only:
        - Removes schedules for tasks that no longer exist in the registry

        Returns:
            Summary dict with counts of removed schedules.
        """
        # Get all tasks from registry (to validate schedule targets)
        tasks = self._agent_registry.list_tasks()
        task_names = {t.name for t in tasks}

        # Get all existing schedules from database
        existing_schedules = {s["task_name"]: s for s in self._activity_store.list_schedules()}

        removed = 0

        # Remove schedules for tasks that no longer exist
        for task_name in existing_schedules:
            if task_name not in task_names:
                self._activity_store.delete_schedule(task_name)
                removed += 1
                logger.info(f"Removed orphaned schedule for '{task_name}' (task not found)")

        result = {
            "created": 0,  # No longer auto-create from YAML
            "updated": 0,
            "removed": removed,
            "total": len(existing_schedules) - removed,
        }

        logger.info(f"Schedule sync complete: {removed} orphaned schedules removed")

        return result

    def get_due_schedules(self) -> list[dict[str, Any]]:
        """Get schedules that are due to run.

        Returns:
            List of schedule records where enabled=1, trigger_type='cron',
            and next_run_at <= now.
        """
        return self._activity_store.get_due_schedules()

    def _is_task_running(self, task_name: str) -> bool:
        """Check if an agent task already has an active run.

        Used to prevent overlapping scheduled executions of the same agent.

        Args:
            task_name: Name of the agent task.

        Returns:
            True if task has a run in RUNNING status.
        """
        runs, _ = self._activity_store.list_agent_runs(
            agent_name=task_name,
            status="running",
            limit=1,
        )
        return len(runs) > 0

    async def run_scheduled_agent(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Run a scheduled agent and update schedule state.

        Prevents concurrent execution of the same agent task. If a task
        is already running, the scheduled run is skipped.

        Args:
            schedule: Schedule record from database.

        Returns:
            Result dict with run_id, status, and any error.
        """
        task_name = schedule["task_name"]
        result: dict[str, Any] = {"task_name": task_name}

        # Check for concurrent execution - skip if already running
        if self._is_task_running(task_name):
            result["skipped"] = True
            result["reason"] = "already_running"
            logger.warning(f"Skipping scheduled run for '{task_name}' - already running")
            return result

        # Get the task and its template
        task = self._agent_registry.get_task(task_name)
        if task is None:
            result["error"] = f"Task '{task_name}' not found"
            logger.error(result["error"])
            return result

        template = self._agent_registry.get_template(task.agent_type)
        if template is None:
            result["error"] = f"Template '{task.agent_type}' not found for task '{task_name}'"
            logger.error(result["error"])
            return result

        logger.info(f"Running scheduled agent: {task_name}")

        try:
            # Compose task prompt with optional assignment (same pattern as manual run)
            task_prompt = task.default_task
            additional_prompt = schedule.get("additional_prompt")
            if additional_prompt:
                task_prompt = f"## Assignment\n{additional_prompt}\n\n---\n\n{task.default_task}"

            # Execute the agent
            run = await self._agent_executor.execute(
                agent=template,
                task=task_prompt,
                agent_task=task,
            )

            result["run_id"] = run.id
            result["status"] = run.status.value

            # Update schedule with run info
            now = datetime.now()

            # Compute next run time from schedule's cron expression (from DB)
            cron_expr = schedule.get("cron_expression")
            next_run = None
            if cron_expr:
                try:
                    next_run = self.compute_next_run(cron_expr, after=now)
                except ValueError as e:
                    logger.warning(f"Invalid cron for '{task_name}': {e}")

            self._activity_store.update_schedule(
                task_name,
                last_run_at=now,
                last_run_id=run.id,
                next_run_at=next_run,
            )

            if run.status == AgentRunStatus.COMPLETED:
                logger.info(f"Scheduled agent '{task_name}' completed: run_id={run.id}")
            else:
                result["error"] = run.error
                logger.warning(
                    f"Scheduled agent '{task_name}' finished with status {run.status}: "
                    f"run_id={run.id}, error={run.error}"
                )

        except (OSError, RuntimeError, ValueError) as e:
            result["error"] = str(e)
            logger.error(f"Failed to run scheduled agent '{task_name}': {e}")

        return result

    async def check_and_run(self) -> list[dict[str, Any]]:
        """Check for due schedules and run them.

        This is the main entry point for the scheduling loop.

        Returns:
            List of result dicts from run_scheduled_agent.
        """
        due_schedules = self.get_due_schedules()
        if not due_schedules:
            return []

        logger.info(f"Found {len(due_schedules)} due schedule(s)")

        results = []
        for schedule in due_schedules:
            result = await self.run_scheduled_agent(schedule)
            results.append(result)

        return results

    async def _run_loop(self, interval_seconds: int) -> None:
        """Background loop that checks and runs due schedules.

        Args:
            interval_seconds: Seconds between checks.
        """
        logger.info(f"Scheduler loop started (interval={interval_seconds}s)")

        while self._running:
            try:
                await self.check_and_run()
            except (OSError, RuntimeError) as e:
                logger.error(f"Error in scheduler loop: {e}")

            # Wait for next check or stop signal
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._stop_event.wait, interval_seconds),
                    timeout=interval_seconds,
                )
                # Stop event was set
                break
            except TimeoutError:
                # Normal timeout, continue loop
                pass

        logger.info("Scheduler loop stopped")

    def start(self) -> None:
        """Start the background scheduling loop.

        Uses scheduler_interval_seconds from AgentConfig.
        """
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._stop_event.clear()

        # Start the loop in the current event loop
        try:
            loop = asyncio.get_running_loop()
            self._loop_task = loop.create_task(self._run_loop(self.scheduler_interval_seconds))
        except RuntimeError:
            # No running loop - caller will need to run it manually
            logger.warning("No running event loop - scheduler loop not started automatically")

        logger.info(f"Scheduler started (interval={self.scheduler_interval_seconds}s)")

    def stop(self) -> None:
        """Stop the background scheduling loop with timeout.

        Waits up to SCHEDULER_STOP_TIMEOUT_SECONDS for clean shutdown.
        """
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            # Wait for task to complete with timeout
            try:
                # Use a synchronous wait with timeout since stop() is sync
                import time

                deadline = time.monotonic() + SCHEDULER_STOP_TIMEOUT_SECONDS
                while not self._loop_task.done() and time.monotonic() < deadline:
                    time.sleep(0.1)

                if not self._loop_task.done():
                    logger.warning(
                        f"Scheduler task did not stop within {SCHEDULER_STOP_TIMEOUT_SECONDS}s"
                    )
            except (RuntimeError, OSError) as e:
                logger.warning(f"Error waiting for scheduler task: {e}")
            finally:
                self._loop_task = None

        logger.info("Scheduler stopped")

    def get_schedule_status(self, task_name: str) -> dict[str, Any] | None:
        """Get the schedule status for a task.

        Returns schedule info from database. YAML is no longer consulted.

        Args:
            task_name: Name of the agent task.

        Returns:
            Schedule status dict, or None if no schedule.
        """
        db_schedule = self._activity_store.get_schedule(task_name)

        if db_schedule is None:
            return None

        # Check if task exists in registry
        task = self._agent_registry.get_task(task_name)

        return {
            "task_name": task_name,
            "has_definition": db_schedule.get("cron_expression") is not None,
            "has_db_record": True,
            "has_task": task is not None,
            "cron": db_schedule.get("cron_expression"),
            "description": db_schedule.get("description"),
            "trigger_type": db_schedule.get("trigger_type", SCHEDULE_TRIGGER_CRON),
            "additional_prompt": db_schedule.get("additional_prompt"),
            "enabled": db_schedule.get("enabled"),
            "last_run_at": db_schedule.get("last_run_at"),
            "last_run_id": db_schedule.get("last_run_id"),
            "next_run_at": db_schedule.get("next_run_at"),
        }

    def list_schedule_statuses(self) -> list[dict[str, Any]]:
        """List schedule statuses for all schedules.

        Returns:
            List of schedule status dicts (from database only).
        """
        # Get all database schedules (database is source of truth)
        db_schedules = self._activity_store.list_schedules()

        # Build status list
        results = []
        for db_schedule in db_schedules:
            task_name = db_schedule["task_name"]
            task = self._agent_registry.get_task(task_name)

            results.append(
                {
                    "task_name": task_name,
                    "has_definition": db_schedule.get("cron_expression") is not None,
                    "has_db_record": True,
                    "has_task": task is not None,
                    "cron": db_schedule.get("cron_expression"),
                    "description": db_schedule.get("description"),
                    "trigger_type": db_schedule.get("trigger_type", SCHEDULE_TRIGGER_CRON),
                    "additional_prompt": db_schedule.get("additional_prompt"),
                    "enabled": db_schedule.get("enabled"),
                    "last_run_at": db_schedule.get("last_run_at"),
                    "last_run_id": db_schedule.get("last_run_id"),
                    "next_run_at": db_schedule.get("next_run_at"),
                }
            )

        return sorted(results, key=lambda x: x["task_name"])

    def to_dict(self) -> dict[str, Any]:
        """Convert scheduler state to dictionary for API responses.

        Returns:
            Dictionary with scheduler statistics.
        """
        statuses = self.list_schedule_statuses()

        return {
            "running": self._running,
            "total_schedules": len(statuses),
            "enabled_schedules": sum(1 for s in statuses if s.get("enabled", False)),
            "schedules": statuses,
        }
