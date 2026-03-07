"""Tests for swarm capability constants.

Verifies that Python-side capability constant values are correct and
follow naming conventions (must align with the TypeScript side).
"""

from open_agent_kit.features.swarm.constants import (
    SWARM_CAPABILITY_MANAGEMENT,
    SWARM_CAPABILITY_SEARCH,
)

_ALL_CAPABILITIES: list[str] = [
    SWARM_CAPABILITY_SEARCH,
    SWARM_CAPABILITY_MANAGEMENT,
]


class TestCapabilityConstants:
    """Verify capability constant values match the TypeScript side."""

    def test_search_capability_value(self) -> None:
        assert SWARM_CAPABILITY_SEARCH == "swarm_search_v1"

    def test_management_capability_value(self) -> None:
        assert SWARM_CAPABILITY_MANAGEMENT == "swarm_management_v1"

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


class TestAdvisoryConstants:
    """Tests for advisory-related constants."""

    def test_advisory_severity_constants(self) -> None:
        from open_agent_kit.features.swarm.constants import (
            SWARM_ADVISORY_SEVERITY_CRITICAL,
            SWARM_ADVISORY_SEVERITY_INFO,
            SWARM_ADVISORY_SEVERITY_WARNING,
        )

        assert SWARM_ADVISORY_SEVERITY_INFO == "info"
        assert SWARM_ADVISORY_SEVERITY_WARNING == "warning"
        assert SWARM_ADVISORY_SEVERITY_CRITICAL == "critical"

    def test_advisory_type_constants(self) -> None:
        from open_agent_kit.features.swarm.constants import (
            SWARM_ADVISORY_TYPE_CAPABILITY_GAP,
            SWARM_ADVISORY_TYPE_GENERAL,
            SWARM_ADVISORY_TYPE_VERSION_DRIFT,
        )

        assert SWARM_ADVISORY_TYPE_VERSION_DRIFT == "version_drift"
        assert SWARM_ADVISORY_TYPE_CAPABILITY_GAP == "capability_gap"
        assert SWARM_ADVISORY_TYPE_GENERAL == "general"

    def test_config_key_constant(self) -> None:
        from open_agent_kit.features.swarm.constants import SWARM_CONFIG_KEY_MIN_OAK_VERSION

        assert SWARM_CONFIG_KEY_MIN_OAK_VERSION == "min_oak_version"

    def test_health_check_tool_constant(self) -> None:
        from open_agent_kit.features.swarm.constants import SWARM_TOOL_HEALTH_CHECK

        assert SWARM_TOOL_HEALTH_CHECK == "swarm_health_check"

    def test_health_check_api_paths(self) -> None:
        from open_agent_kit.features.swarm.constants import (
            SWARM_API_PATH_HEALTH_CHECK,
            SWARM_DAEMON_API_PATH_HEALTH_CHECK,
        )

        assert SWARM_API_PATH_HEALTH_CHECK == "/api/swarm/health-check"
        assert SWARM_DAEMON_API_PATH_HEALTH_CHECK == "/api/swarm/health-check"

    def test_config_min_oak_version_api_path(self) -> None:
        from open_agent_kit.features.swarm.constants import SWARM_API_PATH_CONFIG_MIN_OAK_VERSION

        assert SWARM_API_PATH_CONFIG_MIN_OAK_VERSION == "/api/swarm/config/min-oak-version"
