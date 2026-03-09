"""Deploy routes for the swarm daemon UI."""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.config import (
    get_swarm_config_dir,
    load_swarm_config,
    save_swarm_config,
)
from open_agent_kit.features.swarm.constants import (
    CI_CONFIG_SWARM_KEY_AGENT_TOKEN,
    CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN,
    CI_CONFIG_SWARM_KEY_DEPLOYED_TEMPLATE_HASH,
    CI_CONFIG_SWARM_KEY_URL,
    SWARM_DAEMON_API_PATH_DEPLOY_AUTH,
    SWARM_DAEMON_API_PATH_DEPLOY_INSTALL,
    SWARM_DAEMON_API_PATH_DEPLOY_RUN,
    SWARM_DAEMON_API_PATH_DEPLOY_SCAFFOLD,
    SWARM_DAEMON_API_PATH_DEPLOY_SETTINGS,
    SWARM_DAEMON_API_PATH_DEPLOY_STATUS,
    SWARM_DEPLOY_ERROR_NO_SCAFFOLD_DIR,
    SWARM_DEPLOY_ERROR_NO_SWARM_ID,
    SWARM_DEPLOY_ERROR_NO_TOKEN,
    SWARM_DEPLOY_ERROR_NOT_SCAFFOLDED,
    SWARM_ROUTE_TAG,
    SWARM_SCAFFOLD_WORKER_SUBDIR,
)
from open_agent_kit.features.swarm.daemon.state import get_swarm_state
from open_agent_kit.features.swarm.scaffold import compute_template_hash, make_worker_name
from open_agent_kit.utils.worker_health import invalidate_health_cache, probe_worker_health

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


def _get_scaffold_dir() -> Path | None:
    """Get the scaffold directory for the current swarm."""
    state = get_swarm_state()
    if not state.swarm_id:
        return None
    return get_swarm_config_dir(state.swarm_id) / SWARM_SCAFFOLD_WORKER_SUBDIR


