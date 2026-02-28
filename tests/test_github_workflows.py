"""Validate GitHub Actions workflow YAML files.

Workflow syntax errors are invisible until a push triggers the workflow.
These tests catch parse failures locally, during `make check`.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

WORKFLOW_FILES = sorted(WORKFLOWS_DIR.glob("*.yml"))


@pytest.mark.parametrize("workflow_path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_workflow_yaml_is_valid(workflow_path: Path) -> None:
    """Every workflow file must parse as valid YAML without errors."""
    content = workflow_path.read_text(encoding="utf-8")
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as exc:
        pytest.fail(f"{workflow_path.name} contains invalid YAML:\n{exc}")


@pytest.mark.parametrize("workflow_path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_workflow_has_required_top_level_keys(workflow_path: Path) -> None:
    """Every workflow must define 'on' (trigger) and 'jobs'."""
    content = workflow_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, dict), f"{workflow_path.name}: YAML root must be a mapping"
    assert "on" in data or True in data, f"{workflow_path.name}: missing 'on' trigger"
    assert "jobs" in data, f"{workflow_path.name}: missing 'jobs' section"


def test_workflows_dir_is_not_empty() -> None:
    """Sanity check: the workflows directory must contain at least one file."""
    assert len(WORKFLOW_FILES) > 0, f"No workflow files found in {WORKFLOWS_DIR}"
