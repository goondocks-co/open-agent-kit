"""Tests for version utility functions."""

import pytest

from open_agent_kit.utils.version import (
    compare_versions,
    increment_version,
    is_valid_version,
    parse_version,
)


def test_parse_version_valid() -> None:
    """Test parsing valid semantic versions."""
    assert parse_version("1.0.0") == (1, 0, 0)
    assert parse_version("2.3.4") == (2, 3, 4)
    assert parse_version("0.0.1") == (0, 0, 1)
    assert parse_version("10.20.30") == (10, 20, 30)


def test_parse_version_invalid() -> None:
    """Test parsing invalid version strings."""
    with pytest.raises(ValueError, match="Invalid version format"):
        parse_version("1.0")
    with pytest.raises(ValueError, match="Invalid version format"):
        parse_version("1.0.0.0")
    with pytest.raises(ValueError, match="Invalid version format"):
        parse_version("v1.0.0")
    with pytest.raises(ValueError, match="Invalid version format"):
        parse_version("1.0.x")
    with pytest.raises(ValueError, match="Invalid version format"):
        parse_version("invalid")


def test_is_valid_version() -> None:
    """Test version format validation."""
    assert is_valid_version("1.0.0") is True
    assert is_valid_version("2.3.4") is True
    assert is_valid_version("0.0.1") is True
    assert is_valid_version("10.20.30") is True
    assert is_valid_version("1.0") is False
    assert is_valid_version("1.0.0.0") is False
    assert is_valid_version("v1.0.0") is False
    assert is_valid_version("1.0.x") is False
    assert is_valid_version("invalid") is False
    assert is_valid_version("") is False


def test_increment_version_major() -> None:
    """Test incrementing major version."""
    assert increment_version("1.0.0", "major") == "2.0.0"
    assert increment_version("1.5.3", "major") == "2.0.0"
    assert increment_version("0.1.0", "major") == "1.0.0"
    assert increment_version("9.9.9", "major") == "10.0.0"


def test_increment_version_minor() -> None:
    """Test incrementing minor version."""
    assert increment_version("1.0.0", "minor") == "1.1.0"
    assert increment_version("1.5.3", "minor") == "1.6.0"
    assert increment_version("0.1.0", "minor") == "0.2.0"
    assert increment_version("1.9.9", "minor") == "1.10.0"


def test_increment_version_patch() -> None:
    """Test incrementing patch version."""
    assert increment_version("1.0.0", "patch") == "1.0.1"
    assert increment_version("1.5.3", "patch") == "1.5.4"
    assert increment_version("0.1.0", "patch") == "0.1.1"
    assert increment_version("1.0.9", "patch") == "1.0.10"


def test_increment_version_invalid_type() -> None:
    """Test incrementing with invalid bump type."""
    with pytest.raises(ValueError, match="Invalid bump type"):
        increment_version("1.0.0", "invalid")
    with pytest.raises(ValueError, match="Invalid bump type"):
        increment_version("1.0.0", "Major")
    with pytest.raises(ValueError, match="Invalid bump type"):
        increment_version("1.0.0", "")


def test_increment_version_invalid_version() -> None:
    """Test incrementing invalid version string."""
    with pytest.raises(ValueError, match="Invalid version format"):
        increment_version("1.0", "major")
    with pytest.raises(ValueError, match="Invalid version format"):
        increment_version("invalid", "minor")


def test_compare_versions_equal() -> None:
    """Test comparing equal versions."""
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("2.3.4", "2.3.4") == 0
    assert compare_versions("0.0.1", "0.0.1") == 0


def test_compare_versions_less_than() -> None:
    """Test comparing when first version is less than second."""
    assert compare_versions("1.0.0", "2.0.0") == -1
    assert compare_versions("0.1.0", "1.0.0") == -1
    assert compare_versions("1.0.0", "1.1.0") == -1
    assert compare_versions("1.5.0", "1.6.0") == -1
    assert compare_versions("1.0.0", "1.0.1") == -1
    assert compare_versions("1.0.5", "1.0.6") == -1
    assert compare_versions("1.0.0", "2.1.0") == -1
    assert compare_versions("1.9.9", "2.0.0") == -1


def test_compare_versions_greater_than() -> None:
    """Test comparing when first version is greater than second."""
    assert compare_versions("2.0.0", "1.0.0") == 1
    assert compare_versions("1.0.0", "0.1.0") == 1
    assert compare_versions("1.1.0", "1.0.0") == 1
    assert compare_versions("1.6.0", "1.5.0") == 1
    assert compare_versions("1.0.1", "1.0.0") == 1
    assert compare_versions("1.0.6", "1.0.5") == 1
    assert compare_versions("2.1.0", "1.0.0") == 1
    assert compare_versions("2.0.0", "1.9.9") == 1


def test_compare_versions_invalid() -> None:
    """Test comparing invalid versions."""
    with pytest.raises(ValueError, match="Invalid version format"):
        compare_versions("1.0", "1.0.0")
    with pytest.raises(ValueError, match="Invalid version format"):
        compare_versions("1.0.0", "1.0")
    with pytest.raises(ValueError, match="Invalid version format"):
        compare_versions("invalid", "1.0.0")


def test_increment_version_sequence() -> None:
    """Test incrementing versions in sequence."""
    version = "1.0.0"
    version = increment_version(version, "patch")
    version = increment_version(version, "patch")
    version = increment_version(version, "patch")
    assert version == "1.0.3"
    version = increment_version(version, "minor")
    assert version == "1.1.0"
    version = increment_version(version, "patch")
    version = increment_version(version, "patch")
    assert version == "1.1.2"
    version = increment_version(version, "major")
    assert version == "2.0.0"


def test_version_ordering() -> None:
    """Test version ordering with comparison."""
    versions = ["1.0.0", "2.0.0", "1.5.0", "1.0.1", "0.1.0", "1.5.1"]
    from functools import cmp_to_key

    sorted_versions = sorted(versions, key=cmp_to_key(compare_versions))
    assert sorted_versions == ["0.1.0", "1.0.0", "1.0.1", "1.5.0", "1.5.1", "2.0.0"]


def test_parse_version_with_leading_zeros() -> None:
    """Test parsing versions with leading zeros."""
    assert parse_version("01.00.00") == (1, 0, 0)
    assert parse_version("1.02.3") == (1, 2, 3)


def test_increment_version_edge_cases() -> None:
    """Test increment version edge cases."""
    assert increment_version("999.999.999", "major") == "1000.0.0"
    assert increment_version("999.999.999", "minor") == "999.1000.0"
    assert increment_version("999.999.999", "patch") == "999.999.1000"
    assert increment_version("0.0.0", "major") == "1.0.0"
    assert increment_version("0.0.0", "minor") == "0.1.0"
    assert increment_version("0.0.0", "patch") == "0.0.1"
