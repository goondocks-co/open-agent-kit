"""Configuration test routes for the CI daemon.

Provides endpoints to test embedding and summarization configurations
before applying them, and to discover model context window sizes.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.team.constants import (
    DEFAULT_BASE_URL,
)
from open_agent_kit.features.team.daemon.routes._utils import (
    validate_localhost_url as _validate_localhost_url,
)
from open_agent_kit.features.team.daemon.routes.config_providers import (
    _discover_embedding_context,
)
from open_agent_kit.features.team.embeddings.base import EmbeddingError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


@router.post("/api/config/test")
async def test_config(request: Request) -> dict:
    """Test an embedding configuration before applying it."""
    from open_agent_kit.features.team.config import EmbeddingConfig
    from open_agent_kit.features.team.embeddings.provider_chain import (
        create_provider_from_config,
    )
    from open_agent_kit.features.team.exceptions import ValidationError

    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    base_url = data.get("base_url", DEFAULT_BASE_URL)
    provider_type = data.get("provider", "ollama")
    model_name = data.get("model", "nomic-embed-text")

    # Security: Validate URL is localhost-only to prevent SSRF attacks
    if not _validate_localhost_url(base_url):
        return {
            "success": False,
            "error": "Only localhost URLs are allowed for security reasons",
            "suggestion": "Use localhost or 127.0.0.1 instead",
        }

    # Create config and handle validation errors
    try:
        test_cfg = EmbeddingConfig(
            provider=provider_type,
            model=model_name,
            base_url=base_url,
        )
    except (ValueError, RuntimeError, OSError, ValidationError) as e:
        logger.debug(f"Failed to create config: {e}")
        return {
            "success": False,
            "error": f"Invalid configuration: {e}",
            "suggestion": "Check that the provider and model are valid.",
        }

    logger.info(f"Testing embedding config: {test_cfg.provider}:{test_cfg.model}")

    try:
        provider = create_provider_from_config(test_cfg)
    except (ValueError, RuntimeError, OSError) as e:
        logger.debug(f"Failed to create provider: {e}")
        return {
            "success": False,
            "error": f"Failed to create provider: {e}",
            "suggestion": "Check that the provider type is correct.",
        }

    if test_cfg.provider == "ollama" and hasattr(provider, "check_availability"):
        available, reason = provider.check_availability()
        if not available:
            if "not found" in reason.lower():
                suggestion = f"Pull the model first: ollama pull {test_cfg.model}"
            elif "connect" in reason.lower() or "timed out" in reason.lower():
                suggestion = "Make sure Ollama is running: ollama serve"
            else:
                suggestion = "Check Ollama installation and configuration."

            return {
                "success": False,
                "error": reason,
                "suggestion": suggestion,
            }
    elif not provider.is_available:
        return {
            "success": False,
            "error": f"Provider {provider.name} is not available",
            "suggestion": "Check provider configuration and dependencies.",
        }

    test_text = "Hello, this is a test embedding."
    try:
        result = provider.embed([test_text])
        actual_dims = (
            len(result.embeddings[0])
            if result.embeddings is not None and len(result.embeddings) > 0
            else 0
        )

        # Try to discover context window for the embedding model
        context_window = await _discover_embedding_context(provider_type, model_name, base_url)

        return {
            "success": True,
            "provider": provider.name,
            "dimensions": actual_dims,
            "context_window": context_window,
            "model": test_cfg.model,
            "message": f"Successfully generated embedding with {actual_dims} dimensions.",
        }

    except (ValueError, RuntimeError, OSError, TimeoutError, EmbeddingError) as e:
        logger.debug(f"Embedding test failed: {e}")
        error_str = str(e)

        if "model" in error_str.lower() and "not found" in error_str.lower():
            return {
                "success": False,
                "error": f"Model '{test_cfg.model}' not found in Ollama",
                "suggestion": f"Pull the model first: ollama pull {test_cfg.model}",
            }

        if "connection" in error_str.lower() or "refused" in error_str.lower():
            return {
                "success": False,
                "error": f"Cannot connect to Ollama at {test_cfg.base_url}",
                "suggestion": "Make sure Ollama is running: ollama serve",
            }

        # Handle LM Studio "no models loaded" error - this is expected for on-demand loading
        if "no models loaded" in error_str.lower():
            return {
                "success": True,  # Config is valid, model just needs to load on first use
                "provider": provider.name,
                "dimensions": None,  # Unknown until model loads
                "context_window": None,  # Unknown until model loads
                "model": test_cfg.model,
                "message": "Configuration valid. Model will load on first use (on-demand loading).",
                "pending_load": True,  # Flag indicating model needs to load
            }

        return {
            "success": False,
            "error": f"Embedding test failed: {e}",
            "suggestion": "Check the model name and provider configuration.",
        }


@router.post("/api/config/test-summarization")
async def test_summarization_config(request: Request) -> dict:
    """Test a summarization configuration before applying it.

    Tests that the LLM provider is accessible and the model can generate responses.
    """
    from open_agent_kit.features.team.summarization import (
        create_summarizer,
    )

    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    provider = data.get("provider", "ollama")
    model = data.get("model", "qwen2.5:3b")
    base_url = data.get("base_url", DEFAULT_BASE_URL)
    api_key = data.get("api_key")

    # Security: Validate URL is localhost-only to prevent SSRF attacks
    if not _validate_localhost_url(base_url):
        return {
            "success": False,
            "error": "Only localhost URLs are allowed for security reasons",
            "suggestion": "Use localhost or 127.0.0.1 instead",
        }

    logger.info(f"Testing summarization config: {provider}:{model}")

    summarizer = create_summarizer(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
    )

    if not summarizer:
        # Get available models for suggestion
        from open_agent_kit.features.team.summarization import (
            list_available_models,
        )

        models = list_available_models(base_url=base_url, provider=provider, api_key=api_key)
        if models:
            model_names = [m.id for m in models[:5]]
            suggestion = f"Available models: {', '.join(model_names)}"
        else:
            suggestion = f"Make sure {provider} is running at {base_url}"

        return {
            "success": False,
            "error": f"Model '{model}' not available",
            "suggestion": suggestion,
        }

    # Test with a simple summarization
    try:
        result = summarizer.summarize_session(
            files_created=["test.py"],
            files_modified=[],
            files_read=[],
            commands_run=["pytest"],
            duration_minutes=1.0,
        )

        if result.success:
            # Get context window - try summarizer's cached value first, then discover
            context_window = summarizer._context_window
            if not context_window:
                # Fallback to explicit discovery (works better with Ollama native API)
                from open_agent_kit.features.team.summarization import (
                    discover_model_context,
                )

                resolved_model = summarizer._resolved_model or model
                context_window = discover_model_context(
                    model=resolved_model,
                    base_url=base_url,
                    provider=provider,
                    api_key=api_key,
                )
                logger.info(f"Discovered context window for {resolved_model}: {context_window}")

            return {
                "success": True,
                "provider": provider,
                "model": summarizer._resolved_model or model,
                "context_window": context_window,
                "message": f"Successfully tested summarization with {model}",
            }
        else:
            return {
                "success": False,
                "error": result.error or "Summarization test failed",
                "suggestion": "Check model compatibility",
            }

    except (ValueError, RuntimeError, OSError, TimeoutError) as e:
        logger.debug(f"Summarization test failed: {e}")
        return {
            "success": False,
            "error": f"Summarization test failed: {e}",
            "suggestion": "Check provider configuration",
        }


@router.post("/api/config/discover-context")
async def discover_context_tokens(request: Request) -> dict:
    """Discover context window size for a model via API.

    Tries multiple methods to discover the model's context window:
    1. OpenAI /v1/models endpoint (returns context_length or context_window)
    2. OpenAI /v1/models/{model} endpoint
    3. Ollama /api/show endpoint (fallback)
    """
    from open_agent_kit.features.team.summarization import (
        discover_model_context,
    )

    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    model = data.get("model")
    if not model:
        return {
            "success": False,
            "error": "Model name is required",
        }

    provider = data.get("provider", "ollama")
    base_url = data.get("base_url", DEFAULT_BASE_URL)
    api_key = data.get("api_key")

    # Security: Validate URL is localhost-only to prevent SSRF attacks
    if not _validate_localhost_url(base_url):
        return {
            "success": False,
            "error": "Only localhost URLs are allowed for security reasons",
        }

    logger.info(f"Discovering context window for {provider}:{model}")

    try:
        context_tokens = discover_model_context(
            model=model,
            base_url=base_url,
            provider=provider,
            api_key=api_key,
        )

        if context_tokens:
            return {
                "success": True,
                "context_tokens": context_tokens,
                "model": model,
                "message": f"Discovered context window: {context_tokens:,} tokens",
            }
        else:
            return {
                "success": False,
                "error": "Could not discover context window from API",
                "suggestion": "Enter the context window manually based on model documentation",
            }

    except (ValueError, RuntimeError, OSError, TimeoutError) as e:
        logger.warning(f"Context discovery failed for {model}: {e}")
        return {
            "success": False,
            "error": f"Discovery failed: {e}",
            "suggestion": "Check provider connectivity or enter manually",
        }
