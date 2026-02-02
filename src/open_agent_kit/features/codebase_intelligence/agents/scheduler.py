"""Agent Scheduler for cron-based agent execution.

This module provides the AgentScheduler class that manages scheduled agent runs:
- Syncs schedule definitions from YAML to database runtime state
- Computes next run times from cron expressions
- Checks for and executes due schedules
- Background scheduling loop
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
    SCHEDULER_STOP_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.config import AgentConfig

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Scheduler for cron-based agent execution.

    The scheduler:
    - Syncs schedule definitions from AgentRegistry (YAML) to ActivityStore (SQLite)
    - Computes next run times using croniter
    - Periodically checks for and runs due schedules
    - Tracks run history via AgentExecutor

    YAML defines the schedule (cron expression + description).
    Database tracks runtime state (enabled, last_run, next_run).

    Attributes:
        activity_store: ActivityStore for schedule persistence.
        agent_registry: AgentRegistry for loading instance definitions.
        agent_executor: AgentExecutor for running agents.
    """

    def __init__(
        self,
        activity_store: "ActivityStore",
        agent_registry: "AgentRegistry",
        agent_executor: "AgentExecutor",
        agent_config: "AgentConfig",
    ):
        """Initialize the scheduler.

        Args:
            activity_store: ActivityStore for schedule persistence.
            agent_registry: AgentRegistry for loading instance definitions.
            agent_executor: AgentExecutor for running agents.
            agent_config: AgentConfig with scheduler settings.
        """
        self._activity_store = activity_store
        self._agent_registry = agent_registry
        self._agent_executor = agent_executor
        self._agent_config = agent_config

        # Background loop control
        self._running = False
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = threading.Event()

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

    def sync_schedules(self) -> dict[str, Any]:
        """Sync schedule definitions from YAML to database.

        For each instance with a schedule defined:
        - Creates schedule record if it doesn't exist
        - Computes next_run_at from cron expression if missing
        - Does NOT overwrite enabled state (user-controlled)

        Returns:
            Summary dict with counts of created/updated/removed schedules.
        """
        # Get all instances with schedules from registry
        instances = self._agent_registry.list_instances()
        scheduled_instances = {i.name: i for i in instances if i.schedule}

        # Get all existing schedules from database
        existing_schedules = {s["instance_name"]: s for s in self._activity_store.list_schedules()}

        created = 0
        updated = 0
        removed = 0

        # Create or update schedules for instances with schedule definitions
        for instance_name, instance in scheduled_instances.items():
            if instance.schedule is None:
                continue

            existing = existing_schedules.get(instance_name)

            if existing is None:
                # Create new schedule
                try:
                    next_run = self.compute_next_run(instance.schedule.cron)
                    self._activity_store.create_schedule(instance_name, next_run)
                    created += 1
                    logger.info(
                        f"Created schedule for '{instance_name}': "
                        f"cron={instance.schedule.cron}, next_run={next_run}"
                    )
                except ValueError as e:
                    logger.error(f"Failed to create schedule for '{instance_name}': {e}")
            else:
                # Update next_run if it's missing or in the past
                if existing["next_run_at_epoch"] is None:
                    try:
                        next_run = self.compute_next_run(instance.schedule.cron)
                        self._activity_store.update_schedule(instance_name, next_run_at=next_run)
                        updated += 1
                        logger.debug(f"Updated next_run for '{instance_name}': {next_run}")
                    except ValueError as e:
                        logger.error(f"Failed to update schedule for '{instance_name}': {e}")

        # Remove schedules for instances that no longer have schedule definitions
        for instance_name in existing_schedules:
            if instance_name not in scheduled_instances:
                self._activity_store.delete_schedule(instance_name)
                removed += 1
                logger.info(f"Removed orphaned schedule for '{instance_name}'")

        result = {
            "created": created,
            "updated": updated,
            "removed": removed,
            "total": len(scheduled_instances),
        }

        logger.info(
            f"Schedule sync complete: {created} created, {updated} updated, "
            f"{removed} removed, {len(scheduled_instances)} total"
        )

        return result

    def get_due_schedules(self) -> list[dict[str, Any]]:
        """Get schedules that are due to run.

        Returns:
            List of schedule records where enabled=1 and next_run_at <= now.
        """
        return self._activity_store.get_due_schedules()

    def _is_instance_running(self, instance_name: str) -> bool:
        """Check if an agent instance already has an active run.

        Used to prevent overlapping scheduled executions of the same agent.

        Args:
            instance_name: Name of the agent instance.

        Returns:
            True if instance has a run in RUNNING status.
        """
        runs, _ = self._activity_store.list_agent_runs(
            agent_name=instance_name,
            status="running",
            limit=1,
        )
        return len(runs) > 0

    async def run_scheduled_agent(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Run a scheduled agent and update schedule state.

        Prevents concurrent execution of the same agent instance. If an instance
        is already running, the scheduled run is skipped.

        Args:
            schedule: Schedule record from database.

        Returns:
            Result dict with run_id, status, and any error.
        """
        instance_name = schedule["instance_name"]
        result: dict[str, Any] = {"instance_name": instance_name}

        # Check for concurrent execution - skip if already running
        if self._is_instance_running(instance_name):
            result["skipped"] = True
            result["reason"] = "already_running"
            logger.warning(f"Skipping scheduled run for '{instance_name}' - already running")
            return result

        # Get the instance and its template
        instance = self._agent_registry.get_instance(instance_name)
        if instance is None:
            result["error"] = f"Instance '{instance_name}' not found"
            logger.error(result["error"])
            return result

        template = self._agent_registry.get_template(instance.agent_type)
        if template is None:
            result["error"] = (
                f"Template '{instance.agent_type}' not found for instance '{instance_name}'"
            )
            logger.error(result["error"])
            return result

        logger.info(f"Running scheduled agent: {instance_name}")

        try:
            # Execute the agent
            run = await self._agent_executor.execute(
                agent=template,
                task=instance.default_task,
                instance=instance,
            )

            result["run_id"] = run.id
            result["status"] = run.status.value

            # Update schedule with run info
            now = datetime.now()

            # Compute next run time
            if instance.schedule:
                try:
                    next_run = self.compute_next_run(instance.schedule.cron, after=now)
                except ValueError:
                    next_run = None
            else:
                next_run = None

            self._activity_store.update_schedule(
                instance_name,
                last_run_at=now,
                last_run_id=run.id,
                next_run_at=next_run,
            )

            if run.status == AgentRunStatus.COMPLETED:
                logger.info(f"Scheduled agent '{instance_name}' completed: run_id={run.id}")
            else:
                result["error"] = run.error
                logger.warning(
                    f"Scheduled agent '{instance_name}' finished with status {run.status}: "
                    f"run_id={run.id}, error={run.error}"
                )

        except (OSError, RuntimeError, ValueError) as e:
            result["error"] = str(e)
            logger.error(f"Failed to run scheduled agent '{instance_name}': {e}")

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

    def get_schedule_status(self, instance_name: str) -> dict[str, Any] | None:
        """Get the schedule status for an instance.

        Returns combined info from YAML definition and database state.

        Args:
            instance_name: Name of the agent instance.

        Returns:
            Schedule status dict, or None if no schedule.
        """
        instance = self._agent_registry.get_instance(instance_name)
        db_schedule = self._activity_store.get_schedule(instance_name)

        if instance is None and db_schedule is None:
            return None

        result: dict[str, Any] = {
            "instance_name": instance_name,
            "has_definition": instance is not None and instance.schedule is not None,
            "has_db_record": db_schedule is not None,
        }

        # Add definition info
        if instance and instance.schedule:
            result["cron"] = instance.schedule.cron
            result["description"] = instance.schedule.description

        # Add runtime state
        if db_schedule:
            result["enabled"] = db_schedule["enabled"]
            result["last_run_at"] = db_schedule["last_run_at"]
            result["last_run_id"] = db_schedule["last_run_id"]
            result["next_run_at"] = db_schedule["next_run_at"]

        return result

    def list_schedule_statuses(self) -> list[dict[str, Any]]:
        """List schedule statuses for all instances.

        Returns:
            List of schedule status dicts.
        """
        # Get all instances with schedules
        instances = self._agent_registry.list_instances()
        scheduled_instances = {i.name: i for i in instances if i.schedule}

        # Get all database schedules
        db_schedules = {s["instance_name"]: s for s in self._activity_store.list_schedules()}

        # Build combined list
        all_names = set(scheduled_instances.keys()) | set(db_schedules.keys())
        results = []

        for name in sorted(all_names):
            status = self.get_schedule_status(name)
            if status:
                results.append(status)

        return results

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
