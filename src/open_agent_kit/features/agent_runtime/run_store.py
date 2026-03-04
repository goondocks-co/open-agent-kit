"""In-memory + SQLite run tracking for agent executions.

Provides ``RunStore`` which manages the lifecycle of ``AgentRun`` records:
create, get, list, cancel, persist.  Extracted from ``AgentExecutor`` so
the executor focuses on SDK orchestration.
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from open_agent_kit.features.agent_runtime.models import (
    AgentDefinition,
    AgentRun,
    AgentRunStatus,
    AgentTask,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store import ActivityStore

logger = logging.getLogger(__name__)


class RunStore:
    """Thread-safe run record store backed by in-memory cache and optional SQLite.

    Attributes:
        max_cache_size: Maximum number of runs kept in memory.
    """

    def __init__(
        self,
        activity_store: ActivityStore | None,
        max_cache_size: int = 100,
    ) -> None:
        self._activity_store = activity_store
        self.max_cache_size = max_cache_size
        self._runs: OrderedDict[str, AgentRun] = OrderedDict()
        self._lock = RLock()

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    @property
    def runs(self) -> dict[str, AgentRun]:
        """Get all cached run records (copy for thread safety)."""
        with self._lock:
            return dict(self._runs)

    def create(
        self,
        agent: AgentDefinition,
        task: str,
        agent_task: AgentTask | None = None,
    ) -> AgentRun:
        """Create a new run record, persisting to SQLite if available."""
        agent_name = agent_task.name if agent_task else agent.name

        run = AgentRun(
            id=str(uuid4()),
            agent_name=agent_name,
            task=task,
            status=AgentRunStatus.PENDING,
            created_at=datetime.now(),
        )

        if self._activity_store:
            system_prompt_hash = None
            if agent.system_prompt:
                system_prompt_hash = hashlib.sha256(agent.system_prompt.encode()).hexdigest()[:16]

            project_config = None
            if agent_task:
                project_config = {
                    "task_name": agent_task.name,
                    "agent_type": agent_task.agent_type,
                    "maintained_files": [
                        mf.model_dump(exclude_none=True) for mf in agent_task.maintained_files
                    ],
                    "oak_queries": {
                        phase: [q.model_dump(exclude_none=True) for q in queries]
                        for phase, queries in agent_task.oak_queries.items()
                    },
                }
            elif agent.project_config:
                project_config = agent.project_config

            self._activity_store.create_agent_run(
                run_id=run.id,
                agent_name=run.agent_name,
                task=run.task,
                status=run.status.value,
                project_config=project_config,
                system_prompt_hash=system_prompt_hash,
            )

        with self._lock:
            self._runs[run.id] = run
            self._cleanup_old()

        return run

    def get(self, run_id: str) -> AgentRun | None:
        """Get a run by ID (cache first, then SQLite)."""
        with self._lock:
            if run_id in self._runs:
                return self._runs[run_id]

        if self._activity_store:
            data = self._activity_store.get_agent_run(run_id)
            if data:
                return self._dict_to_run(data)

        return None

    def list(
        self,
        limit: int = 20,
        offset: int = 0,
        agent_name: str | None = None,
        status: AgentRunStatus | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[AgentRun], int]:
        """List runs with optional filtering and sorting."""
        if self._activity_store:
            status_str = status.value if status else None
            created_after_epoch = int(created_after.timestamp()) if created_after else None
            created_before_epoch = int(created_before.timestamp()) if created_before else None
            data_list, total = self._activity_store.list_agent_runs(
                limit=limit,
                offset=offset,
                agent_name=agent_name,
                status=status_str,
                created_after_epoch=created_after_epoch,
                created_before_epoch=created_before_epoch,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            return [self._dict_to_run(d) for d in data_list], total

        # Fall back to in-memory
        with self._lock:
            runs = list(self._runs.values())
            if agent_name:
                runs = [r for r in runs if r.agent_name == agent_name]
            if status:
                runs = [r for r in runs if r.status == status]
            if created_after:
                runs = [r for r in runs if r.created_at >= created_after]
            if created_before:
                runs = [r for r in runs if r.created_at < created_before]

            reverse = sort_order.lower() == "desc"
            if sort_by == "duration":
                runs.sort(key=lambda r: r.duration_seconds or 0, reverse=reverse)
            elif sort_by == "cost":
                runs.sort(key=lambda r: r.cost_usd or 0, reverse=reverse)
            else:
                runs.sort(key=lambda r: r.created_at, reverse=reverse)

            total = len(runs)
            return runs[offset : offset + limit], total

    def persist_completion(self, run: AgentRun) -> None:
        """Persist run completion state to SQLite."""
        if not self._activity_store:
            return

        self._activity_store.update_agent_run(
            run_id=run.id,
            status=run.status.value,
            completed_at=run.completed_at,
            result=run.result,
            error=run.error,
            turns_used=run.turns_used,
            cost_usd=run.cost_usd,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            files_created=run.files_created if run.files_created else None,
            files_modified=run.files_modified if run.files_modified else None,
            files_deleted=run.files_deleted if run.files_deleted else None,
            warnings=run.warnings if run.warnings else None,
        )

    def cancel(self, run_id: str) -> bool:
        """Cancel a running agent. Returns True if cancellation was initiated."""
        run = self.get(run_id)
        if not run or run.is_terminal():
            return False

        run.status = AgentRunStatus.CANCELLED
        run.error = "Cancelled by user"
        run.completed_at = datetime.now()
        self.persist_completion(run)

        logger.info(f"Agent run {run_id} cancelled")
        return True

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _cleanup_old(self) -> None:
        """Remove old runs when cache exceeds threshold."""
        with self._lock:
            if len(self._runs) <= self.max_cache_size:
                return

            items = list(self._runs.items())
            to_remove = len(items) - self.max_cache_size
            for i in range(to_remove):
                run_id = items[i][0]
                del self._runs[run_id]
                logger.debug(f"Cleaned up old run from cache: {run_id}")

    @staticmethod
    def _dict_to_run(data: dict[str, Any]) -> AgentRun:
        """Convert a database row dict to AgentRun model."""
        return AgentRun(
            id=data["id"],
            agent_name=data["agent_name"],
            task=data["task"],
            status=AgentRunStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
            ),
            result=data.get("result"),
            error=data.get("error"),
            turns_used=data.get("turns_used", 0),
            cost_usd=data.get("cost_usd"),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            files_created=data.get("files_created") or [],
            files_modified=data.get("files_modified") or [],
            files_deleted=data.get("files_deleted") or [],
        )
