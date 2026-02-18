"""Wrangler subprocess automation for Cloud MCP Relay.

Provides functions to check prerequisites, install dependencies, and deploy
the scaffolded Cloudflare Worker project via ``npx wrangler``.
"""

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_DEPLOY_NPM_INSTALL_TIMEOUT,
    CLOUD_RELAY_DEPLOY_NPM_NOT_FOUND,
    CLOUD_RELAY_DEPLOY_NPX_NOT_FOUND,
    CLOUD_RELAY_DEPLOY_WRANGLER_TIMEOUT,
    CLOUD_RELAY_DEPLOY_WRANGLER_URL_PATTERN,
    CLOUD_RELAY_DEPLOY_WRANGLER_WHOAMI_TIMEOUT,
)

logger = logging.getLogger(__name__)


@dataclass
class WranglerAuthInfo:
    """Result of ``npx wrangler whoami``.

    Attributes:
        account_name: Cloudflare account name (if authenticated).
        account_id: Cloudflare account ID (if authenticated).
        authenticated: Whether the user is logged in to Cloudflare.
    """

    account_name: str | None = None
    account_id: str | None = None
    authenticated: bool = False


def check_wrangler_available(cwd: Path | None = None) -> bool:
    """Check if ``npx wrangler`` is available.

    Args:
        cwd: Working directory for the subprocess. Falls back to the current
            directory if *None* or the path does not exist.

    Returns:
        True if ``npx wrangler --version`` succeeds.
    """
    run_cwd = cwd if cwd and cwd.is_dir() else None
    try:
        result = subprocess.run(
            ["npx", "wrangler", "--version"],
            capture_output=True,
            text=True,
            cwd=run_cwd,
            timeout=CLOUD_RELAY_DEPLOY_WRANGLER_WHOAMI_TIMEOUT,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("wrangler availability check failed: %s", exc)
        return False


def check_wrangler_auth(cwd: Path | None = None) -> WranglerAuthInfo | None:
    """Check Cloudflare authentication status via ``npx wrangler whoami``.

    Parses account name and ID from the table output.

    Args:
        cwd: Working directory for the subprocess. Falls back to the current
            directory if *None* or the path does not exist.

    Returns:
        WranglerAuthInfo with parsed results, or None if the command fails.
    """
    run_cwd = cwd if cwd and cwd.is_dir() else None
    try:
        result = subprocess.run(
            ["npx", "wrangler", "whoami"],
            capture_output=True,
            text=True,
            cwd=run_cwd,
            timeout=CLOUD_RELAY_DEPLOY_WRANGLER_WHOAMI_TIMEOUT,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("wrangler whoami failed: %s", exc)
        return None

    if result.returncode != 0:
        return WranglerAuthInfo(authenticated=False)

    output = result.stdout + result.stderr

    # Parse account name and ID from wrangler whoami table output.
    # Table lines look like: │ Account Name │ Account ID │
    account_name: str | None = None
    account_id: str | None = None

    for line in output.splitlines():
        # Skip header/separator lines
        if "Account Name" in line and "Account ID" in line:
            continue
        # Look for data rows with pipe separators
        parts = [p.strip() for p in line.split("│") if p.strip()]
        if len(parts) >= 2:
            # First data row after header contains account info
            candidate_name = parts[0]
            candidate_id = parts[1]
            # Account IDs are 32-char hex strings
            if re.fullmatch(r"[0-9a-f]{32}", candidate_id):
                account_name = candidate_name
                account_id = candidate_id
                break

    return WranglerAuthInfo(
        account_name=account_name,
        account_id=account_id,
        authenticated=account_name is not None,
    )


def run_npm_install(scaffold_dir: Path) -> tuple[bool, str]:
    """Run ``npm install`` in the scaffold directory.

    Args:
        scaffold_dir: Directory containing the scaffolded Worker project.

    Returns:
        Tuple of (success, combined_output).
    """
    try:
        result = subprocess.run(
            ["npm", "install"],
            capture_output=True,
            text=True,
            cwd=scaffold_dir,
            timeout=CLOUD_RELAY_DEPLOY_NPM_INSTALL_TIMEOUT,
        )
        combined = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, combined
    except FileNotFoundError:
        return False, CLOUD_RELAY_DEPLOY_NPM_NOT_FOUND
    except subprocess.TimeoutExpired:
        return False, f"npm install timed out after {CLOUD_RELAY_DEPLOY_NPM_INSTALL_TIMEOUT}s"
    except OSError as exc:
        return False, str(exc)


def run_wrangler_deploy(scaffold_dir: Path) -> tuple[bool, str | None, str]:
    """Run ``npx wrangler deploy`` in the scaffold directory.

    Parses the deployed Worker URL from the command output.

    Args:
        scaffold_dir: Directory containing the scaffolded Worker project.

    Returns:
        Tuple of (success, worker_url_or_none, combined_output).
    """
    try:
        result = subprocess.run(
            ["npx", "wrangler", "deploy"],
            capture_output=True,
            text=True,
            cwd=scaffold_dir,
            timeout=CLOUD_RELAY_DEPLOY_WRANGLER_TIMEOUT,
        )
        combined = (result.stdout or "") + (result.stderr or "")

        if result.returncode != 0:
            return False, None, combined

        # Extract worker URL from output
        match = re.search(CLOUD_RELAY_DEPLOY_WRANGLER_URL_PATTERN, combined)
        worker_url = match.group(0) if match else None

        return True, worker_url, combined
    except FileNotFoundError:
        return False, None, CLOUD_RELAY_DEPLOY_NPX_NOT_FOUND
    except subprocess.TimeoutExpired:
        return (
            False,
            None,
            f"wrangler deploy timed out after {CLOUD_RELAY_DEPLOY_WRANGLER_TIMEOUT}s",
        )
    except OSError as exc:
        return False, None, str(exc)
