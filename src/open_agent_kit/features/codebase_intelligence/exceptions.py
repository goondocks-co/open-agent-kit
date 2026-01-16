"""Custom exceptions for Codebase Intelligence feature.

This module defines a hierarchy of exceptions for consistent error handling
across the CI feature. All exceptions inherit from CIError, allowing callers
to catch all CI-related errors with a single except clause if desired.

Exception hierarchy:
    CIError (base)
    ├── ConfigurationError
    │   └── ValidationError
    ├── DaemonError
    │   ├── DaemonStartupError
    │   └── DaemonConnectionError
    ├── IndexingError
    │   ├── ChunkingError
    │   └── FileProcessingError
    ├── EmbeddingError (imported from embeddings.base)
    ├── StorageError
    │   ├── CollectionError
    │   └── DimensionMismatchError
    └── SearchError
        └── QueryValidationError
"""

from pathlib import Path
from typing import Any


class CIError(Exception):
    """Base exception for all Codebase Intelligence errors.

    All CI-specific exceptions inherit from this class, allowing callers
    to catch all CI errors with a single except clause.

    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional context.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        """Initialize CI error.

        Args:
            message: Error description.
            details: Optional dictionary with additional context.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation."""
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(CIError):
    """Raised when configuration is invalid or cannot be loaded.

    Examples:
        - Invalid YAML syntax in config file
        - Missing required configuration keys
        - Invalid provider or model names
    """

    def __init__(
        self,
        message: str,
        config_file: Path | None = None,
        key: str | None = None,
    ):
        """Initialize configuration error.

        Args:
            message: Error description.
            config_file: Path to the problematic config file.
            key: The configuration key that caused the error.
        """
        details = {}
        if config_file:
            details["config_file"] = str(config_file)
        if key:
            details["key"] = key
        super().__init__(message, details)
        self.config_file = config_file
        self.key = key


class ValidationError(ConfigurationError):
    """Raised when configuration values fail validation.

    Examples:
        - Empty model name
        - Invalid URL format
        - Out-of-range numeric values
    """

    def __init__(
        self,
        message: str,
        field: str,
        value: Any = None,
        expected: str | None = None,
    ):
        """Initialize validation error.

        Args:
            message: Error description.
            field: The field that failed validation.
            value: The invalid value (will be truncated if too long).
            expected: Description of expected value format.
        """
        # Call parent with just message (ConfigurationError doesn't accept details)
        super().__init__(message)
        # Build our own details dict
        self.details["field"] = field
        if value is not None:
            value_str = str(value)
            self.details["value"] = value_str[:100] + "..." if len(value_str) > 100 else value_str
        if expected:
            self.details["expected"] = expected
        self.field = field
        self.value = value
        self.expected = expected


# =============================================================================
# Daemon Errors
# =============================================================================


class DaemonError(CIError):
    """Raised when daemon operations fail.

    Base class for daemon-related errors.
    """

    def __init__(
        self,
        message: str,
        port: int | None = None,
        pid: int | None = None,
    ):
        """Initialize daemon error.

        Args:
            message: Error description.
            port: The daemon port involved.
            pid: The process ID involved.
        """
        details = {}
        if port:
            details["port"] = port
        if pid:
            details["pid"] = pid
        super().__init__(message, details)
        self.port = port
        self.pid = pid


class DaemonStartupError(DaemonError):
    """Raised when the daemon fails to start.

    Examples:
        - Port already in use
        - Failed to spawn process
        - Timeout waiting for health check
    """

    def __init__(
        self,
        message: str,
        port: int | None = None,
        log_file: Path | None = None,
        cause: Exception | None = None,
    ):
        """Initialize daemon startup error.

        Args:
            message: Error description.
            port: The port the daemon tried to use.
            log_file: Path to daemon log file for debugging.
            cause: Underlying exception that caused the failure.
        """
        super().__init__(message, port=port)
        if log_file:
            self.details["log_file"] = str(log_file)
        self.log_file = log_file
        self.cause = cause


class DaemonConnectionError(DaemonError):
    """Raised when communication with the daemon fails.

    Examples:
        - Health check failed
        - API request timed out
        - Connection refused
    """

    def __init__(
        self,
        message: str,
        port: int | None = None,
        endpoint: str | None = None,
        cause: Exception | None = None,
    ):
        """Initialize daemon connection error.

        Args:
            message: Error description.
            port: The port the daemon is running on.
            endpoint: The API endpoint that failed.
            cause: Underlying exception.
        """
        super().__init__(message, port=port)
        if endpoint:
            self.details["endpoint"] = endpoint
        self.endpoint = endpoint
        self.cause = cause


# =============================================================================
# Indexing Errors
# =============================================================================


class IndexingError(CIError):
    """Raised when indexing operations fail.

    Base class for indexing-related errors.
    """

    def __init__(
        self,
        message: str,
        file_path: Path | None = None,
        files_processed: int | None = None,
    ):
        """Initialize indexing error.

        Args:
            message: Error description.
            file_path: The file being processed when error occurred.
            files_processed: Number of files processed before error.
        """
        details: dict[str, Any] = {}
        if file_path:
            details["file_path"] = str(file_path)
        if files_processed is not None:
            details["files_processed"] = files_processed
        super().__init__(message, details)
        self.file_path = file_path
        self.files_processed = files_processed


class ChunkingError(IndexingError):
    """Raised when code chunking fails.

    Examples:
        - AST parsing failed
        - Invalid chunk boundaries
        - Unsupported language
    """

    def __init__(
        self,
        message: str,
        file_path: Path | None = None,
        language: str | None = None,
        line_number: int | None = None,
    ):
        """Initialize chunking error.

        Args:
            message: Error description.
            file_path: The file being chunked.
            language: The detected/specified language.
            line_number: Line number where chunking failed.
        """
        super().__init__(message, file_path=file_path)
        if language:
            self.details["language"] = language
        if line_number:
            self.details["line_number"] = line_number
        self.language = language
        self.line_number = line_number


class FileProcessingError(IndexingError):
    """Raised when file processing fails.

    Examples:
        - File not found
        - Permission denied
        - Encoding error
    """

    def __init__(
        self,
        message: str,
        file_path: Path,
        cause: Exception | None = None,
    ):
        """Initialize file processing error.

        Args:
            message: Error description.
            file_path: The file that couldn't be processed.
            cause: Underlying exception.
        """
        super().__init__(message, file_path=file_path)
        self.cause = cause


# =============================================================================
# Storage Errors
# =============================================================================


class StorageError(CIError):
    """Raised when vector store operations fail.

    Base class for storage-related errors.
    """

    def __init__(
        self,
        message: str,
        collection: str | None = None,
    ):
        """Initialize storage error.

        Args:
            message: Error description.
            collection: The collection involved.
        """
        details = {}
        if collection:
            details["collection"] = collection
        super().__init__(message, details)
        self.collection = collection


class CollectionError(StorageError):
    """Raised when collection operations fail.

    Examples:
        - Collection not found
        - Failed to create collection
        - Collection already exists
    """

    pass


class DimensionMismatchError(StorageError):
    """Raised when embedding dimensions don't match collection.

    This typically occurs when:
    - Switching embedding models
    - Index corruption
    - Mixed embeddings from different providers
    """

    def __init__(
        self,
        message: str,
        collection: str,
        expected_dims: int,
        actual_dims: int,
    ):
        """Initialize dimension mismatch error.

        Args:
            message: Error description.
            collection: The collection with mismatched dimensions.
            expected_dims: Expected embedding dimensions.
            actual_dims: Actual embedding dimensions provided.
        """
        super().__init__(message, collection=collection)
        self.details["expected_dims"] = expected_dims
        self.details["actual_dims"] = actual_dims
        self.expected_dims = expected_dims
        self.actual_dims = actual_dims


# =============================================================================
# Search Errors
# =============================================================================


class SearchError(CIError):
    """Raised when search operations fail.

    Base class for search-related errors.
    """

    def __init__(
        self,
        message: str,
        query: str | None = None,
    ):
        """Initialize search error.

        Args:
            message: Error description.
            query: The search query (truncated).
        """
        details = {}
        if query:
            details["query"] = query[:100] + "..." if len(query) > 100 else query
        super().__init__(message, details)
        self.query = query


class QueryValidationError(SearchError):
    """Raised when search query validation fails.

    Examples:
        - Query too long
        - Query is empty
        - Invalid search type
    """

    def __init__(
        self,
        message: str,
        query: str | None = None,
        constraint: str | None = None,
    ):
        """Initialize query validation error.

        Args:
            message: Error description.
            query: The invalid query.
            constraint: The constraint that was violated.
        """
        super().__init__(message, query=query)
        if constraint:
            self.details["constraint"] = constraint
        self.constraint = constraint


# =============================================================================
# Hook Errors
# =============================================================================


class HookError(CIError):
    """Raised when hook operations fail.

    Examples:
        - Failed to load hook template
        - Failed to update agent hooks
        - Invalid hook configuration
    """

    def __init__(
        self,
        message: str,
        agent: str | None = None,
        hook_event: str | None = None,
    ):
        """Initialize hook error.

        Args:
            message: Error description.
            agent: The agent involved (claude, cursor, gemini).
            hook_event: The hook event type.
        """
        details = {}
        if agent:
            details["agent"] = agent
        if hook_event:
            details["hook_event"] = hook_event
        super().__init__(message, details)
        self.agent = agent
        self.hook_event = hook_event
