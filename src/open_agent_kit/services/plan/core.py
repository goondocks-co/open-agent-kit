"""Core PlanService class.

This module provides the main PlanService class that orchestrates
strategic planning workflows including plan creation, research,
task management, and issue export.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from open_agent_kit.config.messages import PLAN_ERROR_MESSAGES
from open_agent_kit.config.paths import (
    CONSTITUTION_FILENAME,
    PLAN_BRANCH_PREFIX,
    PLAN_DATA_FILENAME,
    PLAN_FILE_FILENAME,
    PLAN_ISSUE_CONTEXT_FILENAME,
    PLAN_ISSUE_DIR,
    PLAN_ISSUE_RELATED_DIR,
    PLAN_ISSUE_SUMMARY_FILENAME,
    PLAN_MANIFEST_FILENAME,
    PLAN_RESEARCH_DIR,
    PLAN_TASKS_FILENAME,
)
from open_agent_kit.config.settings import git_settings
from open_agent_kit.models.issue import Issue
from open_agent_kit.models.plan import (
    IssueReference,
    Plan,
    PlanManifest,
    PlanSource,
    PlanStatus,
    PlanTask,
    ResearchDepth,
    ResearchTopic,
)
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.issue_providers.base import IssueProviderError
from open_agent_kit.services.plan.exceptions import PlanServiceError
from open_agent_kit.services.plan.export import ExportOperationsMixin
from open_agent_kit.services.plan.parsing import parse_plan_file
from open_agent_kit.services.plan.rendering import render_issue_plan, render_plan_file
from open_agent_kit.services.plan.research import ResearchOperationsMixin
from open_agent_kit.services.plan.tasks import TaskOperationsMixin
from open_agent_kit.utils import ensure_dir, sanitize_filename


class PlanService(ResearchOperationsMixin, TaskOperationsMixin, ExportOperationsMixin):
    """High-level orchestration for strategic planning workflows.

    This service provides the main interface for:
    - Creating idea-first and issue-first plans
    - Managing research phases
    - Generating and tracking tasks
    - Exporting to issue providers (GitHub, Azure DevOps)
    - Git branch management

    Example:
        >>> service = PlanService(project_root=Path.cwd())
        >>> manifest = service.create_plan("auth-redesign", "Authentication Redesign")
        >>> service.write_research_findings("auth-redesign", "oauth-patterns", findings)
        >>> service.update_plan_status("auth-redesign", PlanStatus.READY)
    """

    def __init__(
        self, project_root: Path | None = None, environment: Mapping[str, str] | None = None
    ) -> None:
        """Initialize plan service.

        Args:
            project_root: Project root directory (defaults to current directory)
            environment: Environment variables (defaults to os.environ)
        """
        self.project_root = project_root or Path.cwd()
        self.environment = environment or os.environ
        self.config_service = ConfigService(project_root)

    # -------------------------------------------------------------------------
    # Prerequisite validation
    # -------------------------------------------------------------------------
    def check_constitution_exists(self) -> bool:
        """Check if constitution exists (required dependency).

        Returns:
            True if constitution file exists at configured location
        """
        constitution_dir = self.config_service.get_constitution_dir()
        constitution_path = constitution_dir / CONSTITUTION_FILENAME
        return constitution_path.exists()

    def validate_prerequisites(self) -> list[str]:
        """Validate all prerequisites for plan feature.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        if not self.check_constitution_exists():
            errors.append(PLAN_ERROR_MESSAGES["constitution_required"])
        return errors

    # -------------------------------------------------------------------------
    # Directory and path management
    # -------------------------------------------------------------------------
    def ensure_plan_dir(self) -> Path:
        """Ensure plan artifacts directory exists.

        Returns:
            Path to plan directory
        """
        plan_dir = self.config_service.get_plan_dir()
        ensure_dir(plan_dir)
        return plan_dir

    def get_plan_dir(self, plan_name: str) -> Path:
        """Get directory for a specific plan.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to plan directory
        """
        plan_dir = self.ensure_plan_dir()
        safe_name = sanitize_filename(plan_name)
        return plan_dir / safe_name

    def get_plan_file_path(self, plan_name: str) -> Path:
        """Get path to plan.md file.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to plan.md
        """
        return self.get_plan_dir(plan_name) / PLAN_FILE_FILENAME

    def get_tasks_file_path(self, plan_name: str) -> Path:
        """Get path to tasks.md file.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to tasks.md
        """
        return self.get_plan_dir(plan_name) / PLAN_TASKS_FILENAME

    def get_manifest_path(self, plan_name: str) -> Path:
        """Get path to manifest file.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to .manifest.json
        """
        return self.get_plan_dir(plan_name) / PLAN_MANIFEST_FILENAME

    def get_research_dir(self, plan_name: str) -> Path:
        """Get research directory for a plan.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to research directory
        """
        return self.get_plan_dir(plan_name) / PLAN_RESEARCH_DIR

    def get_research_file_path(self, plan_name: str, topic_slug: str) -> Path:
        """Get path to research findings file.

        Args:
            plan_name: URL-safe plan name
            topic_slug: URL-safe topic identifier

        Returns:
            Path to research/{topic_slug}.md
        """
        return self.get_research_dir(plan_name) / f"{sanitize_filename(topic_slug)}.md"

    def get_data_path(self, plan_name: str) -> Path:
        """Get path to data.json file for structured storage.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to .data.json
        """
        return self.get_plan_dir(plan_name) / PLAN_DATA_FILENAME

    def get_issue_dir(self, plan_name: str) -> Path:
        """Get issue artifacts directory for issue-first plans.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to issue/ directory
        """
        return self.get_plan_dir(plan_name) / PLAN_ISSUE_DIR

    def get_issue_context_path(self, plan_name: str) -> Path:
        """Get path to issue context.json file.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to issue/context.json
        """
        return self.get_issue_dir(plan_name) / PLAN_ISSUE_CONTEXT_FILENAME

    def get_issue_summary_path(self, plan_name: str) -> Path:
        """Get path to issue summary.md file.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to issue/summary.md
        """
        return self.get_issue_dir(plan_name) / PLAN_ISSUE_SUMMARY_FILENAME

    def get_issue_related_dir(self, plan_name: str) -> Path:
        """Get related issues directory.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Path to issue/related/ directory
        """
        return self.get_issue_dir(plan_name) / PLAN_ISSUE_RELATED_DIR

    # -------------------------------------------------------------------------
    # Plan CRUD operations
    # -------------------------------------------------------------------------
    def create_plan(
        self,
        plan_name: str,
        display_name: str,
        overview: str = "",
        goals: list[str] | None = None,
        research_depth: ResearchDepth = ResearchDepth.STANDARD,
        create_branch: bool = True,
    ) -> PlanManifest:
        """Create a new plan with initial scaffolding.

        Args:
            plan_name: URL-safe plan identifier
            display_name: Human-readable plan name
            overview: High-level plan overview
            goals: List of plan goals/objectives
            research_depth: Depth level for research phase
            create_branch: Whether to create a git branch

        Returns:
            PlanManifest for the created plan

        Raises:
            PlanServiceError: If prerequisites not met or plan already exists
        """
        # Validate prerequisites
        errors = self.validate_prerequisites()
        if errors:
            raise PlanServiceError("\n".join(errors))

        # Check if plan already exists
        plan_dir = self.get_plan_dir(plan_name)
        if plan_dir.exists():
            raise PlanServiceError(
                PLAN_ERROR_MESSAGES["plan_already_exists"].format(name=plan_name)
            )

        # Create directory structure
        ensure_dir(plan_dir)
        ensure_dir(self.get_research_dir(plan_name))

        # Create manifest
        now = datetime.now(UTC).isoformat()
        branch_name = self.build_branch_name(plan_name) if create_branch else None

        manifest = PlanManifest(
            name=plan_name,
            display_name=display_name,
            sources=[PlanSource.RESEARCH.value],  # Idea-first plans use research source
            status=PlanStatus.DRAFT,
            branch_name=branch_name,
            created_at=now,
            updated_at=now,
            research_depth=research_depth,
        )

        # Save manifest
        self._save_manifest(plan_name, manifest)

        # Create initial plan.md
        plan = Plan(
            manifest=manifest,
            overview=overview,
            goals=goals or [],
        )
        self._write_plan_file(plan_name, plan)

        # Save structured data to data.json
        self._save_data(plan_name, plan)

        # Create git branch if requested
        if create_branch and branch_name:
            try:
                self.checkout_branch(branch_name, create=True)
            except subprocess.CalledProcessError:
                # Branch creation failed, but plan is still created
                manifest.branch_name = None
                self._save_manifest(plan_name, manifest)

        return manifest

    def create_plan_from_issue(
        self,
        plan_name: str,
        issue_id: str,
        provider_key: str | None = None,
        create_branch: bool = True,
    ) -> PlanManifest:
        """Create a new plan from an external issue.

        This implements the issue-first workflow:
        1. Fetches issue from provider
        2. Fetches related issues
        3. Creates plan directory structure with issue/ subdirectory
        4. Writes manifest with sources: ["issue"] and issue reference
        5. Writes issue context and summary
        6. Writes related issues
        7. Creates initial plan.md scaffold
        8. Optionally creates git branch

        Args:
            plan_name: URL-safe plan identifier
            issue_id: Issue identifier from provider
            provider_key: Issue provider key (ado, github) or None to use config
            create_branch: Whether to create a git branch

        Returns:
            PlanManifest for the created plan

        Raises:
            PlanServiceError: If prerequisites not met or plan already exists
            IssueProviderError: If provider not configured or issue fetch fails
        """
        # Validate prerequisites
        errors = self.validate_prerequisites()
        if errors:
            raise PlanServiceError("\n".join(errors))

        # Validate provider
        provider_errors = self.validate_provider(provider_key)
        if provider_errors:
            raise PlanServiceError("\n".join(provider_errors))

        # Check if plan already exists
        plan_dir = self.get_plan_dir(plan_name)
        if plan_dir.exists():
            raise PlanServiceError(
                PLAN_ERROR_MESSAGES["plan_already_exists"].format(name=plan_name)
            )

        # Fetch issue from provider
        provider = self.get_provider(provider_key)
        issue = provider.fetch(issue_id)

        # Fetch related issues for context
        related_issues: list[Issue] = []
        if issue.relations:
            for relation in issue.relations:
                if relation.identifier:
                    try:
                        related = provider.fetch(relation.identifier)
                        related_issues.append(related)
                    except IssueProviderError:
                        # Skip related issues that can't be fetched
                        continue

        # Create directory structure
        ensure_dir(plan_dir)
        ensure_dir(self.get_issue_dir(plan_name))
        ensure_dir(self.get_research_dir(plan_name))

        # Create manifest
        now = datetime.now(UTC).isoformat()
        branch_name = self.build_branch_name(plan_name) if create_branch else None
        provider_key_resolved = self.resolve_provider_key(provider_key)

        manifest = PlanManifest(
            name=plan_name,
            display_name=issue.title or f"Issue {issue_id}",
            sources=[PlanSource.ISSUE.value],  # Issue-first plans use issue source
            status=PlanStatus.DRAFT,
            branch_name=branch_name,
            issue=IssueReference(
                provider=provider_key_resolved,
                id=issue.identifier,
                url=issue.url,
                title=issue.title,
            ),
            created_at=now,
            updated_at=now,
            research_depth=ResearchDepth.MINIMAL,  # Issue-first uses minimal research
        )

        # Save manifest
        self._save_manifest(plan_name, manifest)

        # Write issue context
        self.write_issue_context(plan_name, issue, related_issues)

        # Create initial plan.md with issue details
        plan_content = render_issue_plan(issue, related_issues)
        plan_path = self.get_plan_file_path(plan_name)
        plan_path.write_text(plan_content, encoding="utf-8")

        # Create initial Plan object and save to data.json
        plan = Plan(
            manifest=manifest,
            overview=issue.description or "",
            goals=[],  # Will be filled in during planning
        )
        self._save_data(plan_name, plan)

        # Create git branch if requested
        if create_branch and branch_name:
            try:
                self.checkout_branch(branch_name, create=True)
            except subprocess.CalledProcessError:
                # Branch creation failed, but plan is still created
                manifest.branch_name = None
                self._save_manifest(plan_name, manifest)

        return manifest

    def load_plan(self, plan_name: str) -> Plan:
        """Load a plan with its manifest and content.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Complete Plan object

        Raises:
            FileNotFoundError: If plan doesn't exist
        """
        manifest = self.load_manifest(plan_name)

        # Try to load from data.json first (preferred)
        data_path = self.get_data_path(plan_name)
        if data_path.exists():
            return self._load_data(plan_name, manifest)

        # Fall back to parsing plan.md for legacy plans
        plan_path = self.get_plan_file_path(plan_name)
        if not plan_path.exists():
            # Return plan with just manifest if plan.md doesn't exist yet
            return Plan(manifest=manifest)

        # Parse plan.md into structured data
        content = plan_path.read_text(encoding="utf-8")
        plan_data = parse_plan_file(content)

        return Plan(
            manifest=manifest,
            overview=plan_data.get("overview", ""),
            goals=plan_data.get("goals", []),
            success_criteria=plan_data.get("success_criteria", []),
            scope=plan_data.get("scope"),
            constraints=plan_data.get("constraints", []),
            research_topics=plan_data.get("research_topics", []),
            tasks=plan_data.get("tasks", []),
            metadata=plan_data.get("metadata", {}),
        )

    def load_manifest(self, plan_name: str) -> PlanManifest:
        """Load plan manifest.

        Args:
            plan_name: URL-safe plan name

        Returns:
            PlanManifest object

        Raises:
            FileNotFoundError: If manifest doesn't exist
        """
        manifest_path = self.get_manifest_path(plan_name)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Plan not found: {plan_name}")

        with manifest_path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        return PlanManifest.model_validate(data)

    def update_plan_status(self, plan_name: str, status: PlanStatus) -> PlanManifest:
        """Update plan status.

        Args:
            plan_name: URL-safe plan name
            status: New status value

        Returns:
            Updated PlanManifest
        """
        manifest = self.load_manifest(plan_name)
        manifest.status = status
        manifest.updated_at = datetime.now(UTC).isoformat()
        self._save_manifest(plan_name, manifest)
        return manifest

    def update_plan(self, plan_name: str, plan: Plan) -> None:
        """Update plan content.

        Args:
            plan_name: URL-safe plan name
            plan: Updated plan object
        """
        plan.manifest.updated_at = datetime.now(UTC).isoformat()
        self._save_manifest(plan_name, plan.manifest)
        self._write_plan_file(plan_name, plan)
        self._save_data(plan_name, plan)

    def list_plans(self) -> list[PlanManifest]:
        """List all plans.

        Returns:
            List of PlanManifest objects
        """
        plans: list[PlanManifest] = []
        plan_dir = self.config_service.get_plan_dir()
        if not plan_dir.exists():
            return plans

        for item in plan_dir.iterdir():
            if item.is_dir():
                manifest_path = item / PLAN_MANIFEST_FILENAME
                if manifest_path.exists():
                    try:
                        with manifest_path.open(encoding="utf-8") as fh:
                            data = json.load(fh)
                        plans.append(PlanManifest.model_validate(data))
                    except (json.JSONDecodeError, ValueError):
                        # Skip invalid manifests
                        continue

        return sorted(plans, key=lambda p: p.updated_at, reverse=True)

    def plan_exists(self, plan_name: str) -> bool:
        """Check if a plan exists.

        Args:
            plan_name: URL-safe plan name

        Returns:
            True if plan exists
        """
        return self.get_manifest_path(plan_name).exists()

    # -------------------------------------------------------------------------
    # Git operations
    # -------------------------------------------------------------------------
    def build_branch_name(self, plan_name: str) -> str:
        """Generate a branch name for the plan.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Branch name in format plan/{plan_name}
        """
        safe_name = sanitize_filename(plan_name)
        return f"{PLAN_BRANCH_PREFIX}{safe_name}"

    def get_current_branch(self) -> str | None:
        """Get current git branch name.

        Returns:
            Branch name or None if not in a git repo or detached HEAD
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=git_settings.command_timeout_seconds,
            )
            branch = result.stdout.strip()
            return branch if branch and branch != "HEAD" else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def branch_exists(self, branch_name: str) -> bool:
        """Check if a git branch already exists.

        Args:
            branch_name: Branch name to check

        Returns:
            True if branch exists
        """
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch_name],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def checkout_branch(self, branch_name: str, create: bool = True) -> None:
        """Create or switch to a git branch.

        Args:
            branch_name: Branch name
            create: Whether to create the branch if it doesn't exist
        """
        command = ["git", "checkout", branch_name]
        if create and not self.branch_exists(branch_name):
            command.insert(2, "-b")
        subprocess.run(command, cwd=self.project_root, check=True)

    def infer_plan_from_branch(self) -> str | None:
        """Infer plan name from current branch.

        Returns:
            Plan name if current branch is a plan branch, None otherwise
        """
        branch = self.get_current_branch()
        if not branch:
            return None

        if branch.startswith(PLAN_BRANCH_PREFIX):
            plan_name = branch[len(PLAN_BRANCH_PREFIX) :]
            if self.plan_exists(plan_name):
                return plan_name

        return None

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------
    def _save_manifest(self, plan_name: str, manifest: PlanManifest) -> None:
        """Save manifest to file.

        Args:
            plan_name: URL-safe plan name
            manifest: PlanManifest to save
        """
        manifest_path = self.get_manifest_path(plan_name)
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest.model_dump(mode="json"), fh, indent=2)

    def _save_data(self, plan_name: str, plan: Plan) -> None:
        """Save structured plan data to data.json.

        Args:
            plan_name: URL-safe plan name
            plan: Plan object to save
        """
        data_path = self.get_data_path(plan_name)
        # Exclude manifest as it's stored separately
        data = {
            "overview": plan.overview,
            "goals": plan.goals,
            "success_criteria": plan.success_criteria,
            "scope": plan.scope,
            "constraints": plan.constraints,
            "research_topics": [t.model_dump(mode="json") for t in plan.research_topics],
            "tasks": [t.model_dump(mode="json") for t in plan.tasks],
            "metadata": plan.metadata,
        }
        with data_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _load_data(self, plan_name: str, manifest: PlanManifest) -> Plan:
        """Load structured plan data from data.json.

        Args:
            plan_name: URL-safe plan name
            manifest: Already loaded manifest

        Returns:
            Complete Plan object
        """
        data_path = self.get_data_path(plan_name)
        with data_path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        research_topics = [ResearchTopic.model_validate(t) for t in data.get("research_topics", [])]
        tasks = [PlanTask.model_validate(t) for t in data.get("tasks", [])]

        return Plan(
            manifest=manifest,
            overview=data.get("overview", ""),
            goals=data.get("goals", []),
            success_criteria=data.get("success_criteria", []),
            scope=data.get("scope"),
            constraints=data.get("constraints", []),
            research_topics=research_topics,
            tasks=tasks,
            metadata=data.get("metadata", {}),
        )

    def _write_plan_file(self, plan_name: str, plan: Plan) -> None:
        """Write plan.md file.

        Args:
            plan_name: URL-safe plan name
            plan: Plan object to write
        """
        plan_path = self.get_plan_file_path(plan_name)
        content = render_plan_file(plan)
        plan_path.write_text(content, encoding="utf-8")


def get_plan_service(project_root: Path | None = None) -> PlanService:
    """Get a PlanService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        PlanService instance
    """
    return PlanService(project_root)
