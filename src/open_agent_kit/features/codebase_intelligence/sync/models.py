"""Models for CI sync operations."""

from dataclasses import dataclass, field
from enum import Enum


class SyncReason(str, Enum):
    """Reasons why a sync is needed."""

    OAK_VERSION_CHANGED = "oak_version_changed"
    SCHEMA_VERSION_CHANGED = "schema_version_changed"
    TEAM_BACKUPS_AVAILABLE = "team_backups_available"
    MANUAL_FULL_REBUILD = "manual_full_rebuild"
    NO_CHANGES = "no_changes"


@dataclass
class SyncPlan:
    """Plan for what sync operations to perform."""

    needs_sync: bool
    reasons: list[SyncReason] = field(default_factory=list)

    # Daemon status
    daemon_running: bool = False

    # Version comparison
    running_oak_version: str | None = None
    current_oak_version: str = ""
    running_schema_version: int | None = None
    current_schema_version: int = 0
    db_schema_version: int | None = None

    # Operations to perform
    stop_daemon: bool = False
    run_migrations: bool = False
    start_daemon: bool = False
    restore_team_backups: bool = False
    full_index_rebuild: bool = False

    # Team backup info
    team_backup_count: int = 0
    team_backup_files: list[str] = field(default_factory=list)
    compatible_backup_files: list[str] = field(default_factory=list)
    skipped_backup_files: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    """Result of sync operation."""

    success: bool
    operations_completed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    records_imported: int = 0
    records_skipped: int = 0
    migrations_applied: int = 0
