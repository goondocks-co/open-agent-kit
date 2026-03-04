"""Shared scaffold utilities for Cloudflare Worker template projects.

Provides the common functions used by both the Cloud Relay and Swarm scaffold
modules.  Each consumer passes a ``ScaffoldConfig`` with its own constants.
"""

import functools
import hashlib
import logging
import re
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

# Shared Cloudflare Worker scaffold constants (single source of truth).
# Feature-specific modules (cloud_relay, swarm) alias these under their own prefix.
WORKER_TOKEN_BYTES: Final[int] = 32
WORKER_JINJA2_EXTENSION: Final[str] = ".j2"
WORKER_SCAFFOLD_GITIGNORE_ENTRIES: Final[tuple[str, ...]] = (
    "wrangler.toml",
    "node_modules/",
    ".wrangler/",
)
WORKER_SCAFFOLD_PACKAGE_JSON: Final[str] = "package.json"
WORKER_SCAFFOLD_WRANGLER_TOML: Final[str] = "wrangler.toml"
WORKER_SCAFFOLD_NODE_MODULES_DIR: Final[str] = "node_modules"
WORKER_NAME_MAX_LENGTH: Final[int] = 63
WORKER_NAME_FALLBACK: Final[str] = "default"


@dataclass(frozen=True)
class ScaffoldConfig:
    """Per-module constants that vary between Cloud Relay and Swarm scaffolds."""

    template_dir: Path
    token_bytes: int
    worker_name_prefix: str
    worker_name_max_length: int
    worker_name_fallback: str
    jinja2_extension: str
    scaffold_output_dir: str
    scaffold_package_json: str
    scaffold_wrangler_toml: str
    scaffold_gitignore_entries: tuple[str, ...]


# Cloudflare Worker name rules: lowercase, alphanumeric + hyphens.
_WORKER_NAME_INVALID_CHARS = re.compile(r"[^a-z0-9-]")
_WORKER_NAME_MULTI_HYPHENS = re.compile(r"-+")


def generate_token(config: ScaffoldConfig) -> str:
    """Generate a cryptographically secure URL-safe token.

    Returns:
        A URL-safe token string of ``config.token_bytes`` random bytes.
    """
    return secrets.token_urlsafe(config.token_bytes)


def make_worker_name(config: ScaffoldConfig, name: str) -> str:
    """Build a valid Cloudflare Worker name from a project/swarm name.

    Returns ``<prefix>-<sanitized-name>`` where the name is lowercased
    and non-alphanumeric characters are replaced with hyphens.

    Args:
        config: Scaffold configuration with prefix and length constraints.
        name: Human-readable name (project dir name or swarm name).

    Returns:
        A valid Cloudflare Worker name (lowercase, alphanumeric + hyphens,
        max ``config.worker_name_max_length`` characters).
    """
    prefix = config.worker_name_prefix + "-"
    sanitized = name.lower()

    # Replace invalid chars with hyphens, collapse runs, strip edges
    sanitized = _WORKER_NAME_INVALID_CHARS.sub("-", sanitized)
    sanitized = _WORKER_NAME_MULTI_HYPHENS.sub("-", sanitized)
    sanitized = sanitized.strip("-")

    # Truncate to fit within max length with prefix
    max_suffix_len = config.worker_name_max_length - len(prefix)
    sanitized = sanitized[:max_suffix_len].rstrip("-")

    if not sanitized:
        sanitized = config.worker_name_fallback

    return f"{prefix}{sanitized}"


def sync_source_files(config: ScaffoldConfig, scaffold_dir: Path) -> int:
    """Copy non-config source files from the bundled template to *scaffold_dir*.

    Overwrites TypeScript sources, ``package.json``, and ``tsconfig.json``
    so that every deploy picks up the latest bundled code.  Skips Jinja2
    templates (rendered separately) and ``node_modules`` / build artefacts
    that live only in the scaffold directory.

    Args:
        config: Scaffold configuration with template dir and extension.
        scaffold_dir: The scaffold output directory (must already exist).

    Returns:
        Number of files copied.
    """
    copied = 0
    for src_path in config.template_dir.rglob("*"):
        if not src_path.is_file():
            continue
        # Skip Jinja2 templates — handled by render_wrangler_config()
        if src_path.suffix == config.jinja2_extension:
            continue
        rel = src_path.relative_to(config.template_dir)
        dest = scaffold_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest)
        copied += 1
    logger.debug("Synced %d source files from template to %s", copied, scaffold_dir)
    return copied


def get_default_output_dir(config: ScaffoldConfig) -> Path:
    """Return the default scaffold output directory under the current working directory."""
    return Path.cwd() / config.scaffold_output_dir


def is_scaffolded(config: ScaffoldConfig, project_root: Path) -> bool:
    """Check whether the worker has been fully scaffolded.

    Args:
        config: Scaffold configuration with output dir and expected files.
        project_root: Root directory of the project.

    Returns:
        True if the scaffold output directory contains both ``package.json``
        and ``wrangler.toml`` (the rendered Jinja2 template).
    """
    scaffold_dir = project_root / config.scaffold_output_dir
    return (scaffold_dir / config.scaffold_package_json).is_file() and (
        scaffold_dir / config.scaffold_wrangler_toml
    ).is_file()


def _hash_source_dir(root: Path) -> str:
    """Compute SHA-256 over TypeScript source files in *root*.

    Only ``src/**/*.ts`` files are hashed — config files like
    ``wrangler.toml`` (rendered from Jinja2) and ``package-lock.json``
    (generated by npm) are excluded because they are expected to differ
    between the bundled template and the scaffold directory.
    """
    h = hashlib.sha256()
    src_dir = root / "src"
    if src_dir.is_dir():
        for path in sorted(src_dir.rglob("*.ts")):
            h.update(path.read_bytes())
    return h.hexdigest()


@functools.lru_cache(maxsize=4)
def compute_template_hash(template_dir: Path) -> str:
    """Compute SHA-256 hash of the bundled Worker template source files.

    Used to detect when a package update has changed the Worker template,
    signalling that a redeploy is needed.  The result is cached because the
    bundled template is read-only for the lifetime of the process.

    Args:
        template_dir: Path to the bundled template directory.

    Returns:
        Hex digest of the hash.
    """
    return _hash_source_dir(template_dir)


def compute_scaffold_hash(scaffold_dir: Path) -> str | None:
    """Compute SHA-256 hash of the deployed scaffold source files.

    Returns:
        Hex digest, or ``None`` if *scaffold_dir* does not exist.
    """
    if not scaffold_dir.is_dir():
        return None
    return _hash_source_dir(scaffold_dir)
