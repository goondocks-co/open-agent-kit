"""Self-update exemption checks.

Two categories are exempt: editable installs (development) and Windows.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from open_agent_kit.utils.install_detection import get_install_source


@dataclass(frozen=True)
class UpdateExemption:
    """Reason why self-update is disabled."""

    reason: str  # "editable_install" | "windows_unsupported"
    message: str


def check_update_exempt() -> UpdateExemption | None:
    """Check if self-update should be disabled.

    Returns None if self-update is allowed, or an UpdateExemption with the reason.
    """
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
