"""Tests to ensure DecisionContext model and decision_points.yaml stay in sync.

This test suite catches drift between:
1. DecisionContext model (source of truth for validation)
2. decision_points.yaml (agent guidance documentation)

Why this matters:
- Model defines what's valid at runtime
- YAML guides agents during interactive conversations
- If they drift, agents suggest invalid options and users get confusing errors

These tests catch drift automatically in CI/PR checks.
"""

import types
from pathlib import Path
from typing import Union, get_args, get_origin

import pytest
import yaml

from open_agent_kit.models.constitution import DecisionContext


class TestDecisionSchemaSync:
    """Test that model and YAML stay synchronized."""

    @pytest.fixture
    def yaml_data(self):
        """Load decision_points.yaml."""
        yaml_path = Path("features/constitution/templates/decision_points.yaml")
        if not yaml_path.exists():
            pytest.skip("decision_points.yaml not found")

        with open(yaml_path) as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def model_fields(self):
        """Get DecisionContext model fields."""
        return DecisionContext.model_fields

    def test_yaml_file_exists(self):
        """Ensure decision_points.yaml exists."""
        yaml_path = Path("features/constitution/templates/decision_points.yaml")
        assert yaml_path.exists(), "decision_points.yaml not found"

    def test_yaml_has_decision_sections(self, yaml_data):
        """Ensure YAML has decision sections."""
        # YAML is organized by category (testing_strategy, code_review, etc.)
        assert len(yaml_data) > 0, "decision_points.yaml must have decision sections"

        # Should have at least the core decision categories
        expected_categories = ["testing_strategy", "architectural_patterns"]
        for category in expected_categories:
            assert (
                category in yaml_data
            ), f"decision_points.yaml missing expected category: {category}"

    def test_key_literal_fields_have_yaml_documentation(self, model_fields, yaml_data):
        """Ensure key Literal-typed model fields are documented in YAML.

        This catches when a developer adds a new decision to the model
        but forgets to document it in the YAML for agent guidance.

        Note: YAML categories don't map 1:1 to model fields.
        We check that major decision fields have corresponding YAML guidance.
        """
        # Map model field names to YAML category names
        # (YAML uses categories, model uses individual fields)
        field_to_yaml_mapping = {
            "testing_strategy": "testing_strategy",
            "architectural_pattern": "architectural_patterns",  # Note: plural in YAML
            "code_review_policy": "code_review",
            "documentation_level": "documentation",
            "ci_enforcement": "ci_cd",
            "error_handling_pattern": "architectural_patterns",  # Documented within
            "docstring_style": "documentation",  # Documented within
        }

        missing_docs = []

        for model_field, yaml_category in field_to_yaml_mapping.items():
            if model_field not in model_fields:
                continue  # Skip if field doesn't exist in model

            if yaml_category not in yaml_data:
                missing_docs.append(f"{model_field} (expected in YAML: {yaml_category})")

        assert not missing_docs, (
            f"Model has key fields not documented in YAML:\n"
            f"  Missing: {missing_docs}\n"
            f"\n"
            f"Action: Add these categories to features/constitution/templates/decision_points.yaml\n"
            f"with options and descriptions for agent guidance."
        )

    def test_literal_field_values_match_yaml_options(self, model_fields, yaml_data):
        """Ensure Literal values in model match options in YAML.

        This catches when valid options differ between model and YAML.
        Example: Model allows ["strict", "standard", "flexible"]
                 but YAML documents ["strict", "standard", "relaxed"]
        """
        # Map model fields to YAML categories
        field_to_yaml_mapping = {
            "testing_strategy": "testing_strategy",
            "architectural_pattern": "architectural_patterns",
            "code_review_policy": "code_review",
            "documentation_level": "documentation",
            "ci_enforcement": "ci_cd",
        }

        mismatches = []

        for model_field, yaml_category in field_to_yaml_mapping.items():
            if model_field not in model_fields:
                continue

            field_info = model_fields[model_field]
            annotation = field_info.annotation
            origin = get_origin(annotation)

            # Extract Literal values from model
            model_values = None

            # Check for Union types: typing.Union OR types.UnionType (Python 3.10+ X | Y syntax)
            is_union = origin is Union or isinstance(origin, type) and origin is types.UnionType
            # Also check for types.UnionType directly (Python 3.10+)
            if not is_union:
                try:
                    is_union = origin is types.UnionType
                except AttributeError:
                    pass

            if is_union:
                # Optional[Literal[...]] or Literal[...] | None
                args = get_args(annotation)
                for arg in args:
                    # Skip NoneType
                    if arg is type(None):
                        continue
                    # Extract Literal values
                    if hasattr(arg, "__args__"):
                        model_values = {v for v in get_args(arg) if not isinstance(v, type)}
                        break
            elif hasattr(annotation, "__args__"):
                # Direct Literal[...]
                model_values = {v for v in get_args(annotation) if not isinstance(v, type)}

            if model_values and yaml_category in yaml_data:
                # Get YAML options
                yaml_section = yaml_data[yaml_category]
                if "options" in yaml_section:
                    yaml_values = {opt["id"] for opt in yaml_section["options"] if "id" in opt}

                    # Compare
                    if model_values != yaml_values:
                        mismatches.append(
                            {
                                "field": model_field,
                                "yaml_category": yaml_category,
                                "model_values": sorted(model_values),
                                "yaml_values": sorted(yaml_values),
                                "model_only": sorted(model_values - yaml_values),
                                "yaml_only": sorted(yaml_values - model_values),
                            }
                        )

        if mismatches:
            error_msg = "Literal values mismatch between model and YAML:\n\n"
            for mismatch in mismatches:
                error_msg += f"Field: {mismatch['field']} (YAML: {mismatch['yaml_category']})\n"
                error_msg += f"  Model values: {mismatch['model_values']}\n"
                error_msg += f"  YAML values:  {mismatch['yaml_values']}\n"
                if mismatch["model_only"]:
                    error_msg += f"  Only in model: {mismatch['model_only']}\n"
                if mismatch["yaml_only"]:
                    error_msg += f"  Only in YAML:  {mismatch['yaml_only']}\n"
                error_msg += "\n"

            error_msg += (
                "Action: Update either the model or YAML to match.\n"
                "Remember: Model is source of truth for validation."
            )
            pytest.fail(error_msg)

    def test_yaml_categories_are_reasonable(self, yaml_data):
        """Ensure YAML has expected category structure.

        This is a sanity check that YAML isn't accidentally malformed.
        YAML uses categories like 'testing_strategy', 'architectural_patterns', etc.
        These don't map 1:1 to model fields (model is more granular).
        """
        # Expected top-level categories in YAML
        expected_categories = [
            "testing_strategy",
            "architectural_patterns",
            "code_review",
            "documentation",
            "ci_cd",
        ]

        missing = [cat for cat in expected_categories if cat not in yaml_data]

        assert not missing, (
            f"YAML missing expected categories: {missing}\n"
            f"These categories provide agent guidance for key decision areas."
        )

    def test_model_has_reasonable_field_count(self, model_fields):
        """Sanity check: model should have expected number of decision fields.

        This catches accidental mass deletions or major structural changes.
        """
        field_count = len(model_fields)
        assert field_count >= 20, (
            f"DecisionContext has only {field_count} fields. "
            f"Expected at least 20. Were fields accidentally deleted?"
        )
        assert field_count <= 50, (
            f"DecisionContext has {field_count} fields. "
            f"Expected at most 50. Is this intentional growth?"
        )

    def test_yaml_categories_have_descriptions(self, yaml_data):
        """Ensure YAML categories have descriptions for agent guidance.

        YAML's purpose is to guide agents, so each category should have
        a description explaining what it means and why it matters.
        """
        # Check main categories (excluding meta fields like confirmation_template)
        main_categories = [
            "testing_strategy",
            "architectural_patterns",
            "code_review",
            "documentation",
            "ci_cd",
        ]

        missing_descriptions = []

        for category in main_categories:
            if category in yaml_data:
                if not yaml_data[category].get("description"):
                    missing_descriptions.append(category)

        assert not missing_descriptions, (
            f"YAML categories missing descriptions: {missing_descriptions}\n"
            f"Action: Add 'description' to each category in decision_points.yaml\n"
            f"Descriptions help agents understand what to ask users."
        )

    def test_yaml_options_have_ids(self, yaml_data):
        """Ensure YAML options have IDs that match model Literal values.

        Options must have 'id' field that corresponds to model validation.
        """
        categories_with_options = [
            "testing_strategy",
            "architectural_patterns",
            "code_review",
            "documentation",
            "ci_cd",
        ]

        missing_ids = []

        for category in categories_with_options:
            if category in yaml_data and "options" in yaml_data[category]:
                for idx, option in enumerate(yaml_data[category]["options"]):
                    if "id" not in option:
                        missing_ids.append(f"{category}[{idx}]")

        assert not missing_ids, (
            f"YAML options missing 'id' field: {missing_ids}\n"
            f"Action: Add 'id' field to each option in decision_points.yaml\n"
            f"IDs must match model Literal values for validation."
        )


