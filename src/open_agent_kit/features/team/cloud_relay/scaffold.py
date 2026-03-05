"""Worker template scaffolding for Cloud MCP Relay.

Copies the bundled Cloudflare Worker template to the user's directory and
renders Jinja2 templates (wrangler.toml.j2) with the provided tokens.

Shared logic lives in :mod:`worker_scaffold_shared`; this module provides
the Cloud Relay–specific render functions and constant wiring.
"""

import logging
import shutil
from pathlib import Path

import jinja2

from open_agent_kit.features.team.constants import (
    CLOUD_RELAY_DEFAULT_WORKER_NAME_PREFIX,
    CLOUD_RELAY_JINJA2_EXTENSION,
    CLOUD_RELAY_SCAFFOLD_GITIGNORE_ENTRIES,
    CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR,
    CLOUD_RELAY_SCAFFOLD_PACKAGE_JSON,
    CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML,
    CLOUD_RELAY_TOKEN_BYTES,
    CLOUD_RELAY_WORKER_NAME_FALLBACK,
    CLOUD_RELAY_WORKER_NAME_MAX_LENGTH,
    CLOUD_RELAY_WORKER_TEMPLATE_DIR,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    ScaffoldConfig,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    compute_scaffold_hash as _compute_scaffold_hash,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    compute_template_hash as _compute_template_hash,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    generate_token as _generate_token,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    get_default_output_dir as _get_default_output_dir,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    is_scaffolded as _is_scaffolded,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    make_worker_name as _make_worker_name,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    sync_source_files as _sync_source_files,
)

logger = logging.getLogger(__name__)

# Resolve the bundled template directory relative to this file.
_TEMPLATE_DIR = Path(__file__).parent / CLOUD_RELAY_WORKER_TEMPLATE_DIR

_CONFIG = ScaffoldConfig(
    template_dir=_TEMPLATE_DIR,
    token_bytes=CLOUD_RELAY_TOKEN_BYTES,
    worker_name_prefix=CLOUD_RELAY_DEFAULT_WORKER_NAME_PREFIX,
    worker_name_max_length=CLOUD_RELAY_WORKER_NAME_MAX_LENGTH,
    worker_name_fallback=CLOUD_RELAY_WORKER_NAME_FALLBACK,
    jinja2_extension=CLOUD_RELAY_JINJA2_EXTENSION,
    scaffold_output_dir=CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR,
    scaffold_package_json=CLOUD_RELAY_SCAFFOLD_PACKAGE_JSON,
    scaffold_wrangler_toml=CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML,
    scaffold_gitignore_entries=CLOUD_RELAY_SCAFFOLD_GITIGNORE_ENTRIES,
)


