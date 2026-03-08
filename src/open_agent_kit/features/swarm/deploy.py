"""Wrangler subprocess automation for Swarm Worker.

Thin wrapper around :mod:`worker_deploy_shared` with Swarm constants.
"""

from pathlib import Path

from open_agent_kit.utils.worker_deploy_shared import (
    WORKER_DEPLOY_NPM_INSTALL_TIMEOUT,
    WORKER_DEPLOY_NPM_NOT_FOUND,
    WORKER_DEPLOY_NPX_NOT_FOUND,
    WORKER_DEPLOY_WRANGLER_TIMEOUT,
    WORKER_DEPLOY_WRANGLER_URL_PATTERN,
    WORKER_DEPLOY_WRANGLER_WHOAMI_TIMEOUT,
    DeployConfig,
    WranglerAuthInfo,
)
from open_agent_kit.utils.worker_deploy_shared import (
    check_wrangler_auth as _check_wrangler_auth,
)
from open_agent_kit.utils.worker_deploy_shared import (
    check_wrangler_available as _check_wrangler_available,
)
from open_agent_kit.utils.worker_deploy_shared import (
    run_npm_install as _run_npm_install,
)
from open_agent_kit.utils.worker_deploy_shared import (
    run_wrangler_deploy as _run_wrangler_deploy,
)

_CONFIG = DeployConfig(
    npm_install_timeout=WORKER_DEPLOY_NPM_INSTALL_TIMEOUT,
    wrangler_timeout=WORKER_DEPLOY_WRANGLER_TIMEOUT,
    wrangler_whoami_timeout=WORKER_DEPLOY_WRANGLER_WHOAMI_TIMEOUT,
    wrangler_url_pattern=WORKER_DEPLOY_WRANGLER_URL_PATTERN,
    npm_not_found=WORKER_DEPLOY_NPM_NOT_FOUND,
    npx_not_found=WORKER_DEPLOY_NPX_NOT_FOUND,
)

__all__ = [
    "WranglerAuthInfo",
    "check_wrangler_available",
    "check_wrangler_auth",
    "run_npm_install",
    "run_wrangler_deploy",
]


def check_wrangler_available(cwd: Path | None = None) -> bool:
    """Check if ``npx wrangler`` is available."""
    return _check_wrangler_available(_CONFIG, cwd)


def check_wrangler_auth(cwd: Path | None = None) -> WranglerAuthInfo | None:
    """Check Cloudflare authentication status via ``npx wrangler whoami``."""
    return _check_wrangler_auth(_CONFIG, cwd)


def run_npm_install(scaffold_dir: Path) -> tuple[bool, str]:
    """Run ``npm install`` in the scaffold directory."""
    return _run_npm_install(_CONFIG, scaffold_dir)


def run_wrangler_deploy(scaffold_dir: Path) -> tuple[bool, str | None, str]:
    """Run ``npx wrangler deploy`` in the scaffold directory."""
    return _run_wrangler_deploy(_CONFIG, scaffold_dir)
