"""Package installer service for managing pip/uv package installation."""

import logging

from open_agent_kit.utils.install_detection import get_install_source, is_uv_tool_install

logger = logging.getLogger(__name__)


class PackageInstallerService:
    """Service for installing Python packages into OAK's environment.

    Handles both regular pip/uv installs and uv tool installs, which require
    different installation strategies.
    """

    def install(self, packages: list[str], feature_name: str) -> bool:
        """Install pip packages for a feature into OAK's Python environment.

        IMPORTANT: Packages must be installed into the same environment that OAK
        runs from (sys.executable), not the user's project environment. This ensures
        the daemon and other OAK components can import these packages.

        For uv tool installations, we use `uv tool install --upgrade --with` to add
        packages to the tool's isolated environment (uv pip install doesn't work for
        tool environments).

        Args:
            packages: List of package specs to install (e.g., ['fastapi>=0.109.0'])
            feature_name: Name of the feature (for logging)

        Returns:
            True if all packages were installed successfully
        """
        if not packages:
            return True

        if is_uv_tool_install():
            return self._install_via_uv_tool(packages, feature_name)

        return self._install_via_pip(packages, feature_name)

    def _install_via_pip(self, packages: list[str], feature_name: str) -> bool:
        """Install packages using pip or uv pip into the current environment.

        Args:
            packages: List of package specs to install
            feature_name: Name of the feature (for logging)

        Returns:
            True if packages were installed successfully
        """
        import shutil
        import subprocess
        import sys

        from open_agent_kit.utils import print_info, print_success, print_warning

        oak_python = sys.executable
        use_uv = shutil.which("uv") is not None
        installer = "uv" if use_uv else "pip"

        print_info(f"Installing {len(packages)} packages for '{feature_name}' using {installer}...")

        try:
            if use_uv:
                cmd = ["uv", "pip", "install", "--python", oak_python, "--quiet"] + packages
            else:
                cmd = [oak_python, "-m", "pip", "install", "--quiet"] + packages

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                print_success(f"Installed packages for '{feature_name}'")
                return True
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                print_warning(f"Failed to install packages for '{feature_name}':")
                print_warning(f"  Command: {' '.join(cmd)}")
                print_warning(f"  Error: {error_msg}")
                return False
        except Exception as e:
            print_warning(f"Failed to install packages for '{feature_name}': {e}")
            return False

    def _install_via_uv_tool(self, packages: list[str], feature_name: str) -> bool:
        """Install packages for a uv tool installation.

        uv tool environments are isolated and cannot be modified with `uv pip install`.
        We need to use `uv tool install --upgrade --with` to add packages.

        For editable installs, we use `uv tool install -e <path>` instead of the
        package name to avoid trying to fetch from PyPI.

        Args:
            packages: List of package specs to install
            feature_name: Name of the feature (for logging)

        Returns:
            True if packages were installed successfully
        """
        import subprocess
        import sys

        from open_agent_kit.utils import print_info, print_success, print_warning

        print_info(f"Installing {len(packages)} packages for '{feature_name}' via uv tool...")
        print_info("(uv tool environments require reinstallation to add packages)")

        with_args: list[str] = []
        for pkg in packages:
            with_args.extend(["--with", pkg])

        install_source, is_editable = get_install_source()
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        try:
            cmd, manual_cmd = self._build_uv_tool_command(
                install_source, is_editable, python_version, with_args
            )

            if install_source and is_editable:
                source_label = f"-e {install_source}"
            elif install_source:
                source_label = install_source
            else:
                source_label = "oak-ci"
            print_info(f"(detected install source: {source_label})")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                print_success(f"Installed packages for '{feature_name}'")
                return True
            else:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                print_warning(f"Failed to install packages for '{feature_name}':")
                print_warning(f"  Command: {' '.join(cmd)}")
                print_warning(f"  Error: {error_msg}")
                print_warning("\nTry manually running:")
                print_warning(f"  {manual_cmd}")
                return False
        except Exception as e:
            print_warning(f"Failed to install packages for '{feature_name}': {e}")
            return False

    def _build_uv_tool_command(
        self,
        install_source: str | None,
        is_editable: bool,
        python_version: str,
        with_args: list[str],
    ) -> tuple[list[str], str]:
        """Build the uv tool install command and manual fallback string.

        Args:
            install_source: Path or URL for the install source (None for PyPI)
            is_editable: Whether the current install is editable
            python_version: Python version string (e.g., "3.13")
            with_args: List of --with arguments

        Returns:
            Tuple of (command list, manual command string)
        """
        if install_source:
            editable_flag = ["-e"] if is_editable else []
            source_label = f"-e {install_source}" if is_editable else install_source
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
            manual_cmd = (
                f"uv tool install {source_label} --upgrade "
                f"--python {python_version} {' '.join(with_args)}"
            )
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
            manual_cmd = (
                f"uv tool install oak-ci --upgrade --python {python_version} {' '.join(with_args)}"
            )
        return cmd, manual_cmd
