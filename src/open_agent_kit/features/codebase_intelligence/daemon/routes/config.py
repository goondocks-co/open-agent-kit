"""Configuration management routes for the CI daemon."""

import json
import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.embeddings import EmbeddingProviderChain

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


def _validate_localhost_url(url: str) -> bool:
    """Validate that a URL is localhost-only to prevent SSRF attacks.

    Args:
        url: URL to validate.

    Returns:
        True if URL is localhost, False otherwise.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False

        # Only allow localhost and 127.0.0.1
        allowed_hosts = {"localhost", "127.0.0.1", "::1"}
        if hostname.lower() not in allowed_hosts:
            logger.warning(f"Blocked non-localhost URL for security: {url}")
            return False

        # Only allow http/https protocols
        if parsed.scheme not in {"http", "https"}:
            logger.warning(f"Blocked non-http(s) URL for security: {url}")
            return False

        return True
    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid URL format: {url} - {e}")
        return False


@router.get("/api/config")
async def get_config() -> dict:
    """Get current configuration."""
    from open_agent_kit.features.codebase_intelligence.config import load_ci_config

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = load_ci_config(state.project_root)

    return {
        "embedding": {
            "provider": config.embedding.provider,
            "model": config.embedding.model,
            "base_url": config.embedding.base_url,
            "dimensions": config.embedding.get_dimensions(),
            "context_tokens": config.embedding.get_context_tokens(),
            "max_chunk_chars": config.embedding.get_max_chunk_chars(),
            "fallback_enabled": config.embedding.fallback_enabled,
        },
        "summarization": {
            "enabled": config.summarization.enabled,
            "provider": config.summarization.provider,
            "model": config.summarization.model,
            "base_url": config.summarization.base_url,
            "timeout": config.summarization.timeout,
            "context_tokens": config.summarization.context_tokens,
        },
        "index_on_startup": config.index_on_startup,
        "watch_files": config.watch_files,
        "log_level": config.log_level,
    }


@router.put("/api/config")
async def update_config(request: Request) -> dict:
    """Update configuration.

    Accepts JSON with optional fields for embedding and summarization settings.
    """
    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    config = load_ci_config(state.project_root)
    embedding_changed = False
    summarization_changed = False

    # Update embedding settings
    if "provider" in data:
        config.embedding.provider = data["provider"]
        embedding_changed = True
    if "model" in data:
        config.embedding.model = data["model"]
        # Reset max_chunk_chars to auto-detect from new model
        config.embedding.max_chunk_chars = None
        embedding_changed = True
    if "dimensions" in data and data["dimensions"] is not None:
        # Accept dimensions from UI (discovered during model selection)
        config.embedding.dimensions = data["dimensions"]
    elif "model" in data:
        # Model changed but no dimensions provided - will auto-detect on first use
        # This is a fallback, UI should always pass dimensions from model discovery
        config.embedding.dimensions = None
        logger.warning(
            f"Model changed to {data['model']} but no dimensions provided. "
            "Consider passing dimensions from model discovery."
        )
    if "base_url" in data:
        config.embedding.base_url = data["base_url"]
        embedding_changed = True
    if "fallback_enabled" in data:
        config.embedding.fallback_enabled = data["fallback_enabled"]
    if "context_tokens" in data:
        config.embedding.context_tokens = data["context_tokens"]
        embedding_changed = True
    if "max_chunk_chars" in data:
        config.embedding.max_chunk_chars = data["max_chunk_chars"]
        embedding_changed = True

    # Update summarization settings (nested under "summarization" key or flat)
    sum_data = data.get("summarization", data)
    if "summarization_enabled" in sum_data or "sum_enabled" in data:
        config.summarization.enabled = sum_data.get(
            "summarization_enabled", data.get("sum_enabled")
        )
        summarization_changed = True
    if "summarization_provider" in sum_data or "sum_provider" in data:
        config.summarization.provider = sum_data.get(
            "summarization_provider", data.get("sum_provider")
        )
        summarization_changed = True
    if "summarization_model" in sum_data or "sum_model" in data:
        config.summarization.model = sum_data.get("summarization_model", data.get("sum_model"))
        summarization_changed = True
    if "summarization_base_url" in sum_data or "sum_base_url" in data:
        config.summarization.base_url = sum_data.get(
            "summarization_base_url", data.get("sum_base_url")
        )
        summarization_changed = True

    # Handle nested summarization object format from UI
    if "summarization" in data and isinstance(data["summarization"], dict):
        sum_obj = data["summarization"]
        if "enabled" in sum_obj:
            config.summarization.enabled = sum_obj["enabled"]
            summarization_changed = True
        if "provider" in sum_obj:
            config.summarization.provider = sum_obj["provider"]
            summarization_changed = True
        if "model" in sum_obj:
            config.summarization.model = sum_obj["model"]
            summarization_changed = True
        if "base_url" in sum_obj:
            config.summarization.base_url = sum_obj["base_url"]
            summarization_changed = True
        if "context_tokens" in sum_obj:
            # Allow setting to None to clear explicit value
            config.summarization.context_tokens = sum_obj["context_tokens"]
            summarization_changed = True

    save_ci_config(state.project_root, config)

    # NOTE: Do NOT update state.ci_config here!
    # restart_daemon() needs to compare old vs new config to detect changes.
    # It will update state.ci_config after the comparison.

    message = "Configuration saved."
    if embedding_changed:
        message += " Restart daemon and rebuild index to apply embedding changes."
    elif summarization_changed:
        message += " Summarization changes take effect immediately."

    return {
        "status": "updated",
        "embedding": {
            "provider": config.embedding.provider,
            "model": config.embedding.model,
            "base_url": config.embedding.base_url,
            "max_chunk_chars": config.embedding.get_max_chunk_chars(),
        },
        "summarization": {
            "enabled": config.summarization.enabled,
            "provider": config.summarization.provider,
            "model": config.summarization.model,
            "base_url": config.summarization.base_url,
            "context_tokens": config.summarization.context_tokens,
        },
        "embedding_changed": embedding_changed,
        "summarization_changed": summarization_changed,
        "message": message,
    }


async def _query_ollama(client: httpx.AsyncClient, url: str) -> dict:
    """Query Ollama's native API for embedding models."""
    response = await client.get(f"{url}/api/tags")
    if response.status_code != 200:
        return {"success": False, "error": f"Ollama returned status {response.status_code}"}

    data = response.json()
    all_models = data.get("models", [])

    # Known embedding model name patterns (case-insensitive)
    # These are models known to produce embeddings even if not indicated in API
    embedding_patterns = [
        "embed",  # nomic-embed-text, mxbai-embed-large, etc.
        "bge-",  # bge-m3, bge-small, bge-large (BAAI General Embedding)
        "bge:",  # bge:latest
        "gte-",  # gte-qwen (General Text Embedding)
        "e5-",  # e5-large, e5-small (Microsoft)
        "snowflake-arctic-embed",  # Snowflake embedding
        "paraphrase",  # paraphrase-multilingual
    ]

    # Filter for embedding models based on API response and naming
    embedding_models = []
    for model in all_models:
        name = model.get("name", "")
        base_name = name.split(":")[0]
        short_name = base_name.split("/")[-1] if "/" in base_name else base_name
        name_lower = name.lower()

        # Detection: embedding_length in API response or known embedding pattern in name
        details = model.get("details", {})
        has_embedding_details = details.get("embedding_length") is not None
        has_embedding_pattern = any(pattern in name_lower for pattern in embedding_patterns)

        if has_embedding_details or has_embedding_pattern:
            # Get dimensions from API or use heuristic
            dimensions = details.get("embedding_length")
            if not dimensions:
                # Heuristics for common embedding models
                if "minilm" in name_lower or "384" in name or "small" in name_lower:
                    dimensions = 384
                elif "bge-m3" in name_lower:
                    dimensions = 1024  # bge-m3 uses 1024 dimensions
                elif "large" in name_lower or "1024" in name:
                    dimensions = 1024
                elif "nomic-embed-text" in name_lower:
                    dimensions = 768
                else:
                    dimensions = 768  # Default

            size = model.get("size", 0)
            size_str = f"{size / 1e9:.1f}GB" if size > 1e9 else f"{size / 1e6:.0f}MB"

            embedding_models.append(
                {
                    "name": base_name,
                    "display_name": short_name,
                    "full_name": name,
                    "dimensions": dimensions,
                    "size": size_str,
                    "provider": "ollama",
                }
            )

    return {"success": True, "models": embedding_models}


