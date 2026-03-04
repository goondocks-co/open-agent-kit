"""Daemon lifecycle management modules.

This package organises the daemon's startup, shutdown, and background
maintenance responsibilities into focused modules:

- ``startup`` -- lifespan context manager and subsystem init helpers
- ``logging_setup`` -- logging configuration
- ``version_check`` -- version / upgrade / stale-install detection
- ``sync_check`` -- SQLite-to-ChromaDB consistency checks
- ``maintenance`` -- periodic backup and governance pruning
"""

from open_agent_kit.features.team.daemon.lifecycle.logging_setup import (
    configure_logging,
)
from open_agent_kit.features.team.daemon.lifecycle.maintenance import (
    run_auto_backup,
    run_governance_prune,
)
from open_agent_kit.features.team.daemon.lifecycle.startup import (
    lifespan,
)
from open_agent_kit.features.team.daemon.lifecycle.sync_check import (
    check_and_rebuild_chromadb,
)
from open_agent_kit.features.team.daemon.lifecycle.version_check import (
    check_upgrade_needed,
    check_version,
    periodic_version_check,
)

__all__ = [
    "check_and_rebuild_chromadb",
    "check_upgrade_needed",
    "check_version",
    "configure_logging",
    "lifespan",
    "periodic_version_check",
    "run_auto_backup",
    "run_governance_prune",
]
