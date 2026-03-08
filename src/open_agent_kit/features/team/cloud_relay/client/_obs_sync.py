"""Observation sync mixin for CloudRelayClient.

Handles pushing observations to peer nodes, draining buffered observations
on reconnect, and applying incoming observation batches from peers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

    from open_agent_kit.features.team.cloud_relay.base import PolicyAccessor
    from open_agent_kit.features.team.relay.sync.obs_applier import (
        ObsApplierProtocol,
    )

from open_agent_kit.features.team.cloud_relay.protocol import (
    ObsPushMessage,
)
from open_agent_kit.features.team.constants import (
    CLOUD_RELAY_OBS_DRAIN_TIMEOUT_SECONDS,
    CLOUD_RELAY_OBS_HISTORY_PATH,
)

logger = logging.getLogger(__name__)


class ObsSyncMixin:
    """Mixin providing observation synchronisation methods."""

    # Attributes set by CloudRelayClient.__init__ — declared here for clarity.
    _ws: Any
    _connected: bool
    _worker_url: str | None
    _token: str | None
    _machine_id: str
    _online_nodes: list[dict]
    _obs_applier: ObsApplierProtocol | None
    _policy_accessor: PolicyAccessor | None
    _http_client: httpx.AsyncClient | None
    _lock: Any

    # Methods provided by core (declared for mypy)
    _relay_auth_headers: Any

    def set_obs_applier(self, applier: ObsApplierProtocol) -> None:
        """Set the applier for incoming obs batches from peer nodes."""
        self._obs_applier = applier

    def set_policy_accessor(self, accessor: PolicyAccessor) -> None:
        """Set a callable that returns the current DataCollectionPolicy."""
        self._policy_accessor = accessor

    async def request_reconnect(self) -> None:
        """Close the WebSocket to trigger a reconnect with updated capabilities."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception as exc:
                logger.debug("Error closing WS for reconnect: %s", exc)

    @property
    def online_nodes(self) -> list[dict]:
        """List of online nodes from relay presence updates."""
        with self._lock:
            return list(self._online_nodes)

    async def push_observations(self, observations: list[dict]) -> None:
        """Push observations to peer nodes via relay WebSocket.

        Raises on failure so the outbox worker can mark events for retry
        instead of incorrectly marking them as sent.
        """
        if not self._ws or not self._connected:
            logger.debug("Relay not connected, skipping obs push (will retry on next tick)")
            return
        msg = ObsPushMessage(observations=observations)
        await self._ws.send(msg.model_dump_json())

    async def _drain_pending_obs(self) -> None:
        """Drain buffered observations from the relay (called on reconnect)."""
        if not self._worker_url or not self._token or not self._machine_id:
            return
        if not self._http_client or self._http_client.is_closed:
            return
        try:
            url = f"{self._worker_url.rstrip('/')}/obs/pending?machine_id={self._machine_id}"
            resp = await self._http_client.get(
                url,
                headers=self._relay_auth_headers(),
                timeout=CLOUD_RELAY_OBS_DRAIN_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                data = resp.json()
                observations = data.get("observations", [])
                if observations and self._obs_applier is not None:
                    # Group by source machine to batch DB transactions
                    by_machine: dict[str, list] = {}
                    for item in observations:
                        mid = item["from_machine_id"]
                        by_machine.setdefault(mid, []).append(item["obs"])
                    for mid, obs_list in by_machine.items():
                        self._obs_applier.apply_batch(obs_list, mid)
        except Exception as exc:
            logger.warning("Failed to drain pending obs: %s", exc)

    async def _drain_obs_history(self) -> None:
        """Drain observation history from the relay (called on reconnect).

        Fetches historical observations that were recorded while this node
        was offline. Paginates with ``offset`` until an empty page is returned.
        Deduplication is handled by content_hash checks in RemoteObsApplier.
        """
        if not self._worker_url or not self._token or not self._machine_id:
            return
        if self._obs_applier is None:
            return
        if not self._http_client or self._http_client.is_closed:
            return

        try:
            base_url = (
                f"{self._worker_url.rstrip('/')}"
                f"{CLOUD_RELAY_OBS_HISTORY_PATH}?machine_id={self._machine_id}"
            )
            headers = self._relay_auth_headers()
            offset = 0

            while True:
                url = f"{base_url}&offset={offset}"
                resp = await self._http_client.get(
                    url,
                    headers=headers,
                    timeout=CLOUD_RELAY_OBS_DRAIN_TIMEOUT_SECONDS,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                observations = data.get("observations", [])
                if not observations:
                    break
                # Group by source machine to batch DB transactions
                by_machine: dict[str, list] = {}
                for item in observations:
                    mid = item["from_machine_id"]
                    by_machine.setdefault(mid, []).append(item["obs"])
                for mid, obs_list in by_machine.items():
                    self._obs_applier.apply_batch(obs_list, mid)
                offset += len(observations)
        except Exception as exc:
            logger.warning("Failed to drain obs history: %s", exc)

    def _handle_obs_batch(self, data: dict) -> None:
        """Handle incoming obs_batch from a peer node."""
        if self._obs_applier is None:
            obs_count = len(data.get("observations", []))
            logger.warning(
                "Dropping %d obs from %s: no obs applier configured",
                obs_count,
                data.get("from_machine_id", "unknown"),
            )
            return
        from_machine_id = data.get("from_machine_id", "unknown")
        observations = data.get("observations", [])
        try:
            self._obs_applier.apply_batch(observations, from_machine_id)
        except Exception as exc:
            logger.error("Failed to apply remote obs batch: %s", exc)
