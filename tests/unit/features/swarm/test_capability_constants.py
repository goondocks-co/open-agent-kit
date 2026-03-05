"""Tests for swarm capability constants.

Verifies that Python-side capability constant values are correct and
follow naming conventions (must align with the TypeScript side).
"""

from open_agent_kit.features.swarm.constants import (
    SWARM_CAPABILITY_SEARCH,
    SWARM_CAPABILITY_TOOLS,
)

# Conditionally collect SWARM_CAPABILITY_BROADCAST if Unit 1 has been merged.
try:
    from open_agent_kit.features.swarm.constants import (
        SWARM_CAPABILITY_BROADCAST,  # type: ignore[attr-defined]
    )

    _HAS_BROADCAST = True
except ImportError:
    _HAS_BROADCAST = False

# Gather all available capability constants for parametric checks.
_ALL_CAPABILITIES: list[str] = [SWARM_CAPABILITY_SEARCH, SWARM_CAPABILITY_TOOLS]
if _HAS_BROADCAST:
    _ALL_CAPABILITIES.append(SWARM_CAPABILITY_BROADCAST)  # type: ignore[possibly-undefined]


class TestCapabilityConstants:
    """Verify capability constant values match the TypeScript side."""

    def test_search_capability_value(self) -> None:
        assert SWARM_CAPABILITY_SEARCH == "swarm_search_v1"

    def test_tools_capability_value(self) -> None:
        assert SWARM_CAPABILITY_TOOLS == "swarm_tools_v1"

    def test_capability_constants_are_strings(self) -> None:
        for cap in _ALL_CAPABILITIES:
            assert isinstance(cap, str)

    def test_capability_constants_have_version_suffix(self) -> None:
        """All capabilities should end with a version suffix like _v1."""
        for cap in _ALL_CAPABILITIES:
            assert cap.endswith("_v1"), f"{cap} should have version suffix"

    def test_all_capabilities_start_with_swarm(self) -> None:
        for cap in _ALL_CAPABILITIES:
            assert cap.startswith("swarm_"), f"{cap} should start with swarm_"

    def test_capabilities_are_unique(self) -> None:
        assert len(_ALL_CAPABILITIES) == len(
            set(_ALL_CAPABILITIES)
        ), "Capability constants must be unique"


class TestBroadcastCapability:
    """Tests for SWARM_CAPABILITY_BROADCAST (only if Unit 1 merged)."""

    def test_broadcast_capability_value(self) -> None:
        if not _HAS_BROADCAST:
            return  # Unit 1 not merged yet — nothing to test
        assert SWARM_CAPABILITY_BROADCAST == "swarm_broadcast_v1"  # type: ignore[possibly-undefined]
