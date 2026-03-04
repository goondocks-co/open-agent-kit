"""Version comparison utilities for Team."""

import re


def parse_base_release(version_str: str) -> tuple[int, ...]:
    """Extract the base release tuple from a PEP 440 version string.

    Strips dev/pre/post/local suffixes so that e.g. ``1.0.10.dev0+gabcdef``
    and ``1.0.10`` both yield ``(1, 0, 10)``.  This prevents false-positive
    "update available" banners when dogfooding with a dev version alongside
    a release install.
    """
    match = re.match(r"v?(\d+(?:\.\d+)*)", version_str)
    if not match:
        return ()
    return tuple(int(p) for p in match.group(1).split("."))


def is_meaningful_upgrade(running: str, installed: str) -> bool:
    """Return True only when the installed base release is strictly greater."""
    running_rel = parse_base_release(running)
    installed_rel = parse_base_release(installed)
    if not running_rel or not installed_rel:
        return installed != running
    return installed_rel > running_rel
