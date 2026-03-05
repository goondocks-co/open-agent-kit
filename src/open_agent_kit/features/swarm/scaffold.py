"""Worker template scaffolding for Swarm Worker.

Copies the bundled Cloudflare Worker template to the user's directory and
renders Jinja2 templates (wrangler.toml.j2) with the provided tokens.

Shared logic lives in :mod:`worker_scaffold_shared`; this module provides
the Swarm-specific render functions and constant wiring.
"""

import logging
import shutil
from pathlib import Path

import jinja2

from open_agent_kit.features.swarm.constants import (
    SWARM_DEFAULT_WORKER_NAME_PREFIX,
    SWARM_JINJA2_EXTENSION,
    SWARM_SCAFFOLD_GITIGNORE_ENTRIES,
    SWARM_SCAFFOLD_OUTPUT_DIR,
    SWARM_SCAFFOLD_PACKAGE_JSON,
    SWARM_SCAFFOLD_WRANGLER_TOML,
    SWARM_TOKEN_BYTES,
    SWARM_WORKER_NAME_FALLBACK,
    SWARM_WORKER_NAME_MAX_LENGTH,
    SWARM_WORKER_TEMPLATE_DIR,
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
_TEMPLATE_DIR = Path(__file__).parent / SWARM_WORKER_TEMPLATE_DIR

_CONFIG = ScaffoldConfig(
    template_dir=_TEMPLATE_DIR,
    token_bytes=SWARM_TOKEN_BYTES,
    worker_name_prefix=SWARM_DEFAULT_WORKER_NAME_PREFIX,
    worker_name_max_length=SWARM_WORKER_NAME_MAX_LENGTH,
    worker_name_fallback=SWARM_WORKER_NAME_FALLBACK,
    jinja2_extension=SWARM_JINJA2_EXTENSION,
    scaffold_output_dir=SWARM_SCAFFOLD_OUTPUT_DIR,
    scaffold_package_json=SWARM_SCAFFOLD_PACKAGE_JSON,
    scaffold_wrangler_toml=SWARM_SCAFFOLD_WRANGLER_TOML,
    scaffold_gitignore_entries=SWARM_SCAFFOLD_GITIGNORE_ENTRIES,
)


# ---------------------------------------------------------------------------
# Delegated shared functions (preserve public API)
# ---------------------------------------------------------------------------


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token."""
    return _generate_token(_CONFIG)


def make_worker_name(swarm_name: str) -> str:
    """Build a valid Cloudflare Worker name from a swarm name."""
    return _make_worker_name(_CONFIG, swarm_name)


def sync_source_files(scaffold_dir: Path) -> int:
    """Copy non-config source files from the bundled template to *scaffold_dir*."""
    return _sync_source_files(_CONFIG, scaffold_dir)


def get_default_output_dir() -> Path:
    """Return the default scaffold output directory under the current working directory."""
    return _get_default_output_dir(_CONFIG)


def is_scaffolded(project_root: Path) -> bool:
    """Check whether the swarm worker has been fully scaffolded."""
    return _is_scaffolded(_CONFIG, project_root)


def compute_template_hash() -> str:
    """Compute SHA-256 hash of the bundled Worker template source files."""
    return _compute_template_hash(_TEMPLATE_DIR)


def compute_scaffold_hash(scaffold_dir: Path) -> str | None:
    """Compute SHA-256 hash of the deployed scaffold source files."""
    return _compute_scaffold_hash(scaffold_dir)


# ---------------------------------------------------------------------------
# Swarm-specific functions (unique token signature: swarm_token only)
# ---------------------------------------------------------------------------


def render_worker_template(
    output_dir: Path,
    swarm_token: str,
    worker_name: str,
    custom_domain: str | None = None,
    *,
    force: bool = False,
    agent_token: str = "",
) -> Path:
    """Copy the Worker template to *output_dir* and render Jinja2 templates.

    Args:
        output_dir: Destination directory.
        swarm_token: Shared secret for swarm authentication.
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
        ignore=shutil.ignore_patterns(f"*{SWARM_JINJA2_EXTENSION}"),
    )

    # Render .j2 templates with Jinja2.
    template_vars = {
        "swarm_token": swarm_token,
        "worker_name": worker_name,
        "custom_domain": custom_domain,
        "agent_token": agent_token,
    }

    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )

    for j2_path in _TEMPLATE_DIR.rglob(f"*{SWARM_JINJA2_EXTENSION}"):
        rel = j2_path.relative_to(_TEMPLATE_DIR)
        template = jinja_env.get_template(str(rel))
        rendered = template.render(template_vars)

        # Write without the .j2 extension.
        dest = output_dir / str(rel).removesuffix(SWARM_JINJA2_EXTENSION)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered, encoding="utf-8")

    # Write .gitignore to keep secrets and build artifacts out of version control.
    gitignore_path = output_dir / ".gitignore"
    gitignore_content = "\n".join(SWARM_SCAFFOLD_GITIGNORE_ENTRIES) + "\n"
    gitignore_path.write_text(gitignore_content, encoding="utf-8")

    return output_dir


def render_wrangler_config(
    scaffold_dir: Path,
    swarm_token: str,
    worker_name: str,
    custom_domain: str | None = None,
    agent_token: str = "",
) -> None:
    """Re-render only ``wrangler.toml`` inside an existing scaffold directory.

    Args:
        scaffold_dir: The scaffold output directory (must already exist).
        swarm_token: Shared secret for swarm authentication.
        worker_name: Cloudflare Worker name for ``wrangler.toml``.
        custom_domain: Optional base domain for Workers Custom Domains.
    """
    template_vars = {
        "swarm_token": swarm_token,
        "worker_name": worker_name,
        "custom_domain": custom_domain,
        "agent_token": agent_token,
    }

    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )

    template_name = SWARM_SCAFFOLD_WRANGLER_TOML + SWARM_JINJA2_EXTENSION
    template = jinja_env.get_template(template_name)
    rendered = template.render(template_vars)

    dest = scaffold_dir / SWARM_SCAFFOLD_WRANGLER_TOML
    dest.write_text(rendered, encoding="utf-8")
