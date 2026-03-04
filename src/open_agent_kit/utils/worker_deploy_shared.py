"""Shared Wrangler subprocess automation for Cloudflare Worker deploys.

Provides functions to check prerequisites, install dependencies, and deploy
a scaffolded Cloudflare Worker project via ``npx wrangler``.  Both the Cloud
Relay and Swarm modules delegate to these shared implementations, passing
their own ``DeployConfig`` to customise timeouts and error messages.
"""

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Shared Cloudflare Worker deploy constants (single source of truth).
WORKER_DEPLOY_NPM_INSTALL_TIMEOUT: Final[int] = 120
WORKER_DEPLOY_WRANGLER_TIMEOUT: Final[int] = 60
WORKER_DEPLOY_WRANGLER_URL_PATTERN: Final[str] = r"https://[^\s]+\.workers\.dev[^\s]*"
WORKER_DEPLOY_WRANGLER_WHOAMI_TIMEOUT: Final[int] = 15
WORKER_DEPLOY_NPM_NOT_FOUND: Final[str] = "npm not found"
WORKER_DEPLOY_NPX_NOT_FOUND: Final[str] = "npx/wrangler not found"

logger = logging.getLogger(__name__)

# Path to wrangler's actual bin script inside node_modules.
# Node.js v25+ copies .bin entries instead of symlinking, which breaks
# wrangler's relative ``../wrangler-dist/cli.js`` resolution.  Using the
# direct path avoids this issue entirely.
_WRANGLER_BIN_RELATIVE: Final[str] = "node_modules/wrangler/bin/wrangler.js"


def _wrangler_cmd(cwd: Path | None, *args: str) -> list[str]:
    """Build the command list to invoke wrangler.

    Prefers the local ``node_modules`` binary when *cwd* contains an installed
    copy of wrangler (avoids Node.js v25 ``npx`` symlink-copy bug).  Falls
    back to ``npx wrangler`` otherwise.
    """
    if cwd and (cwd / _WRANGLER_BIN_RELATIVE).is_file():
        return ["node", str(cwd / _WRANGLER_BIN_RELATIVE), *args]
    return ["npx", "wrangler", *args]


@dataclass(frozen=True)
class DeployConfig:
    """Per-module constants that vary between Cloud Relay and Swarm deploys."""

    npm_install_timeout: int
    wrangler_timeout: int
    wrangler_whoami_timeout: int
    wrangler_url_pattern: str
    npm_not_found: str
    npx_not_found: str


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


def check_wrangler_available(config: DeployConfig, cwd: Path | None = None) -> bool:
    """Check if ``npx wrangler`` is available.

    Args:
        config: Deploy configuration with timeout values.
        cwd: Working directory for the subprocess. Falls back to the current
            directory if *None* or the path does not exist.

    Returns:
        True if ``npx wrangler --version`` succeeds.
    """
    run_cwd = cwd if cwd and cwd.is_dir() else None
    cmd = _wrangler_cmd(run_cwd, "--version")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=run_cwd,
            timeout=config.wrangler_whoami_timeout,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("wrangler availability check failed: %s", exc)
        return False


def check_wrangler_auth(config: DeployConfig, cwd: Path | None = None) -> WranglerAuthInfo | None:
    """Check Cloudflare authentication status via ``npx wrangler whoami``.

    Parses account name and ID from the table output.

    Args:
        config: Deploy configuration with timeout values.
        cwd: Working directory for the subprocess. Falls back to the current
            directory if *None* or the path does not exist.

    Returns:
        WranglerAuthInfo with parsed results, or None if the command fails.
    """
    run_cwd = cwd if cwd and cwd.is_dir() else None
    cmd = _wrangler_cmd(run_cwd, "whoami")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=run_cwd,
            timeout=config.wrangler_whoami_timeout,
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


def run_npm_install(config: DeployConfig, scaffold_dir: Path) -> tuple[bool, str]:
    """Run ``npm install`` in the scaffold directory.

    Args:
        config: Deploy configuration with timeout values and error messages.
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
            timeout=config.npm_install_timeout,
        )
        combined = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, combined
    except FileNotFoundError:
        return False, config.npm_not_found
    except subprocess.TimeoutExpired:
        return False, f"npm install timed out after {config.npm_install_timeout}s"
    except OSError as exc:
        return False, str(exc)


def run_wrangler_deploy(config: DeployConfig, scaffold_dir: Path) -> tuple[bool, str | None, str]:
    """Run ``npx wrangler deploy`` in the scaffold directory.

    Parses the deployed Worker URL from the command output.

    Args:
        config: Deploy configuration with timeout values and error messages.
        scaffold_dir: Directory containing the scaffolded Worker project.

    Returns:
        Tuple of (success, worker_url_or_none, combined_output).
    """
    cmd = _wrangler_cmd(scaffold_dir, "deploy")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=scaffold_dir,
            timeout=config.wrangler_timeout,
        )
        combined = (result.stdout or "") + (result.stderr or "")

        if result.returncode != 0:
            return False, None, combined

        # Extract worker URL from output
        match = re.search(config.wrangler_url_pattern, combined)
        worker_url = match.group(0) if match else None

        return True, worker_url, combined
    except FileNotFoundError:
        return False, None, config.npx_not_found
    except subprocess.TimeoutExpired:
        return (
            False,
            None,
            f"wrangler deploy timed out after {config.wrangler_timeout}s",
        )
    except OSError as exc:
        return False, None, str(exc)
