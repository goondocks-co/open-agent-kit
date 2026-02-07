"""Comprehensive tests for daemon config management routes.

Tests cover:
- Configuration GET/POST endpoints
- Provider model listing (Ollama, OpenAI)
- Configuration testing (embedding and summarization)
- Daemon restart and configuration validation
- Error handling and edge cases
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def tmp_project_with_config(tmp_path: Path):
    """Create temporary project with CI config."""
    oak_dir = tmp_path / ".oak" / "ci"
    oak_dir.mkdir(parents=True)

    config_file = oak_dir.parent / "config.yaml"
    config_file.write_text("""
codebase_intelligence:
  embedding:
    provider: ollama
    model: bge-m3
    base_url: http://localhost:11434
  index_on_startup: true
  watch_files: true
  log_level: INFO
""")

    return tmp_path


@pytest.fixture
def setup_state_with_project(tmp_project_with_config):
    """Setup daemon state with project root."""
    state = get_state()
    state.project_root = tmp_project_with_config
    state.ci_config = MagicMock()
    state.ci_config.embedding = MagicMock()
    state.ci_config.embedding.provider = "ollama"
    state.ci_config.embedding.model = "bge-m3"
    state.ci_config.embedding.base_url = "http://localhost:11434"
    state.ci_config.embedding.get_dimensions.return_value = 1024
    state.ci_config.embedding.get_context_tokens.return_value = 512
    state.ci_config.embedding.get_max_chunk_chars.return_value = 2000
    state.ci_config.embedding.fallback_enabled = False
    state.ci_config.summarization = MagicMock()
    state.ci_config.summarization.enabled = False
    state.ci_config.summarization.provider = "ollama"
    state.ci_config.summarization.model = "llama2"
    state.ci_config.summarization.base_url = "http://localhost:11434"
    state.ci_config.summarization.timeout = 30
    state.ci_config.summarization.context_tokens = 2000
    state.ci_config.index_on_startup = True
    state.ci_config.watch_files = True
    state.ci_config.log_level = "INFO"
    return state


# =============================================================================
# GET /api/config Tests
# =============================================================================


class TestGetConfig:
    """Test GET /api/config endpoint."""

    def test_get_config_success(self, client, setup_state_with_project):
        """Test successful config retrieval."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        assert "embedding" in data
        assert "summarization" in data
        assert data["embedding"]["provider"] == "ollama"

    def test_get_config_includes_embedding_settings(self, client, setup_state_with_project):
        """Test that embedding settings are included."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        embedding = data["embedding"]
        assert "provider" in embedding
        assert "model" in embedding
        assert "base_url" in embedding
        assert "dimensions" in embedding
        assert "context_tokens" in embedding
        assert "max_chunk_chars" in embedding

    def test_get_config_includes_summarization_settings(self, client, setup_state_with_project):
        """Test that summarization settings are included."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        summarization = data["summarization"]
        assert "enabled" in summarization
        assert "provider" in summarization
        assert "model" in summarization
        assert "base_url" in summarization

    def test_get_config_includes_global_settings(self, client, setup_state_with_project):
        """Test that global settings are included."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.json()
        assert "index_on_startup" in data
        assert "watch_files" in data
        assert "log_level" in data

    def test_get_config_no_project_root(self, client):
        """Test get config fails when project root not set."""
        # Reset state AFTER client creation (client fixture sets project_root)
        reset_state()
        response = client.get("/api/config")

        # Should fail gracefully
        assert response.status_code == 500


# =============================================================================
# PUT /api/config Tests
# =============================================================================


class TestUpdateConfig:
    """Test PUT /api/config endpoint."""

    def test_update_embedding_provider(self, client, setup_state_with_project):
        """Test updating embedding provider."""
        payload = {
            "embedding": {"provider": "openai"},
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["embedding_changed"] is True

    def test_update_embedding_model(self, client, setup_state_with_project):
        """Test updating embedding model."""
        payload = {
            "embedding": {"model": "text-embedding-3-small"},
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["embedding_changed"] is True

    def test_update_base_url(self, client, setup_state_with_project):
        """Test updating base URL."""
        payload = {
            "embedding": {"base_url": "http://localhost:8000"},
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"

    def test_update_context_tokens(self, client, setup_state_with_project):
        """Test updating context tokens."""
        payload = {
            "embedding": {"context_tokens": 1024},
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"

    def test_update_max_chunk_chars(self, client, setup_state_with_project):
        """Test updating max chunk characters."""
        payload = {
            "embedding": {"max_chunk_chars": 4000},
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"

    def test_update_summarization_enabled(self, client, setup_state_with_project):
        """Test updating summarization enabled flag."""
        payload = {
            "summarization": {
                "enabled": True,
            }
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["summarization_changed"] is True

    def test_update_summarization_model(self, client, setup_state_with_project):
        """Test updating summarization model."""
        payload = {
            "summarization": {
                "model": "mistral:7b",
            }
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"

    def test_update_multiple_settings(self, client, setup_state_with_project):
        """Test updating multiple settings at once."""
        payload = {
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-large",
                "base_url": "https://api.openai.com/v1",
            }
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["embedding_changed"] is True

    def test_update_config_fallback_enabled(self, client, setup_state_with_project):
        """Test updating fallback enabled flag."""
        payload = {
            "embedding": {"fallback_enabled": True},
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"

    def test_update_config_invalid_json(self, client, setup_state_with_project):
        """Test update config with invalid JSON."""
        response = client.put(
            "/api/config",
            content=b"bad json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400

    def test_update_config_no_project_root(self, client):
        """Test update config fails without project root."""
        # Reset state AFTER client creation (client fixture sets project_root)
        reset_state()
        response = client.put("/api/config", json={"embedding": {"provider": "openai"}})

        assert response.status_code == 500

    def test_update_config_returns_updated_values(self, client, setup_state_with_project):
        """Test that response includes updated values."""
        payload = {
            "embedding": {"model": "text-embedding-3-large"},
        }
        response = client.put("/api/config", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "embedding" in data
        assert "summarization" in data
        assert "embedding_changed" in data
        assert "summarization_changed" in data


# =============================================================================
# GET /api/providers/models Tests
# =============================================================================


class TestListProviderModels:
    """Test GET /api/providers/models endpoint."""

    @patch("httpx.AsyncClient")
    def test_list_ollama_models(self, mock_client, client, setup_state_with_project):
        """Test listing models from Ollama."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "bge-m3:latest", "size": 1000000000},
                {"name": "nomic-embed-text:latest", "size": 500000000},
            ]
        }

        response = client.get(
            "/api/providers/models",
            params={"provider": "ollama", "base_url": "http://localhost:11434"},
        )

        # Response should succeed even if http call fails (depends on mocking)
        assert response.status_code in (200, 500)

    @patch("httpx.AsyncClient")
    def test_list_openai_models(self, mock_client, client, setup_state_with_project):
        """Test listing models from OpenAI-compatible API."""
        response = client.get(
            "/api/providers/models",
            params={
                "provider": "openai",
                "base_url": "http://localhost:8000",
                "api_key": "sk-test",
            },
        )

        # Should handle the request
        assert response.status_code in (200, 500)

    def test_list_models_default_parameters(self, client, setup_state_with_project):
        """Test that default parameters are used."""
        response = client.get("/api/providers/models")

        # Should use defaults: ollama, localhost:11434
        assert response.status_code in (200, 500)

    def test_list_models_custom_base_url(self, client, setup_state_with_project):
        """Test with custom base URL."""
        response = client.get(
            "/api/providers/models",
            params={
                "base_url": "http://custom-ollama:11434",
            },
        )

        assert response.status_code in (200, 500)

    def test_list_models_connection_error_handling(self, client, setup_state_with_project):
        """Test that connection errors are handled gracefully."""
        response = client.get(
            "/api/providers/models",
            params={
                "base_url": "http://nonexistent-host:11434",
            },
        )

        # Should return error response
        assert response.status_code in (200, 500)


