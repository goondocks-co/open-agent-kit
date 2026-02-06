"""Shared pytest fixtures for Codebase Intelligence feature tests.

This module provides common fixtures for testing the CI feature, including
configuration objects, temporary directories, and mock instances.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.config import (
    CIConfig,
    EmbeddingConfig,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    LOG_LEVEL_DEBUG,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    DaemonState,
    IndexStatus,
)

# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture
def default_embedding_config() -> EmbeddingConfig:
    """Provide a default embedding configuration.

    Returns:
        EmbeddingConfig with default values.
    """
    return EmbeddingConfig(
        provider=DEFAULT_PROVIDER,
        model=DEFAULT_MODEL,
        base_url=DEFAULT_BASE_URL,
    )


@pytest.fixture
def custom_embedding_config() -> EmbeddingConfig:
    """Provide a custom embedding configuration for testing.

    Returns:
        EmbeddingConfig with custom values.
    """
    return EmbeddingConfig(
        provider="openai",
        model="text-embedding-3-small",
        base_url="https://api.openai.com/v1",
        dimensions=1536,
        api_key="${OPENAI_API_KEY}",
    )


@pytest.fixture
def invalid_provider_config() -> dict:
    """Provide invalid provider configuration data.

    Returns:
        Dictionary with invalid provider.
    """
    return {
        "provider": "invalid_provider",
        "model": "some-model",
        "base_url": "http://localhost:11434",
    }


@pytest.fixture
def invalid_url_config() -> dict:
    """Provide configuration with invalid URL.

    Returns:
        Dictionary with invalid URL.
    """
    return {
        "provider": "ollama",
        "model": "bge-m3",
        "base_url": "not-a-valid-url",
    }


@pytest.fixture
def empty_model_config() -> dict:
    """Provide configuration with empty model name.

    Returns:
        Dictionary with empty model.
    """
    return {
        "provider": "ollama",
        "model": "",
        "base_url": "http://localhost:11434",
    }


@pytest.fixture
def default_ci_config() -> CIConfig:
    """Provide a default CI configuration.

    Returns:
        CIConfig with default values.
    """
    return CIConfig()


@pytest.fixture
def custom_ci_config() -> CIConfig:
    """Provide a custom CI configuration for testing.

    Returns:
        CIConfig with custom values.
    """
    return CIConfig(
        embedding=EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-small",
            base_url="https://api.openai.com/v1",
        ),
        index_on_startup=False,
        watch_files=False,
        exclude_patterns=["**/*.pyc", "**/__pycache__/**"],
        log_level=LOG_LEVEL_DEBUG,
    )


# =============================================================================
# Daemon State Fixtures
# =============================================================================


@pytest.fixture
def empty_index_status() -> IndexStatus:
    """Provide an empty index status.

    Returns:
        IndexStatus with default values.
    """
    return IndexStatus()


@pytest.fixture
def indexing_status() -> IndexStatus:
    """Provide an index status indicating active indexing.

    Returns:
        IndexStatus in indexing state.
    """
    status = IndexStatus()
    status.set_indexing()
    return status


@pytest.fixture
def ready_status() -> IndexStatus:
    """Provide an index status indicating ready state.

    Returns:
        IndexStatus in ready state.
    """
    status = IndexStatus()
    status.set_ready(duration=2.5)
    return status


@pytest.fixture
def error_status() -> IndexStatus:
    """Provide an index status indicating error state.

    Returns:
        IndexStatus in error state.
    """
    status = IndexStatus()
    status.set_error()
    return status


@pytest.fixture
def daemon_state() -> DaemonState:
    """Provide a daemon state instance.

    Returns:
        Fresh DaemonState for testing.
    """
    return DaemonState()


@pytest.fixture
def initialized_daemon_state(tmp_path: Path) -> DaemonState:
    """Provide an initialized daemon state.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        Initialized DaemonState with project root set.
    """
    state = DaemonState()
    state.initialize(tmp_path)
    return state


# =============================================================================
# Directory and File Fixtures
# =============================================================================


@pytest.fixture
def project_with_oak_config(tmp_path: Path) -> Path:
    """Create a temporary project with .oak/config.yaml.

    Args:
        tmp_path: Temporary directory from pytest.

    Yields:
        Path to project directory.
    """
    oak_dir = tmp_path / ".oak"
    oak_dir.mkdir()

    config_file = oak_dir / "config.yaml"
    config_file.write_text(
        """
codebase_intelligence:
  embedding:
    provider: ollama
    model: bge-m3
    base_url: http://localhost:11434
  index_on_startup: true
  watch_files: true
  log_level: INFO
"""
    )

    return tmp_path


@pytest.fixture
def project_with_custom_config(tmp_path: Path) -> Path:
    """Create a temporary project with custom CI config.

    Args:
        tmp_path: Temporary directory from pytest.

    Yields:
        Path to project directory.
    """
    oak_dir = tmp_path / ".oak"
    oak_dir.mkdir()

    config_file = oak_dir / "config.yaml"
    config_file.write_text(
        """
