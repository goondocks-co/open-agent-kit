"""Release channel info route.

GET /api/channel — Returns current channel (from ~/.oak/update.yaml),
                   running version, and available PyPI versions (cached 5 min).

Channel switching is handled by PUT /api/update/channel (see routes/update.py).
The binary-swap ``POST /api/channel/switch`` endpoint has been removed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from open_agent_kit.features.team.constants.release_channel import (
    CI_CHANNEL_API_PATH,
)
from open_agent_kit.utils.release_channel import (
    build_channel_info,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["channel"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(CI_CHANNEL_API_PATH)
async def get_channel() -> dict:
    """Return current channel, version, and PyPI availability."""
    return await build_channel_info()
