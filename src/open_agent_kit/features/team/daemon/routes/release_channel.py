"""Release channel info and channel-switch routes.

GET  /api/channel        — Returns current channel, version, and available
                           PyPI versions (cached 5 min).
POST /api/channel/switch — Updates cli_command in config, runs upgrade to
                           re-render skills/hooks, then restarts the daemon
                           with the new binary.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import shutil
import subprocess
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.team.cli_command import (
    resolve_ci_cli_command,
)
from open_agent_kit.features.team.constants.release_channel import (
    CI_CHANNEL_API_PATH,
    CI_CHANNEL_BETA,
    CI_CHANNEL_STABLE,
    CI_CHANNEL_SWITCH_API_PATH,
)
from open_agent_kit.features.team.daemon.state import get_state
from open_agent_kit.utils.daemon_lifecycle import delayed_shutdown
from open_agent_kit.utils.platform import get_process_detach_kwargs
from open_agent_kit.utils.release_channel import (
    SHELL,
    SWITCH_SUBPROCESS_DELAY_SECONDS,
    SwitchChannelRequest,
    build_channel_info,
    get_current_channel,
    target_binary_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["channel"])

_SHUTDOWN_DELAY_SECONDS = 2


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(CI_CHANNEL_API_PATH)
async def get_channel() -> dict:
    """Return current channel, version, and PyPI availability."""
    from pathlib import Path

    state = get_state()
    project_root = state.project_root or Path.cwd()

    cli_command = resolve_ci_cli_command(project_root)
    return await build_channel_info(cli_command)


@router.post(CI_CHANNEL_SWITCH_API_PATH, status_code=HTTPStatus.ACCEPTED)
async def switch_channel(request: SwitchChannelRequest) -> dict:
    """Switch channel: update config, run upgrade, restart daemon.

    1. Validate the target binary exists on PATH.
    2. Update ``cli_command`` in ``.oak/config.yaml``.
    3. Spawn a detached subprocess that runs ``{binary} upgrade --force``
       followed by ``{binary} team start``.
    4. Shut down the current daemon so the new one takes over.
    """
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="No project root configured.",
        )

    project_root = state.project_root
    cli_command = resolve_ci_cli_command(project_root)
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

    # Update cli_command in CI config
    try:
        from open_agent_kit.features.team.config import (
            load_ci_config,
            save_ci_config,
        )

        ci_config = load_ci_config(project_root)
        ci_config.cli_command = new_binary
        save_ci_config(project_root, ci_config)
    except Exception as exc:
        logger.warning("Could not update cli_command in CI config: %s", exc)

    # Build the switch command: upgrade assets then restart daemon
    quoted_root = shlex.quote(str(project_root))
    switch_cmd = (
        f"cd {quoted_root} && "
        f"{shlex.quote(resolved_binary)} upgrade --force && "
        f"{shlex.quote(resolved_binary)} team start"
    )

    # Spawn detached subprocess: sleep briefly, then run the switch command.
    full_cmd = f"sleep {SWITCH_SUBPROCESS_DELAY_SECONDS} && {switch_cmd}"
    detach_kwargs = get_process_detach_kwargs()
    logger.info("Spawning channel switch subprocess: %s", switch_cmd)
    try:
        subprocess.Popen(
            [SHELL, "-c", full_cmd],
            cwd=str(project_root),
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
            log_message="Channel switch initiated — shutting down daemon (SIGTERM).",
        ),
        name="channel_switch_shutdown",
    )

    return {"status": "switching"}