async def _query_openai_compat(client: httpx.AsyncClient, url: str, key: str | None) -> dict:
    """Query OpenAI-compatible API for embedding models."""
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    response = await client.get(f"{url}/v1/models", headers=headers)
    if response.status_code != 200:
        return {"success": False, "error": f"API returned status {response.status_code}"}

    data = response.json()
    all_models = data.get("data", [])

    embedding_models = []
    for model in all_models:
        model_id = model.get("id", "")
        has_embed_in_name = "embed" in model_id.lower()

        if has_embed_in_name:
            # Heuristic dimension guessing based on common model names
            dimensions = 768  # Default
            if "text-embedding-3-small" in model_id:
                dimensions = 1536
            elif "text-embedding-3-large" in model_id:
                dimensions = 3072
            elif "ada" in model_id:
                dimensions = 1536

            embedding_models.append(
                {
                    "name": model_id,
                    "display_name": model_id,
                    "dimensions": dimensions,
                    "provider": "openai",
                }
            )

    return {"success": True, "models": embedding_models}


@router.get("/api/providers/models")
async def list_provider_models(
    provider: str = "ollama",
    base_url: str = "http://localhost:11434",
    api_key: str | None = None,
) -> dict:
    """List embedding models available from a provider.

    Queries the provider's API to get actually installed/available models,
    filtering for embedding-capable models.
    """
    # Security: Validate URL is localhost-only to prevent SSRF attacks
    if not _validate_localhost_url(base_url):
        return {
            "success": False,
            "error": "Only localhost URLs are allowed for security reasons",
            "models": [],
        }

    try:
        url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider == "ollama":
                result = await _query_ollama(client, url)
            else:
                result = await _query_openai_compat(client, url, api_key)

            return result

    except httpx.ConnectError:
        return {
            "success": False,
            "error": f"Cannot connect to {provider} at {base_url}",
            "models": [],
        }
    except (httpx.HTTPError, TimeoutError, ValueError) as e:
        logger.debug(f"Failed to query provider models: {e}")
        return {
            "success": False,
            "error": str(e),
            "models": [],
        }


