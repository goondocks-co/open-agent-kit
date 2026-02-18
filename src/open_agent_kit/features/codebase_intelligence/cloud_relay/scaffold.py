"""Worker template scaffolding for Cloud MCP Relay.

Copies the bundled Cloudflare Worker template to the user's directory and
renders Jinja2 templates (wrangler.toml.j2) with the provided tokens.
"""

import re
import secrets
import shutil
from pathlib import Path

import jinja2

from open_agent_kit.features.codebase_intelligence.constants import (
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

# Resolve the bundled template directory relative to this file.
_TEMPLATE_DIR = Path(__file__).parent / CLOUD_RELAY_WORKER_TEMPLATE_DIR

# Cloudflare Worker name rules: lowercase, alphanumeric + hyphens.
_WORKER_NAME_INVALID_CHARS = re.compile(r"[^a-z0-9-]")
_WORKER_NAME_MULTI_HYPHENS = re.compile(r"-+")


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token.

    Returns:
        A URL-safe token string of ``CLOUD_RELAY_TOKEN_BYTES`` random bytes.
    """
    return secrets.token_urlsafe(CLOUD_RELAY_TOKEN_BYTES)


def make_worker_name(project_name: str) -> str:
    """Build a valid Cloudflare Worker name from a project name.

    Returns ``oak-relay-<sanitized-name>`` where the name is lowercased
    and non-alphanumeric characters are replaced with hyphens.  This
    ensures each project gets its own Worker deployment, avoiding
    conflicts when multiple daemons share a Cloudflare account.

    Args:
        project_name: Human-readable project name (typically the directory
            name, i.e. ``project_root.name``).

    Returns:
        A valid Cloudflare Worker name (lowercase, alphanumeric + hyphens,
        max 63 characters).
    """
    prefix = CLOUD_RELAY_DEFAULT_WORKER_NAME_PREFIX + "-"
    name = project_name.lower()

    # Replace invalid chars with hyphens, collapse runs, strip edges
    sanitized = _WORKER_NAME_INVALID_CHARS.sub("-", name)
    sanitized = _WORKER_NAME_MULTI_HYPHENS.sub("-", sanitized)
    sanitized = sanitized.strip("-")

    # Truncate to fit within max length with prefix
    max_suffix_len = CLOUD_RELAY_WORKER_NAME_MAX_LENGTH - len(prefix)
    sanitized = sanitized[:max_suffix_len].rstrip("-")

    if not sanitized:
        sanitized = CLOUD_RELAY_WORKER_NAME_FALLBACK

    return f"{prefix}{sanitized}"


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

    The directory is copied verbatim except for ``*.j2`` files, which are
    rendered through Jinja2 with the supplied token variables and written
    without the ``.j2`` extension.

    Args:
        output_dir: Destination directory. Defaults to
            ``<cwd>/CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR`` when the caller
            passes a relative path.
        relay_token: Shared secret for local daemon authentication.
        agent_token: Shared secret for cloud agent authentication.
        worker_name: Cloudflare Worker name for ``wrangler.toml``.
        custom_domain: Optional base domain for Cloudflare Workers Custom
            Domains (e.g. ``example.com``).  When set, a ``[[routes]]``
            section is added to ``wrangler.toml`` so Cloudflare provisions
            the DNS record and SSL certificate during deploy.
        force: If ``True``, overwrite *output_dir* if it already exists.
            Defaults to ``False`` (raises ``FileExistsError``).

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
            msg = f"Output directory already exists: {output_dir}. " "Use --force to overwrite."
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


def get_default_output_dir() -> Path:
    """Return the default scaffold output directory under the current working directory."""
    return Path.cwd() / CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR


def is_scaffolded(project_root: Path) -> bool:
    """Check whether the cloud relay worker has been fully scaffolded.

    Args:
        project_root: Root directory of the project.

    Returns:
        True if the scaffold output directory contains both ``package.json``
        and ``wrangler.toml`` (the rendered Jinja2 template).
    """
    scaffold_dir = project_root / CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR
    return (scaffold_dir / CLOUD_RELAY_SCAFFOLD_PACKAGE_JSON).is_file() and (
        scaffold_dir / CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML
    ).is_file()


def render_wrangler_config(
    scaffold_dir: Path,
    relay_token: str,
    agent_token: str,
    worker_name: str,
    custom_domain: str | None = None,
) -> None:
    """Re-render only ``wrangler.toml`` inside an existing scaffold directory.

    This is a lightweight operation (one Jinja2 render + file write) used to
    sync the wrangler config with the current settings without requiring a
    full re-scaffold.  Called before each deploy and when settings change.

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