codebase_intelligence:
  embedding:
    provider: openai
    model: text-embedding-3-small
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
    dimensions: 1536
  index_on_startup: false
  watch_files: false
  exclude_patterns:
    - "**/*.pyc"
    - "**/venv/**"
  log_level: DEBUG
"""
    )

    return tmp_path


@pytest.fixture
def project_with_invalid_config(tmp_path: Path) -> Path:
    """Create a temporary project with invalid CI config.

    Args:
        tmp_path: Temporary directory from pytest.

    Yields:
        Path to project directory.
    """
    oak_dir = tmp_path / ".oak"
    oak_dir.mkdir()

    config_file = oak_dir / "config.yaml"
    config_file.write_text(
        """
codebase_intelligence:
  embedding:
    provider: invalid_provider
    model: bge-m3
    base_url: http://localhost:11434
"""
    )

    return tmp_path


@pytest.fixture
def project_with_malformed_yaml(tmp_path: Path) -> Path:
    """Create a temporary project with malformed YAML config.

    Args:
        tmp_path: Temporary directory from pytest.

    Yields:
        Path to project directory.
    """
    oak_dir = tmp_path / ".oak"
    oak_dir.mkdir()

    config_file = oak_dir / "config.yaml"
    config_file.write_text(
        """
codebase_intelligence:
  embedding:
    - invalid yaml structure
      - bad indentation
    model: bge-m3
"""
    )

    return tmp_path


@pytest.fixture
def project_without_config(tmp_path: Path) -> Path:
    """Create a temporary project without CI config.

    Args:
        tmp_path: Temporary directory from pytest.

    Yields:
        Path to project directory.
    """
    oak_dir = tmp_path / ".oak"
    oak_dir.mkdir()
    return tmp_path


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_embedding_chain() -> MagicMock:
    """Provide a mock embedding chain.

    Returns:
        MagicMock configured for EmbeddingProviderChain.
    """
    mock = MagicMock()
    mock.embed.return_value = [0.1, 0.2, 0.3]
    mock.embed_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]
    mock.dimensions = 1024
    return mock


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Provide a mock vector store.

    Returns:
        MagicMock configured for VectorStore.
    """
    mock = MagicMock()
    mock.add_documents.return_value = True
    mock.search.return_value = [
        {"id": "1", "score": 0.9, "text": "result 1"},
        {"id": "2", "score": 0.8, "text": "result 2"},
    ]
    mock.get_collection_size.return_value = 100
    return mock


@pytest.fixture
def mock_indexer() -> MagicMock:
    """Provide a mock code indexer.

    Returns:
        MagicMock configured for CodebaseIndexer.
    """
    mock = MagicMock()
    mock.index_codebase.return_value = 42  # Number of files indexed
    mock.is_indexing = False
    return mock


@pytest.fixture
def mock_file_watcher() -> MagicMock:
    """Provide a mock file watcher.

    Returns:
        MagicMock configured for FileWatcher.
    """
    mock = MagicMock()
    mock.start.return_value = None
    mock.stop.return_value = None
    mock.is_running = False
    return mock


# =============================================================================
# Dotenv Isolation Fixture
# =============================================================================


@pytest.fixture(autouse=True)
def _isolate_dotenv(monkeypatch):
    """Prevent the real .env file from leaking into tests.

    Two pollution vectors exist:
    1. ``cli.py`` calls ``load_dotenv()`` at import time, which injects
       OAK_CI_BACKUP_DIR from the repo's ``.env`` into ``os.environ``.
       Any test that imports the CLI (directly or transitively) leaves
       the env var set for all subsequent tests in the same process.
    2. ``get_backup_dir()`` reads ``.env`` via ``_read_dotenv_value``.

    This fixture clears the env var and wraps the dotenv reader so that
    only reads from test tmp directories (not the real project root) are
    allowed through.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        _read_dotenv_value as _real_read_dotenv_value,
    )
    from open_agent_kit.features.codebase_intelligence.constants import (
        OAK_CI_BACKUP_DIR_ENV,
    )

    # Vector 1: clear env var that load_dotenv may have injected
    monkeypatch.delenv(OAK_CI_BACKUP_DIR_ENV, raising=False)

    # Vector 2: block _read_dotenv_value from reading the real .env
    real_cwd_dotenv = Path.cwd() / ".env"

    def _filtered_read(dotenv_path: Path, key: str):
        if dotenv_path.resolve() == real_cwd_dotenv.resolve():
            return None
        return _real_read_dotenv_value(dotenv_path, key)

    with patch(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup._read_dotenv_value",
        side_effect=_filtered_read,
    ):
        yield


# =============================================================================
# Environment Variable Fixtures
# =============================================================================


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Provide environment variable mocking helper.

    Args:
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        Helper object for setting env vars.
    """

    class EnvVarHelper:
        def set(self, key: str, value: str) -> None:
            """Set an environment variable."""
            monkeypatch.setenv(key, value)

        def unset(self, key: str) -> None:
            """Unset an environment variable."""
            monkeypatch.delenv(key, raising=False)

    return EnvVarHelper()
