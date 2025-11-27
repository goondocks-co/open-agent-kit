"""Tests for issue provider implementations."""

from __future__ import annotations

from typing import Any

from open_agent_kit.models.config import GitHubIssuesProviderConfig
from open_agent_kit.services.issue_providers.github import GitHubIssuesProvider


def test_github_provider_validation_missing_owner() -> None:
    """GitHub provider validate should flag missing owner/repo/token."""
    provider = GitHubIssuesProvider(GitHubIssuesProviderConfig(), {})
    issues = provider.validate()
    assert any("owner" in issue for issue in issues)
    assert any("repo" in issue for issue in issues)
    assert any("token" in issue.lower() for issue in issues)


def test_github_provider_fetch_parses_issue(monkeypatch: Any) -> None:
    """Fetch should translate GitHub payload into Issue."""
    settings = GitHubIssuesProviderConfig(owner="acme", repo="project", token_env="GITHUB_TOKEN")
    provider = GitHubIssuesProvider(settings, {"GITHUB_TOKEN": "token"})

    payload = {
        "number": 42,
        "title": "Fix bug",
        "body": "- [ ] Acceptance step\nMore details",
        "state": "open",
        "html_url": "https://github.com/acme/project/issues/42",
        "labels": [{"name": "bug"}],
        "assignees": [{"login": "alice"}],
        "pull_request": {"html_url": "https://github.com/acme/project/pull/99"},
    }

    class DummyResponse:
        def __init__(self, data: dict):
            self.data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.data

    monkeypatch.setattr(
        "open_agent_kit.services.issue_providers.github.httpx.get",
        lambda *args, **kwargs: DummyResponse(payload),
    )

    item = provider.fetch("42")
    assert item.identifier == "42"
    assert item.tags == ["bug"]
    assert "Acceptance step" in item.acceptance_criteria
    assert item.assigned_to == "alice"
    assert item.relations[0].relation_type == "pull_request"
