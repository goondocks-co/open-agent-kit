"""Power state transition management for the ActivityProcessor.

Handles logging, backup triggers, governance pruning, and file watcher
control when the daemon transitions between power states.
"""

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    POWER_STATE_ACTIVE,
    POWER_STATE_DEEP_SLEEP,
    POWER_STATE_SLEEP,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.processor.core import (
        ActivityProcessor,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def on_power_transition(
    processor: "ActivityProcessor",
    daemon_state: "DaemonState",
    old_state: str,
    new_state: str,
) -> None:
    """Handle power state transitions with logging and side effects.

    Side effects on entry:
    - SLEEP / DEEP_SLEEP: trigger a backup, prune governance audit events.
    - DEEP_SLEEP: stop file watcher.
    - ACTIVE (from DEEP_SLEEP): start file watcher.

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

    # Trigger backup and governance audit pruning when entering sleep states
    # Call through processor methods for test-patchability
    if new_state in (POWER_STATE_SLEEP, POWER_STATE_DEEP_SLEEP):
        processor._trigger_transition_backup(daemon_state)
        processor._trigger_governance_prune(daemon_state)

    # Stop file watcher on entry to deep sleep
    if new_state == POWER_STATE_DEEP_SLEEP and daemon_state.file_watcher:
        daemon_state.file_watcher.stop()

    # Restart file watcher when waking from deep sleep
    if (
        new_state == POWER_STATE_ACTIVE
        and old_state == POWER_STATE_DEEP_SLEEP
        and daemon_state.file_watcher
    ):
        daemon_state.file_watcher.start()


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
        from open_agent_kit.features.codebase_intelligence.constants import (
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

        from open_agent_kit.features.codebase_intelligence.governance.audit import (
            prune_old_events,
        )

        prune_old_events(processor.activity_store, config.governance.retention_days)
    except Exception:
        logger.debug("Failed to prune governance audit events", exc_info=True)
