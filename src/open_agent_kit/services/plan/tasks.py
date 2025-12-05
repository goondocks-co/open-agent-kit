"""Task operations mixin for PlanService.

This module provides task management operations as a mixin class.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.models.plan import PlanStatus, PlanTask
from open_agent_kit.services.plan.exceptions import PlanServiceError
from open_agent_kit.services.plan.rendering import render_tasks

if TYPE_CHECKING:
    from open_agent_kit.models.plan import Plan


class TaskOperationsMixin:
    """Mixin providing task management operations.

    This mixin is designed to be used with PlanService. It expects
    the following methods/attributes to be available on self:
    - load_plan(plan_name) -> Plan
    - update_plan(plan_name, plan) -> None
    - update_plan_status(plan_name, status) -> PlanManifest
    - get_tasks_file_path(plan_name) -> Path
    """

    def write_tasks(self, plan_name: str, tasks: list[PlanTask]) -> Path:
        """Write tasks to tasks.md.

        Args:
            plan_name: URL-safe plan name
            tasks: List of PlanTask objects

        Returns:
            Path to tasks.md file
        """
        plan: Plan = self.load_plan(plan_name)  # type: ignore[attr-defined]
        plan.tasks = tasks

        # Update plan with tasks
        self.update_plan(plan_name, plan)  # type: ignore[attr-defined]

        # Write tasks.md
        tasks_path: Path = self.get_tasks_file_path(plan_name)  # type: ignore[attr-defined]
        content = render_tasks(plan.manifest.display_name, tasks)
        tasks_path.write_text(content, encoding="utf-8")

        # Update status if not already at READY or beyond
        if plan.manifest.status in (PlanStatus.DRAFT, PlanStatus.RESEARCHING, PlanStatus.PLANNING):
            self.update_plan_status(plan_name, PlanStatus.READY)  # type: ignore[attr-defined]

        return tasks_path

    def load_tasks(self, plan_name: str) -> list[PlanTask]:
        """Load tasks from plan.

        Args:
            plan_name: URL-safe plan name

        Returns:
            List of PlanTask objects
        """
        plan: Plan = self.load_plan(plan_name)  # type: ignore[attr-defined]
        return plan.tasks

    def update_task_issue_link(
        self, plan_name: str, task_id: str, issue_id: str, issue_link: str
    ) -> None:
        """Update task with issue export information.

        Args:
            plan_name: URL-safe plan name
            task_id: Task identifier
            issue_id: Provider issue ID
            issue_link: URL to created issue

        Raises:
            PlanServiceError: If task not found
        """
        plan: Plan = self.load_plan(plan_name)  # type: ignore[attr-defined]

        for task in plan.tasks:
            if task.id == task_id:
                task.issue_id = issue_id
                task.issue_link = issue_link
                break
        else:
            raise PlanServiceError(f"Task not found: {task_id}")

        self.update_plan(plan_name, plan)  # type: ignore[attr-defined]

        # Refresh tasks.md with issue links
        tasks_path: Path = self.get_tasks_file_path(plan_name)  # type: ignore[attr-defined]
        content = render_tasks(plan.manifest.display_name, plan.tasks)
        tasks_path.write_text(content, encoding="utf-8")
