"""Vector store package.

Decomposes the large store.py into focused modules:
- constants.py: Collection name constants
- classification.py: Doc type patterns and classification functions
- models.py: Data models (CodeChunk, MemoryObservation, PlanObservation)
- core.py: Main VectorStore class with ChromaDB setup
- code_ops.py: Code indexing operations
- memory_ops.py: Memory/plan add/delete operations
- search.py: Semantic search functions
- management.py: Stats, listing, archiving, cleanup

All public APIs are re-exported here for backward compatibility.
"""

from open_agent_kit.features.codebase_intelligence.memory.store.classification import (
    DOC_TYPE_CODE,
    DOC_TYPE_CONFIG,
    DOC_TYPE_DOCS,
    DOC_TYPE_I18N,
    DOC_TYPE_PATTERNS,
    DOC_TYPE_TEST,
    classify_doc_type,
    get_short_path,
)
from open_agent_kit.features.codebase_intelligence.memory.store.constants import (
    CODE_COLLECTION,
    MEMORY_COLLECTION,
)
from open_agent_kit.features.codebase_intelligence.memory.store.core import VectorStore
from open_agent_kit.features.codebase_intelligence.memory.store.models import (
    CodeChunk,
    MemoryObservation,
    PlanObservation,
)

__all__ = [
    # Main class
    "VectorStore",
    # Data models
    "CodeChunk",
    "MemoryObservation",
    "PlanObservation",
    # Constants
    "CODE_COLLECTION",
    "MEMORY_COLLECTION",
    # Doc type classification
    "DOC_TYPE_CODE",
    "DOC_TYPE_I18N",
    "DOC_TYPE_CONFIG",
    "DOC_TYPE_TEST",
    "DOC_TYPE_DOCS",
    "DOC_TYPE_PATTERNS",
    "classify_doc_type",
    "get_short_path",
]
