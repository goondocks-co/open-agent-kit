"""Agent provider settings routes for the CI daemon.

These routes provide the HTTP interface for configuring agent providers:
- Get/update agent settings (enabled, max_turns, timeout, provider)
- List available LLM models from a provider
- Test provider connectivity

IMPORTANT: Route order matters in FastAPI. This router uses prefix /api/agents
so specific paths (/settings, /provider-models, /test-provider) must be defined
BEFORE wildcard paths (/{agent_name}). The main agents.py module includes this
router to maintain correct ordering.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from open_agent_kit.features.team.constants import DEFAULT_BASE_URL
from open_agent_kit.features.team.daemon.routes._utils import (
    validate_localhost_url as _validate_localhost_url,
)
from open_agent_kit.features.team.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agent-settings"])


@router.get("/settings")
async def get_agent_settings() -> dict:
    """Get agent settings including provider configuration.

    Returns current agent configuration from CI config file.
    """
    from open_agent_kit.features.agent_runtime.models import AgentProvider

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")
    agents_config = config.agents

    # Create provider instance to get computed properties
    provider = AgentProvider(
        type=agents_config.provider_type,
        base_url=agents_config.provider_base_url,
        model=agents_config.provider_model,
    )

    return {
        "enabled": agents_config.enabled,
        "max_turns": agents_config.max_turns,
        "timeout_seconds": agents_config.timeout_seconds,
        "provider": {
            "type": agents_config.provider_type,
            "base_url": agents_config.provider_base_url or provider.default_base_url,
            "model": agents_config.provider_model,
            "api_format": provider.api_format,
            "recommended_models": provider.recommended_models,
        },
    }


@router.put("/settings")
async def update_agent_settings(request: dict) -> dict:
    """Update agent settings including provider configuration.

    Accepts JSON with optional fields:
    - enabled: bool
    - max_turns: int
    - timeout_seconds: int
    - provider: { type, base_url, model }
    """
    from open_agent_kit.features.team.config import save_ci_config

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")
    changed = False

    # Update basic settings
    if "enabled" in request:
        config.agents.enabled = request["enabled"]
        changed = True
    if "max_turns" in request:
        config.agents.max_turns = request["max_turns"]
        changed = True
    if "timeout_seconds" in request:
        config.agents.timeout_seconds = request["timeout_seconds"]
        changed = True

    # Update provider settings
    if "provider" in request and isinstance(request["provider"], dict):
        provider_data = request["provider"]
        if "type" in provider_data:
            config.agents.provider_type = provider_data["type"]
            changed = True
        if "base_url" in provider_data:
            config.agents.provider_base_url = provider_data["base_url"]
            changed = True
        if "model" in provider_data:
            config.agents.provider_model = provider_data["model"]
            changed = True

    if changed:
        save_ci_config(state.project_root, config)
        state.ci_config = config

    return {
        "success": True,
        "message": "Agent settings updated" if changed else "No changes made",
        "settings": {
            "enabled": config.agents.enabled,
            "max_turns": config.agents.max_turns,
            "timeout_seconds": config.agents.timeout_seconds,
            "provider_type": config.agents.provider_type,
            "provider_base_url": config.agents.provider_base_url,
            "provider_model": config.agents.provider_model,
        },
    }


@router.get("/provider-models")
async def list_agent_provider_models(
    provider: str = Query(default="ollama", description="Provider type"),
    base_url: str = Query(default=DEFAULT_BASE_URL, description="Provider base URL"),
) -> dict:
    """List LLM models available from a provider for agent execution.

    Queries the provider's API to get available chat/completion models.
    Filters out embedding-only models.

    Note: Only localhost URLs are allowed for security (prevents SSRF).
    """
    import httpx

    # Security: Validate URL is localhost-only
    if not _validate_localhost_url(base_url):
        return {
            "success": False,
            "error": "Only localhost URLs are allowed for security",
            "models": [],
        }

    # Patterns to filter out embedding models
    embedding_patterns = [
        "embed",
        "embedding",
        "bge-",
        "bge:",
        "gte-",
        "e5-",
        "nomic-embed",
        "arctic-embed",
        "mxbai-embed",
    ]

    try:
        url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider == "ollama":
                # Query Ollama native API
                response = await client.get(f"{url}/api/tags")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Ollama returned status {response.status_code}",
                        "models": [],
                    }

                data = response.json()
                all_models = data.get("models", [])

                # Filter for LLM models (exclude embedding models)
                llm_models = []
                for model in all_models:
                    name = model.get("name", "")
                    name_lower = name.lower()

                    # Skip embedding models
                    if any(pattern in name_lower for pattern in embedding_patterns):
                        continue

                    # Get size for display
                    size = model.get("size", 0)
                    size_str = f"{size / 1e9:.1f}GB" if size > 1e9 else f"{size / 1e6:.0f}MB"

                    llm_models.append(
                        {
                            "id": name,
                            "name": name,
                            "size": size_str,
                            "provider": "ollama",
                        }
                    )

                return {"success": True, "models": llm_models}

            else:
                # Use OpenAI-compatible /v1/models endpoint
                api_url = url if url.endswith("/v1") else f"{url}/v1"
                response = await client.get(f"{api_url}/models")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API returned status {response.status_code}",
                        "models": [],
                    }

                data = response.json()
                all_models = data.get("data", [])

                # Filter for LLM models
                llm_models = []
                for model in all_models:
                    model_id = model.get("id", "")
                    model_lower = model_id.lower()

                    # Skip embedding models
                    if any(pattern in model_lower for pattern in embedding_patterns):
                        continue

                    llm_models.append(
                        {
                            "id": model_id,
                            "name": model_id,
                            "context_window": model.get("context_window"),
                            "provider": provider,
                        }
                    )

                return {"success": True, "models": llm_models}

    except httpx.ConnectError:
        return {
            "success": False,
            "error": f"Cannot connect to {provider} at {base_url}",
            "models": [],
        }
    except (httpx.HTTPError, TimeoutError, ValueError) as e:
        logger.debug(f"Failed to query provider models: {e}")
        return {"success": False, "error": str(e), "models": []}


@router.post("/test-provider")
async def test_agent_provider(request: dict) -> dict:
    """Test agent provider connection.

    Tests that the provider is accessible and can list models.
    This is a lightweight check that doesn't run a full agent.

    Accepts JSON with:
    - provider: Provider type (ollama, lmstudio, etc.)
    - base_url: Provider base URL
    - model: Optional model to check for
    """
    import httpx

    provider = request.get("provider", "ollama")
    base_url = request.get("base_url", DEFAULT_BASE_URL)
    model = request.get("model")

    # Security: Validate URL is localhost-only
    if not _validate_localhost_url(base_url):
        return {
            "success": False,
            "error": "Only localhost URLs are allowed for security",
            "suggestion": "Use localhost or 127.0.0.1",
        }

    try:
        url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider == "ollama":
                # Test Ollama connection
                response = await client.get(f"{url}/api/tags")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Ollama returned status {response.status_code}",
                        "suggestion": "Make sure Ollama is running: ollama serve",
                    }

                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]

                # Check if specific model is available
                if model and model not in models:
                    # Check partial match (model without tag)
                    base_model = model.split(":")[0]
                    if not any(m.startswith(base_model) for m in models):
                        return {
                            "success": False,
                            "error": f"Model '{model}' not found",
                            "suggestion": f"Pull the model: ollama pull {model}",
                            "available_models": models[:10],
                        }

                return {
                    "success": True,
                    "provider": provider,
                    "message": f"Connected to Ollama with {len(models)} models available",
                    "model_available": model in models if model else None,
                }

            else:
                # Test OpenAI-compatible endpoint
                api_url = url if url.endswith("/v1") else f"{url}/v1"
                response = await client.get(f"{api_url}/models")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API returned status {response.status_code}",
                        "suggestion": f"Make sure {provider} is running at {base_url}",
                    }

                data = response.json()
                models = [m.get("id", "") for m in data.get("data", [])]

                return {
                    "success": True,
                    "provider": provider,
                    "message": f"Connected with {len(models)} models available",
                    "model_available": model in models if model else None,
                }

    except httpx.ConnectError:
        suggestions = {
            "ollama": "Make sure Ollama is running: ollama serve",
            "lmstudio": "Make sure LM Studio is running with the server enabled",
        }
        return {
            "success": False,
            "error": f"Cannot connect to {provider} at {base_url}",
            "suggestion": suggestions.get(provider, f"Check that {provider} is running"),
        }
    except (httpx.HTTPError, TimeoutError, ValueError) as e:
        return {"success": False, "error": f"Connection test failed: {e}"}