@router.post("/api/config/test")
async def test_config(request: Request) -> dict:
    """Test an embedding configuration before applying it."""
    from open_agent_kit.features.codebase_intelligence.config import EmbeddingConfig
    from open_agent_kit.features.codebase_intelligence.embeddings.provider_chain import (
        create_provider_from_config,
    )
    from open_agent_kit.features.codebase_intelligence.exceptions import ValidationError

    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    base_url = data.get("base_url", "http://localhost:11434")

    # Security: Validate URL is localhost-only to prevent SSRF attacks
    if not _validate_localhost_url(base_url):
        return {
            "success": False,
            "error": "Only localhost URLs are allowed for security reasons",
            "suggestion": "Use localhost or 127.0.0.1 instead",
        }

    # Create config and handle validation errors
    try:
        test_config = EmbeddingConfig(
            provider=data.get("provider", "ollama"),
            model=data.get("model", "nomic-embed-text"),
            base_url=base_url,
        )
    except (ValueError, RuntimeError, OSError, ValidationError) as e:
        logger.debug(f"Failed to create config: {e}")
        return {
            "success": False,
            "error": f"Invalid configuration: {e}",
            "suggestion": "Check that the provider and model are valid.",
        }

    logger.info(f"Testing embedding config: {test_config.provider}:{test_config.model}")

    try:
        provider = create_provider_from_config(test_config)
    except (ValueError, RuntimeError, OSError) as e:
        logger.debug(f"Failed to create provider: {e}")
        return {
            "success": False,
            "error": f"Failed to create provider: {e}",
            "suggestion": "Check that the provider type is correct.",
        }

    if test_config.provider == "ollama" and hasattr(provider, "check_availability"):
        available, reason = provider.check_availability()
        if not available:
            if "not found" in reason.lower():
                suggestion = f"Pull the model first: ollama pull {test_config.model}"
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

        return {
            "success": True,
            "provider": provider.name,
            "dimensions": actual_dims,
            "model": test_config.model,
            "message": f"Successfully generated embedding with {actual_dims} dimensions.",
        }

    except (ValueError, RuntimeError, OSError, TimeoutError) as e:
        logger.debug(f"Embedding test failed: {e}")
        error_str = str(e)

        if "model" in error_str.lower() and "not found" in error_str.lower():
            return {
                "success": False,
                "error": f"Model '{test_config.model}' not found in Ollama",
                "suggestion": f"Pull the model first: ollama pull {test_config.model}",
            }

        if "connection" in error_str.lower() or "refused" in error_str.lower():
            return {
                "success": False,
                "error": f"Cannot connect to Ollama at {test_config.base_url}",
                "suggestion": "Make sure Ollama is running: ollama serve",
            }

        return {
            "success": False,
            "error": f"Embedding test failed: {e}",
            "suggestion": "Check the model name and provider configuration.",
        }


