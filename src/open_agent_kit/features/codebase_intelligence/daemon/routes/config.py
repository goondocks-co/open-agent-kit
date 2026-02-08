"""Configuration management routes for the CI daemon.

Event Handlers:
    _on_embedding_model_changed: Called when embedding model/dimensions change.
        Handles ChromaDB reinitialization and triggers re-embedding of all data.

    _on_index_params_changed: Called when chunk params or exclusions change.
        Clears code index for re-chunking (memories preserved).
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.codebase_intelligence.constants import (
    BACKUP_CONFIG_KEY,
    CI_CONFIG_KEY_TUNNEL,
    CI_CONFIG_TUNNEL_KEY_AUTO_START,
    CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH,
    CI_CONFIG_TUNNEL_KEY_NGROK_PATH,
    CI_CONFIG_TUNNEL_KEY_PROVIDER,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.features.codebase_intelligence.embeddings import EmbeddingProviderChain
from open_agent_kit.features.codebase_intelligence.embeddings.base import EmbeddingError

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


# =============================================================================
# Shared Constants (DRY)
# =============================================================================

# Default provider URLs
DEFAULT_PROVIDER_URLS: dict[str, str] = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234",
    "openai": "https://api.openai.com",
}

# Known embedding model metadata: dimensions and context window (tokens)
# Used by model discovery and test endpoints to provide accurate metadata
KNOWN_EMBEDDING_MODELS: dict[str, dict[str, int]] = {
    # Nomic models
    "nomic-embed-text": {"dimensions": 768, "context_window": 8192},
    "nomic-embed-code": {"dimensions": 768, "context_window": 8192},
    # BGE family (BAAI General Embedding)
    "bge-small": {"dimensions": 384, "context_window": 512},
    "bge-base": {"dimensions": 768, "context_window": 512},
    "bge-large": {"dimensions": 1024, "context_window": 512},
    "bge-m3": {"dimensions": 1024, "context_window": 8192},
    # GTE family (General Text Embedding)
    "gte-small": {"dimensions": 384, "context_window": 512},
    "gte-base": {"dimensions": 768, "context_window": 512},
    "gte-large": {"dimensions": 1024, "context_window": 512},
    "gte-qwen": {"dimensions": 1536, "context_window": 8192},
    # E5 family (Microsoft)
    "e5-small": {"dimensions": 384, "context_window": 512},
    "e5-base": {"dimensions": 768, "context_window": 512},
    "e5-large": {"dimensions": 1024, "context_window": 512},
    # Other common models
    "mxbai-embed-large": {"dimensions": 1024, "context_window": 512},
    "all-minilm": {"dimensions": 384, "context_window": 256},
    "snowflake-arctic-embed": {"dimensions": 1024, "context_window": 512},
    # OpenAI models
    "text-embedding-3-small": {"dimensions": 1536, "context_window": 8191},
    "text-embedding-3-large": {"dimensions": 3072, "context_window": 8191},
    "text-embedding-ada-002": {"dimensions": 1536, "context_window": 8191},
    # LM Studio prefixed variants (maps to same underlying models)
    "text-embedding-nomic-embed-text-v1.5": {"dimensions": 768, "context_window": 8192},
    "text-embedding-nomic-embed-code": {"dimensions": 768, "context_window": 8192},
    "text-embedding-bge-m3": {"dimensions": 1024, "context_window": 8192},
    "text-embedding-gte-qwen2": {"dimensions": 1536, "context_window": 8192},
}

# Patterns that indicate a model is an embedding model (case-insensitive)
# Used to filter embedding models from general model lists
EMBEDDING_MODEL_PATTERNS: list[str] = [
    "embed",  # nomic-embed-text, mxbai-embed-large, etc.
    "embedding",  # text-embedding-3-small, etc.
    "bge-",  # bge-m3, bge-small, bge-large (BAAI General Embedding)
    "bge:",  # bge:latest
    "gte-",  # gte-qwen (General Text Embedding)
    "e5-",  # e5-large, e5-small (Microsoft)
    "snowflake-arctic-embed",  # Snowflake embedding
    "paraphrase",  # paraphrase-multilingual
    "nomic-embed",  # Explicit nomic embedding
    "arctic-embed",  # Arctic embedding
    "mxbai-embed",  # mxbai embedding
]


def _get_known_model_metadata(model_name: str) -> dict[str, int | None]:
    """Look up known model metadata by name (case-insensitive partial match).

    Args:
        model_name: Model name to look up.

    Returns:
        Dict with 'dimensions' and 'context_window' keys
        (values may be None if model is unknown).
    """
    model_lower = model_name.lower()
    for known_name, metadata in KNOWN_EMBEDDING_MODELS.items():
        if known_name in model_lower or model_lower in known_name:
            return {
                "dimensions": metadata.get("dimensions"),
                "context_window": metadata.get("context_window"),
            }
    return {"dimensions": None, "context_window": None}


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

    except Exception as e:
        logger.debug(f"Failed to query Ollama /api/show for {model_name}: {e}")

    return result


@dataclass
class ConfigChangeResult:
    """Result of a configuration change event handler."""

    index_cleared: bool = False
    memories_reset: int = 0
    indexing_scheduled: bool = False
    memory_rebuild_scheduled: bool = False


async def _on_embedding_model_changed(
    state: "DaemonState",
    old_model: str,
    new_model: str,
) -> ConfigChangeResult:
    """Handle embedding model change event.

    When the embedding model changes, all existing embeddings become invalid
    because different models produce incompatible vector representations.

    This handler coordinates the rebuild process:
    1. Explicitly clears the code index (update_embedding_provider only clears
       when dimensions change, not model name)
    2. Schedules background code re-indexing via _background_index()
    3. Schedules memory re-embedding via rebuild_chromadb_from_sqlite()
       (which handles resetting embedded flags internally)

    Note: rebuild_chromadb_from_sqlite(reset_embedded_flags=True) is the single
    source of truth for memory rebuild - it resets flags and re-embeds atomically.

    Args:
        state: Daemon state with stores and processors.
        old_model: Previous model name.
        new_model: New model name.

    Returns:
        ConfigChangeResult with actions taken.
    """
    result = ConfigChangeResult()

    logger.info(f"Embedding model changed: {old_model} -> {new_model}")

    # Explicitly clear the code index - this is necessary because:
    # - update_embedding_provider() only clears collections when DIMENSIONS change
    # - Model name changes (same dims) also require clearing since embeddings are incompatible
    # - This ensures _background_index() sees 0 chunks and performs a full rebuild
    if state.vector_store:
        state.vector_store.clear_code_index()
        logger.info("Cleared code index (memories preserved)")
    result.index_cleared = True

    # Schedule code re-indexing
    if state.indexer and state.vector_store:
        from open_agent_kit.features.codebase_intelligence.daemon.server import (
            _background_index,
        )

        asyncio.create_task(_background_index())
        result.indexing_scheduled = True
        logger.info("Scheduled code re-indexing with new embedding model")

    # Schedule memory and session summary re-embedding using shared compaction logic
    # Note: Code index is already cleared above; we skip clearing it again here
    if state.activity_store and state.vector_store:
        total_observations = state.activity_store.count_observations()
        activity_store = state.activity_store  # Capture for closure
        vector_store = state.vector_store

        async def _rebuild_all_embeddings() -> None:
            from open_agent_kit.features.codebase_intelligence.activity.processor.indexing import (
                compact_all_chromadb,
            )

            loop = asyncio.get_event_loop()
            try:
                # Use shared compaction logic (skip code index - already cleared above)
                # Use hard_reset=False since we just need to re-embed, not reclaim space
                stats = await loop.run_in_executor(
                    None,
                    lambda: compact_all_chromadb(
                        activity_store=activity_store,
                        vector_store=vector_store,
                        clear_code_index=False,  # Already cleared above
                        hard_reset=False,  # No need to delete directory for model change
                    ),
                )
                logger.info(
                    f"Embedding rebuild complete: {stats['memories_embedded']} memories, "
                    f"{stats['sessions_embedded']} sessions, "
                    f"{stats['memories_cleared']} orphaned entries cleared"
                )
            except (OSError, ValueError, RuntimeError) as e:
                logger.error(f"Embedding rebuild failed: {e}")

        asyncio.create_task(_rebuild_all_embeddings())
        result.memory_rebuild_scheduled = True
        result.memories_reset = total_observations
        logger.info(
            f"Scheduled re-embedding of {total_observations} memories and session summaries"
        )

    return result


async def _on_index_params_changed(
    state: "DaemonState",
    reason: str,
) -> ConfigChangeResult:
    """Handle index parameter change event (chunk size, exclusions).

    When chunking parameters or exclusion patterns change, the code index
    needs to be rebuilt but memories are preserved (they don't depend on
    chunk parameters).

    Args:
        state: Daemon state with stores and processors.
        reason: Description of what changed (for logging).

    Returns:
        ConfigChangeResult with actions taken.
    """
    result = ConfigChangeResult()

    logger.info(f"Index parameters changed: {reason}")

    # Clear code index only (memories preserved)
    if state.vector_store:
        try:
            state.vector_store.clear_code_index()
            result.index_cleared = True
            logger.info("Code index cleared (memories preserved)")
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to clear code index: {e}")

    # Schedule re-indexing
    if state.indexer and state.vector_store:
        from open_agent_kit.features.codebase_intelligence.daemon.server import (
            _background_index,
        )

        asyncio.create_task(_background_index())
        result.indexing_scheduled = True
        logger.info("Scheduled code re-indexing after parameter change")

    return result


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
    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    # Compute origin of each config section (user/project/default)
    from open_agent_kit.features.codebase_intelligence.config import get_config_origins

    origins = get_config_origins(state.project_root)

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
        "session_quality": {
            "min_activities": config.session_quality.min_activities,
            "stale_timeout_seconds": config.session_quality.stale_timeout_seconds,
        },
        "log_rotation": {
            "enabled": config.log_rotation.enabled,
            "max_size_mb": config.log_rotation.max_size_mb,
            "backup_count": config.log_rotation.backup_count,
        },
        "index_on_startup": config.index_on_startup,
        "watch_files": config.watch_files,
        CI_CONFIG_KEY_TUNNEL: {
            CI_CONFIG_TUNNEL_KEY_PROVIDER: config.tunnel.provider,
            CI_CONFIG_TUNNEL_KEY_AUTO_START: config.tunnel.auto_start,
            CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH: config.tunnel.cloudflared_path or "",
            CI_CONFIG_TUNNEL_KEY_NGROK_PATH: config.tunnel.ngrok_path or "",
        },
        BACKUP_CONFIG_KEY: {
            "auto_enabled": config.backup.auto_enabled,
            "include_activities": config.backup.include_activities,
            "interval_minutes": config.backup.interval_minutes,
            "on_upgrade": config.backup.on_upgrade,
        },
        "log_level": config.log_level,
        "origins": origins,
    }


@router.put("/api/config")
async def update_config(request: Request) -> dict:
    """Update configuration.

    Accepts JSON with optional fields for embedding and summarization settings.
    """
    from open_agent_kit.features.codebase_intelligence.config import save_ci_config

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    logger.debug(f"Config update request: {list(data.keys())}")
    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")
    embedding_changed = False
    summarization_changed = False

    # Update embedding settings (nested object: { embedding: { provider, model, ... } })
    if "embedding" in data and isinstance(data["embedding"], dict):
        emb = data["embedding"]
        if "provider" in emb:
            config.embedding.provider = emb["provider"]
            embedding_changed = True
        if "model" in emb:
            config.embedding.model = emb["model"]
            config.embedding.max_chunk_chars = None  # Reset for new model
            embedding_changed = True
        if "base_url" in emb:
            config.embedding.base_url = emb["base_url"]
            embedding_changed = True
        if "dimensions" in emb and emb["dimensions"] is not None:
            old_dims = config.embedding.dimensions
            config.embedding.dimensions = emb["dimensions"]
            if old_dims != emb["dimensions"]:
                embedding_changed = True
        if "fallback_enabled" in emb:
            config.embedding.fallback_enabled = emb["fallback_enabled"]
        if "context_tokens" in emb:
            config.embedding.context_tokens = emb["context_tokens"]
            embedding_changed = True
        if "max_chunk_chars" in emb:
            config.embedding.max_chunk_chars = emb["max_chunk_chars"]
            embedding_changed = True

    # Update summarization settings (nested object: { summarization: { enabled, provider, ... } })
    if "summarization" in data and isinstance(data["summarization"], dict):
        summ = data["summarization"]
        logger.debug(f"Summarization update request: {summ}")
        if "enabled" in summ:
            config.summarization.enabled = summ["enabled"]
            summarization_changed = True
        if "provider" in summ:
            config.summarization.provider = summ["provider"]
            summarization_changed = True
        if "model" in summ:
            config.summarization.model = summ["model"]
            summarization_changed = True
        if "base_url" in summ:
            config.summarization.base_url = summ["base_url"]
            summarization_changed = True
        if "context_tokens" in summ:
            logger.info(
                f"Setting summarization.context_tokens to: {summ['context_tokens']} (type: {type(summ['context_tokens']).__name__})"
            )
            config.summarization.context_tokens = summ["context_tokens"]
            summarization_changed = True

    # Handle log_level updates (top-level key)
    log_level_changed = False
    if "log_level" in data:
        new_level = data["log_level"].upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if new_level in valid_levels and new_level != config.log_level:
            config.log_level = new_level
            log_level_changed = True

    # Handle log_rotation updates (requires restart)
    log_rotation_changed = False
    if "log_rotation" in data and isinstance(data["log_rotation"], dict):
        rot = data["log_rotation"]
        if "enabled" in rot and rot["enabled"] != config.log_rotation.enabled:
            config.log_rotation.enabled = rot["enabled"]
            log_rotation_changed = True
        if "max_size_mb" in rot and rot["max_size_mb"] != config.log_rotation.max_size_mb:
            config.log_rotation.max_size_mb = rot["max_size_mb"]
            log_rotation_changed = True
        if "backup_count" in rot and rot["backup_count"] != config.log_rotation.backup_count:
            config.log_rotation.backup_count = rot["backup_count"]
            log_rotation_changed = True

    # Handle session_quality updates (takes effect immediately)
    session_quality_changed = False
    if "session_quality" in data and isinstance(data["session_quality"], dict):
        sq = data["session_quality"]
        if "min_activities" in sq and sq["min_activities"] != config.session_quality.min_activities:
            config.session_quality.min_activities = sq["min_activities"]
            session_quality_changed = True
        if (
            "stale_timeout_seconds" in sq
            and sq["stale_timeout_seconds"] != config.session_quality.stale_timeout_seconds
        ):
            config.session_quality.stale_timeout_seconds = sq["stale_timeout_seconds"]
            session_quality_changed = True

    # Handle backup config updates (takes effect immediately via periodic loop)
    backup_changed = False
    if BACKUP_CONFIG_KEY in data and isinstance(data[BACKUP_CONFIG_KEY], dict):
        bkp = data[BACKUP_CONFIG_KEY]
        if "auto_enabled" in bkp and bkp["auto_enabled"] != config.backup.auto_enabled:
            config.backup.auto_enabled = bool(bkp["auto_enabled"])
            backup_changed = True
        if (
            "include_activities" in bkp
            and bkp["include_activities"] != config.backup.include_activities
        ):
            config.backup.include_activities = bool(bkp["include_activities"])
            backup_changed = True
        if "interval_minutes" in bkp and bkp["interval_minutes"] != config.backup.interval_minutes:
            config.backup.interval_minutes = int(bkp["interval_minutes"])
            backup_changed = True
        if "on_upgrade" in bkp and bkp["on_upgrade"] != config.backup.on_upgrade:
            config.backup.on_upgrade = bool(bkp["on_upgrade"])
            backup_changed = True
    # Update tunnel settings (nested object: { tunnel: { provider, auto_start, ... } })
    if CI_CONFIG_KEY_TUNNEL in data and isinstance(data[CI_CONFIG_KEY_TUNNEL], dict):
        tun = data[CI_CONFIG_KEY_TUNNEL]
        if CI_CONFIG_TUNNEL_KEY_PROVIDER in tun:
            config.tunnel.provider = tun[CI_CONFIG_TUNNEL_KEY_PROVIDER]
        if CI_CONFIG_TUNNEL_KEY_AUTO_START in tun:
            config.tunnel.auto_start = bool(tun[CI_CONFIG_TUNNEL_KEY_AUTO_START])
        if CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH in tun:
            config.tunnel.cloudflared_path = tun[CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH] or None
        if CI_CONFIG_TUNNEL_KEY_NGROK_PATH in tun:
            config.tunnel.ngrok_path = tun[CI_CONFIG_TUNNEL_KEY_NGROK_PATH] or None

    save_ci_config(state.project_root, config)
    # Keep in-memory config in sync so other routes (e.g. tunnel start) see updates
    state.ci_config = config
    logger.info(
        f"Config saved. summarization.context_tokens = {config.summarization.context_tokens}"
    )

    # Auto-apply embedding changes by triggering restart
    # This provides better UX - user doesn't need to manually click restart
    if embedding_changed:
        # Import restart handler and call it directly
        restart_result = await restart_daemon()
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
            "session_quality": {
                "min_activities": config.session_quality.min_activities,
                "stale_timeout_seconds": config.session_quality.stale_timeout_seconds,
            },
            "log_rotation": {
                "enabled": config.log_rotation.enabled,
                "max_size_mb": config.log_rotation.max_size_mb,
                "backup_count": config.log_rotation.backup_count,
            },
            CI_CONFIG_KEY_TUNNEL: {
                CI_CONFIG_TUNNEL_KEY_PROVIDER: config.tunnel.provider,
                CI_CONFIG_TUNNEL_KEY_AUTO_START: config.tunnel.auto_start,
                CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH: config.tunnel.cloudflared_path or "",
                CI_CONFIG_TUNNEL_KEY_NGROK_PATH: config.tunnel.ngrok_path or "",
            },
            BACKUP_CONFIG_KEY: config.backup.to_dict(),
            "log_level": config.log_level,
            "embedding_changed": embedding_changed,
            "summarization_changed": summarization_changed,
            "session_quality_changed": session_quality_changed,
            "log_level_changed": log_level_changed,
            "log_rotation_changed": log_rotation_changed,
            "backup_changed": backup_changed,
            "auto_applied": True,
            "indexing_started": restart_result.get("indexing_started", False),
            "message": restart_result.get("message", "Configuration saved and applied."),
        }

    message = "Configuration saved."
    if backup_changed:
        message += " Backup settings take effect on next cycle."
    if summarization_changed or session_quality_changed:
        message += " Changes take effect immediately."
    elif log_level_changed or log_rotation_changed:
        changes = []
        if log_level_changed:
            changes.append(f"log level to {config.log_level}")
        if log_rotation_changed:
            changes.append("log rotation settings")
        message = f"Changed {', '.join(changes)}. Restart daemon to apply."

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
        "session_quality": {
            "min_activities": config.session_quality.min_activities,
            "stale_timeout_seconds": config.session_quality.stale_timeout_seconds,
        },
        "log_rotation": {
            "enabled": config.log_rotation.enabled,
            "max_size_mb": config.log_rotation.max_size_mb,
            "backup_count": config.log_rotation.backup_count,
        },
        CI_CONFIG_KEY_TUNNEL: {
            CI_CONFIG_TUNNEL_KEY_PROVIDER: config.tunnel.provider,
            CI_CONFIG_TUNNEL_KEY_AUTO_START: config.tunnel.auto_start,
            CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH: config.tunnel.cloudflared_path or "",
            CI_CONFIG_TUNNEL_KEY_NGROK_PATH: config.tunnel.ngrok_path or "",
        },
        BACKUP_CONFIG_KEY: config.backup.to_dict(),
        "log_level": config.log_level,
        "embedding_changed": embedding_changed,
        "summarization_changed": summarization_changed,
        "session_quality_changed": session_quality_changed,
        "log_level_changed": log_level_changed,
        "log_rotation_changed": log_rotation_changed,
        "backup_changed": backup_changed,
        "auto_applied": False,
        "message": message,
    }


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
                # Heuristics for unknown models
                if "minilm" in name_lower or "384" in name or "small" in name_lower:
                    dimensions = 384
                elif "large" in name_lower or "1024" in name:
                    dimensions = 1024
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
                if "1.5b" in model_lower or "large" in model_lower:
                    dimensions = 1024
                elif "small" in model_lower or "mini" in model_lower:
                    dimensions = 384
                else:
                    dimensions = 768  # Default

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
            if "1.5b" in model_lower or "large" in model_lower:
                dimensions = 1024
            elif "small" in model_lower or "mini" in model_lower:
                dimensions = 384
            elif "3-large" in model_lower:
                dimensions = 3072
            elif "3-small" in model_lower:
                dimensions = 1536
            else:
                dimensions = 768  # Default

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
        except Exception as e:
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
        except Exception as e:
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
            except Exception as e:
                logger.debug(f"Failed to get context from Ollama /api/show: {e}")

    # Default fallback - return None to indicate manual entry needed
    logger.debug(f"Could not discover context for {model}")
    return None


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
        test_config = EmbeddingConfig(
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

        # Try to discover context window for the embedding model
        context_window = await _discover_embedding_context(provider_type, model_name, base_url)

        return {
            "success": True,
            "provider": provider.name,
            "dimensions": actual_dims,
            "context_window": context_window,
            "model": test_config.model,
            "message": f"Successfully generated embedding with {actual_dims} dimensions.",
        }

    except (ValueError, RuntimeError, OSError, TimeoutError, EmbeddingError) as e:
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

        # Handle LM Studio "no models loaded" error - this is expected for on-demand loading
        if "no models loaded" in error_str.lower():
            return {
                "success": True,  # Config is valid, model just needs to load on first use
                "provider": provider.name,
                "dimensions": None,  # Unknown until model loads
                "context_window": None,  # Unknown until model loads
                "model": test_config.model,
                "message": "Configuration valid. Model will load on first use (on-demand loading).",
                "pending_load": True,  # Flag indicating model needs to load
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
    old_dims = (old_config.embedding.get_dimensions() or 768) if old_config else 768

    # Track old chunk parameters to detect changes that require re-indexing
    old_context_tokens = old_config.embedding.get_context_tokens() if old_config else None
    old_max_chunk = old_config.embedding.get_max_chunk_chars() if old_config else None
    old_exclude_patterns = set(old_config.exclude_patterns) if old_config else set()

    logger.info(f"Reloading configuration (current model: {old_model_name}, dims: {old_dims})...")

    ci_config = load_ci_config(state.project_root)
    new_model_name = ci_config.embedding.model
    new_dims = ci_config.embedding.get_dimensions() or 768
    new_context_tokens = ci_config.embedding.get_context_tokens()
    new_max_chunk = ci_config.embedding.get_max_chunk_chars()

    logger.info(f"New config loaded: model={new_model_name}, dims={new_dims}")

    state.ci_config = ci_config

    # Embedding config changed if model name OR dimensions changed
    # Either change invalidates all existing embeddings
    model_changed = old_model_name != new_model_name
    dims_changed = old_dims != new_dims
    embedding_config_changed = model_changed or dims_changed

    if dims_changed and not model_changed:
        logger.info(f"Embedding dimensions changed: {old_dims} -> {new_dims}")
    new_exclude_patterns = set(ci_config.exclude_patterns)

    # Check if chunk parameters changed (requires re-indexing even if embedding is same)
    chunk_params_changed = (
        old_context_tokens != new_context_tokens or old_max_chunk != new_max_chunk
    )
    if chunk_params_changed and not embedding_config_changed:
        logger.info(
            f"Chunk parameters changed: context {old_context_tokens}->{new_context_tokens}, "
            f"max_chunk {old_max_chunk}->{new_max_chunk}"
        )

    # Check if exclusion patterns changed (requires re-indexing)
    exclusions_changed = old_exclude_patterns != new_exclude_patterns
    if exclusions_changed:
        added = new_exclude_patterns - old_exclude_patterns
        removed = old_exclude_patterns - new_exclude_patterns
        logger.info(f"Exclusion patterns changed: added={list(added)}, removed={list(removed)}")

    # Create the new provider FIRST - this must happen before any ChromaDB operations
    # so that dimension changes are properly detected and handled
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

    # Update vector store with new provider - this handles dimension changes
    # and reinitializes ChromaDB collections when embedding dimensions change
    if state.vector_store:
        state.vector_store.update_embedding_provider(state.embedding_chain)

    # Update indexer configuration
    if state.indexer:
        from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
            ChunkerConfig,
        )

        state.indexer.chunker = state.indexer.chunker.__class__(
            ChunkerConfig(max_chunk_chars=ci_config.embedding.get_max_chunk_chars())
        )
        combined_patterns = ci_config.get_combined_exclude_patterns()
        state.indexer.config.ignore_patterns = combined_patterns
        logger.info(
            f"Updated indexer with {len(combined_patterns)} config exclude patterns "
            f"(gitignore loaded at index time)"
        )

    # ========================================================================
    # Dispatch config change events
    # ========================================================================
    change_result = ConfigChangeResult()

    # Check if index is empty (first-time setup triggers indexing)
    index_empty = False
    if state.vector_store:
        stats = state.vector_store.get_stats()
        index_empty = stats.get("code_chunks", 0) == 0

    if embedding_config_changed:
        # Event: Embedding config changed (model or dimensions) - triggers full re-embedding
        change_result = await _on_embedding_model_changed(
            state, f"{old_model_name} ({old_dims}d)", f"{new_model_name} ({new_dims}d)"
        )
    elif chunk_params_changed or exclusions_changed:
        # Event: Index params changed - triggers code re-indexing only
        reason = []
        if chunk_params_changed:
            reason.append(f"chunk params (context: {new_context_tokens}, max: {new_max_chunk})")
        if exclusions_changed:
            reason.append("exclusion patterns")
        change_result = await _on_index_params_changed(state, ", ".join(reason))
    elif index_empty and state.indexer and state.vector_store:
        # First-time setup - trigger initial indexing
        from open_agent_kit.features.codebase_intelligence.daemon.server import (
            _background_index,
        )

        asyncio.create_task(_background_index())
        change_result.indexing_scheduled = True
        logger.info("Starting initial indexing after config save")

    # Ensure file watcher is running regardless of other changes
    from open_agent_kit.features.codebase_intelligence.daemon.server import (
        _start_file_watcher,
    )

    asyncio.create_task(_start_file_watcher())

    # Convenience aliases for message generation
    index_cleared = change_result.index_cleared
    indexing_started = change_result.indexing_scheduled

    # Determine message based on what happened
    if indexing_started and index_empty:
        message = "Configuration saved! Indexing your codebase for the first time..."
    elif indexing_started and exclusions_changed:
        message = "Exclusion patterns changed. Re-indexing your codebase with updated exclusions..."
    elif indexing_started and embedding_config_changed:
        if dims_changed and not model_changed:
            message = (
                f"Embedding dimensions changed ({old_dims} -> {new_dims}). "
                "Re-indexing your codebase with new dimensions..."
            )
        else:
            message = (
                f"Model changed from {old_model_name} to {new_model_name}. "
                "Re-indexing your codebase with the new model..."
            )
    elif indexing_started and chunk_params_changed:
        message = (
            f"Chunk settings changed (context: {new_context_tokens}, max_chunk: {new_max_chunk}). "
            "Re-indexing your codebase with new chunk sizes..."
        )
    elif embedding_config_changed and index_cleared:
        if dims_changed and not model_changed:
            message = (
                f"Embedding dimensions changed ({old_dims} -> {new_dims}). "
                "Index cleared - click 'Rebuild Index' to re-embed your code."
            )
        else:
            message = (
                f"Model changed from {old_model_name} to {new_model_name}. "
                "Index cleared - click 'Rebuild Index' to re-embed your code."
            )
    elif embedding_config_changed:
        message = (
            f"Embedding config changed to {new_model_name} ({new_dims}d). "
            "Please rebuild the index to re-embed your code."
        )
    elif exclusions_changed:
        message = "Exclusion patterns updated. Restart to apply changes."
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
        "dims_changed": dims_changed,
        "embedding_config_changed": embedding_config_changed,
        "chunk_params_changed": chunk_params_changed,
        "exclusions_changed": exclusions_changed,
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
            except Exception:
                pass  # Fallback to default/heuristics if 'show' fails

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
            # Get context window - try summarizer's cached value first, then discover
            context_window = summarizer._context_window
            if not context_window:
                # Fallback to explicit discovery (works better with Ollama native API)
                from open_agent_kit.features.codebase_intelligence.summarization import (
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


# =============================================================================
# Backup Configuration Convenience Endpoint
# =============================================================================


@router.get("/api/backup/config")
async def get_backup_config() -> dict:
    """Get backup configuration and last auto-backup timestamp.

    Convenience endpoint combining backup config with runtime state.
    """
    from datetime import datetime

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    from open_agent_kit.features.codebase_intelligence.daemon.routes.backup import (
        get_last_backup_epoch,
    )

    last_backup_epoch = get_last_backup_epoch(state)
    last_auto_backup_iso: str | None = None
    if last_backup_epoch is not None:
        last_auto_backup_iso = datetime.fromtimestamp(last_backup_epoch).isoformat()

    return {
        "auto_enabled": config.backup.auto_enabled,
        "include_activities": config.backup.include_activities,
        "interval_minutes": config.backup.interval_minutes,
        "on_upgrade": config.backup.on_upgrade,
        "last_auto_backup": last_auto_backup_iso,
    }


# =============================================================================
# Exclusions Management Endpoints
# =============================================================================


@router.get("/api/config/exclusions")
async def get_exclusions() -> dict:
    """Get current exclusion patterns.

    Returns both user-configured patterns and built-in defaults.
    """
    from open_agent_kit.features.codebase_intelligence.config import DEFAULT_EXCLUDE_PATTERNS

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    return {
        "user_patterns": config.get_user_exclude_patterns(),
        "default_patterns": list(DEFAULT_EXCLUDE_PATTERNS),
        "all_patterns": config.get_combined_exclude_patterns(),
    }


@router.put("/api/config/exclusions")
async def update_exclusions(request: Request) -> dict:
    """Update exclusion patterns.

    Accepts JSON with:
    - add: list of patterns to add
    - remove: list of patterns to remove
    """
    from open_agent_kit.features.codebase_intelligence.config import (
        DEFAULT_EXCLUDE_PATTERNS,
        save_ci_config,
    )

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    try:
        data = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    added = []
    removed = []
    already_exists = []
    not_found = []

    # Add patterns
    patterns_to_add = data.get("add", [])
    for pattern in patterns_to_add:
        if pattern not in config.exclude_patterns:
            config.exclude_patterns.append(pattern)
            added.append(pattern)
        else:
            already_exists.append(pattern)

    # Remove patterns
    patterns_to_remove = data.get("remove", [])
    for pattern in patterns_to_remove:
        if pattern in config.exclude_patterns:
            # Don't allow removing default patterns
            if pattern in DEFAULT_EXCLUDE_PATTERNS:
                not_found.append(f"{pattern} (built-in, cannot remove)")
            else:
                config.exclude_patterns.remove(pattern)
                removed.append(pattern)
        else:
            not_found.append(pattern)

    save_ci_config(state.project_root, config)
    state.ci_config = config

    return {
        "status": "updated",
        "added": added,
        "removed": removed,
        "already_exists": already_exists,
        "not_found": not_found,
        "user_patterns": config.get_user_exclude_patterns(),
        "message": (
            "Exclusions updated. Restart daemon and rebuild index to apply changes."
            if added or removed
            else "No changes made."
        ),
    }


@router.post("/api/config/exclusions/reset")
async def reset_exclusions() -> dict:
    """Reset exclusion patterns to defaults."""
    from open_agent_kit.features.codebase_intelligence.config import (
        DEFAULT_EXCLUDE_PATTERNS,
        save_ci_config,
    )

    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")

    config = state.ci_config
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")
    config.exclude_patterns = DEFAULT_EXCLUDE_PATTERNS.copy()
    save_ci_config(state.project_root, config)
    state.ci_config = config

    return {
        "status": "reset",
        "default_patterns": DEFAULT_EXCLUDE_PATTERNS,
        "message": "Exclusion patterns reset to defaults. Restart daemon and rebuild index to apply.",
    }
