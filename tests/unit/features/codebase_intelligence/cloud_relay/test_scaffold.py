"""Tests for cloud relay scaffold (template rendering).

Tests cover:
- render_worker_template() with/without custom_domain
- render_wrangler_config() re-rendering wrangler.toml in place
"""

from pathlib import Path

from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
    render_worker_template,
    render_wrangler_config,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML,
)

from .fixtures import TEST_AGENT_TOKEN, TEST_RELAY_TOKEN

TEST_WORKER_NAME = "oak-relay-testproject"
TEST_CUSTOM_DOMAIN = "goondocks.co"


class TestRenderWorkerTemplate:
    """Tests for render_worker_template()."""

    def test_without_custom_domain(self, tmp_path: Path) -> None:
        """Rendered wrangler.toml has no [[routes]] when custom_domain is None."""
        output = render_worker_template(
            tmp_path / "relay",
            relay_token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
            worker_name=TEST_WORKER_NAME,
        )

        wrangler = (output / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML).read_text()
        assert "[[routes]]" not in wrangler
        assert "custom_domain" not in wrangler
        assert f'name = "{TEST_WORKER_NAME}"' in wrangler
        assert f'RELAY_TOKEN = "{TEST_RELAY_TOKEN}"' in wrangler
        assert f'AGENT_TOKEN = "{TEST_AGENT_TOKEN}"' in wrangler

    def test_with_custom_domain(self, tmp_path: Path) -> None:
        """Rendered wrangler.toml includes [[routes]] when custom_domain is set."""
        output = render_worker_template(
            tmp_path / "relay",
            relay_token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
            worker_name=TEST_WORKER_NAME,
            custom_domain=TEST_CUSTOM_DOMAIN,
        )

        wrangler = (output / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML).read_text()
        assert "[[routes]]" in wrangler
        assert f'pattern = "{TEST_WORKER_NAME}.{TEST_CUSTOM_DOMAIN}"' in wrangler
        assert "custom_domain = true" in wrangler

    def test_custom_domain_none_explicit(self, tmp_path: Path) -> None:
        """Explicitly passing custom_domain=None produces no routes section."""
        output = render_worker_template(
            tmp_path / "relay",
            relay_token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
            worker_name=TEST_WORKER_NAME,
            custom_domain=None,
        )

        wrangler = (output / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML).read_text()
        assert "[[routes]]" not in wrangler


class TestRenderWranglerConfig:
    """Tests for render_wrangler_config()."""

    def test_updates_wrangler_toml_in_place(self, tmp_path: Path) -> None:
        """render_wrangler_config() overwrites wrangler.toml with new values."""
        # First scaffold without custom domain
        scaffold_dir = render_worker_template(
            tmp_path / "relay",
            relay_token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
            worker_name=TEST_WORKER_NAME,
        )

        wrangler_before = (scaffold_dir / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML).read_text()
        assert "[[routes]]" not in wrangler_before

        # Now re-render with custom domain
        render_wrangler_config(
            scaffold_dir=scaffold_dir,
            relay_token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
            worker_name=TEST_WORKER_NAME,
            custom_domain=TEST_CUSTOM_DOMAIN,
        )

        wrangler_after = (scaffold_dir / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML).read_text()
        assert "[[routes]]" in wrangler_after
        assert f'pattern = "{TEST_WORKER_NAME}.{TEST_CUSTOM_DOMAIN}"' in wrangler_after

    def test_removes_routes_when_domain_cleared(self, tmp_path: Path) -> None:
        """render_wrangler_config() removes [[routes]] when custom_domain is None."""
        # Scaffold with custom domain
        scaffold_dir = render_worker_template(
            tmp_path / "relay",
            relay_token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
            worker_name=TEST_WORKER_NAME,
            custom_domain=TEST_CUSTOM_DOMAIN,
        )

        wrangler = (scaffold_dir / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML).read_text()
        assert "[[routes]]" in wrangler

        # Re-render without custom domain
        render_wrangler_config(
            scaffold_dir=scaffold_dir,
            relay_token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
            worker_name=TEST_WORKER_NAME,
            custom_domain=None,
        )

        wrangler_cleared = (scaffold_dir / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML).read_text()
        assert "[[routes]]" not in wrangler_cleared

    def test_preserves_other_files(self, tmp_path: Path) -> None:
        """render_wrangler_config() only touches wrangler.toml, not package.json etc."""
        scaffold_dir = render_worker_template(
            tmp_path / "relay",
            relay_token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
            worker_name=TEST_WORKER_NAME,
        )

        package_json_before = (scaffold_dir / "package.json").read_text()

        render_wrangler_config(
            scaffold_dir=scaffold_dir,
            relay_token="new-token",
            agent_token="new-agent-token",
            worker_name="oak-relay-other",
            custom_domain=TEST_CUSTOM_DOMAIN,
        )

        # package.json should be untouched
        package_json_after = (scaffold_dir / "package.json").read_text()
        assert package_json_before == package_json_after

        # But wrangler.toml should have the new values
        wrangler = (scaffold_dir / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML).read_text()
        assert 'RELAY_TOKEN = "new-token"' in wrangler
        assert 'name = "oak-relay-other"' in wrangler
