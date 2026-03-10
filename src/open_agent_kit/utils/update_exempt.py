"""Self-update exemption checks.

Two categories are exempt: editable installs (development) and Windows.
"""

from __future__ import annotations

import functools
import os
import sys
from dataclasses import dataclass

from open_agent_kit.utils.install_detection import get_install_source


@dataclass(frozen=True)
class UpdateExemption:
    """Reason why self-update is disabled."""

    reason: str  # "editable_install" | "windows_unsupported"
    message: str


FORCE_SELF_UPDATE_ENV_VAR = "OAK_FORCE_SELF_UPDATE"


@functools.lru_cache(maxsize=1)
def check_update_exempt() -> UpdateExemption | None:
    """Check if self-update should be disabled.

    Returns None if self-update is allowed, or an UpdateExemption with the reason.
    Result is cached for the process lifetime (install method and platform
    never change while the daemon is running).

    Set ``OAK_FORCE_SELF_UPDATE=1`` to bypass all exemption checks (useful for
    smoke-testing the self-update UI on an editable/dev install).
    """
    if os.environ.get(FORCE_SELF_UPDATE_ENV_VAR):
        return None

    _, is_editable = get_install_source()
    if is_editable:
        return UpdateExemption(
            reason="editable_install",
            message="Self-update is disabled for editable (development) installs.",
        )

    if sys.platform == "win32":
        return UpdateExemption(
            reason="windows_unsupported",
            message="Self-update is not yet supported on Windows. Use pip install --upgrade oak-ci.",
        )

    return None


__all__ = ["UpdateExemption", "check_update_exempt"]
