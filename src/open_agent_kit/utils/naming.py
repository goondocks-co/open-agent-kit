"""Naming utilities for OAK conventions.

Centralises the feature-name ↔ directory-name conversion so every
service that needs it imports from one place.
"""


def feature_name_to_dir(feature_name: str) -> str:
    """Convert feature name to directory name (hyphens to underscores).

    Feature names use hyphens (codebase-intelligence) but Python packages
    use underscores (codebase_intelligence).

    Args:
        feature_name: Feature name with hyphens

    Returns:
        Directory name with underscores
    """
    return feature_name.replace("-", "_")
