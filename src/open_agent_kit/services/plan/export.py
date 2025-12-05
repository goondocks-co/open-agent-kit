"""Export and provider operations for PlanService.

This module provides issue provider management and export operations.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from open_agent_kit.config.messages import ERROR_MESSAGES
from open_agent_kit.config.paths import (
    PLAN_ISSUE_CONTEXT_FILENAME,
    PLAN_ISSUE_SUMMARY_FILENAME,
)
from open_agent_kit.constants import ISSUE_PROVIDER_CONFIG_MAP
from open_agent_kit.models.config import IssueConfig
from open_agent_kit.models.issue import Issue
from open_agent_kit.models.plan import PlanStatus
from open_agent_kit.services.issue_providers import AzureDevOpsProvider, GitHubIssuesProvider
from open_agent_kit.services.issue_providers.base import IssueProvider, IssueProviderError
from open_agent_kit.services.plan.exceptions import PlanServiceError
from open_agent_kit.services.plan.parsing import detect_issue_changes
from open_agent_kit.services.plan.rendering import render_issue_summary
from open_agent_kit.utils import ensure_dir

if TYPE_CHECKING:
    from open_agent_kit.models.plan import PlanManifest
    from open_agent_kit.services.config_service import ConfigService

# Provider registry
PROVIDER_REGISTRY: dict[str, type[IssueProvider]] = {
    "ado": AzureDevOpsProvider,
    "github": GitHubIssuesProvider,
}


class ExportOperationsMixin:
    """Mixin providing export and provider operations.

    This mixin is designed to be used with PlanService. It expects
    the following attributes to be available on self:
    - config_service: ConfigService
    - environment: Mapping[str, str]
    - load_manifest(plan_name) -> PlanManifest
    - update_plan_status(plan_name, status) -> PlanManifest
    - get_issue_dir(plan_name) -> Path
    - get_issue_context_path(plan_name) -> Path
    - get_issue_summary_path(plan_name) -> Path
    - get_issue_related_dir(plan_name) -> Path
    - _save_manifest(plan_name, manifest) -> None
    """

    # These will be set by the main PlanService class
    config_service: ConfigService
    environment: Mapping[str, str]

    def get_issue_config(self) -> IssueConfig:
        """Return current issue configuration."""
        return self.config_service.get_issue_config()

    def resolve_provider_key(self, provider_key: str | None = None) -> str:
        """Resolve provider key using explicit value or configuration.

        Args:
            provider_key: Optional provider key override

        Returns:
            Resolved provider key

        Raises:
            IssueProviderError: If provider not configured or invalid
        """
        config = self.get_issue_config()
        resolved = provider_key or config.provider
        if not resolved:
            raise IssueProviderError(ERROR_MESSAGES["issue_provider_not_set"])
        if resolved not in PROVIDER_REGISTRY:
            raise IssueProviderError(
                ERROR_MESSAGES["issue_provider_invalid"].format(provider=resolved)
            )
        return resolved

    def get_provider(self, provider_key: str | None = None) -> IssueProvider:
        """Instantiate provider implementation.

        Args:
            provider_key: Optional provider key override

        Returns:
            IssueProvider instance

        Raises:
            IssueProviderError: If provider not configured or invalid
        """
        key = self.resolve_provider_key(provider_key)
        provider_cls = PROVIDER_REGISTRY[key]
        config = self.get_issue_config()
        provider_attr = ISSUE_PROVIDER_CONFIG_MAP.get(key)
        settings = getattr(config, provider_attr) if provider_attr else None
        return provider_cls(settings=settings, environment=self.environment)

    def validate_provider(self, provider_key: str | None = None) -> list[str]:
        """Return validation issues for the provider configuration.

        Args:
            provider_key: Optional provider key override

        Returns:
            List of validation error messages (empty if valid)
        """
        try:
            provider = self.get_provider(provider_key)
        except IssueProviderError as exc:
            return [str(exc)]
        return provider.validate()

    def load_issue_context(self, plan_name: str) -> Issue:
        """Load issue context from issue/context.json.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Issue object

        Raises:
            FileNotFoundError: If issue context doesn't exist
        """
        context_path: Path = self.get_issue_context_path(plan_name)  # type: ignore[attr-defined]
        if not context_path.exists():
            raise FileNotFoundError(f"Issue context not found for plan: {plan_name}")

        with context_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return Issue.model_validate(data)

    def write_issue_context(
        self, plan_name: str, issue: Issue, related_issues: list[Issue] | None = None
    ) -> None:
        """Write issue context and related issues to plan directory.

        Creates:
        - issue/context.json: Main issue context
        - issue/summary.md: LLM-optimized issue summary
        - issue/related/{id}/context.json: Related issue contexts
        - issue/related/{id}/summary.md: Related issue summaries

        Args:
            plan_name: URL-safe plan name
            issue: Main issue to write
            related_issues: Optional list of related issues
        """
        issue_dir: Path = self.get_issue_dir(plan_name)  # type: ignore[attr-defined]
        ensure_dir(issue_dir)

        # Write main issue context
        context_path: Path = self.get_issue_context_path(plan_name)  # type: ignore[attr-defined]
        with context_path.open("w", encoding="utf-8") as fh:
            json.dump(issue.model_dump(mode="json"), fh, indent=2)

        # Write main issue summary
        summary_path: Path = self.get_issue_summary_path(plan_name)  # type: ignore[attr-defined]
        summary_content = render_issue_summary(issue)
        summary_path.write_text(summary_content, encoding="utf-8")

        # Write related issues if provided
        if related_issues:
            related_dir: Path = self.get_issue_related_dir(plan_name)  # type: ignore[attr-defined]
            ensure_dir(related_dir)

            for related in related_issues:
                related_item_dir = related_dir / related.identifier
                ensure_dir(related_item_dir)

                # Write related issue context
                related_context_path = related_item_dir / PLAN_ISSUE_CONTEXT_FILENAME
                with related_context_path.open("w", encoding="utf-8") as fh:
                    json.dump(related.model_dump(mode="json"), fh, indent=2)

                # Write related issue summary
                related_summary_path = related_item_dir / PLAN_ISSUE_SUMMARY_FILENAME
                related_summary_content = render_issue_summary(related)
                related_summary_path.write_text(related_summary_content, encoding="utf-8")

    def refresh_issue_context(self, plan_name: str) -> tuple[Issue, Issue, dict[str, Any]]:
        """Refresh issue context from provider.

        Fetches fresh data from the provider and updates issue/context.json
        and issue/summary.md while preserving all other artifacts.

        Args:
            plan_name: URL-safe plan name

        Returns:
            Tuple of (old_issue, new_issue, changes_summary)

        Raises:
            FileNotFoundError: If plan or issue context doesn't exist
            IssueProviderError: If provider fetch fails
        """
        # Load manifest to get issue reference
        manifest: PlanManifest = self.load_manifest(plan_name)  # type: ignore[attr-defined]
        if not manifest.issue:
            raise PlanServiceError(f"Plan {plan_name} is not an issue-first plan")

        # Load existing context
        old_issue = self.load_issue_context(plan_name)

        # Fetch fresh data from provider
        provider = self.get_provider(manifest.issue.provider)
        new_issue = provider.fetch(manifest.issue.id)

        # Detect changes
        changes = detect_issue_changes(old_issue, new_issue)

        # Update context files
        self.write_issue_context(plan_name, new_issue)

        return old_issue, new_issue, changes

    def set_export_mode(self, plan_name: str, mode: str, provider: str) -> None:
        """Set export mode and provider for a plan.

        Args:
            plan_name: URL-safe plan name
            mode: Export mode (hierarchical or flat)
            provider: Issue provider key (ado, github)
        """
        manifest: PlanManifest = self.load_manifest(plan_name)  # type: ignore[attr-defined]
        manifest.export_mode = mode
        manifest.export_provider = provider
        manifest.updated_at = datetime.now(UTC).isoformat()
        self._save_manifest(plan_name, manifest)  # type: ignore[attr-defined]

    def mark_exported(self, plan_name: str) -> None:
        """Mark plan as exported.

        Args:
            plan_name: URL-safe plan name
        """
        self.update_plan_status(plan_name, PlanStatus.EXPORTED)  # type: ignore[attr-defined]
