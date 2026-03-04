"""Core configuration CRUD and restart routes for the CI daemon.

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

from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.team.constants import (
    AUTO_RESOLVE_CONFIG_KEY,
    BACKUP_CONFIG_KEY,
    CI_CONFIG_KEY_EMBEDDING,
    CI_CONFIG_KEY_LOG_LEVEL,
    CI_CONFIG_KEY_LOG_ROTATION,
    CI_CONFIG_KEY_SESSION_QUALITY,
    CI_CONFIG_KEY_SUMMARIZATION,
)
from open_agent_kit.features.team.daemon.state import get_state
from open_agent_kit.features.team.embeddings import EmbeddingProviderChain

if TYPE_CHECKING:
    from open_agent_kit.features.team.daemon.state import DaemonState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


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
        from open_agent_kit.features.team.daemon.background import (
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
            from open_agent_kit.features.team.activity.processor.indexing import (
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
        from open_agent_kit.features.team.daemon.background import (
            _background_index,
        )

        asyncio.create_task(_background_index())
        result.indexing_scheduled = True
        logger.info("Scheduled code re-indexing after parameter change")

    return result


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
    from open_agent_kit.features.team.config import get_config_origins

    origins = get_config_origins(state.project_root)

    return {
        CI_CONFIG_KEY_EMBEDDING: {
            "provider": config.embedding.provider,
            "model": config.embedding.model,
            "base_url": config.embedding.base_url,
            "dimensions": config.embedding.get_dimensions(),
            "context_tokens": config.embedding.get_context_tokens(),
            "max_chunk_chars": config.embedding.get_max_chunk_chars(),
        },
        CI_CONFIG_KEY_SUMMARIZATION: {
            "enabled": config.summarization.enabled,
            "provider": config.summarization.provider,
            "model": config.summarization.model,
            "base_url": config.summarization.base_url,
            "timeout": config.summarization.timeout,
            "context_tokens": config.summarization.context_tokens,
        },
        CI_CONFIG_KEY_SESSION_QUALITY: {
            "min_activities": config.session_quality.min_activities,
            "stale_timeout_seconds": config.session_quality.stale_timeout_seconds,
        },
        CI_CONFIG_KEY_LOG_ROTATION: {
            "enabled": config.log_rotation.enabled,
            "max_size_mb": config.log_rotation.max_size_mb,
            "backup_count": config.log_rotation.backup_count,
        },
        BACKUP_CONFIG_KEY: {
            "auto_enabled": config.backup.auto_enabled,
            "include_activities": config.backup.include_activities,
            "on_upgrade": config.backup.on_upgrade,
        },
        AUTO_RESOLVE_CONFIG_KEY: {
            "enabled": config.auto_resolve.enabled,
            "similarity_threshold": config.auto_resolve.similarity_threshold,
            "similarity_threshold_no_context": config.auto_resolve.similarity_threshold_no_context,
            "search_limit": config.auto_resolve.search_limit,
        },
        CI_CONFIG_KEY_LOG_LEVEL: config.log_level,
        "origins": origins,
    }


@router.put("/api/config")
async def update_config(request: Request) -> dict:
    """Update configuration.

    Accepts JSON with optional fields for embedding and summarization settings.
    """
    from open_agent_kit.features.team.config import save_ci_config

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
    if CI_CONFIG_KEY_EMBEDDING in data and isinstance(data[CI_CONFIG_KEY_EMBEDDING], dict):
        emb = data[CI_CONFIG_KEY_EMBEDDING]
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
        if "context_tokens" in emb:
            config.embedding.context_tokens = emb["context_tokens"]
            embedding_changed = True
        if "max_chunk_chars" in emb:
            config.embedding.max_chunk_chars = emb["max_chunk_chars"]
            embedding_changed = True

    # Update summarization settings (nested object: { summarization: { enabled, provider, ... } })
    if CI_CONFIG_KEY_SUMMARIZATION in data and isinstance(data[CI_CONFIG_KEY_SUMMARIZATION], dict):
        summ = data[CI_CONFIG_KEY_SUMMARIZATION]
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
    if CI_CONFIG_KEY_LOG_LEVEL in data:
        new_level = data[CI_CONFIG_KEY_LOG_LEVEL].upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if new_level in valid_levels and new_level != config.log_level:
            config.log_level = new_level
            log_level_changed = True

    # Handle log_rotation updates (requires restart)
    log_rotation_changed = False
    if CI_CONFIG_KEY_LOG_ROTATION in data and isinstance(data[CI_CONFIG_KEY_LOG_ROTATION], dict):
        rot = data[CI_CONFIG_KEY_LOG_ROTATION]
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
    if CI_CONFIG_KEY_SESSION_QUALITY in data and isinstance(
        data[CI_CONFIG_KEY_SESSION_QUALITY], dict
    ):
        sq = data[CI_CONFIG_KEY_SESSION_QUALITY]
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
        if "on_upgrade" in bkp and bkp["on_upgrade"] != config.backup.on_upgrade:
            config.backup.on_upgrade = bool(bkp["on_upgrade"])
            backup_changed = True
    # Handle auto_resolve config updates (takes effect immediately)
    auto_resolve_changed = False
    if AUTO_RESOLVE_CONFIG_KEY in data and isinstance(data[AUTO_RESOLVE_CONFIG_KEY], dict):
        ar = data[AUTO_RESOLVE_CONFIG_KEY]
        if "enabled" in ar and ar["enabled"] != config.auto_resolve.enabled:
            config.auto_resolve.enabled = bool(ar["enabled"])
            auto_resolve_changed = True
        if (
            "similarity_threshold" in ar
            and ar["similarity_threshold"] != config.auto_resolve.similarity_threshold
        ):
            config.auto_resolve.similarity_threshold = float(ar["similarity_threshold"])
            auto_resolve_changed = True
        if (
            "similarity_threshold_no_context" in ar
            and ar["similarity_threshold_no_context"]
            != config.auto_resolve.similarity_threshold_no_context
        ):
            config.auto_resolve.similarity_threshold_no_context = float(
                ar["similarity_threshold_no_context"]
            )
            auto_resolve_changed = True
        if "search_limit" in ar and ar["search_limit"] != config.auto_resolve.search_limit:
            config.auto_resolve.search_limit = int(ar["search_limit"])
            auto_resolve_changed = True

    save_ci_config(state.project_root, config)
    # Keep in-memory config in sync so other routes see updates
    state.ci_config = config
    logger.info(
        f"Config saved. summarization.context_tokens = {config.summarization.context_tokens}"
    )

    def _build_update_response(
        *,
        auto_applied: bool,
        message: str,
        indexing_started: bool = False,
    ) -> dict:
        return {
            "status": "updated",
            CI_CONFIG_KEY_EMBEDDING: {
                "provider": config.embedding.provider,
                "model": config.embedding.model,
                "base_url": config.embedding.base_url,
                "max_chunk_chars": config.embedding.get_max_chunk_chars(),
            },
            CI_CONFIG_KEY_SUMMARIZATION: {
                "enabled": config.summarization.enabled,
                "provider": config.summarization.provider,
                "model": config.summarization.model,
                "base_url": config.summarization.base_url,
                "context_tokens": config.summarization.context_tokens,
            },
            CI_CONFIG_KEY_SESSION_QUALITY: {
                "min_activities": config.session_quality.min_activities,
                "stale_timeout_seconds": config.session_quality.stale_timeout_seconds,
            },
            CI_CONFIG_KEY_LOG_ROTATION: {
                "enabled": config.log_rotation.enabled,
                "max_size_mb": config.log_rotation.max_size_mb,
                "backup_count": config.log_rotation.backup_count,
            },
            BACKUP_CONFIG_KEY: config.backup.to_dict(),
            AUTO_RESOLVE_CONFIG_KEY: config.auto_resolve.to_dict(),
            CI_CONFIG_KEY_LOG_LEVEL: config.log_level,
            "embedding_changed": embedding_changed,
            "summarization_changed": summarization_changed,
            "session_quality_changed": session_quality_changed,
            "log_level_changed": log_level_changed,
            "log_rotation_changed": log_rotation_changed,
            "backup_changed": backup_changed,
            "auto_resolve_changed": auto_resolve_changed,
            "auto_applied": auto_applied,
            "indexing_started": indexing_started,
            "message": message,
        }

    # Auto-apply embedding changes by triggering restart
    # This provides better UX - user doesn't need to manually click restart
    if embedding_changed:
        restart_result = await restart_daemon()
        return _build_update_response(
            auto_applied=True,
            indexing_started=restart_result.get("indexing_started", False),
            message=restart_result.get("message", "Configuration saved and applied."),
        )

    message = "Configuration saved."
    if backup_changed:
        message += " Backup settings take effect on next cycle."
    if auto_resolve_changed:
        message += " Auto-resolve settings take effect immediately."
    if summarization_changed or session_quality_changed:
        message += " Changes take effect immediately."
    elif log_level_changed or log_rotation_changed:
        changes = []
        if log_level_changed:
            changes.append(f"log level to {config.log_level}")
        if log_rotation_changed:
            changes.append("log rotation settings")
        message = f"Changed {', '.join(changes)}. Restart daemon to apply."

    return _build_update_response(auto_applied=False, message=message)


@router.post("/api/restart")
async def restart_daemon() -> dict:
    """Reload configuration and reinitialize embedding chain."""
    from open_agent_kit.features.team.config import (
        load_ci_config,
    )
    from open_agent_kit.features.team.embeddings.provider_chain import (
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
        from open_agent_kit.features.team.indexing.chunker import (
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
        from open_agent_kit.features.team.daemon.background import (
            _background_index,
        )

        asyncio.create_task(_background_index())
        change_result.indexing_scheduled = True
        logger.info("Starting initial indexing after config save")

    # Ensure file watcher is running regardless of other changes
    from open_agent_kit.features.team.daemon.background import (
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
        CI_CONFIG_KEY_EMBEDDING: {
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
