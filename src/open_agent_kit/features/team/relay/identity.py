"""Project identity for Oak Teams sync.

Derives a stable project identity from the directory name and git remote URL,
used to identify the project across team members.
"""

import hashlib
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from open_agent_kit.features.team.constants.team import (
    TEAM_PROJECT_ID_SEPARATOR,
    TEAM_REMOTE_HASH_LENGTH,
)

logger = logging.getLogger(__name__)

# Timeout for git remote command (seconds)
GIT_REMOTE_TIMEOUT = 5


@dataclass(frozen=True)
class ProjectIdentity:
    """Stable identity for a project across team members.

    Attributes:
        slug: Project directory name.
        remote_hash: Truncated MD5 hash of the normalized git remote URL.
        full_id: Combined identifier in "{slug}:{remote_hash}" format.
    """

    slug: str
    remote_hash: str
    full_id: str  # "{slug}:{remote_hash}" (hash is truncated SHA-256)


def _normalize_git_remote(url: str) -> str:
    """Normalize a git remote URL for consistent hashing.

    Strips trailing slashes and .git suffix.
    Same normalization as daemon/manager.py:derive_port_from_git_remote.

    Args:
        url: Raw git remote URL.

    Returns:
        Normalized URL string.
    """
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return url


def get_project_identity(project_root: Path) -> ProjectIdentity:
    """Derive project identity from directory name and git remote URL.

    Args:
        project_root: Project root directory.

    Returns:
        ProjectIdentity with slug, remote_hash, and full_id.
    """
    slug = project_root.name

    remote_hash = _get_remote_hash(project_root)
    if remote_hash is None:
        # Fallback: hash the absolute path
        path_str = str(project_root.resolve())
        remote_hash = hashlib.sha256(path_str.encode()).hexdigest()[:TEAM_REMOTE_HASH_LENGTH]

    full_id = f"{slug}{TEAM_PROJECT_ID_SEPARATOR}{remote_hash}"
    return ProjectIdentity(slug=slug, remote_hash=remote_hash, full_id=full_id)


def _get_remote_hash(project_root: Path) -> str | None:
    """Get hash of normalized git remote URL.

    Args:
        project_root: Project root directory.

    Returns:
        Truncated SHA-256 hash string, or None if git remote is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=GIT_REMOTE_TIMEOUT,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        normalized = _normalize_git_remote(result.stdout.strip())
        return hashlib.sha256(normalized.encode()).hexdigest()[:TEAM_REMOTE_HASH_LENGTH]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("Failed to get git remote for project identity: %s", e)
        return None
