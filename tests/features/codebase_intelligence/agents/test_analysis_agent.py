"""Tests for the analysis agent template and ci_access gating.

Tests cover:
- Analysis template loads correctly via registry
- Analysis tasks load and reference correct template
- ci_access flags are respected (analysis gets ci_query, documentation doesn't)
- Analysis system prompt contains expected schema markers
"""

import pytest

from open_agent_kit.features.codebase_intelligence.agents.models import AgentCIAccess
from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_TOOL_MEMORIES,
    CI_TOOL_PROJECT_STATS,
    CI_TOOL_QUERY,
    CI_TOOL_SEARCH,
    CI_TOOL_SESSIONS,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def registry() -> AgentRegistry:
    """Create an AgentRegistry loaded from the built-in definitions."""
    reg = AgentRegistry()
    reg.load_all()
    return reg


# =============================================================================
# Template Loading Tests
# =============================================================================


class TestAnalysisTemplateLoading:
    """Tests that the analysis template loads correctly."""

    def test_analysis_template_exists(self, registry: AgentRegistry) -> None:
        """The analysis template is discovered and loaded."""
        template = registry.get_template("analysis")
        assert template is not None

    def test_analysis_template_display_name(self, registry: AgentRegistry) -> None:
        """Analysis template has correct display name."""
        template = registry.get_template("analysis")
        assert template is not None
        assert template.display_name == "Analysis Agent"

    def test_analysis_template_has_system_prompt(self, registry: AgentRegistry) -> None:
        """Analysis template has a system prompt loaded from file."""
        template = registry.get_template("analysis")
        assert template is not None
        assert template.system_prompt is not None
        assert len(template.system_prompt) > 0

    def test_analysis_system_prompt_contains_ci_query(self, registry: AgentRegistry) -> None:
        """Analysis system prompt references ci_query tool."""
        template = registry.get_template("analysis")
        assert template is not None
        assert template.system_prompt is not None
        assert "ci_query" in template.system_prompt

    def test_analysis_system_prompt_has_schema_markers(self, registry: AgentRegistry) -> None:
        """Analysis system prompt contains generated schema markers."""
        template = registry.get_template("analysis")
        assert template is not None
        assert template.system_prompt is not None
        assert "<!-- BEGIN GENERATED CORE TABLES -->" in template.system_prompt
        assert "<!-- END GENERATED CORE TABLES -->" in template.system_prompt

    def test_analysis_system_prompt_has_core_tables(self, registry: AgentRegistry) -> None:
        """Analysis system prompt contains core table names."""
        template = registry.get_template("analysis")
        assert template is not None
        assert template.system_prompt is not None
        for table in ["sessions", "activities", "memory_observations", "agent_runs"]:
            assert f"`{table}`" in template.system_prompt


# =============================================================================
# CI Access Gating Tests
# =============================================================================


class TestCIAccessGating:
    """Tests that ci_access flags are correctly set per template."""

    def test_analysis_has_sql_query(self, registry: AgentRegistry) -> None:
        """Analysis template has sql_query enabled."""
        template = registry.get_template("analysis")
        assert template is not None
        assert template.ci_access.sql_query is True

    def test_analysis_has_no_code_search(self, registry: AgentRegistry) -> None:
        """Analysis template has code_search disabled (not needed for data analysis)."""
        template = registry.get_template("analysis")
        assert template is not None
        assert template.ci_access.code_search is False

    def test_analysis_has_memory_search(self, registry: AgentRegistry) -> None:
        """Analysis template has memory_search enabled."""
        template = registry.get_template("analysis")
        assert template is not None
        assert template.ci_access.memory_search is True

    def test_documentation_has_no_sql_query(self, registry: AgentRegistry) -> None:
        """Documentation template does NOT have sql_query enabled."""
        template = registry.get_template("documentation")
        assert template is not None
        assert template.ci_access.sql_query is False

    def test_documentation_has_code_search(self, registry: AgentRegistry) -> None:
        """Documentation template has code_search enabled."""
        template = registry.get_template("documentation")
        assert template is not None
        assert template.ci_access.code_search is True


