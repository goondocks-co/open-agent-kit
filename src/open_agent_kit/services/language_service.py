"""Language service for managing code intelligence language parsers.

This module provides functionality for installing, removing, and listing
language parsers for code intelligence.
"""

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from open_agent_kit.constants import DEFAULT_LANGUAGES, SUPPORTED_LANGUAGES
from open_agent_kit.models.results import LanguageAddResult
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.utils.install_detection import get_install_source, is_uv_tool_install

logger = logging.getLogger(__name__)


class LanguageService:
    """Service for managing language parser installation."""

    def __init__(self, project_root: Path | None = None):
        """Initialize language service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)

    def list_installed(self) -> list[str]:
        """Get installed languages from config.

        Returns:
            List of installed language identifiers
        """
        config = self.config_service.load_config()
        return config.languages.installed

    def list_available(self) -> list[str]:
        """Get languages not yet installed.

        Returns:
            List of available language identifiers that can be installed
        """
        installed = set(self.list_installed())
        return [lang for lang in SUPPORTED_LANGUAGES if lang not in installed]

    def list_all(self) -> dict[str, dict[str, Any]]:
        """Get all supported languages with their info and installation status.

        Returns:
            Dictionary mapping language id to info dict with 'installed' key
        """
        installed = set(self.list_installed())
        result: dict[str, dict[str, Any]] = {}
        for lang, info in SUPPORTED_LANGUAGES.items():
            result[lang] = {
                **info,
                "installed": lang in installed,
            }
        return result

    def add_languages(self, languages: list[str]) -> LanguageAddResult:
        """Install language parsers via pip.

        Args:
            languages: List of language identifiers to install

        Returns:
            LanguageAddResult with installation details.
        """
        from open_agent_kit.utils import print_error, print_info, print_success, print_warning

        # Validate languages
        invalid = [lang for lang in languages if lang not in SUPPORTED_LANGUAGES]
        if invalid:
            print_error(f"Unknown languages: {', '.join(invalid)}")
            print_info(f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}")
            return {"success": False, "error": f"Unknown languages: {invalid}"}

        # Filter out already installed
        installed = set(self.list_installed())
        to_install = [lang for lang in languages if lang not in installed]

        if not to_install:
            print_info("All specified languages are already installed.")
            return {"success": True, "installed": [], "skipped": languages}

        # Get extras to install
        extras = [SUPPORTED_LANGUAGES[lang]["extra"] for lang in to_install]

        print_info(f"Installing {len(to_install)} language parser(s)...")

        success = self._install_parser_extras(extras, to_install)

        if success:
            # Update config
            config = self.config_service.load_config()
            config.languages.installed = sorted(set(config.languages.installed + to_install))
            self.config_service.save_config(config)
            print_success(f"Installed: {', '.join(to_install)}")
            return {"success": True, "installed": to_install}
        else:
            print_warning("Some parsers may not have been installed correctly.")
            return {"success": False, "error": "Installation failed"}

    def remove_languages(self, languages: list[str]) -> dict[str, Any]:
        """Remove language parsers via pip.

        Args:
            languages: List of language identifiers to remove

        Returns:
            Dictionary with removal results
        """
        from open_agent_kit.utils import print_error, print_info, print_success, print_warning

        # Validate languages
        invalid = [lang for lang in languages if lang not in SUPPORTED_LANGUAGES]
        if invalid:
            print_error(f"Unknown languages: {', '.join(invalid)}")
            return {"success": False, "error": f"Unknown languages: {invalid}"}

        # Filter to only installed
        installed = set(self.list_installed())
        to_remove = [lang for lang in languages if lang in installed]

        if not to_remove:
            print_info("None of the specified languages are installed.")
            return {"success": True, "removed": [], "skipped": languages}

        # Get packages to uninstall
        packages = [SUPPORTED_LANGUAGES[lang]["package"] for lang in to_remove]

        print_info(f"Removing {len(to_remove)} language parser(s)...")

        try:
            # Try using uv if available
            use_uv = shutil.which("uv") is not None

            if use_uv:
                cmd = ["uv", "pip", "uninstall", "--python", sys.executable] + packages
            else:
                cmd = [sys.executable, "-m", "pip", "uninstall", "-y"] + packages

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                print_warning(f"Some packages may not have been removed: {result.stderr}")

            # Update config regardless (mark as removed)
            config = self.config_service.load_config()
            config.languages.installed = [
                lang for lang in config.languages.installed if lang not in to_remove
            ]
            self.config_service.save_config(config)
            print_success(f"Removed: {', '.join(to_remove)}")
            return {"success": True, "removed": to_remove}

        except Exception as e:
            print_error(f"Failed to remove parsers: {e}")
            return {"success": False, "error": str(e)}

    def _install_parser_extras(self, extras: list[str], languages: list[str]) -> bool:
        """Install parser extras via pip or uv.

        Args:
            extras: List of extra names (e.g., ['parser-python', 'parser-javascript'])
            languages: List of language names (for logging)

        Returns:
            True if installation succeeded
        """
        from open_agent_kit.utils import print_info, print_warning

        if is_uv_tool_install():
            return self._install_via_uv_tool(extras, languages)

        # Regular environment
        use_uv = shutil.which("uv") is not None
        installer = "uv" if use_uv else "pip"

        print_info(f"Installing parsers using {installer}...")

        try:
            # Get packages from extras
            packages = [SUPPORTED_LANGUAGES[lang]["package"] for lang in languages]

            if use_uv:
                cmd = ["uv", "pip", "install", "--python", sys.executable, "--quiet"] + packages
            else:
                cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + packages

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            return result.returncode == 0

        except Exception as e:
            print_warning(f"Installation failed: {e}")
            return False

    def _install_via_uv_tool(self, extras: list[str], languages: list[str]) -> bool:
        """Install parsers via uv tool reinstall.

        Args:
            extras: List of extra names
            languages: List of language names (for logging)

        Returns:
            True if installation succeeded
        """
        from open_agent_kit.utils import print_info, print_warning

        print_info("Installing via uv tool...")
        print_info("(uv tool environments require reinstallation to add packages)")

        # Build --with arguments
        with_args = []
        for extra in extras:
            with_args.extend(["--with", f"oak-ci[{extra}]"])

        install_source, is_editable = get_install_source()
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        try:
            if install_source:
                # Preserve editable flag (-e) if the current install is editable
                editable_flag = ["-e"] if is_editable else []
                source_label = f"-e {install_source}" if is_editable else install_source
                print_info(f"(detected install source: {source_label})")
                cmd = [
                    "uv",
                    "tool",
                    "install",
                    *editable_flag,
                    install_source,
                    "--upgrade",
                    "--python",
                    python_version,
                ] + with_args
            else:
                cmd = [
                    "uv",
                    "tool",
                    "install",
                    "oak-ci",
                    "--upgrade",
                    "--python",
                    python_version,
                ] + with_args

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                print_warning(f"uv tool install failed: {result.stderr}")
                return False

            return True

        except Exception as e:
            print_warning(f"Installation failed: {e}")
            return False

    def get_default_languages(self) -> list[str]:
        """Get the default languages for fresh installs.

        Returns:
            List of default language identifiers
        """
        return list(DEFAULT_LANGUAGES)


def get_language_service(project_root: Path | None = None) -> LanguageService:
    """Get a LanguageService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        LanguageService instance
    """
    return LanguageService(project_root)
