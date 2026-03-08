"""Self-restart and upgrade-and-restart routes for the CI daemon.

Uses ``/bin/sh`` (not ``sys.executable``) for the restarter subprocess because
after a package-manager upgrade (e.g. Homebrew) the old Python interpreter that
started this daemon may have been deleted from disk.
"""

import asyncio
import logging
import shlex
import subprocess
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

if TYPE_CHECKING:
    from open_agent_kit.services.upgrade_service import UpgradePlan

from open_agent_kit.features.team.cli_command import (
    resolve_ci_cli_command,
)
from open_agent_kit.features.team.constants import (
    CI_RESTART_API_PATH,
    CI_RESTART_ERROR_NO_PROJECT_ROOT,
    CI_RESTART_ERROR_SPAWN_DETAIL,
    CI_RESTART_LOG_SCHEDULING_SHUTDOWN,
    CI_RESTART_LOG_SPAWN_FAILED,
    CI_RESTART_LOG_SPAWNING,
    CI_RESTART_ROUTE_TAG,
    CI_RESTART_SHUTDOWN_DELAY_SECONDS,
    CI_RESTART_STATUS_RESTARTING,
    CI_RESTART_SUBPROCESS_DELAY_SECONDS,
    CI_SHUTDOWN_LOG_SIGTERM,
    CI_UPGRADE_AND_RESTART_API_PATH,
    CI_UPGRADE_AND_RESTART_DETAIL_RESTART_FAILED,
    CI_UPGRADE_AND_RESTART_ERROR_FAILED,
    CI_UPGRADE_AND_RESTART_ERROR_PARTIAL_FAILURE,
    CI_UPGRADE_AND_RESTART_ERROR_SPAWN_FAILED,
    CI_UPGRADE_AND_RESTART_LOG_FAILED,
    CI_UPGRADE_AND_RESTART_LOG_PARTIAL_FAILURE,
    CI_UPGRADE_AND_RESTART_STATUS,
    CI_UPGRADE_AND_RESTART_STATUS_UP_TO_DATE,
    CI_UPGRADE_AND_RESTART_STATUS_UPGRADED,
)
from open_agent_kit.features.team.daemon.state import get_state
from open_agent_kit.utils.daemon_lifecycle import delayed_shutdown
from open_agent_kit.utils.platform import get_process_detach_kwargs

logger = logging.getLogger(__name__)

router = APIRouter(tags=[CI_RESTART_ROUTE_TAG])

# /bin/sh is guaranteed to exist on all POSIX systems.  We use it instead of
# sys.executable because after a Homebrew (or similar) upgrade the old Python
# interpreter path baked into the running process may no longer exist on disk.
_SHELL = "/bin/sh"


def _run_upgrade_pipeline(
    project_root: Path,
    plan: "UpgradePlan",
) -> dict:
    """Run the full upgrade pipeline (same code path as ``oak upgrade --force``).

    This ensures the daemon upgrade includes both the upgrade stages
    (migrations, structural repairs, version bump) AND the reconciliation
    stages (agent commands, settings, skills, hooks, MCP servers) that
    ``UpgradeService.execute_upgrade()`` alone would skip.

    Args:
        project_root: Project root directory.
        plan: Upgrade plan from ``UpgradeService.plan_upgrade()``.

    Returns:
        Dict with ``success`` bool and optional ``failed`` list of error strings.
    """
    from open_agent_kit.pipeline.context import FlowType, PipelineContext, SelectionState
    from open_agent_kit.pipeline.executor import build_upgrade_pipeline
    from open_agent_kit.services.config_service import ConfigService

    config_service = ConfigService(project_root)
    config = config_service.load_config()

    # Build the same pipeline context the CLI constructs in upgrade_cmd.py
    context = PipelineContext(
        project_root=Path(project_root),
        flow_type=FlowType.UPGRADE,
        dry_run=False,
        selections=SelectionState(
            agents=config.agents,
            languages=config.languages.installed,
        ),
    )
    # Pre-populate the plan so the PlanUpgradeStage is skipped
    context.set_result("plan_upgrade", {"plan": plan, "has_upgrades": True})
    context.set_result(
        "upgrade_options",
        {"commands": True, "templates": True},
    )

    pipeline = build_upgrade_pipeline().build()
    result = pipeline.execute(context)

    # Collect failures from pipeline stages
    failed_items: list[str] = []
    if not result.success:
        for stage_name, error in result.stages_failed:
            failed_items.append(f"{stage_name}: {error}")

    return {"success": result.success, "failed": failed_items}


