"""Abstract base class for team gateway operations.

The gateway abstracts the difference between server mode (direct DB
queries) and client mode (HTTP proxy to remote server) for dashboard
routes that need to behave differently depending on the daemon's role.
"""

from abc import ABC, abstractmethod
from typing import Any


class TeamGateway(ABC):
    """Abstract gateway for team dashboard operations.

    Implementations handle the details of how team data is fetched:
    locally from the database (server mode) or via HTTP proxy (client mode).
    """

    @abstractmethod
    async def get_members(self) -> dict[str, Any]:
        """Get team member list.

        Returns:
            Dict with ``members`` key containing a list of member dicts.
        """
        ...

    @abstractmethod
    async def get_join_status(self, key_id: str) -> dict[str, Any]:
        """Get join request status for a key.

        Args:
            key_id: The key ID to check.

        Returns:
            Dict with ``status`` and ``pending_approval`` keys.
        """
        ...

    @abstractmethod
    async def get_pending_joins(self) -> list[dict[str, Any]]:
        """List pending join requests.

        Returns:
            List of pending join request dicts.
        """
        ...

    @abstractmethod
    async def approve_join(self, key_id: str) -> dict[str, bool]:
        """Approve a pending join request.

        Args:
            key_id: The key ID to approve.

        Returns:
            Dict with ``approved`` key.
        """
        ...

    @abstractmethod
    async def reject_join(self, key_id: str) -> dict[str, bool]:
        """Reject a pending join request.

        Args:
            key_id: The key ID to reject.

        Returns:
            Dict with ``rejected`` key.
        """
        ...

    @abstractmethod
    def is_server(self) -> bool:
        """Whether this gateway is in server mode.

        Returns:
            True if the gateway operates on local DB (server mode).
        """
        ...
