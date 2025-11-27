"""Plan synthesis from TaskCreate activities.

Extracts derived plans from sessions that have TaskCreate activities
but no explicit plan file. This captures implementation intent even when:
- The plan file wasn't re-sent after "clear context"
- Auto-compact removed the original plan from context
- The agent decomposed the plan internally before starting work

Tasks are a resilient tracking mechanism because:
1. Structured data - Subject, description, status, dependencies are explicit fields
2. Survives compaction - Task list is compact; plan prose gets summarized/lost
3. Agent convergence - Multiple agents (Claude, Cursor) are adopting task tracking
4. Incremental progress - Each TaskUpdate is a checkpoint
5. Dependency graphs - addBlocks/addBlockedBy encode relationships
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    PROMPT_SOURCE_DERIVED_PLAN,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        Activity,
        ActivityStore,
        PromptBatch,
    )

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTask:
    """A task extracted from TaskCreate activity."""

    task_id: str
    subject: str
    description: str = ""
    status: str = "pending"
    blocks: list[str] = field(default_factory=list)  # Tasks this blocks
    blocked_by: list[str] = field(default_factory=list)  # Tasks blocking this
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DerivedPlan:
    """A plan synthesized from task activities."""

    session_id: str
    tasks: list[ExtractedTask]
    created_at: datetime = field(default_factory=datetime.now)

    def to_markdown(self) -> str:
        """Format the derived plan as markdown.

        Returns:
            Markdown-formatted plan content.
        """
        if not self.tasks:
            return ""

        lines = [
            "# Derived Plan (from TaskCreate activities)",
            "",
            f"*Synthesized at: {self.created_at.isoformat()}*",
            "",
            "## Tasks",
            "",
        ]

        # Find root tasks (not blocked by anything)
        root_tasks = [t for t in self.tasks if not t.blocked_by]
        other_tasks = [t for t in self.tasks if t.blocked_by]

        def format_task(task: ExtractedTask, indent: int = 0) -> list[str]:
            prefix = "  " * indent
            task_lines = [f"{prefix}- **{task.subject}**"]

            if task.description:
                # Indent description and truncate if too long
                desc = task.description[:500]
                if len(task.description) > 500:
                    desc += "..."
                task_lines.append(f"{prefix}  {desc}")

            if task.blocked_by:
                blockers = ", ".join(f"#{bid}" for bid in task.blocked_by)
                task_lines.append(f"{prefix}  *Blocked by: {blockers}*")

            return task_lines

        # Format root tasks first
        for task in root_tasks:
            lines.extend(format_task(task))
            lines.append("")

        # Then format dependent tasks
        if other_tasks:
            lines.append("### Dependent Tasks")
            lines.append("")
            for task in other_tasks:
                lines.extend(format_task(task))
                lines.append("")

        # Add dependency summary if there are dependencies
        has_deps = any(t.blocks or t.blocked_by for t in self.tasks)
        if has_deps:
            lines.append("## Dependency Graph")
            lines.append("")
            for task in self.tasks:
                if task.blocks:
                    blocks_str = ", ".join(f"#{bid}" for bid in task.blocks)
                    lines.append(f"- #{task.task_id} blocks: {blocks_str}")
            lines.append("")

        return "\n".join(lines)


def extract_tasks_from_activities(activities: list[Activity]) -> list[ExtractedTask]:
    """Extract task information from TaskCreate and TaskUpdate activities.

    Args:
        activities: List of activities to process.

    Returns:
        List of extracted tasks with their dependencies.
    """
    tasks_by_id: dict[str, ExtractedTask] = {}

    for activity in activities:
        if activity.tool_name not in ("TaskCreate", "TaskUpdate"):
            continue

        tool_input = activity.tool_input or {}

        # Handle TaskCreate
        if activity.tool_name == "TaskCreate":
            # Extract task_id from output if available
            task_id = ""
            if activity.tool_output_summary:
                # Try to parse task ID from output like "Task #1 created successfully"
                output = activity.tool_output_summary
                if "Task #" in output:
                    try:
                        start = output.index("Task #") + 6
                        end = output.index(" ", start)
                        task_id = output[start:end]
                    except (ValueError, IndexError):
                        pass

            if not task_id:
                # Generate a temporary ID
                task_id = f"temp_{len(tasks_by_id) + 1}"

            task = ExtractedTask(
                task_id=task_id,
                subject=tool_input.get("subject", ""),
                description=tool_input.get("description", ""),
                metadata=tool_input.get("metadata", {}),
            )
            tasks_by_id[task_id] = task

        # Handle TaskUpdate (for dependencies)
        elif activity.tool_name == "TaskUpdate":
            task_id = tool_input.get("taskId", "")
            if not task_id:
                continue

            # Create task if not seen before
            if task_id not in tasks_by_id:
                tasks_by_id[task_id] = ExtractedTask(
                    task_id=task_id,
                    subject=tool_input.get("subject", f"Task #{task_id}"),
                )

            task = tasks_by_id[task_id]

            # Update with any new info
            if tool_input.get("subject"):
                task.subject = tool_input["subject"]
            if tool_input.get("description"):
                task.description = tool_input["description"]
            if tool_input.get("status"):
                task.status = tool_input["status"]

            # Handle dependencies
            if tool_input.get("addBlocks"):
                for blocked_id in tool_input["addBlocks"]:
                    if blocked_id not in task.blocks:
                        task.blocks.append(blocked_id)
            if tool_input.get("addBlockedBy"):
                for blocker_id in tool_input["addBlockedBy"]:
                    if blocker_id not in task.blocked_by:
                        task.blocked_by.append(blocker_id)

    return list(tasks_by_id.values())


def synthesize_derived_plan(
    session_id: str,
    activities: list[Activity],
) -> DerivedPlan | None:
    """Synthesize a derived plan from TaskCreate activities.

    Args:
        session_id: Session to synthesize plan for.
        activities: Activities to extract tasks from.

    Returns:
        DerivedPlan if tasks found, None otherwise.
    """
    tasks = extract_tasks_from_activities(activities)

    if not tasks:
        return None

    plan = DerivedPlan(
        session_id=session_id,
        tasks=tasks,
    )

    logger.debug(
        f"Synthesized derived plan for session {session_id[:8]}...: "
        f"{len(tasks)} tasks extracted"
    )

    return plan


def should_synthesize_plan(
    batch: PromptBatch,
    activities: list[Activity],
) -> bool:
    """Determine if we should synthesize a derived plan for this batch.

    Conditions for synthesis:
    1. Batch has TaskCreate activities
    2. Batch does NOT already have an explicit plan (source_type != 'plan')
    3. There's meaningful task content (not just status updates)

    Args:
        batch: The prompt batch to check.
        activities: Activities in the batch.

    Returns:
        True if we should synthesize a plan.
    """
    # Don't synthesize if already a plan
    if batch.source_type == "plan":
        return False

    # Don't synthesize if already a derived plan
    if batch.source_type == PROMPT_SOURCE_DERIVED_PLAN:
        return False

    # Check for TaskCreate activities with meaningful content
    for activity in activities:
        if activity.tool_name == "TaskCreate":
            tool_input = activity.tool_input or {}
            # Only synthesize if there's a real subject/description
            if tool_input.get("subject") and len(tool_input.get("subject", "")) > 5:
                return True

    return False


def store_derived_plan(
    activity_store: ActivityStore,
    batch_id: int,
    plan: DerivedPlan,
) -> None:
    """Store a derived plan in the database.

    Updates the batch with:
    - source_type = 'derived_plan'
    - plan_content = markdown representation of tasks

    Args:
        activity_store: Activity store instance.
        batch_id: Batch to update.
        plan: Derived plan to store.
    """
    plan_content = plan.to_markdown()

    with activity_store._transaction() as conn:
        conn.execute(
            """
            UPDATE prompt_batches
            SET source_type = ?, plan_content = ?
            WHERE id = ?
            """,
            (PROMPT_SOURCE_DERIVED_PLAN, plan_content, batch_id),
        )

    logger.info(
        f"Stored derived plan for batch {batch_id}: "
        f"{len(plan.tasks)} tasks, {len(plan_content)} chars"
    )
