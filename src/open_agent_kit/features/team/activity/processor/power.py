"""Power state transition management for the ActivityProcessor.

Handles logging, backup triggers, governance pruning, file watcher
control, and team subsystem lifecycle when the daemon transitions
between power states.
"""

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.team.constants import (
    POWER_STATE_ACTIVE,
    POWER_STATE_DEEP_SLEEP,
    POWER_STATE_SLEEP,
)
from open_agent_kit.features.team.constants.team import (
    TEAM_LOG_KEEP_RELAY_ALIVE,
    TEAM_LOG_RELAY_POWER_DISCONNECT,
    TEAM_LOG_SYNC_WORKER_POWER_STOP,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.processor.core import (
        ActivityProcessor,
    )
    from open_agent_kit.features.team.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def _get_keep_relay_alive(daemon_state: "DaemonState") -> bool:
    """Read keep_relay_alive from live config (mtime-cached, no I/O on hit)."""
    ci_config = daemon_state.ci_config
    if ci_config is None:
        return False
    return ci_config.team.keep_relay_alive


def _stop_team_sync_worker(daemon_state: "DaemonState") -> None:
    """Stop the team sync worker if running."""
    if daemon_state.team_sync_worker is not None:
        try:
            daemon_state.team_sync_worker.stop()
            logger.info(TEAM_LOG_SYNC_WORKER_POWER_STOP)
        except (RuntimeError, OSError) as e:
            logger.warning("Failed to stop team sync worker: %s", e)


def _disconnect_relay_for_power(daemon_state: "DaemonState") -> None:
    """Cache relay credentials then disconnect the cloud relay client.

    Reads ``_worker_url``, ``_token``, ``_daemon_port``, ``_machine_id``
    from the live client before calling ``disconnect()``.
    """
    import asyncio

    client = daemon_state.cloud_relay_client
    if client is None:
        return

    # Cache credentials for reconnect on wake
    worker_url = getattr(client, "_worker_url", None)
    token = getattr(client, "_token", None)
    daemon_port = getattr(client, "_daemon_port", None)
    machine_id = getattr(client, "_machine_id", "")
    if worker_url and token and daemon_port is not None:
        daemon_state.cache_relay_credentials(worker_url, token, daemon_port, machine_id)

    logger.info(TEAM_LOG_RELAY_POWER_DISCONNECT)
    try:
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(client.disconnect(), loop=loop)
    except (RuntimeError, OSError) as e:
        logger.warning("Failed to disconnect cloud relay for power: %s", e)
    finally:
        daemon_state.cloud_relay_client = None


def on_power_transition(
    processor: "ActivityProcessor",
    daemon_state: "DaemonState",
    old_state: str,
    new_state: str,
) -> None:
    """Handle power state transitions with logging and side effects.

    Side effects on entry:
    - SLEEP / DEEP_SLEEP: trigger a backup, prune governance audit events.
    - SLEEP: stop team sync worker (unless keep_relay_alive).
    - DEEP_SLEEP: stop file watcher, stop team sync worker, disconnect
      cloud relay (unless keep_relay_alive).
    - ACTIVE (from SLEEP): restart team sync worker (unless keep_relay_alive).
    - ACTIVE (from DEEP_SLEEP): start file watcher, restart team
      subsystems (unless keep_relay_alive).

    Args:
        processor: The ActivityProcessor instance (for store access).
        daemon_state: The current daemon state instance.
        old_state: The power state being left.
        new_state: The power state being entered.
    """
    import time

    last_activity = daemon_state.last_hook_activity or daemon_state.start_time
    idle_seconds = (time.time() - last_activity) if last_activity else 0.0

    logger.info(f"Power state: {old_state} -> {new_state} (idle {idle_seconds:.0f}s)")
    daemon_state.power_state = new_state

    keep_alive = _get_keep_relay_alive(daemon_state)

    # Trigger backup and governance audit pruning when entering sleep states
    # Call through processor methods for test-patchability
    if new_state in (POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP):
        processor._trigger_transition_backup(daemon_state)
        processor._trigger_governance_prune(daemon_state)

    # --- Entering SLEEP ---
    if new_state == POWER_STATE_SLEEP:
        if keep_alive:
            logger.info(TEAM_LOG_KEEP_RELAY_ALIVE)
        else:
            _stop_team_sync_worker(daemon_state)

    # --- Entering DEEP_SLEEP ---
    if new_state == POWER_STATE_DEEP_SLEEP:
        # Stop file watcher (always, regardless of keep_relay_alive)
        if daemon_state.file_watcher:
            daemon_state.file_watcher.stop()

        if keep_alive:
            logger.info(TEAM_LOG_KEEP_RELAY_ALIVE)
        else:
            _stop_team_sync_worker(daemon_state)
            _disconnect_relay_for_power(daemon_state)

    # --- Waking to ACTIVE ---
    if new_state == POWER_STATE_ACTIVE:
        # Restart file watcher when waking from deep sleep
        if old_state == POWER_STATE_DEEP_SLEEP and daemon_state.file_watcher:
            daemon_state.file_watcher.start()

        if not keep_alive:
            if old_state == POWER_STATE_SLEEP:
                # Only sync worker was stopped; restart it
                if daemon_state.team_sync_worker is not None:
                    try:
                        daemon_state.team_sync_worker.start()
                    except (RuntimeError, OSError) as e:
                        logger.warning("Failed to restart team sync worker: %s", e)
            elif old_state == POWER_STATE_DEEP_SLEEP:
                # Both subsystems were stopped; full restart
                daemon_state._restart_team_subsystems_on_wake()


def _trigger_transition_backup(
    processor: "ActivityProcessor",
    daemon_state: "DaemonState",
) -> None:
    """Trigger a backup on power state transition (entering sleep/deep_sleep).

    Reuses the existing activity_store when available to avoid opening
    a second connection to the same SQLite database.

    Args:
        processor: The ActivityProcessor instance.
        daemon_state: The current daemon state instance.
    """
    from ..store.backup import create_backup

    try:
        config = daemon_state.ci_config
        if not config or not config.backup.auto_enabled:
            return

        if not daemon_state.project_root:
            return

        from open_agent_kit.config.paths import OAK_DIR
        from open_agent_kit.features.team.constants import (
            CI_ACTIVITIES_DB_FILENAME,
            CI_DATA_DIR,
        )

        db_path = daemon_state.project_root / OAK_DIR / CI_DATA_DIR / CI_ACTIVITIES_DB_FILENAME
        if not db_path.exists():
            return

        result = create_backup(
            project_root=daemon_state.project_root,
            db_path=db_path,
            activity_store=processor.activity_store,
        )
        if result and result.success:
            logger.info(f"Transition backup created: {result.record_count} records")
    except Exception:
        logger.exception("Failed to create transition backup")


def _trigger_governance_prune(
    processor: "ActivityProcessor",
    daemon_state: "DaemonState",
) -> None:
    """Prune old governance audit events on power transition.

    Runs alongside backup when entering sleep/deep_sleep states.
    Uses the governance retention_days config to determine the cutoff.

    Args:
        processor: The ActivityProcessor instance.
        daemon_state: The current daemon state instance.
    """
    try:
        config = daemon_state.ci_config
        if not config or not config.governance.enabled:
            return

        if not processor.activity_store:
            return

        from open_agent_kit.features.team.governance.audit import (
            prune_old_events,
        )

        prune_old_events(processor.activity_store, config.governance.retention_days)
    except Exception:
        logger.debug("Failed to prune governance audit events", exc_info=True)
