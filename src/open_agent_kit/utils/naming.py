"""Naming utilities for OAK conventions.

Centralises the feature-name ↔ directory-name conversion so every
service that needs it imports from one place.
"""


def feature_name_to_dir(feature_name: str) -> str:
    """Convert feature name to directory name (hyphens to underscores).

    Feature names use hyphens (team) but Python packages
    use underscores (team).

    Args:
        feature_name: Feature name with hyphens

    Returns:
        Directory name with underscores
    """
    return feature_name.replace("-", "_")