@router.post("/api/restart")
async def restart_daemon() -> dict:
    """Reload configuration and reinitialize embedding chain."""
    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
    )
    from open_agent_kit.features.codebase_intelligence.embeddings.provider_chain import (
        create_provider_from_config,
    )

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    old_config = state.ci_config
    old_model_name = old_config.embedding.model if old_config else "unknown"

    # Track old chunk parameters to detect changes that require re-indexing
    old_context_tokens = old_config.embedding.get_context_tokens() if old_config else None
    old_max_chunk = old_config.embedding.get_max_chunk_chars() if old_config else None

    logger.info(f"Reloading configuration (current model: {old_model_name})...")

    ci_config = load_ci_config(state.project_root)
    new_model_name = ci_config.embedding.model
    new_dims = ci_config.embedding.get_dimensions() or 768
    new_context_tokens = ci_config.embedding.get_context_tokens()
    new_max_chunk = ci_config.embedding.get_max_chunk_chars()

    logger.info(f"New config loaded: model={new_model_name}, dims={new_dims}")

    state.ci_config = ci_config

    model_changed = old_model_name != new_model_name

    # Check if chunk parameters changed (requires re-indexing even if model is same)
    chunk_params_changed = (
        old_context_tokens != new_context_tokens or old_max_chunk != new_max_chunk
    )
    if chunk_params_changed and not model_changed:
        logger.info(
            f"Chunk parameters changed: context {old_context_tokens}->{new_context_tokens}, "
            f"max_chunk {old_max_chunk}->{new_max_chunk}"
        )

    index_cleared = False

    # Clear index if model changed (requires new embeddings) or chunk params changed
    # (chunk IDs include position, so old chunks won't be replaced - need clean slate)
    if (model_changed or chunk_params_changed) and state.vector_store:
        if model_changed:
            logger.warning(
                f"Embedding model changed from {old_model_name} to {new_model_name}. "
                "Clearing existing index..."
            )
        else:
            logger.info("Chunk parameters changed. Clearing existing index for re-chunking...")
        try:
            state.vector_store.clear_code_index()
            index_cleared = True
            logger.info("Code index cleared (memories preserved).")
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to clear index: {e}")

    try:
        primary_provider = create_provider_from_config(ci_config.embedding)
        logger.info(
            f"Created new embedding provider: {primary_provider.name} "
            f"(dims={new_dims}, max_chunk={ci_config.embedding.get_max_chunk_chars()})"
        )
    except (ValueError, RuntimeError, OSError) as e:
        logger.error(f"Failed to create new provider: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create embedding provider: {e}",
        ) from e

    # Create single-provider chain (no built-in fallback)
    state.embedding_chain = EmbeddingProviderChain(providers=[primary_provider])

    if state.vector_store:
        state.vector_store.embedding_provider = state.embedding_chain

    if state.indexer:
        from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
            ChunkerConfig,
        )

        # Update chunker with new config
        state.indexer.chunker = state.indexer.chunker.__class__(
            ChunkerConfig(max_chunk_chars=ci_config.embedding.get_max_chunk_chars())
        )

    # Check if index is empty (first-time setup)
    index_empty = False
    indexing_started = False
    if state.vector_store:
        stats = state.vector_store.get_stats()
        index_empty = stats.get("code_chunks", 0) == 0

    # Determine if we should index:
    # 1. No index exists (first-time setup) -> index
    # 2. Model changed (index was cleared above) -> rebuild with new embeddings
    # 3. Chunk parameters changed (index was cleared above) -> rebuild with new chunk sizes
    # 4. No changes -> do NOT re-index
    should_index = index_empty or index_cleared

    if should_index and state.indexer and state.vector_store:
        import asyncio

        from open_agent_kit.features.codebase_intelligence.daemon.server import (
            _background_index,
        )

        asyncio.create_task(_background_index())
        indexing_started = True
        if chunk_params_changed and not model_changed and not index_empty:
            logger.info("Starting background indexing after chunk parameter change")
        else:
            logger.info("Starting background indexing after config save")

    # Determine message based on what happened
    if indexing_started and index_empty:
        message = "Configuration saved! Indexing your codebase for the first time..."
    elif indexing_started and index_cleared:
        message = (
            f"Model changed from {old_model_name} to {new_model_name}. "
            "Re-indexing your codebase with the new model..."
        )
    elif indexing_started and chunk_params_changed:
        message = (
            f"Chunk settings changed (context: {new_context_tokens}, max_chunk: {new_max_chunk}). "
            "Re-indexing your codebase with new chunk sizes..."
        )
    elif model_changed and index_cleared:
        message = (
            f"Model changed from {old_model_name} to {new_model_name}. "
            "Index cleared - click 'Rebuild Index' to re-embed your code."
        )
    elif model_changed:
        message = (
            f"Model changed to {new_model_name}. " "Please rebuild the index to re-embed your code."
        )
    else:
        message = "Configuration reloaded successfully."

    return {
        "status": "restarted",
        "embedding": {
            "provider": ci_config.embedding.provider,
            "model": ci_config.embedding.model,
            "dimensions": new_dims,
            "max_chunk_chars": ci_config.embedding.get_max_chunk_chars(),
        },
        "model_changed": model_changed,
        "chunk_params_changed": chunk_params_changed,
        "index_cleared": index_cleared,
        "indexing_started": indexing_started,
        "message": message,
    }


