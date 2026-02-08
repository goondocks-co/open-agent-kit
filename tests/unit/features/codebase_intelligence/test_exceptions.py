"""Tests for custom exceptions module.

Tests verify exception creation, inheritance, string representation,
and attribute preservation across the exception hierarchy.

Uses parameterized tests to keep the file concise while covering every
exception class.
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
        error = CIError("Test error message")
        assert error.message == "Test error message"
        assert error.details == {}

    def test_init_with_details(self):
        details = {"key": "value", "code": 123}
        error = CIError("Test error", details=details)
        assert error.details == details

    def test_str_without_details(self):
        assert str(CIError("Simple error")) == "Simple error"

    def test_str_with_details(self):
        error = CIError("Error occurred", details={"file": "test.py", "line": 42})
        error_str = str(error)
        assert "Error occurred" in error_str
        assert "file=test.py" in error_str
        assert "line=42" in error_str

    def test_inherits_from_exception(self):
        assert isinstance(CIError("Test"), Exception)

    def test_catchable_as_exception(self):
        with pytest.raises(Exception):  # noqa: B017
            raise CIError("Test error")


# =============================================================================
# Hierarchy — every CI exception must inherit from CIError
# =============================================================================

_ALL_CI_EXCEPTIONS = [
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


@pytest.mark.parametrize(
    "exc_class",
    _ALL_CI_EXCEPTIONS,
    ids=[e.__name__ for e in _ALL_CI_EXCEPTIONS],
)
def test_inherits_from_ci_error(exc_class):
    """Every CI exception must be a subclass of CIError."""
    assert issubclass(exc_class, CIError)


# =============================================================================
# Subclass relationships
# =============================================================================

_SUBCLASS_PAIRS = [
    # (child, parent)
    (ValidationError, ConfigurationError),
    (DaemonStartupError, DaemonError),
    (DaemonConnectionError, DaemonError),
    (ChunkingError, IndexingError),
    (FileProcessingError, IndexingError),
    (CollectionError, StorageError),
    (DimensionMismatchError, StorageError),
    (QueryValidationError, SearchError),
]


@pytest.mark.parametrize(
    "child,parent",
    _SUBCLASS_PAIRS,
    ids=[f"{c.__name__}<{p.__name__}" for c, p in _SUBCLASS_PAIRS],
)
def test_subclass_relationship(child, parent):
    """Verify specific inheritance relationships."""
    assert issubclass(child, parent)


# =============================================================================
# Catch-all test — every CI exception catchable via CIError
# =============================================================================

_CATCHABLE_INSTANCES = [
    ConfigurationError("Config error"),
    ValidationError("Invalid", field="test"),
    DaemonError("Daemon error"),
    IndexingError("Index error"),
    SearchError("Search error"),
]


@pytest.mark.parametrize(
    "error",
    _CATCHABLE_INSTANCES,
    ids=[type(e).__name__ for e in _CATCHABLE_INSTANCES],
)
def test_catchable_via_ci_error(error):
    """All CI exceptions can be caught with CIError."""
    with pytest.raises(CIError):
        raise error


# =============================================================================
# Attribute preservation — test each exception's custom kwargs
# =============================================================================


class TestConfigurationError:
    def test_config_file(self):
        path = Path("/path/to/config.yaml")
        error = ConfigurationError("Config invalid", config_file=path)
        assert error.config_file == path
        assert str(path) in error.details["config_file"]

    def test_key(self):
        error = ConfigurationError("Invalid key", key="embedding.provider")
        assert error.key == "embedding.provider"
        assert error.details["key"] == "embedding.provider"


class TestValidationError:
    def test_field_and_value(self):
        error = ValidationError("Invalid value", field="provider", value="bad")
        assert error.field == "provider"
        assert error.value == "bad"

    def test_long_value_truncated(self):
        error = ValidationError("Invalid", field="x", value="x" * 150)
        assert len(error.details["value"]) <= 103  # 100 chars + "..."

    def test_expected(self):
        error = ValidationError("Invalid", field="p", expected="one of: a, b")
        assert error.expected == "one of: a, b"


class TestDaemonError:
    def test_port_and_pid(self):
        error = DaemonError("Crashed", port=37800, pid=5678)
        assert error.port == 37800
        assert error.pid == 5678
        assert error.details["port"] == 37800
        assert error.details["pid"] == 5678

    def test_defaults_none(self):
        error = DaemonError("Failed")
        assert error.port is None
        assert error.pid is None


class TestDaemonStartupError:
    def test_log_file_and_cause(self):
        log_path = Path("/tmp/daemon.log")
        cause = ValueError("Resource unavailable")
        error = DaemonStartupError("Failed", log_file=log_path, cause=cause)
        assert error.log_file == log_path
        assert error.cause == cause


class TestDaemonConnectionError:
    def test_endpoint_and_cause(self):
        cause = ConnectionError("Network unreachable")
        error = DaemonConnectionError("Failed", endpoint="/api/health", cause=cause)
        assert error.endpoint == "/api/health"
        assert error.cause == cause


class TestIndexingError:
    def test_file_path_and_count(self):
        path = Path("/project/src/module.py")
        error = IndexingError("Failed", file_path=path, files_processed=42)
        assert error.file_path == path
        assert error.files_processed == 42


class TestChunkingError:
    def test_language_and_line(self):
        error = ChunkingError("Unsupported", language="cobol", line_number=42)
        assert error.language == "cobol"
        assert error.line_number == 42


class TestFileProcessingError:
    def test_file_path_and_cause(self):
        path = Path("/project/file.py")
        cause = FileNotFoundError("No such file")
        error = FileProcessingError("Failed", file_path=path, cause=cause)
        assert error.file_path == path
        assert error.cause == cause


class TestStorageError:
    def test_collection(self):
        error = StorageError("Error", collection="code")
        assert error.collection == "code"


class TestCollectionError:
    def test_collection(self):
        error = CollectionError("Not found", collection="memory")
        assert error.collection == "memory"


class TestDimensionMismatchError:
    def test_dimensions(self):
        error = DimensionMismatchError(
            "Mismatch", collection="code", expected_dims=1024, actual_dims=768
        )
        assert error.expected_dims == 1024
        assert error.actual_dims == 768
        assert error.details["expected_dims"] == 1024
        assert error.details["actual_dims"] == 768


class TestSearchError:
    def test_query(self):
        error = SearchError("No results", query="find me")
        assert error.query == "find me"

    def test_long_query_truncated(self):
        error = SearchError("Error", query="search " * 100)
        assert len(error.details["query"]) <= 103


class TestQueryValidationError:
    def test_constraint(self):
        error = QueryValidationError("Violated", constraint="max_length=1000")
        assert error.constraint == "max_length=1000"


class TestHookError:
    def test_agent_and_event(self):
        error = HookError("Failed", agent="cursor", hook_event="session-start")
        assert error.agent == "cursor"
        assert error.hook_event == "session-start"
