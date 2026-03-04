"""Data models for backup and restore operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImportResult:
    """Result statistics from importing a backup file."""

    sessions_imported: int = 0
    sessions_skipped: int = 0
    batches_imported: int = 0
    batches_skipped: int = 0
    observations_imported: int = 0
    observations_skipped: int = 0
    activities_imported: int = 0
    activities_skipped: int = 0
    schedules_imported: int = 0
    schedules_skipped: int = 0
    resolution_events_imported: int = 0
    resolution_events_skipped: int = 0
    gov_audit_imported: int = 0
    gov_audit_skipped: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)

    # Deleted counts (populated when replace_machine=True or delete-then-import)
    sessions_deleted: int = 0
    batches_deleted: int = 0
    observations_deleted: int = 0
    activities_deleted: int = 0
    runs_deleted: int = 0
    gov_audit_deleted: int = 0

    @property
    def total_imported(self) -> int:
        """Total records imported across all tables."""
        return (
            self.sessions_imported
            + self.batches_imported
            + self.observations_imported
            + self.activities_imported
            + self.schedules_imported
            + self.resolution_events_imported
            + self.gov_audit_imported
        )

    @property
    def total_skipped(self) -> int:
        """Total records skipped (duplicates) across all tables."""
        return (
            self.sessions_skipped
            + self.batches_skipped
            + self.observations_skipped
            + self.activities_skipped
            + self.schedules_skipped
            + self.resolution_events_skipped
            + self.gov_audit_skipped
        )

    @property
    def total_deleted(self) -> int:
        """Total records deleted (replace mode) across all tables."""
        return (
            self.sessions_deleted
            + self.batches_deleted
            + self.observations_deleted
            + self.activities_deleted
            + self.runs_deleted
            + self.gov_audit_deleted
        )


@dataclass
class BackupResult:
    """Result from a create_backup() operation."""

    success: bool
    backup_path: Path | None = None
    record_count: int = 0
    machine_id: str = ""
    include_activities: bool = False
    error: str | None = None


@dataclass
class RestoreResult:
    """Result from a restore_backup() operation."""

    success: bool
    backup_path: Path | None = None
    import_result: ImportResult | None = None
    machine_id: str = ""
    error: str | None = None


@dataclass
class RestoreAllResult:
    """Result from a restore_all() operation."""

    success: bool
    per_file: dict[str, ImportResult] = field(default_factory=dict)
    machine_id: str = ""
    error: str | None = None

    @property
    def total_imported(self) -> int:
        """Total records imported across all files."""
        return sum(r.total_imported for r in self.per_file.values())

    @property
    def total_skipped(self) -> int:
        """Total records skipped across all files."""
        return sum(r.total_skipped for r in self.per_file.values())

    @property
    def total_deleted(self) -> int:
        """Total records deleted (replace mode) across all files."""
        return sum(r.total_deleted for r in self.per_file.values())
