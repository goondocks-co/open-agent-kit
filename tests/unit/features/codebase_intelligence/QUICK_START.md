# Quick Start Guide - Running Tests

## File Structure

```
tests/unit/features/codebase_intelligence/
├── conftest.py                    # All shared fixtures
├── test_config.py                 # 100+ tests for configuration
├── test_constants.py              # 100+ tests for constants
├── test_exceptions.py             # 70+ tests for exceptions
├── daemon/
│   ├── test_state.py              # 50+ tests for state management
│   └── test_manager.py            # 40+ tests for daemon lifecycle
├── TEST_SUITE_SUMMARY.md          # Comprehensive documentation
└── QUICK_START.md                 # This file
```

## Running Tests

### All Tests
```bash
cd /Users/chris/Repos/open-agent-kit
pytest tests/unit/features/codebase_intelligence/ -v
```

### Specific Test File
```bash
pytest tests/unit/features/codebase_intelligence/test_config.py -v
pytest tests/unit/features/codebase_intelligence/test_constants.py -v
pytest tests/unit/features/codebase_intelligence/test_exceptions.py -v
pytest tests/unit/features/codebase_intelligence/daemon/test_state.py -v
pytest tests/unit/features/codebase_intelligence/daemon/test_manager.py -v
```

### Specific Test Class
```bash
pytest tests/unit/features/codebase_intelligence/test_config.py::TestEmbeddingConfigInit -v
pytest tests/unit/features/codebase_intelligence/daemon/test_state.py::TestIndexStatusTransitions -v
```

### With Coverage Report
```bash
pytest tests/unit/features/codebase_intelligence/ \
  --cov=src/open_agent_kit/features/codebase_intelligence \
  --cov-report=html \
  -v
```

### Run Only Tests Matching Pattern
```bash
pytest tests/unit/features/codebase_intelligence/ -k "test_init" -v
pytest tests/unit/features/codebase_intelligence/ -k "validation" -v
```

## Test Organization

### conftest.py - 30+ Fixtures

**Configuration Fixtures:**
- `default_embedding_config`
- `custom_embedding_config`
- `invalid_provider_config`
- `invalid_url_config`
- `empty_model_config`
- `default_ci_config`
- `custom_ci_config`

**State Fixtures:**
- `empty_index_status`
- `indexing_status`
- `ready_status`
- `error_status`
- `sample_session_info`
- `daemon_state`
- `initialized_daemon_state`

**File/Directory Fixtures:**
- `project_with_oak_config`
- `project_with_custom_config`
- `project_with_invalid_config`
- `project_with_malformed_yaml`
- `project_without_config`

**Mock Fixtures:**
- `mock_embedding_chain`
- `mock_vector_store`
- `mock_indexer`
- `mock_file_watcher`

**Helper Fixtures:**
- `mock_env_vars`

## Test Classes Overview

### test_config.py (22 Classes, 100+ Tests)

Configuration validation and loading:
- `TestEmbeddingConfigInit` - Initialization
- `TestEmbeddingConfigValidation` - Input validation
- `TestEmbeddingConfigFromDict` - Factory method
- `TestEmbeddingConfigToDict` - Serialization
- `TestEmbeddingConfigContextTokens` - Token handling
- `TestEmbeddingConfigMaxChunkChars` - Chunk calculation
- `TestEmbeddingConfigDimensions` - Dimension lookup
- `TestCIConfigInit` - Initialization
- `TestCIConfigValidation` - Validation
- `TestCIConfigEffectiveLogLevel` - Log level precedence
- `TestCIConfigFromDict` - Factory method
- `TestCIConfigToDict` - Serialization
- `TestLoadCIConfig` - File loading
- `TestSaveCIConfig` - File saving
- `TestGetModelInfo` - Model information
- `TestListKnownModels` - Model listing

### test_constants.py (17 Classes, 100+ Tests)

Verify all constants:
- `TestSearchTypeConstants`
- `TestCollectionConstants`
- `TestEmbeddingProviderConstants`
- `TestIndexStatusConstants`
- `TestDaemonStatusConstants`
- `TestAgentNameConstants`
- `TestFileNamesConstants`
- `TestAPIDefaultsConstants`
- `TestChunkTypeConstants`
- `TestMemoryTypeConstants`
- `TestKeywordConstants`
- `TestToolNameConstants`
- `TestBatchingConstants`
- `TestLoggingConstants`
- `TestInputValidationConstants`
- `TestHookEventConstants`
- `TestTagConstants`

### test_exceptions.py (14 Classes, 70+ Tests)

Exception hierarchy testing:
- `TestCIError` - Base exception
- `TestConfigurationError` - Configuration errors
- `TestValidationError` - Validation errors
- `TestDaemonError` - Daemon base errors
- `TestDaemonStartupError` - Startup failures
- `TestDaemonConnectionError` - Connection failures
- `TestIndexingError` - Indexing errors
- `TestChunkingError` - Chunking errors
- `TestFileProcessingError` - File processing errors
- `TestStorageError` - Storage errors
- `TestCollectionError` - Collection errors
- `TestDimensionMismatchError` - Dimension errors
- `TestSearchError` - Search errors
- `TestQueryValidationError` - Query validation
- `TestHookError` - Hook errors
- `TestExceptionHierarchy` - Inheritance verification