class TestDecisionContextIntegrity:
    """Additional integrity checks for DecisionContext model."""

    def test_all_fields_have_descriptions(self):
        """Ensure all model fields have Field() with description."""
        model_fields = DecisionContext.model_fields
        missing_descriptions = []

        for field_name, field_info in model_fields.items():
            if not field_info.description:
                missing_descriptions.append(field_name)

        assert not missing_descriptions, (
            f"Model fields missing descriptions: {missing_descriptions}\n"
            f"Action: Add description= to Field() for each field.\n"
            f"Descriptions help developers understand the field's purpose."
        )

    def test_required_fields_are_reasonable(self):
        """Ensure model doesn't have too many required fields.

        Most fields should be optional with sensible defaults to make
        the model easy to use.
        """
        model_fields = DecisionContext.model_fields
        required_fields = [name for name, info in model_fields.items() if info.is_required()]

        # DecisionContext should have mostly optional fields
        # (all fields should have defaults)
        assert len(required_fields) == 0, (
            f"DecisionContext has required fields: {required_fields}\n"
            f"All fields should have defaults for ease of use."
        )

    def test_model_has_to_template_context_method(self):
        """Ensure model has to_template_context() method."""
        assert hasattr(DecisionContext, "to_template_context"), (
            "DecisionContext must have to_template_context() method "
            "to convert to template rendering format"
        )

        # Test it's callable
        decisions = DecisionContext.get_defaults()
        context = decisions.to_template_context()
        assert isinstance(context, dict), "to_template_context() must return dict"
        assert len(context) > 0, "to_template_context() must return non-empty dict"

    def test_model_has_get_defaults_method(self):
        """Ensure model has get_defaults() class method."""
        assert hasattr(DecisionContext, "get_defaults"), (
            "DecisionContext must have get_defaults() class method "
            "for creating instances with sensible defaults"
        )

        # Test it works
        defaults = DecisionContext.get_defaults()
        assert isinstance(
            defaults, DecisionContext
        ), "get_defaults() must return DecisionContext instance"
