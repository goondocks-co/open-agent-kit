"""Install source detection for OAK packages.

Detects how OAK was installed (PyPI, local path, git URL, editable)
by inspecting PEP 610 ``direct_url.json`` metadata.  Used by both
``FeatureService`` and ``LanguageService`` when installing dependencies
into the correct environment.
"""

from __future__ import annotations

from open_agent_kit.utils.platform import is_uv_tool_install


def get_install_source(package_name: str = "oak-ci") -> tuple[str | None, bool]:
    """Get the install source if *package_name* was installed from a non-PyPI source.

    Detects:
    - Local file paths (``uv tool install /path/to/oak``)
    - Editable installs (``uv tool install -e /path/to/oak``)
    - Git URLs (``uv tool install git+https://github.com/...``)

    This allows feature dependency installation to work without requiring
    PyPI publication.  The *is_editable* flag ensures that editable installs
    (used during development) are preserved when reinstalling with
    additional dependencies.

    Args:
        package_name: Distribution name to inspect (default ``"oak-ci"``).

    Returns:
        Tuple of *(install_source, is_editable)*:
        - *install_source*: local path or git URL if non-PyPI, ``None`` otherwise
        - *is_editable*: ``True`` if this is an editable install (dir_info.editable)
    """
    try:
        from importlib.metadata import distribution

        dist = distribution(package_name)

        # Check direct_url.json (PEP 610) for non-PyPI installs
        direct_url = dist.read_text("direct_url.json")
        if direct_url:
            import json

            url_info = json.loads(direct_url)
            url = url_info.get("url", "")

            # Check if this is an editable install (PEP 610 dir_info)
            is_editable = bool(url_info.get("dir_info", {}).get("editable", False))

            # Local file path install
            if url.startswith("file://"):
                return str(url[7:]), is_editable  # Strip file:// prefix

            # Git URL install (vcs_info present means it's a VCS install)
            if url_info.get("vcs_info"):
                vcs = url_info["vcs_info"].get("vcs", "git")
                return f"{vcs}+{url}", False  # Git installs are never editable

        return None, False
    except Exception:
        return None, False


__all__ = ["get_install_source", "is_uv_tool_install"]