# =============================================================================
# Summarization Configuration Endpoints
# =============================================================================


async def _query_llm_models(
    client: httpx.AsyncClient,
    url: str,
    api_key: str | None,
    provider: str,
) -> dict:
    """Query provider for LLM (chat/completion) models.

    Filters out embedding-only models to return only models capable of chat.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Use OpenAI-compatible /v1/models endpoint
    api_url = url.rstrip("/")
    if provider == "ollama" and not api_url.endswith("/v1"):
        api_url = f"{api_url}/v1"

    response = await client.get(f"{api_url}/models", headers=headers)
    if response.status_code != 200:
        return {
            "success": False,
            "error": f"API returned status {response.status_code}",
            "models": [],
        }

    data = response.json()
    all_models = data.get("data", [])

    # Filter for chat/completion models (exclude embedding models)
    # Common embedding model patterns to filter out
    embedding_patterns = [
        "embed",
        "embedding",  # Generic
        "bge-",
        "gte-",
        "e5-",  # Popular embedding model families
        "nomic-embed",
        "arctic-embed",
        "mxbai-embed",  # Specific models
    ]
    llm_models = []
    for model in all_models:
        model_id = model.get("id", "")
        # Skip embedding models - they can't do chat completions
        if any(x in model_id.lower() for x in embedding_patterns):
            continue

        llm_models.append(
            {
                "id": model_id,
                "name": model_id,  # Show full name with tag (e.g., gpt-oss:120b)
                "context_window": model.get("context_window") or model.get("context_length"),
                "owned_by": model.get("owned_by"),
            }
        )

    return {"success": True, "models": llm_models}


@router.get("/api/providers/summarization-models")
async def list_summarization_models(
    provider: str = "ollama",
    base_url: str = "http://localhost:11434",
    api_key: str | None = None,
) -> dict:
    """List LLM models available for summarization from a provider.

    Queries the provider's OpenAI-compatible API to get available chat models.
    Filters out embedding-only models.
    """
    # Security: Validate URL is localhost-only to prevent SSRF attacks
    if not _validate_localhost_url(base_url):
        return {
            "success": False,
            "error": "Only localhost URLs are allowed for security reasons",
            "models": [],
        }

    try:
        url = base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            return await _query_llm_models(client, url, api_key, provider)

    except httpx.ConnectError:
        return {
            "success": False,
            "error": f"Cannot connect to {provider} at {base_url}",
            "models": [],
        }
    except (httpx.HTTPError, TimeoutError, ValueError) as e:
        logger.debug(f"Failed to query summarization models: {e}")
        return {
            "success": False,
            "error": str(e),
            "models": [],
        }


@router.post("/api/config/test-summarization")
async def test_summarization_config(request: Request) -> dict:
    """Test a summarization configuration before applying it.

    Tests that the LLM provider is accessible and the model can generate responses.
    """
    from open_agent_kit.features.codebase_intelligence.summarization import (
        create_summarizer,
    )

    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    provider = data.get("provider", "ollama")
    model = data.get("model", "qwen2.5:3b")
    base_url = data.get("base_url", "http://localhost:11434")
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
        from open_agent_kit.features.codebase_intelligence.summarization import (
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
            return {
                "success": True,
                "provider": provider,
                "model": summarizer._resolved_model or model,
                "context_window": summarizer._context_window,
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
    from open_agent_kit.features.codebase_intelligence.summarization import (
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
    base_url = data.get("base_url", "http://localhost:11434")
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
