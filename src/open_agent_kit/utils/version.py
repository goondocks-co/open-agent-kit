"""Version utilities for open-agent-kit."""

import re


def get_package_version() -> str:
    """Get the current package version.

    Returns:
        Package version string (e.g., "0.1.0")
    """
    from open_agent_kit import __version__

    return str(__version__)


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse semantic version string into components.

    Args:
        version: Version string (e.g., "1.2.3")

    Returns:
        Tuple of (major, minor, patch)

    Raises:
        ValueError: If version format is invalid

    Example:
        >>> parse_version("1.2.3")
        (1, 2, 3)
    """
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        raise ValueError(f"Invalid version format: {version}. Expected format: X.Y.Z")

    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def increment_version(current: str, bump_type: str) -> str:
    """Increment version based on bump type.

    Args:
        current: Current version string (e.g., "1.2.3")
        bump_type: Type of bump ("major", "minor", or "patch")

    Returns:
        New version string

    Raises:
        ValueError: If version format or bump type is invalid

    Examples:
        >>> increment_version("1.2.3", "major")
        '2.0.0'
        >>> increment_version("1.2.3", "minor")
        '1.3.0'
        >>> increment_version("1.2.3", "patch")
        '1.2.4'
    """
    major, minor, patch = parse_version(current)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid bump type: {bump_type}. Must be 'major', 'minor', or 'patch'")


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semantic versions.

    Args:
        v1: First version string
        v2: Second version string

    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2

    Raises:
        ValueError: If either version format is invalid

    Examples:
        >>> compare_versions("1.2.3", "1.2.4")
        -1
        >>> compare_versions("2.0.0", "1.9.9")
        1
        >>> compare_versions("1.2.3", "1.2.3")
        0
    """
    major1, minor1, patch1 = parse_version(v1)
    major2, minor2, patch2 = parse_version(v2)

    if (major1, minor1, patch1) < (major2, minor2, patch2):
        return -1
    elif (major1, minor1, patch1) > (major2, minor2, patch2):
        return 1
    else:
        return 0


def is_valid_version(version: str) -> bool:
    """Check if a version string is valid semantic versioning format.

    Args:
        version: Version string to validate

    Returns:
        True if valid, False otherwise

    Example:
        >>> is_valid_version("1.2.3")
        True
        >>> is_valid_version("1.2")
        False
    """
    try:
        parse_version(version)
        return True
    except ValueError:
        return False
