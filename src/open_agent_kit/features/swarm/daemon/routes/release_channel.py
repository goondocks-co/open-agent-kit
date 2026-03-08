"""Release channel info and channel-switch routes for the swarm daemon.

GET  /api/channel        — Returns current channel, version, and available
                           PyPI versions (cached 5 min).
POST /api/channel/switch — Updates cli_command in config, runs upgrade to
                           re-render skills/hooks, then restarts the swarm
                           daemon with the new binary.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import subprocess
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.swarm.constants import (
    SWARM_CLI_COMMAND_ENV_VAR,
    SWARM_ENV_VAR_ID,
)
from open_agent_kit.features.team.constants.release_channel import (
    CI_CHANNEL_API_PATH,
    CI_CHANNEL_BETA,
    CI_CHANNEL_STABLE,
    CI_CHANNEL_SWITCH_API_PATH,
)
from open_agent_kit.utils.daemon_lifecycle import delayed_shutdown
from open_agent_kit.utils.platform import get_process_detach_kwargs
from open_agent_kit.utils.release_channel import (
    SHELL,
    SWITCH_SUBPROCESS_DELAY_SECONDS,
    SwitchChannelRequest,
    build_channel_info,
    get_current_channel,
    resolve_swarm_cli_command,
    target_binary_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["channel"])

_SHUTDOWN_DELAY_SECONDS = 2


def _resolve_cli_command() -> str:
    """Resolve the CLI command from the env var set at daemon launch."""
    return resolve_swarm_cli_command(SWARM_CLI_COMMAND_ENV_VAR)


@router.get(CI_CHANNEL_API_PATH)
async def get_channel() -> dict:
    """Return current channel, version, and PyPI availability."""
    cli_command = _resolve_cli_command()
    return await build_channel_info(cli_command)


@router.post(CI_CHANNEL_SWITCH_API_PATH, status_code=HTTPStatus.ACCEPTED)
async def switch_channel(request: SwitchChannelRequest) -> dict:
    """Switch channel: update config, run upgrade, restart swarm daemon.

    1. Validate the target binary exists on PATH.
    2. Update ``cli_command`` in ``.oak/config.yaml`` (if a project root
       is available via the team config).
    3. Spawn a detached subprocess that runs ``{binary} upgrade --force``
       followed by ``{binary} swarm restart -n {swarm_id}``.
    4. Shut down the current daemon so the new one takes over.
    """
    cli_command = _resolve_cli_command()
    current_channel = get_current_channel(cli_command)

    target = request.target_channel
    if target not in (CI_CHANNEL_STABLE, CI_CHANNEL_BETA):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid target_channel '{target}'. Must be 'stable' or 'beta'.",
        )

    if target == current_channel:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Already on the '{target}' channel.",
        )

    swarm_id = os.environ.get(SWARM_ENV_VAR_ID, "")
    if not swarm_id:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="No swarm ID configured. Cannot restart after switch.",
        )

    new_binary = target_binary_name(target)
    resolved_binary = shutil.which(new_binary)
    if not resolved_binary:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"Binary '{new_binary}' not found on PATH. "
                f"Install it first (e.g. brew install goondocks-co/oak/"
                f"{'oak-ci-beta' if target == CI_CHANNEL_BETA else 'oak-ci'})."
            ),
        )

    # Build the switch command: upgrade assets then restart swarm daemon
    switch_cmd = (
        f"{shlex.quote(resolved_binary)} upgrade --force && "
        f"{shlex.quote(resolved_binary)} swarm restart -n {shlex.quote(swarm_id)}"
    )

    # Spawn detached subprocess: sleep briefly, then run the switch command.
    full_cmd = f"sleep {SWITCH_SUBPROCESS_DELAY_SECONDS} && {switch_cmd}"
    detach_kwargs = get_process_detach_kwargs()
    logger.info("Spawning channel switch subprocess: %s", switch_cmd)
    try:
        subprocess.Popen(
            [SHELL, "-c", full_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **detach_kwargs,
        )
    except OSError as exc:
        logger.error("Failed to spawn channel switch subprocess: %s", exc)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to spawn switch subprocess: {exc}",
        ) from exc

    # Gracefully shut down so the new daemon takes over.
    asyncio.create_task(
        delayed_shutdown(
            _SHUTDOWN_DELAY_SECONDS,
            log_message="Channel switch initiated — shutting down swarm daemon (SIGTERM).",
        ),
        name="swarm_channel_switch_shutdown",
    )

    return {"status": "switching"}