@router.post(CI_RESTART_API_PATH)
async def self_restart() -> dict:
    """Trigger a graceful self-restart of the CI daemon.

    Spawns a detached ``/bin/sh`` subprocess that waits for the current process
    to exit, then runs ``<cli_command> team restart`` to bring the daemon back up.
    """
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_RESTART_ERROR_NO_PROJECT_ROOT,
        )

    project_root = str(state.project_root)

    # Resolve CLI command from config (e.g. "oak" or a custom wrapper)
    cli_command = resolve_ci_cli_command(state.project_root)

    # Build a shell one-liner: sleep then restart via the CLI on $PATH.
    restart_cmd = (
        f"sleep {CI_RESTART_SUBPROCESS_DELAY_SECONDS} && {shlex.quote(cli_command)} team restart"
    )

    detach_kwargs = get_process_detach_kwargs()
    logger.info(CI_RESTART_LOG_SPAWNING.format(command=f"{cli_command} team restart"))
    try:
        subprocess.Popen(
            [_SHELL, "-c", restart_cmd],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **detach_kwargs,
        )
    except OSError as exc:
        logger.error(CI_RESTART_LOG_SPAWN_FAILED, exc)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_RESTART_ERROR_SPAWN_DETAIL.format(error=exc),
        ) from exc

    # Schedule graceful shutdown
    logger.info(CI_RESTART_LOG_SCHEDULING_SHUTDOWN.format(delay=CI_RESTART_SHUTDOWN_DELAY_SECONDS))
    asyncio.create_task(
        delayed_shutdown(CI_RESTART_SHUTDOWN_DELAY_SECONDS, log_message=CI_SHUTDOWN_LOG_SIGTERM),
        name="self_restart_shutdown",
    )

    return {"status": CI_RESTART_STATUS_RESTARTING}


@router.post(CI_UPGRADE_AND_RESTART_API_PATH)
async def upgrade_and_restart() -> dict:
    """Run project upgrade in-process, then restart the daemon.

    Uses the same pipeline as ``oak upgrade --force`` to ensure consistent
    results.  The pipeline includes both upgrade stages (migrations,
    structural repairs, version bump) and reconciliation stages (agent
    commands, settings, skills, hooks, MCP servers).

    Runs synchronously so errors are reported back to the UI immediately.
    A daemon restart is triggered only after a successful upgrade.
    """
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_RESTART_ERROR_NO_PROJECT_ROOT,
        )

    project_root = state.project_root

    # --- Run upgrade via the same pipeline as `oak upgrade --force` ---
    try:
        from typing import Any, cast

        from open_agent_kit.pipeline.models import plan_has_upgrades
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(project_root)
        plan = upgrade_service.plan_upgrade()

        if not plan_has_upgrades(cast(dict[str, Any], plan)):
            return {"status": CI_UPGRADE_AND_RESTART_STATUS_UP_TO_DATE}

        # Build and execute the full upgrade pipeline (same as CLI)
        loop = asyncio.get_event_loop()
        pipeline_result = await loop.run_in_executor(
            None, _run_upgrade_pipeline, project_root, plan
        )

        if not pipeline_result["success"]:
            failed_items: list[str] = pipeline_result.get("failed", [])
            detail = "; ".join(failed_items[:5])
            if len(failed_items) > 5:
                detail += f" (+{len(failed_items) - 5} more)"
            logger.warning(CI_UPGRADE_AND_RESTART_LOG_PARTIAL_FAILURE, detail)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=CI_UPGRADE_AND_RESTART_ERROR_PARTIAL_FAILURE.format(detail=detail),
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(CI_UPGRADE_AND_RESTART_LOG_FAILED, exc, exc_info=True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_UPGRADE_AND_RESTART_ERROR_FAILED.format(error=exc),
        ) from exc

    # --- Upgrade succeeded — restart daemon to reload config ---
    cli_command = resolve_ci_cli_command(project_root)
    restart_cmd = (
        f"sleep {CI_RESTART_SUBPROCESS_DELAY_SECONDS} && {shlex.quote(cli_command)} team restart"
    )

    detach_kwargs = get_process_detach_kwargs()
    logger.info(CI_RESTART_LOG_SPAWNING.format(command=f"{cli_command} team restart"))
    try:
        subprocess.Popen(
            [_SHELL, "-c", restart_cmd],
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **detach_kwargs,
        )
    except OSError as exc:
        logger.error(CI_UPGRADE_AND_RESTART_ERROR_SPAWN_FAILED, exc)
        # Upgrade succeeded but restart couldn't be spawned — tell the user
        return {
            "status": CI_UPGRADE_AND_RESTART_STATUS_UPGRADED,
            "detail": CI_UPGRADE_AND_RESTART_DETAIL_RESTART_FAILED.format(cli_command=cli_command),
        }

    logger.info(CI_RESTART_LOG_SCHEDULING_SHUTDOWN.format(delay=CI_RESTART_SHUTDOWN_DELAY_SECONDS))
    asyncio.create_task(
        delayed_shutdown(CI_RESTART_SHUTDOWN_DELAY_SECONDS, log_message=CI_SHUTDOWN_LOG_SIGTERM),
        name="upgrade_restart_shutdown",
    )

    return {"status": CI_UPGRADE_AND_RESTART_STATUS}
