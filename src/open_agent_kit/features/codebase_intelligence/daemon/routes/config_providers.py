"""Provider model discovery routes for the CI daemon.

Provides endpoints to query embedding and summarization model providers
(Ollama, LM Studio, OpenAI-compatible APIs) for available models.
"""

import logging
from typing import TYPE_CHECKING

import httpx
from fastapi import APIRouter

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_BASE_URL,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._utils import (
    validate_localhost_url as _validate_localhost_url,
)
from open_agent_kit.features.codebase_intelligence.embeddings.metadata import (
    EMBEDDING_MODEL_PATTERNS,
)
from open_agent_kit.features.codebase_intelligence.embeddings.metadata import (
    get_known_model_metadata as _get_known_model_metadata,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


def _heuristic_dimensions(model_name: str) -> int:
    """Guess embedding dimensions from model name when metadata is unavailable.

    This is the single shared heuristic used by all provider query helpers.

    Args:
        model_name: Model name/identifier (case-insensitive matching).

    Returns:
        Best-guess embedding dimension count.
    """
    name_lower = model_name.lower()
    if "3-large" in name_lower:
        return 3072
    if "3-small" in name_lower:
        return 1536
    if "1.5b" in name_lower or "large" in name_lower or "1024" in name_lower:
        return 1024
    if (
        "minilm" in name_lower
        or "384" in name_lower
        or "small" in name_lower
        or "mini" in name_lower
    ):
        return 384
    return 768  # Default


async def _query_ollama_model_info(
    client: httpx.AsyncClient,
    url: str,
    model_name: str,
) -> dict[str, int | None]:
    """Query Ollama /api/show for model metadata.

    Args:
        client: HTTP client.
        url: Ollama base URL.
        model_name: Model name to query.

    Returns:
        Dict with 'dimensions' and 'context_window' keys (values may be None).
    """
    import re

    result: dict[str, int | None] = {"dimensions": None, "context_window": None}

    try:
        response = await client.post(
            f"{url}/api/show",
            json={"name": model_name},
        )
        if response.status_code != 200:
            return result

        data = response.json()
        model_info = data.get("model_info", {})

        # Get embedding dimensions
        if "embedding_length" in model_info:
            result["dimensions"] = model_info["embedding_length"]

        # Get context window from model_info
        for key, value in model_info.items():
            key_lower = key.lower()
            if "context" in key_lower and isinstance(value, int):
                result["context_window"] = value
                break

        # Fallback: Check parameters for num_ctx
        if result["context_window"] is None:
            params = data.get("parameters", "")
            if params and "num_ctx" in params:
                match = re.search(r"num_ctx\s+(\d+)", params)
                if match:
                    result["context_window"] = int(match.group(1))

    except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
        logger.debug(f"Failed to query Ollama /api/show for {model_name}: {e}")

    return result


async def _query_ollama(client: httpx.AsyncClient, url: str) -> dict:
    """Query Ollama's native API for embedding models."""
    response = await client.get(f"{url}/api/tags")
    if response.status_code != 200:
        return {"success": False, "error": f"Ollama returned status {response.status_code}"}

    data = response.json()
    all_models = data.get("models", [])

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
        has_embedding_pattern = any(pattern in name_lower for pattern in EMBEDDING_MODEL_PATTERNS)

        if has_embedding_details or has_embedding_pattern:
            # Get dimensions from API first
            dimensions = details.get("embedding_length")

            # Try known models for dimensions/context
            known_meta = _get_known_model_metadata(name)
            if not dimensions:
                dimensions = known_meta.get("dimensions")
            if not dimensions:
                dimensions = _heuristic_dimensions(name)

            size = model.get("size", 0)
            size_str = f"{size / 1e9:.1f}GB" if size > 1e9 else f"{size / 1e6:.0f}MB"

            embedding_models.append(
                {
                    "name": base_name,
                    "display_name": short_name,
                    "full_name": name,
                    "dimensions": dimensions,
                    "context_window": known_meta.get("context_window"),
                    "size": size_str,
                    "provider": "ollama",
                }
            )

    # Enrich with context_window from /api/show for models that don't have known context
    for model in embedding_models:
        if model.get("context_window") is None:
            show_info = await _query_ollama_model_info(client, url, model["full_name"])
            if show_info.get("context_window"):
                model["context_window"] = show_info["context_window"]

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
        model_lower = model_id.lower()

        # Detection: text-embedding prefix, jina embedding, or OpenAI ada model
        is_text_embedding = model_lower.startswith("text-embedding-")
        is_jina_embedding = "jina" in model_lower and "embedding" in model_lower
        is_openai_embedding = "ada" in model_lower or model_lower.startswith("text-embedding-")

        if is_text_embedding or is_jina_embedding or is_openai_embedding:
            # Try to get from known models first
            known_meta = _get_known_model_metadata(model_id)
            dimensions = known_meta.get("dimensions")
            context_window = known_meta.get("context_window")

            # Fallback heuristic dimension guessing
            if dimensions is None:
                dimensions = _heuristic_dimensions(model_id)

            # Check if API returned context_window
            if context_window is None:
                context_window = model.get("context_window") or model.get("context_length")

            embedding_models.append(
                {
                    "name": model_id,
                    "display_name": model_id,
                    "dimensions": dimensions,
                    "context_window": context_window,
                    "provider": "openai",
                }
            )

    return {"success": True, "models": embedding_models}


async def _query_lmstudio(client: httpx.AsyncClient, url: str) -> dict:
    """Query LM Studio API for embedding models.

    LM Studio requires the 'text-embedding-' prefix for embedding models.
    """
    response = await client.get(f"{url}/v1/models")
    if response.status_code != 200:
        return {"success": False, "error": f"API returned status {response.status_code}"}

    data = response.json()
    all_models = data.get("data", [])

    embedding_models = []
    for model in all_models:
        model_id = model.get("id", "")
        model_lower = model_id.lower()

        # LM Studio only treats models with text-embedding- prefix as embedding models
        if not model_lower.startswith("text-embedding-"):
            continue

        display_name = model_id.replace("text-embedding-", "")

        # Try to get from known models first
        known_meta = _get_known_model_metadata(model_id)
        dimensions = known_meta.get("dimensions")
        context_window = known_meta.get("context_window")

        # Fallback heuristics for dimensions if not found
        if dimensions is None:
            dimensions = _heuristic_dimensions(model_id)

        # Check if LM Studio API returned context_window
        if context_window is None:
            context_window = model.get("context_window") or model.get("context_length")

        embedding_models.append(
            {
                "name": model_id,
                "display_name": display_name,
                "dimensions": dimensions,
                "context_window": context_window,
                "provider": "lmstudio",
            }
        )

    return {"success": True, "models": embedding_models}


@router.get("/api/providers/models")
async def list_provider_models(
    provider: str = "ollama",
    base_url: str = DEFAULT_BASE_URL,
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
            elif provider == "lmstudio":
                result = await _query_lmstudio(client, url)
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
    # All providers (Ollama, LM Studio, OpenAI-compat) use /v1/models
    api_url = url.rstrip("/")
    if not api_url.endswith("/v1"):
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

    # Filter for chat/completion models (exclude embedding models using shared patterns)
    llm_models = []
    for model in all_models:
        model_id = model.get("id", "")
        # Skip embedding models - they can't do chat completions
        if any(pattern in model_id.lower() for pattern in EMBEDDING_MODEL_PATTERNS):
            continue

        llm_models.append(
            {
                "id": model_id,
                "name": model_id,  # Show full name with tag (e.g., gpt-oss:120b)
                "context_window": model.get("context_window") or model.get("context_length"),
                "owned_by": model.get("owned_by"),
            }
        )

    # If provider is Ollama, try to enrich with real context window
    if provider == "ollama":
        base_api_url = url.replace("/v1", "")
        for model in llm_models:
            try:
                # Call /api/show for each model to get precise context
                show_resp = await client.post(
                    f"{base_api_url}/api/show", json={"name": model["name"]}
                )
                if show_resp.status_code == 200:
                    details = show_resp.json()
                    # Ollama returns 'context_length' in model_info, or 'parameters' string
                    # But usually 'details' object has quantization, etc.
                    # The 'model_info' key typically contains the GGUF metadata
                    model_info = details.get("model_info", {})

                    # Try to find context length in standard GGUF keys or namespaced keys
                    ctx = None

                    # 1. Check direct keys
                    if "context_length" in model_info:
                        ctx = model_info["context_length"]
                    elif "llama.context_length" in model_info:
                        ctx = model_info["llama.context_length"]
                    else:
                        # 2. Search for any key ending in .context_length (e.g. nomic-bert.context_length)
                        for k, v in model_info.items():
                            if k.endswith(".context_length"):
                                ctx = v
                                break

                    # 3. Fallback to details object if available
                    if not ctx:
                        ctx = details.get("details", {}).get("context_length")

                    if ctx:
                        model["context_window"] = int(ctx)
            except (httpx.HTTPError, ValueError, KeyError, OSError):
                pass  # Fallback to default/heuristics if 'show' fails

    return {"success": True, "models": llm_models}


@router.get("/api/providers/summarization-models")
async def list_summarization_models(
    provider: str = "ollama",
    base_url: str = DEFAULT_BASE_URL,
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


async def _discover_embedding_context(
    provider: str,
    model: str,
    base_url: str,
) -> int | None:
    """Discover context window for an embedding model.

    Tries multiple methods depending on provider:
    - Known model metadata lookup (fastest)
    - OpenAI-compatible /v1/models endpoint (LM Studio, vLLM, etc.)
    - Ollama: /api/show endpoint (most reliable for unknown models)

    Args:
        provider: Provider type (ollama, lmstudio, openai).
        model: Model name/identifier.
        base_url: Provider base URL.

    Returns:
        Context window in tokens, or None if unable to discover.
    """
    url = base_url.rstrip("/")

    # Check known models first (fastest path)
    known_meta = _get_known_model_metadata(model)
    if known_meta.get("context_window"):
        context = known_meta["context_window"]
        logger.debug(f"Found known context for {model}: {context}")
        return int(context) if context is not None else None

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Try OpenAI-compatible /v1/models endpoint (works for LM Studio, vLLM, etc.)
        v1_url = url if url.endswith("/v1") else f"{url}/v1"
        try:
            response = await client.get(f"{v1_url}/models")
            if response.status_code == 200:
                data = response.json()
                models_list = data.get("data", [])
                for m in models_list:
                    model_id = m.get("id", "")
                    # Match by exact ID or by model name being contained in ID
                    if model_id == model or model in model_id or model_id in model:
                        ctx = (
                            m.get("context_window")
                            or m.get("context_length")
                            or m.get("max_tokens")
                        )
                        if ctx and isinstance(ctx, int):
                            logger.debug(f"Found context for {model}: {ctx} (from /v1/models)")
                            return int(ctx)
        except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
            logger.debug(f"OpenAI /v1/models failed: {e}")

        # Try OpenAI-compatible /v1/models/{model} endpoint
        try:
            response = await client.get(f"{v1_url}/models/{model}")
            if response.status_code == 200:
                data = response.json()
                ctx = (
                    data.get("context_window")
                    or data.get("context_length")
                    or data.get("max_tokens")
                )
                if ctx and isinstance(ctx, int):
                    logger.debug(f"Found context for {model}: {ctx} (from /v1/models/{model})")
                    return int(ctx)
        except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
            logger.debug(f"OpenAI /v1/models/{model} failed: {e}")

        # For Ollama, try to get context from /api/show
        if provider == "ollama":
            try:
                show_info = await _query_ollama_model_info(client, url, model)
                if show_info.get("context_window"):
                    logger.debug(
                        f"Found context for {model}: {show_info['context_window']} from /api/show"
                    )
                    return show_info["context_window"]
            except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
                logger.debug(f"Failed to get context from Ollama /api/show: {e}")

    # Default fallback - return None to indicate manual entry needed
    logger.debug(f"Could not discover context for {model}")
    return None
