"""Download and stage OAK wheels from PyPI.

Downloads the wheel for a specific version, verifies its SHA256 checksum,
and stages it in ~/.oak/staging/ for later installation.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import sys
import time
from collections.abc import Generator
from typing import Any

import httpx

# fcntl is POSIX-only; Windows is exempt from self-update but we guard the import
if sys.platform != "win32":
    import fcntl

from open_agent_kit.utils.global_config import (
    LOCK_FILE,
    STAGING_DIR,
    get_global_oak_dir,
    read_staged_update,
    write_staged_update,
)
from open_agent_kit.utils.release_channel import fetch_pypi_raw

logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT_SECONDS = 120


def _find_wheel_url(pypi_data: dict[str, Any], version: str) -> tuple[str, str, str]:
    """Extract wheel URL, SHA256, and filename from PyPI JSON data.

    Raises ValueError if version or wheel not found.
    """
    releases = pypi_data.get("releases", {})
    if version not in releases:
        msg = f"Version {version} not found in PyPI releases"
        raise ValueError(msg)

    for entry in releases[version]:
        if entry.get("packagetype") == "bdist_wheel":
            return entry["url"], entry["digests"]["sha256"], entry["filename"]

    msg = f"No wheel found for version {version}"
    raise ValueError(msg)


async def _download_file(url: str) -> bytes:
    """Download a file from URL and return its content."""
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT_SECONDS) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


@contextlib.contextmanager
def _try_acquire_lock() -> Generator[bool, None, None]:
    """Try to acquire the update lock file. Yields True if acquired, False if busy."""
    lock_path = get_global_oak_dir() / LOCK_FILE
    try:
        lock_fd = lock_path.open("w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield True
        except BlockingIOError:
            yield False
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            lock_fd.close()
    except OSError:
        yield False


def clean_staging() -> None:
    """Remove all files from the staging directory."""
    staging = get_global_oak_dir() / STAGING_DIR
    if staging.exists():
        for f in staging.iterdir():
            f.unlink(missing_ok=True)


async def download_and_stage(version: str, channel: str = "stable") -> bool:
    """Download a wheel from PyPI and stage it for installation.

    Args:
        version: The version string to download.
        channel: The update channel that triggered this download.

    Returns True on success, False on failure.
    """
    with _try_acquire_lock() as acquired:
        if not acquired:
            # Another daemon is downloading — check if it already staged
            existing = read_staged_update()
            if existing and existing.get("version") == version:
                logger.info("Update already staged by another process")
                return True
            logger.info("Update lock held by another process, skipping download")
            return False

        try:
            # Fetch PyPI metadata (fetch_pypi_raw is synchronous)
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, fetch_pypi_raw)
            pypi_data = json.loads(raw)

            # Find the wheel
            url, expected_sha256, filename = _find_wheel_url(pypi_data, version)

            # Clean staging directory
            clean_staging()

            # Download
            logger.info("Downloading %s from PyPI...", filename)
            content = await _download_file(url)

            # Verify checksum
            actual_sha256 = hashlib.sha256(content).hexdigest()
            if actual_sha256 != expected_sha256:
                logger.error(
                    "Checksum mismatch for %s: expected %s, got %s",
                    filename,
                    expected_sha256,
                    actual_sha256,
                )
                return False

            # Write wheel to staging
            staging_dir = get_global_oak_dir() / STAGING_DIR
            wheel_path = staging_dir / filename
            wheel_path.write_bytes(content)

            # Write metadata
            write_staged_update(
                {
                    "schema_version": 1,
                    "version": version,
                    "wheel_path": str(wheel_path),
                    "channel": channel,
                    "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "sha256": actual_sha256,
                }
            )

            logger.info("Successfully staged %s at %s", filename, wheel_path)
            return True

        except Exception as exc:
            logger.error("Failed to download and stage update: %s", exc)
            clean_staging()
            return False
