"""Team feature for Open Agent Kit.

Provides semantic search and persistent memory for AI assistants.

Key Components:
- TeamService: Feature lifecycle management
- CIConfig, EmbeddingConfig: Configuration classes with validation
- CIError and subclasses: Custom exception hierarchy
- Constants: Centralized magic string definitions
"""

# Service layer
# Configuration
from open_agent_kit.features.team.config import (
    CIConfig,
    EmbeddingConfig,
    load_ci_config,
    save_ci_config,
)

# Exceptions
from open_agent_kit.features.team.exceptions import (
    ChunkingError,
    CIError,
    CollectionError,
    ConfigurationError,
    DaemonConnectionError,
    DaemonError,
    DaemonStartupError,
    DimensionMismatchError,
    FileProcessingError,
    HookError,
    IndexingError,
    QueryValidationError,
    SearchError,
    StorageError,
    ValidationError,
)
from open_agent_kit.features.team.service import TeamService

__all__ = [
    # Service
    "TeamService",
    # Configuration
    "CIConfig",
    "EmbeddingConfig",
    "load_ci_config",
    "save_ci_config",
    # Exceptions
    "CIError",
    "ConfigurationError",
    "ValidationError",
    "DaemonError",
    "DaemonStartupError",
    "DaemonConnectionError",
    "IndexingError",
    "ChunkingError",
    "FileProcessingError",
    "StorageError",
    "CollectionError",
    "DimensionMismatchError",
    "SearchError",
    "QueryValidationError",
    "HookError",
]