# ---------------------------------------------------------------------------
# Delegated shared functions (preserve public API)
# ---------------------------------------------------------------------------


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token."""
    return _generate_token(_CONFIG)


def make_worker_name(project_name: str) -> str:
    """Build a valid Cloudflare Worker name from a project name."""
    return _make_worker_name(_CONFIG, project_name)


def sync_source_files(scaffold_dir: Path) -> int:
    """Copy non-config source files from the bundled template to *scaffold_dir*."""
    return _sync_source_files(_CONFIG, scaffold_dir)


def get_default_output_dir() -> Path:
    """Return the default scaffold output directory under the current working directory."""
    return _get_default_output_dir(_CONFIG)


def is_scaffolded(project_root: Path) -> bool:
    """Check whether the cloud relay worker has been fully scaffolded."""
    return _is_scaffolded(_CONFIG, project_root)


def compute_template_hash() -> str:
    """Compute SHA-256 hash of the bundled Worker template source files."""
    return _compute_template_hash(_TEMPLATE_DIR)


def compute_scaffold_hash(scaffold_dir: Path) -> str | None:
    """Compute SHA-256 hash of the deployed scaffold source files."""
    return _compute_scaffold_hash(scaffold_dir)


# ---------------------------------------------------------------------------
# Cloud Relay–specific functions (unique token signatures)
# ---------------------------------------------------------------------------


def render_worker_template(
    output_dir: Path,
    relay_token: str,
    agent_token: str,
    worker_name: str,
    custom_domain: str | None = None,
    *,
    force: bool = False,
) -> Path:
    """Copy the Worker template to *output_dir* and render Jinja2 templates.

    Args:
        output_dir: Destination directory.
        relay_token: Shared secret for local daemon authentication.
        agent_token: Shared secret for cloud agent authentication.
        worker_name: Cloudflare Worker name for ``wrangler.toml``.
        custom_domain: Optional base domain for Workers Custom Domains.
        force: If ``True``, overwrite *output_dir* if it already exists.

    Returns:
        The resolved *output_dir* path.

    Raises:
        FileExistsError: If *output_dir* exists and *force* is ``False``.
        FileNotFoundError: If the bundled template directory is missing.
    """
    output_dir = output_dir.resolve()

    if not _TEMPLATE_DIR.is_dir():
        msg = f"Bundled worker template not found at {_TEMPLATE_DIR}"
        raise FileNotFoundError(msg)

    if output_dir.exists():
        if not force:
            msg = f"Output directory already exists: {output_dir}. Use --force to overwrite."
            raise FileExistsError(msg)
        shutil.rmtree(output_dir)

    # Copy everything except .j2 files first.
    shutil.copytree(
        _TEMPLATE_DIR,
        output_dir,
        ignore=shutil.ignore_patterns(f"*{CLOUD_RELAY_JINJA2_EXTENSION}"),
    )

    # Render .j2 templates with Jinja2.
    template_vars = {
        "relay_token": relay_token,
        "agent_token": agent_token,
        "worker_name": worker_name,
        "custom_domain": custom_domain,
    }

    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )

    for j2_path in _TEMPLATE_DIR.rglob(f"*{CLOUD_RELAY_JINJA2_EXTENSION}"):
        rel = j2_path.relative_to(_TEMPLATE_DIR)
        template = jinja_env.get_template(str(rel))
        rendered = template.render(template_vars)

        # Write without the .j2 extension.
        dest = output_dir / str(rel).removesuffix(CLOUD_RELAY_JINJA2_EXTENSION)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered, encoding="utf-8")

    # Write .gitignore to keep secrets and build artifacts out of version control.
    gitignore_path = output_dir / ".gitignore"
    gitignore_content = "\n".join(CLOUD_RELAY_SCAFFOLD_GITIGNORE_ENTRIES) + "\n"
    gitignore_path.write_text(gitignore_content, encoding="utf-8")

    return output_dir


def migrate_scaffold_dir(project_root: Path) -> None:
    """Migrate scaffold from legacy git-tracked location to .oak/ci/cloud-relay.

    One-time idempotent migration: copies the old ``oak/cloud-relay/`` directory
    to the new ``.oak/ci/cloud-relay/`` location if the old one exists and the
    new one does not.

    Args:
        project_root: Root directory of the project.
    """
    old_dir = project_root / "oak" / "cloud-relay"
    new_dir = project_root / CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR
    if old_dir.is_dir() and not new_dir.is_dir():
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(old_dir, new_dir)
        logger.info(
            "Migrated cloud relay scaffold from oak/cloud-relay to %s",
            CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR,
        )


def render_wrangler_config(
    scaffold_dir: Path,
    relay_token: str,
    agent_token: str,
    worker_name: str,
    custom_domain: str | None = None,
) -> None:
    """Re-render only ``wrangler.toml`` inside an existing scaffold directory.

    Args:
        scaffold_dir: The scaffold output directory (must already exist).
        relay_token: Shared secret for local daemon authentication.
        agent_token: Shared secret for cloud agent authentication.
        worker_name: Cloudflare Worker name for ``wrangler.toml``.
        custom_domain: Optional base domain for Workers Custom Domains.
    """
    template_vars = {
        "relay_token": relay_token,
        "agent_token": agent_token,
        "worker_name": worker_name,
        "custom_domain": custom_domain,
    }

    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )

    template_name = CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML + CLOUD_RELAY_JINJA2_EXTENSION
    template = jinja_env.get_template(template_name)
    rendered = template.render(template_vars)

    dest = scaffold_dir / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML
    dest.write_text(rendered, encoding="utf-8")