class TestCIAccessToEnabledTools:
    """Tests that ci_access flags map correctly to enabled tool sets."""

    def test_analysis_ci_access_produces_correct_tools(self) -> None:
        """Analysis ci_access flags produce correct enabled_tools set."""
        ci_access = AgentCIAccess(
            code_search=False,
            memory_search=True,
            session_history=True,
            project_stats=True,
            sql_query=True,
        )

        enabled: set[str] = set()
        if ci_access.code_search:
            enabled.add(CI_TOOL_SEARCH)
        if ci_access.memory_search:
            enabled.add(CI_TOOL_MEMORIES)
        if ci_access.session_history:
            enabled.add(CI_TOOL_SESSIONS)
        if ci_access.project_stats:
            enabled.add(CI_TOOL_PROJECT_STATS)
        if ci_access.sql_query:
            enabled.add(CI_TOOL_QUERY)

        assert CI_TOOL_QUERY in enabled
        assert CI_TOOL_SEARCH not in enabled
        assert CI_TOOL_MEMORIES in enabled
        assert CI_TOOL_SESSIONS in enabled
        assert CI_TOOL_PROJECT_STATS in enabled

    def test_documentation_ci_access_excludes_query(self) -> None:
        """Documentation ci_access flags do NOT include ci_query."""
        ci_access = AgentCIAccess(
            code_search=True,
            memory_search=True,
            session_history=True,
            project_stats=True,
            sql_query=False,
        )

        enabled: set[str] = set()
        if ci_access.code_search:
            enabled.add(CI_TOOL_SEARCH)
        if ci_access.memory_search:
            enabled.add(CI_TOOL_MEMORIES)
        if ci_access.session_history:
            enabled.add(CI_TOOL_SESSIONS)
        if ci_access.project_stats:
            enabled.add(CI_TOOL_PROJECT_STATS)
        if ci_access.sql_query:
            enabled.add(CI_TOOL_QUERY)

        assert CI_TOOL_QUERY not in enabled
        assert CI_TOOL_SEARCH in enabled

    def test_default_ci_access_excludes_query(self) -> None:
        """Default AgentCIAccess does NOT include sql_query."""
        ci_access = AgentCIAccess()
        assert ci_access.sql_query is False
        assert ci_access.code_search is True


# =============================================================================
# Task Loading Tests
# =============================================================================


class TestAnalysisTaskLoading:
    """Tests that analysis tasks load correctly."""

    EXPECTED_TASKS = [
        "usage-report",
        "productivity-report",
        "codebase-activity-report",
        "prompt-analysis",
    ]

    def test_all_analysis_tasks_loaded(self, registry: AgentRegistry) -> None:
        """All 4 analysis tasks are discovered and loaded."""
        for task_name in self.EXPECTED_TASKS:
            task = registry.get_task(task_name)
            assert task is not None, f"Task '{task_name}' not found in registry"

    def test_analysis_tasks_reference_analysis_template(self, registry: AgentRegistry) -> None:
        """All analysis tasks reference the 'analysis' agent_type."""
        for task_name in self.EXPECTED_TASKS:
            task = registry.get_task(task_name)
            assert task is not None
            assert (
                task.agent_type == "analysis"
            ), f"Task '{task_name}' has agent_type '{task.agent_type}', expected 'analysis'"

    def test_analysis_tasks_have_default_task(self, registry: AgentRegistry) -> None:
        """All analysis tasks have a non-empty default_task."""
        for task_name in self.EXPECTED_TASKS:
            task = registry.get_task(task_name)
            assert task is not None
            assert len(task.default_task) > 0

    def test_analysis_tasks_have_maintained_files(self, registry: AgentRegistry) -> None:
        """All analysis tasks declare at least one maintained file."""
        for task_name in self.EXPECTED_TASKS:
            task = registry.get_task(task_name)
            assert task is not None
            assert len(task.maintained_files) > 0, f"Task '{task_name}' has no maintained_files"

    def test_analysis_tasks_write_to_insights_dir(self, registry: AgentRegistry) -> None:
        """All analysis tasks write to oak/insights/."""
        for task_name in self.EXPECTED_TASKS:
            task = registry.get_task(task_name)
            assert task is not None
            paths = [mf.path for mf in task.maintained_files]
            assert any(
                "oak/insights" in p for p in paths
            ), f"Task '{task_name}' doesn't write to oak/insights/"

    def test_analysis_tasks_are_builtin(self, registry: AgentRegistry) -> None:
        """All analysis tasks are marked as built-in."""
        for task_name in self.EXPECTED_TASKS:
            task = registry.get_task(task_name)
            assert task is not None
            assert task.is_builtin is True

    def test_usage_report_task_details(self, registry: AgentRegistry) -> None:
        """Usage report task has expected configuration."""
        task = registry.get_task("usage-report")
        assert task is not None
        assert task.display_name == "Usage & Cost Report"
        assert "cost" in task.default_task.lower() or "usage" in task.default_task.lower()

    def test_prompt_analysis_task_details(self, registry: AgentRegistry) -> None:
        """Prompt analysis task has expected configuration."""
        task = registry.get_task("prompt-analysis")
        assert task is not None
        assert task.display_name == "Prompt Quality Analysis"
        assert "prompt" in task.default_task.lower()
