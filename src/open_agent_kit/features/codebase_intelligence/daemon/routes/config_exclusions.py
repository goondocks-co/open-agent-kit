"""Exclusion pattern management routes for the CI daemon.

Provides endpoints to view, update, and reset file exclusion patterns
that control which files are indexed by the codebase intelligence engine.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])


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