### daemon/test_state.py (10 Classes, 50+ Tests)

State management testing:
- `TestIndexStatusInit` - Initialization
- `TestIndexStatusTransitions` - State transitions
- `TestIndexStatusProgress` - Progress tracking
- `TestIndexStatusSerialization` - Serialization
- `TestSessionInfoInit` - Initialization
- `TestSessionInfoRecording` - Activity recording
- `TestDaemonStateInit` - Initialization
- `TestDaemonStateReadiness` - Readiness checks
- `TestDaemonStateSessionManagement` - Session lifecycle
- `TestDaemonStateReset` - State reset
- `TestModuleLevelState` - Global state functions

### daemon/test_manager.py (10 Classes, 40+ Tests)

Daemon lifecycle testing:
- `TestDerivePortFromPath` - Port derivation
- `TestGetProjectPort` - Port persistence
- `TestDaemonManagerInit` - Initialization
- `TestDaemonManagerPIDOperations` - PID management
- `TestDaemonManagerProcessChecks` - Process detection
- `TestDaemonManagerHealthCheck` - Health monitoring
- `TestDaemonManagerStatus` - Status reporting
- `TestDaemonManagerEnsureDataDir` - Directory management

## Key Testing Patterns

### 1. Using Fixtures

```python
def test_something(default_embedding_config):
    """Test using a fixture."""
    assert default_embedding_config.provider == "ollama"
```

### 2. Parametrized Tests

```python
@pytest.mark.parametrize("valid_url", [
    "http://localhost:11434",
    "https://api.openai.com/v1",
])
def test_valid_urls(self, valid_url):
    """Test multiple valid URLs."""
    config = EmbeddingConfig(base_url=valid_url)
    assert config.base_url == valid_url
```

### 3. Testing Exceptions

```python
def test_invalid_provider_raises_error(self):
    """Test that invalid provider raises error."""
    with pytest.raises(ValidationError) as exc_info:
        EmbeddingConfig(provider="invalid")
    assert exc_info.value.field == "provider"
```

### 4. Mocking

```python
@patch("os.kill")
def test_process_running(self, mock_kill):
    """Test using mocked os.kill."""
    mock_kill.return_value = None
    result = manager._is_process_running(1234)
    assert result is True
```

## Coverage Target

- **Overall Target**: 80% minimum
- **test_config.py**: 90%+
- **test_constants.py**: 100%
- **test_exceptions.py**: 95%+
- **daemon/test_state.py**: 90%+
- **daemon/test_manager.py**: 85%+

## Common Commands

```bash
# Run with verbose output
pytest tests/unit/features/codebase_intelligence/ -v

# Run with short output
pytest tests/unit/features/codebase_intelligence/ -q

# Run and stop on first failure
pytest tests/unit/features/codebase_intelligence/ -x

# Run specific test function
pytest tests/unit/features/codebase_intelligence/test_config.py::TestEmbeddingConfigInit::test_init_with_defaults -v

# Generate coverage report
pytest tests/unit/features/codebase_intelligence/ --cov=src/open_agent_kit/features/codebase_intelligence --cov-report=term-missing

# Run with profiling
pytest tests/unit/features/codebase_intelligence/ --durations=10

# Run tests in parallel (requires pytest-xdist)
pytest tests/unit/features/codebase_intelligence/ -n auto
```

## Adding New Tests

1. **Add to existing test class if related functionality**
2. **Create new test class if new functionality area**
3. **Use fixtures from conftest.py**
4. **Follow naming convention: `test_<feature>_<scenario>`**
5. **Include docstring explaining test**
6. **Use parametrize for multiple variations**

Example:

```python
class TestNewFeature:
    """Test new feature functionality."""

    def test_something_happens(self, fixture_name):
        """Test that something happens when X occurs.

        Args:
            fixture_name: Description of fixture.
        """
        # Setup
        obj = fixture_name

        # Execute
        result = obj.do_something()

        # Assert
        assert result is True
```

## Troubleshooting

### Import Errors
- Ensure project root is in PYTHONPATH
- Run from project root: `cd /Users/chris/Repos/open-agent-kit`

### Fixture Not Found
- Check fixture name spelling in conftest.py
- Ensure conftest.py is in parent directory

### Mocking Issues
- Use proper patch path: `module.Class.method`
- Mock at the point of use, not definition

### Test Isolation Issues
- Ensure fixtures create fresh instances
- Use monkeypatch for environment variables
- Clean up side effects in teardown

## Next Steps

Once tests pass, add integration tests for:
- embeddings/ module
- indexing/ module
- memory/ module
- retrieval/ module
- Full daemon server
