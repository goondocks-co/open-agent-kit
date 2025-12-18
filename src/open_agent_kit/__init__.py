"""open-agent-kit: CLI tool for engineering productivity."""

try:
    # Import version from hatch-vcs generated file
    from open_agent_kit._version import __version__, __version_tuple__
except ImportError:
    # Fallback for development without build
    try:
        from importlib.metadata import version

        __version__ = version("open_agent_kit")
        __version_tuple__ = tuple(__version__.split("."))
    except Exception:
        __version__ = "0.0.0-dev"
        __version_tuple__ = (0, 0, 0, "dev")

__all__ = ["__version__", "__version_tuple__"]