@router.get(SWARM_DAEMON_API_PATH_DEPLOY_STATUS)
async def deploy_status() -> dict:
    """Check deploy status using stored config and health probe."""
    state = get_swarm_state()
    worker_name = make_worker_name(state.swarm_id) if state.swarm_id else None

    # Compute update_available from in-memory cached hash (populated at startup
    # and updated after deploy)
    update_available = False
    if state.deployed_template_hash:
        update_available = state.deployed_template_hash != compute_template_hash()

    # Health probe (cached, 30s TTL)
    worker_reachable: bool | None = None
    if state.swarm_url:
        worker_reachable = await probe_worker_health(state.swarm_url)

    return {
        "worker_url": state.swarm_url or None,
        "swarm_id": state.swarm_id,
        "worker_name": worker_name,
        "custom_domain": state.custom_domain or None,
        "update_available": update_available,
        "worker_reachable": worker_reachable,
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
    """Scaffold the worker template using the token from config."""
    from open_agent_kit.features.swarm.scaffold import render_worker_template

    state = get_swarm_state()
    if not state.swarm_id:
        return {"success": False, "error": SWARM_DEPLOY_ERROR_NO_SWARM_ID}

    scaffold_dir = _get_scaffold_dir()
    if not scaffold_dir:
        return {"success": False, "error": SWARM_DEPLOY_ERROR_NO_SCAFFOLD_DIR}

    # Use token from daemon state (which came from config via env vars)
    swarm_token = state.swarm_token
    if not swarm_token:
        return {"success": False, "error": SWARM_DEPLOY_ERROR_NO_TOKEN}

    # Get or generate agent token
    config = load_swarm_config(state.swarm_id) if state.swarm_id else {}
    agent_token = config.get(CI_CONFIG_SWARM_KEY_AGENT_TOKEN, "") if config else ""
    if not agent_token:
        from open_agent_kit.features.swarm.scaffold import generate_token

        agent_token = generate_token()
        if state.swarm_id and config is not None:
            config[CI_CONFIG_SWARM_KEY_AGENT_TOKEN] = agent_token
            save_swarm_config(state.swarm_id, config)

    try:
        worker_name = make_worker_name(state.swarm_id)
        await asyncio.to_thread(
            render_worker_template,
            output_dir=scaffold_dir,
            swarm_token=swarm_token,
            worker_name=worker_name,
            custom_domain=state.custom_domain or None,
            force=body.force,
            agent_token=agent_token,
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
        return {"success": False, "error": SWARM_DEPLOY_ERROR_NOT_SCAFFOLDED}

    success, output = await asyncio.to_thread(run_npm_install, scaffold_dir)
    return {"success": success, "output": output}


@router.post(SWARM_DAEMON_API_PATH_DEPLOY_RUN)
async def deploy_run() -> dict:
    """Run wrangler deploy and persist the result to config."""
    from open_agent_kit.features.swarm.deploy import run_wrangler_deploy

    state = get_swarm_state()
    scaffold_dir = _get_scaffold_dir()
    if not scaffold_dir or not scaffold_dir.is_dir():
        return {"success": False, "error": SWARM_DEPLOY_ERROR_NOT_SCAFFOLDED}

    success, worker_url, output = await asyncio.to_thread(run_wrangler_deploy, scaffold_dir)

    if success and worker_url and state.swarm_id:
        # Prefer custom domain URL when configured
        effective_url = worker_url
        if state.custom_domain:
            worker_name = make_worker_name(state.swarm_id)
            effective_url = f"https://{worker_name}.{state.custom_domain}"

        # Persist URL and template hash in a single config save
        template_hash = compute_template_hash()
        config = load_swarm_config(state.swarm_id) or {}
        config[CI_CONFIG_SWARM_KEY_URL] = effective_url
        config[CI_CONFIG_SWARM_KEY_DEPLOYED_TEMPLATE_HASH] = template_hash
        save_swarm_config(state.swarm_id, config)

        # Update in-memory state so daemon connects without restart
        state.swarm_url = effective_url
        state.deployed_template_hash = template_hash

        # Create a fresh SwarmWorkerClient for the new URL
        from open_agent_kit.features.swarm.daemon.client import SwarmWorkerClient

        state.http_client = SwarmWorkerClient(
            swarm_url=effective_url,
            swarm_token=state.swarm_token,
        )

        # Flush all health cache entries (old URL entry would linger otherwise)
        invalidate_health_cache()

    return {
        "success": success,
        "worker_url": worker_url,
        "output": output,
    }


class DeploySettingsRequest(BaseModel):
    """Deploy settings request body."""

    custom_domain: str | None = None


def _normalize_domain(raw: str) -> str:
    """Strip protocol prefix and trailing slashes from a domain string."""
    domain = raw.strip()
    for prefix in ("https://", "http://"):
        if domain.lower().startswith(prefix):
            domain = domain[len(prefix) :]
    return domain.rstrip("/")


@router.put(SWARM_DAEMON_API_PATH_DEPLOY_SETTINGS)
async def deploy_settings(body: DeploySettingsRequest) -> dict:
    """Save deploy settings (custom domain) and re-render wrangler.toml."""
    from open_agent_kit.features.swarm.scaffold import render_wrangler_config

    state = get_swarm_state()
    if not state.swarm_id:
        return {"success": False, "error": SWARM_DEPLOY_ERROR_NO_SWARM_ID}

    # Normalize and persist
    custom_domain = _normalize_domain(body.custom_domain) if body.custom_domain else ""

    config = load_swarm_config(state.swarm_id) or {}
    config[CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN] = custom_domain
    save_swarm_config(state.swarm_id, config)

    state.custom_domain = custom_domain

    worker_name = make_worker_name(state.swarm_id)

    # Update swarm_url to reflect custom domain when deployed
    if state.swarm_url:
        if custom_domain:
            effective_url = f"https://{worker_name}.{custom_domain}"
        else:
            # Clearing domain: fall back to workers.dev URL from wrangler output.
            # We can't recover the original workers.dev URL, so keep current.
            effective_url = state.swarm_url

        if effective_url != state.swarm_url:
            state.swarm_url = effective_url
            config[CI_CONFIG_SWARM_KEY_URL] = effective_url
            save_swarm_config(state.swarm_id, config)

            # Reconnect client with new URL
            from open_agent_kit.features.swarm.daemon.client import (
                SwarmWorkerClient,
            )

            state.http_client = SwarmWorkerClient(
                swarm_url=effective_url,
                swarm_token=state.swarm_token,
            )

    # Re-render wrangler.toml if scaffold exists
    scaffold_dir = _get_scaffold_dir()
    if scaffold_dir and scaffold_dir.is_dir():
        agent_token = config.get(CI_CONFIG_SWARM_KEY_AGENT_TOKEN, "")
        await asyncio.to_thread(
            render_wrangler_config,
            scaffold_dir,
            state.swarm_token,
            worker_name,
            custom_domain or None,
            agent_token,
        )
        # Flush all cached health results (old URL entry would linger)
        invalidate_health_cache()

    return await deploy_status()
