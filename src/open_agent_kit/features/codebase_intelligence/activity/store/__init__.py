"""Activity store package.

Decomposes the large store.py into focused modules:
- schema.py: Database schema version and SQL
- migrations.py: Schema migration logic
- models.py: Data models (Activity, PromptBatch, Session, StoredObservation)
- core.py: Main ActivityStore class with connection management
- sessions.py: Session CRUD operations
- batches.py: Prompt batch operations and plan embedding
- activities.py: Activity CRUD and FTS5 search
- observations.py: Memory observation storage
- stats.py: Statistics and caching
- backup.py: SQL export/import
- delete.py: Cascade delete operations

All public APIs are re-exported here for backward compatibility.
"""

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    Activity,
    PromptBatch,
    ResolutionEvent,
    Session,
    StoredObservation,
)
from open_agent_kit.features.codebase_intelligence.activity.store.schema import (
    SCHEMA_SQL,
    SCHEMA_VERSION,
)

__all__ = [
    # Main class
    "ActivityStore",
    # Data models
    "Activity",
    "PromptBatch",
    "ResolutionEvent",
    "Session",
    "StoredObservation",
    # Schema constants
    "SCHEMA_VERSION",
    "SCHEMA_SQL",
]