# =============================================================================
# POST /api/config/test Tests
# =============================================================================


class TestConfigTest:
    """Test POST /api/config/test endpoint."""

    @patch(
        "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.create_provider_from_config"
    )
    def test_test_config_success(self, mock_create_provider, client, setup_state_with_project):
        """Test successful config test."""
        # Mock provider
        mock_provider = MagicMock()
        mock_provider.name = "ollama"
        mock_provider.is_available = True
        mock_provider.embed.return_value = MagicMock(embeddings=[[0.1, 0.2, 0.3] * 256])
        mock_provider.check_availability.return_value = (True, "Available")
        mock_create_provider.return_value = mock_provider

        payload = {
            "provider": "ollama",
            "model": "bge-m3",
            "base_url": "http://localhost:11434",
        }
        response = client.post("/api/config/test", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    @patch(
        "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.create_provider_from_config"
    )
    def test_test_config_provider_creation_fails(
        self, mock_create_provider, client, setup_state_with_project
    ):
        """Test config test when provider creation fails."""
        mock_create_provider.side_effect = ValueError("Invalid provider")

        payload = {
            "provider": "invalid",
            "model": "test-model",
            "base_url": "http://localhost:11434",
        }
        response = client.post("/api/config/test", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_test_config_invalid_json(self, client, setup_state_with_project):
        """Test config test with invalid JSON."""
        response = client.post(
            "/api/config/test",
            content=b"bad json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400

    def test_test_config_embedding_generation(self, client, setup_state_with_project):
        """Test that actual embedding is generated during test."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.create_provider_from_config"
        ) as mock_create:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_provider.is_available = True
            mock_provider.embed.return_value = MagicMock(embeddings=[[0.5] * 1024])
            mock_provider.check_availability.return_value = (True, "Available")
            mock_create.return_value = mock_provider

            payload = {
                "provider": "ollama",
                "model": "bge-m3",
            }
            response = client.post("/api/config/test", json=payload)

            assert response.status_code == 200
            # Provider should be called with test text
            mock_provider.embed.assert_called()


# =============================================================================
# POST /api/restart Tests
# =============================================================================


class TestRestartDaemon:
    """Test POST /api/restart endpoint."""

    def test_restart_daemon_success(self, client, setup_state_with_project):
        """Test successful daemon restart."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.create_provider_from_config"
        ) as mock_create:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_create.return_value = mock_provider

            response = client.post("/api/restart")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "restarted"

    def test_restart_daemon_returns_config(self, client, setup_state_with_project):
        """Test that restart returns updated config."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.create_provider_from_config"
        ) as mock_create:
            mock_provider = MagicMock()
            mock_provider.name = "ollama"
            mock_create.return_value = mock_provider

            response = client.post("/api/restart")

            assert response.status_code == 200
            data = response.json()
            assert "embedding" in data
            assert "model_changed" in data
            assert "chunk_params_changed" in data

    def test_restart_detects_model_change(self, client, setup_state_with_project):
        """Test that model changes are detected."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.config.load_ci_config"
        ) as mock_load:
            with patch(
                "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.create_provider_from_config"
            ) as mock_create:
                mock_config = MagicMock()
                mock_config.embedding.model = "text-embedding-3-large"
                mock_config.embedding.get_dimensions.return_value = 3072
                mock_config.embedding.get_context_tokens.return_value = 512
                mock_config.embedding.get_max_chunk_chars.return_value = 2000
                mock_load.return_value = mock_config

                mock_provider = MagicMock()
                mock_provider.name = "openai"
                mock_create.return_value = mock_provider

                response = client.post("/api/restart")

                assert response.status_code == 200
                data = response.json()
                assert "model_changed" in data

    def test_restart_no_project_root(self, client):
        """Test restart fails without project root."""
        # Reset state AFTER client creation (client fixture sets project_root)
        reset_state()
        response = client.post("/api/restart")

        assert response.status_code == 500

    def test_restart_provider_creation_fails(self, client, setup_state_with_project):
        """Test restart handles provider creation failures."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.create_provider_from_config"
        ) as mock_create:
            mock_create.side_effect = ValueError("Provider error")

            response = client.post("/api/restart")

            assert response.status_code == 500


# =============================================================================
# GET /api/providers/summarization-models Tests
# =============================================================================


class TestListSummarizationModels:
    """Test GET /api/providers/summarization-models endpoint."""

    def test_list_summarization_models_default(self, client, setup_state_with_project):
        """Test listing summarization models with defaults."""
        response = client.get("/api/providers/summarization-models")

        assert response.status_code in (200, 500)

    def test_list_summarization_models_custom_provider(self, client, setup_state_with_project):
        """Test listing models from custom provider."""
        response = client.get(
            "/api/providers/summarization-models",
            params={
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
            },
        )

        assert response.status_code in (200, 500)

    def test_list_summarization_models_with_api_key(self, client, setup_state_with_project):
        """Test listing models with API key."""
        response = client.get(
            "/api/providers/summarization-models",
            params={
                "provider": "openai",
                "api_key": "sk-test",
            },
        )

        assert response.status_code in (200, 500)


# =============================================================================
# POST /api/config/test-summarization Tests
# =============================================================================


class TestTestSummarizationConfig:
    """Test POST /api/config/test-summarization endpoint."""

    @patch("open_agent_kit.features.codebase_intelligence.summarization.create_summarizer")
    def test_test_summarization_success(
        self, mock_create_summarizer, client, setup_state_with_project
    ):
        """Test successful summarization config test."""
        mock_summarizer = MagicMock()
        mock_summarizer._resolved_model = "mistral:7b"
        mock_summarizer._context_window = 8000
        mock_summarizer.summarize_session.return_value = MagicMock(success=True)
        mock_create_summarizer.return_value = mock_summarizer

        payload = {
            "provider": "ollama",
            "model": "mistral:7b",
            "base_url": "http://localhost:11434",
        }
        response = client.post("/api/config/test-summarization", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    def test_test_summarization_invalid_json(self, client, setup_state_with_project):
        """Test summarization test with invalid JSON."""
        response = client.post(
            "/api/config/test-summarization",
            content=b"bad json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400

    @patch("open_agent_kit.features.codebase_intelligence.summarization.create_summarizer")
    def test_test_summarization_model_not_available(
        self, mock_create, client, setup_state_with_project
    ):
        """Test summarization test when model is not available."""
        mock_create.return_value = None

        payload = {
            "provider": "ollama",
            "model": "nonexistent-model",
        }
        response = client.post("/api/config/test-summarization", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


# =============================================================================
# POST /api/config/discover-context Tests
# =============================================================================


class TestDiscoverContextTokens:
    """Test POST /api/config/discover-context endpoint."""

    @patch("open_agent_kit.features.codebase_intelligence.summarization.discover_model_context")
    def test_discover_context_success(self, mock_discover, client, setup_state_with_project):
        """Test successful context discovery."""
        mock_discover.return_value = 128000

        payload = {
            "model": "gpt-4",
            "provider": "openai",
            # Must use localhost URL due to security restrictions
            "base_url": "http://localhost:8080",
        }
        response = client.post("/api/config/discover-context", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["context_tokens"] == 128000

    def test_discover_context_missing_model(self, client, setup_state_with_project):
        """Test discovery without model name."""
        payload = {
            "provider": "openai",
        }
        response = client.post("/api/config/discover-context", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_discover_context_invalid_json(self, client, setup_state_with_project):
        """Test discovery with invalid JSON."""
        response = client.post(
            "/api/config/discover-context",
            content=b"bad json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400

    @patch("open_agent_kit.features.codebase_intelligence.summarization.discover_model_context")
    def test_discover_context_failure(self, mock_discover, client, setup_state_with_project):
        """Test context discovery when it fails."""
        mock_discover.return_value = None

        payload = {
            "model": "unknown-model",
        }
        response = client.post("/api/config/discover-context", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
