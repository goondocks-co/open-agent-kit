"""Machine identification for backup file naming."""

from __future__ import annotations

import getpass
import hashlib
import platform
import re
from pathlib import Path


def sanitize_identifier(identifier: str) -> str:
    """Sanitize identifier for use in filename.

    Args:
        identifier: Raw identifier string.

    Returns:
        Sanitized string safe for filenames (lowercase, alphanumeric + underscore).
    """
    sanitized = re.sub(r"[^a-zA-Z0-9]", "_", identifier)
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized[:40].strip("_").lower()


def get_machine_identifier(project_root: Path | None = None) -> str:
    """Get deterministic, privacy-preserving machine identifier for backup files.

    Format: {github_username}_{short_hash} (e.g., "octocat_a7b3c2")

    The identifier is cached in .oak/ci/machine_id for stability. If MAC address
    or hostname changes, the cached value is still used. Delete the cache file
    to regenerate.

    Args:
        project_root: Project root directory (for cache location).
            If None, auto-resolves by searching for .oak/ directory upward
            from cwd. Falls back to cwd if .oak/ is not found.

    Returns:
        Sanitized machine identifier string (e.g., "octocat_a7b3c2").
    """
    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.features.team.constants import (
        CI_DATA_DIR,
        MACHINE_ID_CACHE_FILENAME,
        MACHINE_ID_SEPARATOR,
    )

    # Auto-resolve project root by searching for .oak/ directory
    if project_root is None:
        from open_agent_kit.utils.file_utils import get_project_root

        project_root = get_project_root() or Path.cwd()

    cache_path = project_root / OAK_DIR / CI_DATA_DIR / MACHINE_ID_CACHE_FILENAME

    if cache_path.exists():
        try:
            cached_id: str = cache_path.read_text().strip()
            if cached_id:
                return cached_id
        except OSError:
            pass  # Fall through to compute

    # Compute new identifier
    github_user = _get_github_username()
    machine_hash = _get_machine_hash()
    raw_id = f"{github_user}{MACHINE_ID_SEPARATOR}{machine_hash}"
    machine_id = sanitize_identifier(raw_id)

    # Cache for stability
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(machine_id)
    except OSError:
        pass  # Non-fatal - will recompute next time

    return machine_id


def _get_github_username() -> str:
    """Resolve GitHub username through fallback chain.

    Resolution order:
    1. GITHUB_USER environment variable (manual override)
    2. gh CLI: `gh api user --jq .login` (most accurate, requires gh auth)
    3. "anonymous" (final fallback)

    Note: We intentionally do NOT use `git config user.name` because it often
    contains real names (PII) rather than GitHub usernames.

    Returns:
        GitHub username or fallback value.
    """
    import os
    import subprocess

    from open_agent_kit.features.team.constants import (
        MACHINE_ID_FALLBACK_USERNAME,
        MACHINE_ID_MAX_USERNAME_LENGTH,
        MACHINE_ID_SUBPROCESS_TIMEOUT,
    )

    # 1. Environment variable override
    env_user = os.environ.get("GITHUB_USER", "").strip()
    if env_user:
        return env_user[:MACHINE_ID_MAX_USERNAME_LENGTH]

    # 2. Try gh CLI (requires `gh auth login`)
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            check=False,
            timeout=MACHINE_ID_SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:MACHINE_ID_MAX_USERNAME_LENGTH]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # If the `gh` CLI is not available or times out, silently fall back to
        # MACHINE_ID_FALLBACK_USERNAME below to avoid breaking backup behavior.
        pass

    return MACHINE_ID_FALLBACK_USERNAME


def _get_machine_hash() -> str:
    """Generate short deterministic hash from machine-specific data.

    Uses hostname, username, and MAC address to create a unique identifier
    for this machine. The hash is truncated to 6 characters for readability.

    Returns:
        6-character hex hash string.
    """
    import uuid

    from open_agent_kit.features.team.constants import (
        MACHINE_ID_HASH_LENGTH,
    )

    raw_machine = f"{platform.node()}:{getpass.getuser()}:{uuid.getnode()}"
    return hashlib.sha256(raw_machine.encode()).hexdigest()[:MACHINE_ID_HASH_LENGTH]


def get_backup_filename(machine_id: str) -> str:
    """Get backup filename for the given machine identifier.

    Args:
        machine_id: Pre-resolved machine identifier string.

    Returns:
        Backup filename with machine identifier (e.g., "octocat_a7b3c2.sql").
    """
    return f"{machine_id}.sql"
