"""Periodic maintenance tasks (backup, governance pruning).

Extracted from ``server.py`` -- these are synchronous helpers designed
to run in a thread-pool executor during daemon operation.
"""

import logging
from typing import TYPE_CHECKING

from open_agent_kit.config.paths import OAK_DIR

if TYPE_CHECKING:
    from open_agent_kit.features.team.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def run_auto_backup(state: "DaemonState") -> None:
    """Run a single auto-backup cycle (sync, for use in executor)."""
    import time

    from open_agent_kit.features.team.activity.store.backup import (
        create_backup,
    )
    from open_agent_kit.features.team.constants import (
        CI_ACTIVITIES_DB_FILENAME as _DB_FILENAME,
    )
    from open_agent_kit.features.team.constants import (
        CI_DATA_DIR as _DATA_DIR,
    )

    if not state.project_root:
        return

    db_path = state.project_root / OAK_DIR / _DATA_DIR / _DB_FILENAME
    if not db_path.exists():
        logger.debug("Auto-backup skipped: database does not exist")
        return

    result = create_backup(project_root=state.project_root, db_path=db_path)
    if result.success:
        state.last_auto_backup = time.time()
        logger.info(f"Auto-backup: {result.record_count} records -> {result.backup_path}")
    else:
        logger.warning(f"Auto-backup failed: {result.error}")


def run_governance_prune(state: "DaemonState") -> None:
    """Run a single governance audit retention prune cycle (sync)."""
    if not state.activity_store:
        return

    config = state.ci_config
    if config is None or not config.governance.enabled:
        return

    from open_agent_kit.features.team.governance.audit import (
        prune_old_events,
    )

    prune_old_events(state.activity_store, config.governance.retention_days)
