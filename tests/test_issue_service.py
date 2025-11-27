"""Tests for issue service and configuration helpers."""

from pathlib import Path

from open_agent_kit.models.issue import Issue
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.issue_service import IssueService


def _setup_project(tmp_path: Path) -> ConfigService:
    """Create a minimal project with config."""
    (tmp_path / ".oak").mkdir(exist_ok=True)
    config_service = ConfigService(tmp_path)
    config_service.create_default_config()
    return config_service


def test_update_issue_provider_sets_active(tmp_path: Path) -> None:
    """Updating issue provider should persist settings and active key."""
    config_service = _setup_project(tmp_path)
    config_service.update_issue_provider(
        "ado",
        organization="contoso",
        project="web",
        pat_env="ADO_PAT",
        default_branch="develop",
    )
    issue_config = config_service.get_issue_config()
    assert issue_config.provider == "ado"
    assert issue_config.azure_devops.organization == "contoso"
    assert issue_config.azure_devops.project == "web"
    assert issue_config.azure_devops.pat_env == "ADO_PAT"
    assert issue_config.azure_devops.default_branch == "develop"


def test_issue_service_writes_artifacts(tmp_path: Path) -> None:
    """Context and plan files should be created under oak/issue."""
    config_service = _setup_project(tmp_path)
    config_service.update_issue_provider(
        "ado", organization="contoso", project="web", pat_env="ADO_PAT"
    )

    issue = Issue(provider="ado", identifier="12345", title="Test Issue")
    service = IssueService(tmp_path, environment={"ADO_PAT": "token"})

    context_path = service.write_context(issue)
    plan_path = service.write_plan(issue, None)

    assert context_path.exists()
    assert plan_path.exists()
    assert context_path.parent == plan_path.parent
    relative = context_path.parent.relative_to(tmp_path)
    # Use as_posix() for cross-platform path comparison (Windows uses backslashes)
    assert relative.as_posix().startswith("oak/issue/ado/")


def test_validate_provider_detects_missing_env(tmp_path: Path) -> None:
    """Validation should surface missing environment variables."""
    config_service = _setup_project(tmp_path)
    config_service.update_issue_provider(
        "ado", organization="contoso", project="web", pat_env="ADO_PAT"
    )

    service = IssueService(tmp_path, environment={})
    issues = service.validate_provider()
    assert issues
    assert "ADO_PAT" in issues[0]
