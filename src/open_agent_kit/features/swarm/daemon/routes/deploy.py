"""Deploy routes for the swarm daemon UI."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_DEPLOY_AUTH,
    SWARM_DAEMON_API_PATH_DEPLOY_INSTALL,
    SWARM_DAEMON_API_PATH_DEPLOY_RUN,
    SWARM_DAEMON_API_PATH_DEPLOY_SCAFFOLD,
    SWARM_DAEMON_API_PATH_DEPLOY_STATUS,
    SWARM_DAEMON_CONFIG_DIR,
    SWARM_ROUTE_TAG,
    SWARM_SCAFFOLD_NODE_MODULES_DIR,
    SWARM_SCAFFOLD_WORKER_SUBDIR,
)
from open_agent_kit.features.swarm.daemon.state import get_swarm_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


def _get_scaffold_dir() -> Path | None:
    """Get the scaffold directory for the current swarm."""
    state = get_swarm_state()
    if not state.swarm_id:
        return None
    return (
        Path(SWARM_DAEMON_CONFIG_DIR).expanduser() / state.swarm_id / SWARM_SCAFFOLD_WORKER_SUBDIR
    )


@router.get(SWARM_DAEMON_API_PATH_DEPLOY_STATUS)
async def deploy_status() -> dict:
    """Check scaffold status and worker deployment info."""
    state = get_swarm_state()
    scaffold_dir = _get_scaffold_dir()
    scaffolded = scaffold_dir is not None and scaffold_dir.is_dir()
    node_modules = (
        scaffolded
        and scaffold_dir is not None
        and (scaffold_dir / SWARM_SCAFFOLD_NODE_MODULES_DIR).is_dir()
    )

    return {
        "scaffolded": scaffolded,
        "scaffold_dir": str(scaffold_dir) if scaffold_dir else None,
        "node_modules_installed": node_modules,
        "worker_url": state.swarm_url or None,
        "swarm_id": state.swarm_id,
    }


@router.get(SWARM_DAEMON_API_PATH_DEPLOY_AUTH)
async def deploy_auth() -> dict:
    """Check Cloudflare authentication status."""
    from open_agent_kit.features.swarm.deploy import check_wrangler_auth, check_wrangler_available

    available = await asyncio.to_thread(check_wrangler_available)
    if not available:
        return {"authenticated": False, "wrangler_available": False, "account_name": None}

    auth_info = await asyncio.to_thread(check_wrangler_auth)
    if auth_info:
        return {
            "authenticated": auth_info.authenticated,
            "wrangler_available": True,
            "account_name": auth_info.account_name,
            "account_id": auth_info.account_id,
        }
    return {"authenticated": False, "wrangler_available": True, "account_name": None}


class ScaffoldRequest(BaseModel):
    """Scaffold request body."""

    force: bool = False


@router.post(SWARM_DAEMON_API_PATH_DEPLOY_SCAFFOLD)
async def deploy_scaffold(body: ScaffoldRequest) -> dict:
    """Scaffold the worker template."""
    from open_agent_kit.features.swarm.scaffold import (
        generate_token,
        make_worker_name,
        render_worker_template,
    )

    state = get_swarm_state()
    if not state.swarm_id:
        return {"success": False, "error": "No swarm ID configured"}

    scaffold_dir = _get_scaffold_dir()
    if not scaffold_dir:
        return {"success": False, "error": "Cannot determine scaffold directory"}

    try:
        swarm_token = generate_token()
        worker_name = make_worker_name(state.swarm_id)
        await asyncio.to_thread(
            render_worker_template,
            output_dir=scaffold_dir,
            swarm_token=swarm_token,
            worker_name=worker_name,
            force=body.force,
        )
        return {
            "success": True,
            "scaffold_dir": str(scaffold_dir),
            "worker_name": worker_name,
        }
    except Exception as exc:
        logger.error("Scaffold failed: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post(SWARM_DAEMON_API_PATH_DEPLOY_INSTALL)
async def deploy_install() -> dict:
    """Run npm install in the scaffold directory."""
    from open_agent_kit.features.swarm.deploy import run_npm_install

    scaffold_dir = _get_scaffold_dir()
    if not scaffold_dir or not scaffold_dir.is_dir():
        return {"success": False, "error": "Worker not scaffolded. Run scaffold first."}

    success, output = await asyncio.to_thread(run_npm_install, scaffold_dir)
    return {"success": success, "output": output}


@router.post(SWARM_DAEMON_API_PATH_DEPLOY_RUN)
async def deploy_run() -> dict:
    """Run wrangler deploy."""
    from open_agent_kit.features.swarm.deploy import run_wrangler_deploy

    scaffold_dir = _get_scaffold_dir()
    if not scaffold_dir or not scaffold_dir.is_dir():
        return {"success": False, "error": "Worker not scaffolded. Run scaffold first."}

    success, worker_url, output = await asyncio.to_thread(run_wrangler_deploy, scaffold_dir)
    return {
        "success": success,
        "worker_url": worker_url,
        "output": output,
    }
