"""Tests for naming utilities.

Tests cover:
- Basic hyphen-to-underscore conversion
- No-op when no hyphens present
- Multiple consecutive and separated hyphens
- Empty string edge case
"""

import pytest

from open_agent_kit.utils.naming import feature_name_to_dir

# =============================================================================
# feature_name_to_dir()
# =============================================================================

_CONVERSION_CASES = [
    # (input, expected, description)
    ("codebase-intelligence", "codebase_intelligence", "basic single-hyphen"),
    ("rules", "rules", "no hyphens unchanged"),
    ("foo-bar-baz", "foo_bar_baz", "multiple hyphens"),
    ("", "", "empty string"),
    ("already_underscored", "already_underscored", "underscores unchanged"),
    ("a-b-c-d-e", "a_b_c_d_e", "many short segments"),
    ("leading-", "leading_", "trailing hyphen converted"),
    ("-leading", "_leading", "leading hyphen converted"),
    ("double--hyphen", "double__hyphen", "consecutive hyphens become consecutive underscores"),
]


@pytest.mark.parametrize(
    "input_name,expected",
    [(c[0], c[1]) for c in _CONVERSION_CASES],
    ids=[c[2] for c in _CONVERSION_CASES],
)
def test_feature_name_to_dir(input_name: str, expected: str) -> None:
    """Verify feature_name_to_dir converts hyphens to underscores correctly."""
    assert feature_name_to_dir(input_name) == expected


def test_feature_name_to_dir_is_idempotent() -> None:
    """Applying the conversion twice yields the same result."""
    name = "codebase-intelligence"
    once = feature_name_to_dir(name)
    twice = feature_name_to_dir(once)
    assert once == twice
