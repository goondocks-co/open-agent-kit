"""Tests for DecisionContext model."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from open_agent_kit.models.constitution import DecisionContext


class TestDecisionContextValidation:
    """Test DecisionContext validation rules."""

    def test_valid_decision_context(self):
        """Test that valid decision context is accepted."""
        decisions = DecisionContext(
            testing_strategy="balanced",
            coverage_target=70,
            architectural_pattern="clean_architecture",
            error_handling_pattern="result_pattern",
        )

        assert decisions.testing_strategy == "balanced"
        assert decisions.coverage_target == 70
        assert decisions.architectural_pattern == "clean_architecture"
        assert decisions.error_handling_pattern == "result_pattern"

    def test_invalid_testing_strategy(self):
        """Test that invalid testing strategy is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionContext(testing_strategy="invalid")

        # Check error mentions the field
        assert "testing_strategy" in str(exc_info.value)

    def test_coverage_target_too_high(self):
        """Test that coverage target over 100 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionContext(coverage_target=150)

        assert "coverage_target" in str(exc_info.value)

    def test_coverage_target_negative(self):
        """Test that negative coverage target is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionContext(coverage_target=-10)

        assert "coverage_target" in str(exc_info.value)

    def test_num_reviewers_too_high(self):
        """Test that excessive number of reviewers is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionContext(num_reviewers=20)

        assert "num_reviewers" in str(exc_info.value)

    def test_invalid_code_review_policy(self):
        """Test that invalid code review policy is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionContext(code_review_policy="invalid")

        assert "code_review_policy" in str(exc_info.value)

    def test_invalid_architectural_pattern(self):
        """Test that invalid architectural pattern is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionContext(architectural_pattern="invalid_pattern")

        assert "architectural_pattern" in str(exc_info.value)

    def test_invalid_error_handling_pattern(self):
        """Test that invalid error handling pattern is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DecisionContext(error_handling_pattern="invalid")

        assert "error_handling_pattern" in str(exc_info.value)

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored (allows comments in JSON)."""
        # Should not raise - extra fields starting with _ are for documentation
        decisions = DecisionContext(
            testing_strategy="balanced",
            _comment="This is a comment field",
            _description="For documentation",
        )
        assert decisions.testing_strategy == "balanced"


class TestDecisionContextDefaults:
    """Test DecisionContext default values."""

    def test_get_defaults(self):
        """Test that get_defaults() returns sensible defaults."""
        decisions = DecisionContext.get_defaults()

        assert decisions.testing_strategy == "balanced"
        assert decisions.code_review_policy == "standard"
        assert decisions.documentation_level == "standard"
        assert decisions.docstring_style == "google"
        assert decisions.ci_enforcement == "standard"
        assert decisions.num_reviewers == 1
        assert decisions.coverage_target is None
        assert decisions.architectural_pattern is None

    def test_empty_constructor_uses_defaults(self):
        """Test that empty constructor uses defaults."""
        decisions = DecisionContext()

        assert decisions.testing_strategy == "balanced"
        assert decisions.num_reviewers == 1
        assert decisions.coverage_strict is False

    def test_partial_values_with_defaults(self):
        """Test that partial values use defaults for missing fields."""
        decisions = DecisionContext(testing_strategy="comprehensive", coverage_target=80)

        # Specified values
        assert decisions.testing_strategy == "comprehensive"
        assert decisions.coverage_target == 80

        # Default values
        assert decisions.code_review_policy == "standard"
        assert decisions.num_reviewers == 1


class TestDecisionContextTemplateContext:
    """Test DecisionContext to_template_context conversion."""

    def test_to_template_context_includes_all_fields(self):
        """Test that to_template_context() includes all decision fields."""
        from open_agent_kit.constants import (
            DECISION_ARCHITECTURAL_PATTERN,
            DECISION_COVERAGE_TARGET,
            DECISION_TESTING_STRATEGY,
        )

        decisions = DecisionContext(
            testing_strategy="balanced",
            coverage_target=70,
            architectural_pattern="clean_architecture",
        )

        context = decisions.to_template_context()

        assert DECISION_TESTING_STRATEGY in context
        assert DECISION_COVERAGE_TARGET in context
        assert DECISION_ARCHITECTURAL_PATTERN in context
        assert context[DECISION_TESTING_STRATEGY] == "balanced"
        assert context[DECISION_COVERAGE_TARGET] == 70
        assert context[DECISION_ARCHITECTURAL_PATTERN] == "clean_architecture"

    def test_to_template_context_uses_constants_as_keys(self):
        """Test that template context uses DECISION_* constants as keys."""
        decisions = DecisionContext.get_defaults()
        context = decisions.to_template_context()

        # All keys should start with the constants pattern
        # Check that context has the expected structure
        assert len(context) > 0
        assert all(isinstance(k, str) for k in context.keys())


class TestDecisionContextExampleFiles:
    """Test that example JSON files are valid."""

    def test_example_decisions_json(self):
        """Test that example-decisions.json validates."""
        example_path = Path("templates/constitution/example-decisions.json")
        if not example_path.exists():
            pytest.skip("Example file not found")

        with open(example_path) as f:
            data = json.load(f)

        # Should not raise ValidationError
        decisions = DecisionContext(**data)
        assert decisions is not None

    def test_example_decisions_minimal_json(self):
        """Test that example-decisions-minimal.json validates."""
        example_path = Path("templates/constitution/example-decisions-minimal.json")
        if not example_path.exists():
            pytest.skip("Example file not found")

        with open(example_path) as f:
            data = json.load(f)

        decisions = DecisionContext(**data)
        assert decisions is not None

    def test_example_decisions_comprehensive_json(self):
        """Test that example-decisions-comprehensive.json validates."""
        example_path = Path("templates/constitution/example-decisions-comprehensive.json")
        if not example_path.exists():
            pytest.skip("Example file not found")

        with open(example_path) as f:
            data = json.load(f)

        decisions = DecisionContext(**data)
        assert decisions is not None


class TestDecisionContextFromJSON:
    """Test creating DecisionContext from JSON data (CLI use case)."""

    def test_create_from_valid_json_dict(self):
        """Test that model can be created from JSON dict (CLI pattern)."""
        json_data = {
            "testing_strategy": "balanced",
            "coverage_target": 70,
            "code_review_policy": "standard",
        }

        decisions = DecisionContext(**json_data)
        assert decisions.testing_strategy == "balanced"
        assert decisions.coverage_target == 70
        assert decisions.code_review_policy == "standard"

    def test_provides_helpful_error_for_invalid_json(self):
        """Test that invalid JSON data provides helpful error message."""
        invalid_data = {"testing_strategy": "invalid_value", "coverage_target": 150}

        with pytest.raises(ValidationError) as exc_info:
            DecisionContext(**invalid_data)

        error_str = str(exc_info.value)
        # Should mention validation errors
        assert "testing_strategy" in error_str or "coverage_target" in error_str


class TestDecisionContextEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_coverage_target_zero(self):
        """Test that coverage target of 0 is valid."""
        decisions = DecisionContext(coverage_target=0)
        assert decisions.coverage_target == 0

    def test_coverage_target_one_hundred(self):
        """Test that coverage target of 100 is valid."""
        decisions = DecisionContext(coverage_target=100)
        assert decisions.coverage_target == 100

    def test_empty_lists_accepted(self):
        """Test that empty lists are accepted for list fields."""
        decisions = DecisionContext(
            critical_integration_points=[], required_checks=[], coding_principles=[]
        )

        assert decisions.critical_integration_points == []
        assert decisions.required_checks == []
        assert decisions.coding_principles == []

    def test_populated_lists_accepted(self):
        """Test that populated lists work correctly."""
        decisions = DecisionContext(
            critical_integration_points=["database", "api"],
            required_checks=["lint", "test", "build"],
            coding_principles=["SOLID", "DRY", "KISS"],
        )

        assert len(decisions.critical_integration_points) == 2
        assert len(decisions.required_checks) == 3
        assert len(decisions.coding_principles) == 3

    def test_none_values_for_optional_strings(self):
        """Test that None is accepted for optional string fields."""
        decisions = DecisionContext(
            reviewer_qualifications=None,
            hotfix_definition=None,
            ci_platform=None,
            architectural_rationale=None,
        )

        assert decisions.reviewer_qualifications is None
        assert decisions.hotfix_definition is None
        assert decisions.ci_platform is None
        assert decisions.architectural_rationale is None
