"""Tests for custom exceptions module.

Tests verify exception creation, inheritance, string representation,
and attribute preservation across the exception hierarchy.
"""

from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.exceptions import (
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

# =============================================================================
# Base CIError Tests
# =============================================================================


class TestCIError:
    """Test base CIError exception."""

    def test_init_with_message_only(self):
        """Test creating CIError with message only."""
        error = CIError("Test error message")
        assert error.message == "Test error message"
        assert error.details == {}

    def test_init_with_message_and_details(self):
        """Test creating CIError with message and details dict."""
        details = {"key": "value", "code": 123}
        error = CIError("Test error", details=details)
        assert error.message == "Test error"
        assert error.details == details

    def test_string_representation_without_details(self):
        """Test string representation when details is empty."""
        error = CIError("Simple error")
        assert str(error) == "Simple error"

    def test_string_representation_with_details(self):
        """Test string representation includes details."""
        error = CIError("Error occurred", details={"file": "test.py", "line": 42})
        error_str = str(error)
        assert "Error occurred" in error_str
        assert "file=test.py" in error_str
        assert "line=42" in error_str

    def test_inheritance_with_exception(self):
        """Test that CIError inherits from Exception."""
        error = CIError("Test")
        assert isinstance(error, Exception)

    def test_catching_as_exception(self):
        """Test that CIError can be caught as Exception."""
        with pytest.raises(Exception):  # noqa: B017 - intentionally testing inheritance
            raise CIError("Test error")


# =============================================================================
# ConfigurationError Tests
# =============================================================================


class TestConfigurationError:
    """Test ConfigurationError exception."""

    def test_init_with_message_only(self):
        """Test creating ConfigurationError with message only."""
        error = ConfigurationError("Config invalid")
        assert error.message == "Config invalid"
        assert "config_file" not in error.details

    def test_init_with_config_file(self):
        """Test creating ConfigurationError with config file path."""
        config_path = Path("/path/to/config.yaml")
        error = ConfigurationError("Config invalid", config_file=config_path)
        assert error.config_file == config_path
        assert str(config_path) in error.details["config_file"]

    def test_init_with_config_key(self):
        """Test creating ConfigurationError with config key."""
        error = ConfigurationError("Invalid key", key="embedding.provider")
        assert error.key == "embedding.provider"
        assert error.details["key"] == "embedding.provider"

    def test_init_with_all_parameters(self):
        """Test creating ConfigurationError with all parameters."""
        config_path = Path("/etc/config.yaml")
        error = ConfigurationError(
            "Validation failed",
            config_file=config_path,
            key="provider",
        )
        assert error.config_file == config_path
        assert error.key == "provider"

    def test_is_subclass_of_ci_error(self):
        """Test that ConfigurationError is subclass of CIError."""
        assert issubclass(ConfigurationError, CIError)


# =============================================================================
# ValidationError Tests
# =============================================================================


class TestValidationError:
    """Test ValidationError exception."""

    def test_init_with_required_parameters(self):
        """Test creating ValidationError with required parameters."""
        error = ValidationError("Invalid value", field="provider")
        assert error.message == "Invalid value"
        assert error.field == "provider"
        assert error.details["field"] == "provider"

    def test_init_with_value_parameter(self):
        """Test creating ValidationError with value parameter."""
        error = ValidationError("Invalid value", field="model", value="bad-model")
        assert error.value == "bad-model"
        assert error.details["value"] == "bad-model"

    def test_long_value_is_truncated(self):
        """Test that very long values are truncated in details."""
        long_value = "x" * 150
        error = ValidationError(
            "Invalid value",
            field="content",
            value=long_value,
        )
        assert len(error.details["value"]) <= 103  # 100 chars + "..."

    def test_init_with_expected_parameter(self):
        """Test creating ValidationError with expected parameter."""
        error = ValidationError(
            "Invalid provider",
            field="provider",
            value="invalid",
            expected="one of: ollama, openai, lmstudio",
        )
        assert error.expected == "one of: ollama, openai, lmstudio"
        assert error.details["expected"] == "one of: ollama, openai, lmstudio"

    def test_is_subclass_of_configuration_error(self):
        """Test that ValidationError is subclass of ConfigurationError."""
        assert issubclass(ValidationError, ConfigurationError)


# =============================================================================
# DaemonError Tests
# =============================================================================


class TestDaemonError:
    """Test DaemonError exception."""

    def test_init_with_message_only(self):
        """Test creating DaemonError with message only."""
        error = DaemonError("Daemon failed")
        assert error.message == "Daemon failed"
        assert error.port is None
        assert error.pid is None

    def test_init_with_port(self):
        """Test creating DaemonError with port."""
        error = DaemonError("Port in use", port=37800)
        assert error.port == 37800
        assert error.details["port"] == 37800

    def test_init_with_pid(self):
        """Test creating DaemonError with process ID."""
        error = DaemonError("Process error", pid=1234)
        assert error.pid == 1234
        assert error.details["pid"] == 1234

    def test_init_with_port_and_pid(self):
        """Test creating DaemonError with both port and pid."""
        error = DaemonError("Daemon crashed", port=37800, pid=5678)
        assert error.port == 37800
        assert error.pid == 5678

    def test_is_subclass_of_ci_error(self):
        """Test that DaemonError is subclass of CIError."""
        assert issubclass(DaemonError, CIError)


# =============================================================================
# DaemonStartupError Tests
# =============================================================================


class TestDaemonStartupError:
    """Test DaemonStartupError exception."""

    def test_init_with_message_only(self):
        """Test creating DaemonStartupError with message only."""
        error = DaemonStartupError("Failed to start")
        assert error.message == "Failed to start"

    def test_init_with_port(self):
        """Test creating DaemonStartupError with port."""
        error = DaemonStartupError("Port in use", port=37800)
        assert error.port == 37800

    def test_init_with_log_file(self):
        """Test creating DaemonStartupError with log file."""
        log_path = Path("/tmp/daemon.log")
        error = DaemonStartupError("Startup failed", log_file=log_path)
        assert error.log_file == log_path
        assert str(log_path) in error.details["log_file"]

    def test_init_with_cause_exception(self):
        """Test creating DaemonStartupError with underlying cause."""
        cause = ValueError("Resource unavailable")
        error = DaemonStartupError("Startup failed", cause=cause)
        assert error.cause == cause

    def test_is_subclass_of_daemon_error(self):
        """Test that DaemonStartupError is subclass of DaemonError."""
        assert issubclass(DaemonStartupError, DaemonError)


# =============================================================================
# DaemonConnectionError Tests
# =============================================================================


class TestDaemonConnectionError:
    """Test DaemonConnectionError exception."""

    def test_init_with_message_only(self):
        """Test creating DaemonConnectionError with message only."""
        error = DaemonConnectionError("Connection refused")
        assert error.message == "Connection refused"

    def test_init_with_port(self):
        """Test creating DaemonConnectionError with port."""
        error = DaemonConnectionError("Connection failed", port=37800)
        assert error.port == 37800

    def test_init_with_endpoint(self):
        """Test creating DaemonConnectionError with endpoint."""
        error = DaemonConnectionError(
            "API error",
            endpoint="/api/health",
        )
        assert error.endpoint == "/api/health"
        assert error.details["endpoint"] == "/api/health"

    def test_init_with_cause_exception(self):
        """Test creating DaemonConnectionError with underlying cause."""
        cause = ConnectionError("Network unreachable")
        error = DaemonConnectionError("Connection failed", cause=cause)
        assert error.cause == cause

    def test_is_subclass_of_daemon_error(self):
        """Test that DaemonConnectionError is subclass of DaemonError."""
        assert issubclass(DaemonConnectionError, DaemonError)


# =============================================================================
# IndexingError Tests
# =============================================================================


class TestIndexingError:
    """Test IndexingError exception."""

    def test_init_with_message_only(self):
        """Test creating IndexingError with message only."""
        error = IndexingError("Indexing failed")
        assert error.message == "Indexing failed"

    def test_init_with_file_path(self):
        """Test creating IndexingError with file path."""
        file_path = Path("/project/src/module.py")
        error = IndexingError("Processing failed", file_path=file_path)
        assert error.file_path == file_path
        assert str(file_path) in error.details["file_path"]

    def test_init_with_files_processed(self):
        """Test creating IndexingError with file count."""
        error = IndexingError("Processing failed", files_processed=42)
        assert error.files_processed == 42
        assert error.details["files_processed"] == 42

    def test_is_subclass_of_ci_error(self):
        """Test that IndexingError is subclass of CIError."""
        assert issubclass(IndexingError, CIError)


# =============================================================================
# ChunkingError Tests
# =============================================================================


class TestChunkingError:
    """Test ChunkingError exception."""

    def test_init_with_message_only(self):
        """Test creating ChunkingError with message only."""
        error = ChunkingError("Chunking failed")
        assert error.message == "Chunking failed"

    def test_init_with_file_path(self):
        """Test creating ChunkingError with file path."""
        file_path = Path("/project/src/code.py")
        error = ChunkingError("AST parsing failed", file_path=file_path)
        assert error.file_path == file_path

    def test_init_with_language(self):
        """Test creating ChunkingError with language."""
        error = ChunkingError(
            "Unsupported language",
            language="cobol",
        )
        assert error.language == "cobol"
        assert error.details["language"] == "cobol"

    def test_init_with_line_number(self):
        """Test creating ChunkingError with line number."""
        error = ChunkingError(
            "Invalid syntax",
            line_number=42,
        )
        assert error.line_number == 42
        assert error.details["line_number"] == 42

    def test_is_subclass_of_indexing_error(self):
        """Test that ChunkingError is subclass of IndexingError."""
        assert issubclass(ChunkingError, IndexingError)


# =============================================================================
# FileProcessingError Tests
# =============================================================================


class TestFileProcessingError:
    """Test FileProcessingError exception."""

    def test_init_with_message_and_path(self):
        """Test creating FileProcessingError with message and path."""
        file_path = Path("/project/missing.py")
        error = FileProcessingError("File not found", file_path=file_path)
        assert error.file_path == file_path
        assert error.message == "File not found"

    def test_init_with_cause_exception(self):
        """Test creating FileProcessingError with underlying cause."""
        file_path = Path("/project/file.py")
        cause = FileNotFoundError("No such file or directory")
        error = FileProcessingError(
            "Failed to read file",
            file_path=file_path,
            cause=cause,
        )
        assert error.cause == cause

    def test_is_subclass_of_indexing_error(self):
        """Test that FileProcessingError is subclass of IndexingError."""
        assert issubclass(FileProcessingError, IndexingError)


# =============================================================================
# StorageError Tests
# =============================================================================


class TestStorageError:
    """Test StorageError exception."""

    def test_init_with_message_only(self):
        """Test creating StorageError with message only."""
        error = StorageError("Storage operation failed")
        assert error.message == "Storage operation failed"

    def test_init_with_collection(self):
        """Test creating StorageError with collection name."""
        error = StorageError("Collection error", collection="code")
        assert error.collection == "code"
        assert error.details["collection"] == "code"

    def test_is_subclass_of_ci_error(self):
        """Test that StorageError is subclass of CIError."""
        assert issubclass(StorageError, CIError)


# =============================================================================
# CollectionError Tests
# =============================================================================


class TestCollectionError:
    """Test CollectionError exception."""

    def test_init_with_message_only(self):
        """Test creating CollectionError with message only."""
        error = CollectionError("Collection not found")
        assert error.message == "Collection not found"

    def test_init_with_collection(self):
        """Test creating CollectionError with collection name."""
        error = CollectionError("Collection exists", collection="memory")
        assert error.collection == "memory"

    def test_is_subclass_of_storage_error(self):
        """Test that CollectionError is subclass of StorageError."""
        assert issubclass(CollectionError, StorageError)


# =============================================================================
# DimensionMismatchError Tests
# =============================================================================


class TestDimensionMismatchError:
    """Test DimensionMismatchError exception."""

    def test_init_with_all_parameters(self):
        """Test creating DimensionMismatchError with all parameters."""
        error = DimensionMismatchError(
            "Dimension mismatch",
            collection="code",
            expected_dims=1024,
            actual_dims=768,
        )
        assert error.collection == "code"
        assert error.expected_dims == 1024
        assert error.actual_dims == 768

    def test_details_include_dimension_info(self):
        """Test that details dictionary includes dimension info."""
        error = DimensionMismatchError(
            "Mismatch",
            collection="code",
            expected_dims=1024,
            actual_dims=768,
        )
        assert error.details["expected_dims"] == 1024
        assert error.details["actual_dims"] == 768

    def test_is_subclass_of_storage_error(self):
        """Test that DimensionMismatchError is subclass of StorageError."""
        assert issubclass(DimensionMismatchError, StorageError)


# =============================================================================
# SearchError Tests
# =============================================================================


class TestSearchError:
    """Test SearchError exception."""

    def test_init_with_message_only(self):
        """Test creating SearchError with message only."""
        error = SearchError("Search failed")
        assert error.message == "Search failed"

    def test_init_with_query(self):
        """Test creating SearchError with query string."""
        error = SearchError("No results", query="find me")
        assert error.query == "find me"
        assert error.details["query"] == "find me"

    def test_long_query_is_truncated(self):
        """Test that long queries are truncated in details."""
        long_query = "search " * 100
        error = SearchError("Error", query=long_query)
        assert len(error.details["query"]) <= 103  # 100 chars + "..."

    def test_is_subclass_of_ci_error(self):
        """Test that SearchError is subclass of CIError."""
        assert issubclass(SearchError, CIError)


# =============================================================================
# QueryValidationError Tests
# =============================================================================


class TestQueryValidationError:
    """Test QueryValidationError exception."""

    def test_init_with_message_only(self):
        """Test creating QueryValidationError with message only."""
        error = QueryValidationError("Invalid query")
        assert error.message == "Invalid query"

    def test_init_with_query(self):
        """Test creating QueryValidationError with query."""
        error = QueryValidationError("Query too long", query="very long search")
        assert error.query == "very long search"

    def test_init_with_constraint(self):
        """Test creating QueryValidationError with constraint."""
        error = QueryValidationError(
            "Constraint violated",
            constraint="max_length=1000",
        )
        assert error.constraint == "max_length=1000"
        assert error.details["constraint"] == "max_length=1000"

    def test_is_subclass_of_search_error(self):
        """Test that QueryValidationError is subclass of SearchError."""
        assert issubclass(QueryValidationError, SearchError)


# =============================================================================
# HookError Tests
# =============================================================================


class TestHookError:
    """Test HookError exception."""

    def test_init_with_message_only(self):
        """Test creating HookError with message only."""
        error = HookError("Hook failed")
        assert error.message == "Hook failed"

    def test_init_with_agent(self):
        """Test creating HookError with agent name."""
        error = HookError("Hook update failed", agent="claude")
        assert error.agent == "claude"
        assert error.details["agent"] == "claude"

    def test_init_with_hook_event(self):
        """Test creating HookError with hook event."""
        error = HookError(
            "Event processing failed",
            hook_event="post-tool-use",
        )
        assert error.hook_event == "post-tool-use"
        assert error.details["hook_event"] == "post-tool-use"

    def test_init_with_agent_and_event(self):
        """Test creating HookError with both agent and event."""
        error = HookError(
            "Hook error",
            agent="cursor",
            hook_event="session-start",
        )
        assert error.agent == "cursor"
        assert error.hook_event == "session-start"

    def test_is_subclass_of_ci_error(self):
        """Test that HookError is subclass of CIError."""
        assert issubclass(HookError, CIError)


# =============================================================================
# Exception Hierarchy Tests
# =============================================================================


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_all_ci_exceptions_inherit_from_ci_error(self):
        """Test that all CI exceptions inherit from CIError."""
        ci_exceptions = [
            ConfigurationError,
            ValidationError,
            DaemonError,
            DaemonStartupError,
            DaemonConnectionError,
            IndexingError,
            ChunkingError,
            FileProcessingError,
            StorageError,
            CollectionError,
            DimensionMismatchError,
            SearchError,
            QueryValidationError,
            HookError,
        ]
        for exc_class in ci_exceptions:
            assert issubclass(exc_class, CIError)

    def test_can_catch_all_ci_errors_with_ci_error(self):
        """Test that all CI exceptions can be caught with CIError."""
        errors_to_test = [
            ConfigurationError("Config error"),
            ValidationError("Invalid", field="test"),
            DaemonError("Daemon error"),
            IndexingError("Index error"),
            SearchError("Search error"),
        ]
        for error in errors_to_test:
            with pytest.raises(CIError):
                raise error
