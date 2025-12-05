"""Research operations mixin for PlanService.

This module provides research phase operations as a mixin class.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from open_agent_kit.models.plan import ResearchFinding, ResearchTopic
from open_agent_kit.services.plan.exceptions import PlanServiceError
from open_agent_kit.services.plan.rendering import render_research_findings
from open_agent_kit.utils import ensure_dir

if TYPE_CHECKING:
    from open_agent_kit.models.plan import Plan


class ResearchOperationsMixin:
    """Mixin providing research phase operations.

    This mixin is designed to be used with PlanService. It expects
    the following methods/attributes to be available on self:
    - load_plan(plan_name) -> Plan
    - update_plan(plan_name, plan) -> None
    - get_research_dir(plan_name) -> Path
    - get_research_file_path(plan_name, topic_slug) -> Path
    - get_plan_dir(plan_name) -> Path
    """

    def get_research_topics(self, plan_name: str) -> list[ResearchTopic]:
        """Get research topics from plan.

        Args:
            plan_name: URL-safe plan name

        Returns:
            List of ResearchTopic objects
        """
        plan: Plan = self.load_plan(plan_name)  # type: ignore[attr-defined]
        return plan.research_topics

    def add_research_topic(self, plan_name: str, topic: ResearchTopic) -> None:
        """Add a research topic to the plan.

        Args:
            plan_name: URL-safe plan name
            topic: ResearchTopic to add

        Raises:
            PlanServiceError: If topic slug already exists
        """
        plan: Plan = self.load_plan(plan_name)  # type: ignore[attr-defined]

        # Check for duplicate slugs
        existing_slugs = {t.slug for t in plan.research_topics}
        if topic.slug in existing_slugs:
            raise PlanServiceError(f"Research topic already exists: {topic.slug}")

        plan.research_topics.append(topic)
        self.update_plan(plan_name, plan)  # type: ignore[attr-defined]

    def update_research_topic_status(self, plan_name: str, topic_slug: str, status: str) -> None:
        """Update status of a research topic.

        Args:
            plan_name: URL-safe plan name
            topic_slug: Topic identifier
            status: New status (pending, in_progress, completed, skipped)

        Raises:
            PlanServiceError: If topic not found
        """
        plan: Plan = self.load_plan(plan_name)  # type: ignore[attr-defined]

        for topic in plan.research_topics:
            if topic.slug == topic_slug:
                topic.status = status
                break
        else:
            raise PlanServiceError(f"Research topic not found: {topic_slug}")

        self.update_plan(plan_name, plan)  # type: ignore[attr-defined]

    def write_research_findings(
        self, plan_name: str, topic_slug: str, findings: ResearchFinding
    ) -> Path:
        """Write research findings for a topic.

        Args:
            plan_name: URL-safe plan name
            topic_slug: Topic identifier
            findings: ResearchFinding object

        Returns:
            Path to created findings file
        """
        research_dir: Path = self.get_research_dir(plan_name)  # type: ignore[attr-defined]
        ensure_dir(research_dir)

        findings_path: Path = self.get_research_file_path(  # type: ignore[attr-defined]
            plan_name, topic_slug
        )
        content = render_research_findings(findings)
        findings_path.write_text(content, encoding="utf-8")

        # Update topic status and findings path
        plan: Plan = self.load_plan(plan_name)  # type: ignore[attr-defined]
        plan_dir: Path = self.get_plan_dir(plan_name)  # type: ignore[attr-defined]

        for topic in plan.research_topics:
            if topic.slug == topic_slug:
                topic.status = "completed"
                topic.findings_path = str(findings_path.relative_to(plan_dir))
                break

        self.update_plan(plan_name, plan)  # type: ignore[attr-defined]

        return findings_path

    def load_research_findings(self, plan_name: str, topic_slug: str) -> str:
        """Load research findings content.

        Args:
            plan_name: URL-safe plan name
            topic_slug: Topic identifier

        Returns:
            Findings markdown content

        Raises:
            FileNotFoundError: If findings file doesn't exist
        """
        findings_path: Path = self.get_research_file_path(  # type: ignore[attr-defined]
            plan_name, topic_slug
        )
        if not findings_path.exists():
            raise FileNotFoundError(f"Research findings not found: {topic_slug}")
        return findings_path.read_text(encoding="utf-8")

    def get_research_status(self, plan_name: str) -> dict[str, Any]:
        """Get research completion status.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Dictionary with research status:
            {
                'total': int,
                'completed': int,
                'pending': int,
                'in_progress': int,
                'skipped': int,
                'topics': list[dict]
            }
        """
        topics = self.get_research_topics(plan_name)

        topic_list: list[dict[str, Any]] = []
        completed = 0
        pending = 0
        in_progress = 0
        skipped = 0

        for topic in topics:
            topic_info: dict[str, Any] = {
                "slug": topic.slug,
                "title": topic.title,
                "status": topic.status,
                "priority": topic.priority,
                "has_findings": topic.findings_path is not None,
            }
            topic_list.append(topic_info)

            if topic.status == "completed":
                completed += 1
            elif topic.status == "in_progress":
                in_progress += 1
            elif topic.status == "skipped":
                skipped += 1
            else:
                pending += 1

        return {
            "total": len(topics),
            "completed": completed,
            "pending": pending,
            "in_progress": in_progress,
            "skipped": skipped,
            "topics": topic_list,
        }
