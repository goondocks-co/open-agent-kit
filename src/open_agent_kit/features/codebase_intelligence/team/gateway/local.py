"""Local team gateway — server mode: direct DB queries."""

import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from open_agent_kit.features.codebase_intelligence.team.gateway.base import TeamGateway

logger = logging.getLogger(__name__)


class LocalTeamGateway(TeamGateway):
    """Gateway that queries the local database directly.

    Used in server mode where the daemon IS the team server.
    """

    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]) -> None:
        self._conn_factory = conn_factory

    async def get_members(self) -> dict[str, Any]:
        from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
        from open_agent_kit.features.codebase_intelligence.team.server.membership import (
            MembershipService,
        )

        conn = self._conn_factory()
        svc = MembershipService(conn_factory=lambda: conn)
        members = svc.list_members()
        server_machine_id = get_state().machine_id
        result = []
        for m in members:
            d = m.model_dump()
            d["is_server"] = server_machine_id is not None and m.machine_id == server_machine_id
            result.append(d)
        return {"members": result}

    async def get_join_status(self, key_id: str) -> dict[str, Any]:
        from open_agent_kit.features.codebase_intelligence.team.server.auth import (
            get_key_join_status,
        )

        conn = self._conn_factory()
        db_status = get_key_join_status(conn, key_id)
        if db_status is None:
            return {"status": "not_found", "pending_approval": False}
        return {"status": db_status, "pending_approval": db_status == "pending"}

    async def get_pending_joins(self) -> list[dict[str, Any]]:
        from open_agent_kit.features.codebase_intelligence.team.server.auth import (
            list_pending_keys,
        )

        conn = self._conn_factory()
        keys = list_pending_keys(conn)
        return [
            {
                "key_id": k.id,
                "name": k.name,
                "machine_id": k.machine_id or "",
                "display_name": k.display_name or "",
                "created_at": k.created_at,
            }
            for k in keys
        ]

    async def approve_join(self, key_id: str) -> dict[str, bool]:
        from open_agent_kit.features.codebase_intelligence.team.server.auth import (
            approve_join_request,
        )

        conn = self._conn_factory()
        success, key_info = approve_join_request(conn, key_id)
        if key_info is None:
            raise HTTPException(status_code=404, detail="Pending key not found")
        if not success:
            raise HTTPException(status_code=404, detail="Pending key not found")
        return {"approved": True}

    async def reject_join(self, key_id: str) -> dict[str, bool]:
        from open_agent_kit.features.codebase_intelligence.team.server.auth import (
            reject_key,
        )

        conn = self._conn_factory()
        success = reject_key(conn, key_id)
        if not success:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"rejected": True}

    def is_server(self) -> bool:
        return True
