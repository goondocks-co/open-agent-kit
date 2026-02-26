"""Backup and restore operations for activity store.

Functions for exporting and importing database data with support for
multi-machine/multi-user backup and restore with content-based deduplication.

All public symbols are re-exported here so that existing imports like
``from ...store.backup import create_backup`` continue to work.
"""

from open_agent_kit.features.codebase_intelligence.activity.store.backup.api import (
    create_backup,
    restore_all,
    restore_backup,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup.exporter import (
    _parse_backup_schema_version,
    export_to_sql,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup.hashes import (
    backfill_content_hashes,
    compute_activity_hash,
    compute_hash,
    compute_observation_hash,
    compute_prompt_batch_hash,
    compute_resolution_event_hash,
    get_all_activity_hashes,
    get_all_observation_hashes,
    get_all_prompt_batch_hashes,
    get_all_session_ids,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup.importer import (
    import_from_sql_with_dedup,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup.machine_id import (
    get_backup_filename,
    get_machine_identifier,
    sanitize_identifier,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup.models import (
    BackupResult,
    ImportResult,
    RestoreAllResult,
    RestoreResult,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup.paths import (
    _read_dotenv_value,
    discover_backup_files,
    extract_machine_id_from_filename,
    get_backup_dir,
    get_backup_dir_source,
    validate_backup_dir,
)

__all__ = [
    "BackupResult",
    "ImportResult",
    "_parse_backup_schema_version",
    "_read_dotenv_value",
    "RestoreAllResult",
    "RestoreResult",
    "backfill_content_hashes",
    "compute_activity_hash",
    "compute_hash",
    "compute_observation_hash",
    "compute_prompt_batch_hash",
    "compute_resolution_event_hash",
    "create_backup",
    "discover_backup_files",
    "export_to_sql",
    "extract_machine_id_from_filename",
    "get_all_activity_hashes",
    "get_all_observation_hashes",
    "get_all_prompt_batch_hashes",
    "get_all_session_ids",
    "get_backup_dir",
    "get_backup_dir_source",
    "get_backup_filename",
    "get_machine_identifier",
    "import_from_sql_with_dedup",
    "restore_all",
    "restore_backup",
    "sanitize_identifier",
    "validate_backup_dir",
]
