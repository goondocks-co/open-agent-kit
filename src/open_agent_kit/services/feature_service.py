"""Feature service for managing OAK features."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from open_agent_kit.config.paths import FEATURE_MANIFEST_FILE, FEATURES_DIR

if TYPE_CHECKING:
    from open_agent_kit.services.template_service import TemplateService
from open_agent_kit.constants import FEATURE_CONFIG, SUPPORTED_FEATURES
from open_agent_kit.models.feature import FeatureManifest
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.state_service import StateService
from open_agent_kit.utils import (
    add_gitignore_entries,
    read_file,
    remove_gitignore_entries,
    write_file,
)

logger = logging.getLogger(__name__)


def _feature_name_to_dir(feature_name: str) -> str:
    """Convert feature name to directory name (hyphens to underscores).

    Feature names use hyphens (codebase-intelligence) but Python packages
    use underscores (codebase_intelligence).

    Args:
        feature_name: Feature name with hyphens

    Returns:
        Directory name with underscores
    """
    return feature_name.replace("-", "_")


class FeatureService:
    """Service for managing OAK features with dependency resolution.

    Handles feature discovery, installation, removal, and dependency management.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize feature service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.state_service = StateService(project_root)

        # Package features directory (where feature manifests/templates are stored)
        # Path: services/feature_service.py -> services/ -> open_agent_kit/
        self.package_features_dir = Path(__file__).parent.parent / FEATURES_DIR
        self._template_service: TemplateService | None = None

    @property
    def template_service(self) -> "TemplateService":
        """Lazy-load template service to avoid circular dependencies."""
        if self._template_service is None:
            from open_agent_kit.services.template_service import TemplateService

            self._template_service = TemplateService(project_root=self.project_root)
        return self._template_service

    def _is_uv_tool_install(self) -> bool:
        """Check if OAK is running from a uv tool installation.

        Works on both POSIX and Windows systems:
        - POSIX: ~/.local/share/uv/tools/
        - Windows: %LOCALAPPDATA%\\uv\\tools\\
        """
        from open_agent_kit.utils.platform import is_uv_tool_install

        return is_uv_tool_install()

    def _get_install_source(self) -> tuple[str | None, bool]:
        """Get the install source if OAK was installed from a non-PyPI source.

        Detects:
        - Local file paths (`uv tool install /path/to/oak`)
        - Editable installs (`uv tool install -e /path/to/oak`)
        - Git URLs (`uv tool install git+https://github.com/...`)

        This allows feature dependency installation to work without requiring
        PyPI publication. The editable flag ensures that editable installs
        (used during development) are preserved when reinstalling with
        additional dependencies.

        Returns:
            Tuple of (install_source, is_editable):
            - install_source: local path or git URL if non-PyPI, None otherwise
            - is_editable: True if this is an editable install (dir_info.editable)
        """
        try:
            from importlib.metadata import distribution

            dist = distribution("open-agent-kit")

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

    def _install_pip_packages(self, packages: list[str], feature_name: str) -> bool:
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
        import shutil
        import subprocess
        import sys

        from open_agent_kit.utils import print_info, print_success, print_warning

        if not packages:
            return True

        # Check if running from uv tool install
        if self._is_uv_tool_install():
            return self._install_packages_uv_tool(packages, feature_name)

        # Regular environment (venv, pip install, etc.)
        oak_python = sys.executable

        # Prefer uv for faster installs
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

    def _install_packages_uv_tool(self, packages: list[str], feature_name: str) -> bool:
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

        from open_agent_kit.utils import print_info, print_success, print_warning

        print_info(f"Installing {len(packages)} packages for '{feature_name}' via uv tool...")
        print_info("(uv tool environments require reinstallation to add packages)")

        # Build --with arguments for each package
        with_args = []
        for pkg in packages:
            with_args.extend(["--with", pkg])

        # Check if this is a non-PyPI install (local path or git URL)
        install_source, is_editable = self._get_install_source()

        # Get current Python version to ensure consistency
        import sys

        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        try:
            if install_source:
                # Non-PyPI install: use the original source (local path or git URL)
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
                manual_cmd = (
                    f"uv tool install {source_label} --upgrade "
                    f"--python {python_version} {' '.join(with_args)}"
                )
            else:
                # PyPI install: use package name (only works if published to PyPI)
                cmd = [
                    "uv",
                    "tool",
                    "install",
                    "open-agent-kit",
                    "--upgrade",
                    "--python",
                    python_version,
                ] + with_args
                manual_cmd = (
                    f"uv tool install open-agent-kit --upgrade "
                    f"--python {python_version} {' '.join(with_args)}"
                )

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

    def _check_prerequisites(self, prerequisites: list[dict]) -> dict[str, Any]:
        """Check if prerequisites for a feature are satisfied.

        Args:
            prerequisites: List of prerequisite definitions from manifest

        Returns:
            Dictionary with check results:
            {
                'satisfied': True/False,
                'missing': [{'name': 'ollama', 'instructions': '...'}],
                'warnings': ['Ollama not found, will use FastEmbed fallback']
            }
        """
        import shutil
        import subprocess

        from open_agent_kit.utils import print_info, print_success, print_warning

        result: dict[str, Any] = {
            "satisfied": True,
            "missing": [],
            "warnings": [],
        }

        for prereq in prerequisites:
            name = prereq.get("name", "unknown")
            prereq_type = prereq.get("type", "command")
            check_cmd = prereq.get("check_command")
            required = prereq.get("required", True)
            install_url = prereq.get("install_url", "")
            install_instructions = prereq.get("install_instructions", "")

            print_info(f"Checking prerequisite: {name}...")

            is_available = False

            if prereq_type == "service" and check_cmd:
                # Check if command exists and runs
                cmd_name = check_cmd.split()[0]
                if shutil.which(cmd_name):
                    try:
                        proc = subprocess.run(
                            check_cmd.split(),
                            capture_output=True,
                            timeout=5,
                            check=False,
                        )
                        is_available = proc.returncode == 0
                    except (subprocess.TimeoutExpired, OSError):
                        is_available = False

            elif prereq_type == "command" and check_cmd:
                # Just check if command exists
                cmd_name = check_cmd.split()[0]
                is_available = shutil.which(cmd_name) is not None

            if is_available:
                print_success(f"  {name} is available")
            else:
                if required:
                    result["satisfied"] = False
                    result["missing"].append(
                        {
                            "name": name,
                            "install_url": install_url,
                            "instructions": install_instructions,
                        }
                    )
                    print_warning(f"  {name} is not available (required)")
                else:
                    result["warnings"].append(
                        f"{name} not found - feature will use fallback if available"
                    )
                    print_warning(f"  {name} not found (optional, will use fallback)")

        return result

    def list_available_features(self) -> list[FeatureManifest]:
        """List all available features from package.

        Returns:
            List of FeatureManifest objects for all available features
        """
        features = []
        for feature_name in SUPPORTED_FEATURES:
            manifest = self.get_feature_manifest(feature_name)
            if manifest:
                features.append(manifest)
        return features

    def get_feature_manifest(self, feature_name: str) -> FeatureManifest | None:
        """Get manifest for a specific feature.

        Args:
            feature_name: Name of the feature

        Returns:
            FeatureManifest or None if not found
        """
        feature_dir = _feature_name_to_dir(feature_name)
        manifest_path = self.package_features_dir / feature_dir / FEATURE_MANIFEST_FILE
        if manifest_path.exists():
            return FeatureManifest.load(manifest_path)

        # Fall back to FEATURE_CONFIG if manifest doesn't exist
        if feature_name in FEATURE_CONFIG:
            config = FEATURE_CONFIG[feature_name]
            return FeatureManifest(
                name=feature_name,
                display_name=str(config["name"]),
                description=str(config["description"]),
                default_enabled=bool(config["default_enabled"]),
                dependencies=cast(list[str], config["dependencies"]),
                commands=cast(list[str], config["commands"]),
            )
        return None

    def list_installed_features(self) -> list[str]:
        """List features currently installed in the project.

        All features are always installed (not user-selectable).

        Returns:
            List of installed feature names
        """
        return list(SUPPORTED_FEATURES)

    def is_feature_installed(self, feature_name: str) -> bool:
        """Check if a feature is installed.

        Args:
            feature_name: Name of the feature

        Returns:
            True if feature is installed
        """
        return feature_name in self.list_installed_features()

    def get_feature_dependencies(self, feature_name: str) -> list[str]:
        """Get direct dependencies for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of dependency feature names
        """
        manifest = self.get_feature_manifest(feature_name)
        if manifest:
            return manifest.dependencies
        return []

    def get_all_dependencies(self, feature_name: str) -> list[str]:
        """Get all transitive dependencies for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of all dependency feature names (including transitive)
        """
        manifest = self.get_feature_manifest(feature_name)
        if not manifest:
            return []

        all_features = {f.name: f for f in self.list_available_features()}
        return manifest.get_all_dependencies(all_features)

    def resolve_dependencies(self, features: list[str]) -> list[str]:
        """Resolve dependencies for a list of features.

        Adds any missing dependencies and returns features in installation order.

        Args:
            features: List of feature names to install

        Returns:
            List of feature names with dependencies resolved, in correct order
        """
        resolved: set[str] = set()
        result: list[str] = []

        def add_feature(name: str) -> None:
            if name in resolved:
                return

            # Add dependencies first
            deps = self.get_all_dependencies(name)
            for dep in deps:
                if dep not in resolved:
                    add_feature(dep)

            resolved.add(name)
            result.append(name)

        for feature in features:
            add_feature(feature)

        return result

    def get_features_requiring(self, feature_name: str) -> list[str]:
        """Get features that depend on the given feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of feature names that require this feature
        """
        dependents = []
        for manifest in self.list_available_features():
            if feature_name in manifest.dependencies:
                dependents.append(manifest.name)
        return dependents

    def can_remove_feature(self, feature_name: str) -> tuple[bool, list[str]]:
        """Check if a feature can be safely removed.

        Args:
            feature_name: Name of the feature

        Returns:
            Tuple of (can_remove, list_of_blocking_features)
        """
        installed = set(self.list_installed_features())
        dependents = self.get_features_requiring(feature_name)
        blocking = [d for d in dependents if d in installed]
        return (len(blocking) == 0, blocking)

    def get_feature_commands_dir(self, feature_name: str) -> Path:
        """Get commands directory for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            Path to feature's commands directory
        """
        feature_dir = _feature_name_to_dir(feature_name)
        return self.package_features_dir / feature_dir / "commands"

    def get_feature_templates_dir(self, feature_name: str) -> Path:
        """Get templates directory for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            Path to feature's templates directory
        """
        feature_dir = _feature_name_to_dir(feature_name)
        return self.package_features_dir / feature_dir / "templates"

    def get_feature_commands(self, feature_name: str) -> list[str]:
        """Get list of command names for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of command names (e.g., ['rfc-create', 'rfc-list'])
        """
        manifest = self.get_feature_manifest(feature_name)
        if manifest:
            return manifest.commands
        return []

    def install_feature(self, feature_name: str, agents: list[str]) -> dict[str, list[str]]:
        """Install a feature for the given agents.

        This installs the feature's commands to each agent's native directory.
        Does NOT handle dependencies - call resolve_dependencies first.

        Args:
            feature_name: Name of the feature to install
            agents: List of agent types to install for

        Returns:
            Dictionary with installation results:
            {
                'commands_installed': ['rfc-create', 'rfc-list'],
                'templates_copied': ['engineering.md', 'architecture.md'],
                'agents': ['claude', 'copilot'],
                'pip_packages_installed': ['fastapi>=0.109.0', ...]
            }
        """
        results: dict[str, Any] = {
            "commands_installed": [],
            "templates_copied": [],
            "agents": [],
            "pip_packages_installed": [],
            "prerequisites_checked": False,
            "prerequisites_warnings": [],
        }

        manifest = self.get_feature_manifest(feature_name)
        if not manifest:
            return results

        # Check prerequisites if declared
        if manifest.prerequisites:
            prereq_result = self._check_prerequisites(manifest.prerequisites)
            results["prerequisites_checked"] = True
            results["prerequisites_warnings"] = prereq_result.get("warnings", [])

            # If required prerequisites are missing, we still continue but warn
            # The feature's fallback mechanisms should handle missing optional deps
            if prereq_result.get("missing"):
                from open_agent_kit.utils import print_warning

                for missing in prereq_result["missing"]:
                    print_warning(f"\nMissing prerequisite: {missing['name']}")
                    if missing.get("instructions"):
                        print_warning(f"Installation instructions:\n{missing['instructions']}")

        # Install pip packages if declared
        if manifest.pip_packages:
            packages_installed = self._install_pip_packages(manifest.pip_packages, feature_name)
            if packages_installed:
                results["pip_packages_installed"] = manifest.pip_packages
            else:
                # Pip package installation failed - this is fatal for the feature
                from open_agent_kit.utils import print_error

                print_error(
                    f"Failed to install required packages for '{feature_name}'. "
                    f"The feature cannot function without these dependencies."
                )
                print_error(
                    "You can try installing manually: "
                    f"pip install {' '.join(manifest.pip_packages)}"
                )
                raise RuntimeError(
                    f"Required pip packages for feature '{feature_name}' failed to install"
                )

        # Add gitignore entries if declared
        if manifest.gitignore:
            added = add_gitignore_entries(
                self.project_root,
                manifest.gitignore,
                section_comment=f"open-agent-kit: {manifest.display_name}",
            )
            if added:
                results["gitignore_added"] = added

        # Install commands for each agent
        # Commands are sub-agents (specialized expertise), separate from skills (domain knowledge)
        # All agents receive commands - they are not a fallback for skill-less agents
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService(self.project_root)

        commands_dir = self.get_feature_commands_dir(feature_name)

        for agent_type in agents:
            agent_commands_dir = agent_service.create_agent_commands_dir(agent_type)

            for command_name in manifest.commands:
                # Read template from feature's commands directory
                template_file = commands_dir / f"oak.{command_name}.md"
                if not template_file.exists():
                    continue

                content = read_file(template_file)

                # Render with agent-specific context if command uses Jinja2 syntax
                rendered_content = self.template_service.render_command_for_agent(
                    content, agent_type
                )

                # Write to agent's commands directory with proper extension
                filename = agent_service.get_command_filename(agent_type, command_name)
                file_path = agent_commands_dir / filename

                write_file(file_path, rendered_content)

                # Record the created file for smart removal later
                self.state_service.record_created_file(file_path, rendered_content)

                # Record the directory if this is the first file we're adding to it
                self.state_service.record_created_directory(agent_commands_dir)

                if command_name not in results["commands_installed"]:
                    results["commands_installed"].append(command_name)

            results["agents"].append(agent_type)

        # Note: We no longer copy commands/templates to .oak/features/
        # Feature assets are read directly from the installed package.
        # Only agent-native directories receive the rendered commands.

        # All features are always installed (not user-selectable)
        # Check state to determine if this is a fresh install for hooks
        config = self.config_service.load_config()
        was_disabled = not self.state_service.is_feature_initialized(feature_name)
        if was_disabled:
            self.state_service.mark_feature_initialized(feature_name)

        # Trigger feature enabled hook if this is a new install
        if was_disabled:
            try:
                hook_result = self.trigger_feature_enabled_hook(feature_name)
                # Check if any hooks failed and surface the error
                for f_name, result in hook_result.items():
                    if not result.get("success"):
                        from open_agent_kit.utils import print_warning

                        error = result.get("error", "Unknown error")
                        print_warning(f"Feature hook for {f_name} failed: {error}")
                        logger.warning(f"Feature hook for {f_name} failed: {error}")
            except Exception as e:
                from open_agent_kit.utils import print_warning

                print_warning(f"Failed to run initialization hook for {feature_name}: {e}")
                logger.warning(f"Failed to trigger feature enabled hook for {feature_name}: {e}")

        # Auto-install associated skills if enabled
        if was_disabled and config.skills.auto_install:
            try:
                from open_agent_kit.services.skill_service import SkillService

                skill_service = SkillService(self.project_root)
                skill_results = skill_service.install_skills_for_feature(feature_name)
                if skill_results.get("skills_installed"):
                    results["skills_installed"] = skill_results["skills_installed"]
            except Exception as e:
                logger.warning(f"Failed to auto-install skills for {feature_name}: {e}")

        return results

    def remove_feature(
        self, feature_name: str, agents: list[str], remove_config: bool = False
    ) -> dict[str, list[str]]:
        """Remove a feature from the project.

        Does NOT check dependencies - call can_remove_feature first.

        Args:
            feature_name: Name of the feature to remove
            agents: List of agent types to remove from
            remove_config: Whether to remove feature config from config.yaml

        Returns:
            Dictionary with removal results
        """
        results: dict[str, list[str]] = {
            "commands_removed": [],
            "templates_removed": [],
            "agents": [],
        }

        manifest = self.get_feature_manifest(feature_name)
        if not manifest:
            return results

        # Remove commands from each agent
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService(self.project_root)

        for agent_type in agents:
            agent_commands_dir = agent_service.get_agent_commands_dir(agent_type)
            if not agent_commands_dir.exists():
                continue

            for command_name in manifest.commands:
                filename = agent_service.get_command_filename(agent_type, command_name)
                file_path = agent_commands_dir / filename

                if file_path.exists():
                    file_path.unlink()
                    if command_name not in results["commands_removed"]:
                        results["commands_removed"].append(command_name)

            results["agents"].append(agent_type)

        # Note: We no longer store feature assets in .oak/features/
        # Nothing to clean up there - feature assets are in the package.

        # Remove gitignore entries if declared
        if manifest.gitignore:
            removed_entries = remove_gitignore_entries(
                self.project_root,
                manifest.gitignore,
            )
            if removed_entries:
                results["gitignore_removed"] = removed_entries

        # Remove associated skills
        try:
            from open_agent_kit.services.skill_service import SkillService

            skill_service = SkillService(self.project_root)
            skill_results = skill_service.remove_skills_for_feature(feature_name)
            if skill_results.get("skills_removed"):
                results["skills_removed"] = skill_results["skills_removed"]
        except Exception as e:
            logger.warning(f"Failed to remove skills for {feature_name}: {e}")

        # Trigger feature disabled hook BEFORE updating state
        # All features are always installed, but track initialization state
        was_enabled = self.state_service.is_feature_initialized(feature_name)
        if was_enabled:
            try:
                self.trigger_feature_disabled_hook(feature_name)
            except Exception as e:
                logger.warning(f"Failed to trigger feature disabled hook for {feature_name}: {e}")

        # Update state to mark feature as uninitialized
        if was_enabled:
            self.state_service.unmark_feature_initialized(feature_name)

        return results

    def refresh_features(self) -> dict[str, Any]:
        """Refresh all installed features by re-rendering with current config.

        This re-renders command templates using current agent_capabilities,
        allowing users to update capabilities in config.yaml and apply changes
        without a package upgrade.

        Returns:
            Dictionary with refresh results:
            - features_refreshed: list of feature names
            - commands_rendered: dict of feature -> list of commands
            - agents: list of agents updated
        """
        results: dict[str, Any] = {
            "features_refreshed": [],
            "commands_rendered": {},
            "agents": [],
        }

        # Get installed features and configured agents
        # All features are always installed
        config = self.config_service.load_config()
        installed_features = SUPPORTED_FEATURES
        agents = config.agents

        if not agents:
            return results

        results["agents"] = agents

        # Re-render each feature for all agents
        for feature_name in installed_features:
            manifest = self.get_feature_manifest(feature_name)
            if not manifest:
                continue

            feature_results = self.install_feature(feature_name, agents)
            results["features_refreshed"].append(feature_name)
            results["commands_rendered"][feature_name] = feature_results.get(
                "commands_installed", []
            )

        return results

    # =========================================================================
    # Lifecycle Hook System
    # =========================================================================
    #
    # OAK defines system-level lifecycle events that features can subscribe to.
    # Features declare subscriptions in their manifest.yaml under 'hooks:'.
    # When an event occurs, OAK calls each subscribed feature's handler.
    #
    # Hook spec format: "feature:action" (e.g., "constitution:sync_agent_files")
    # =========================================================================

    def _trigger_hook(
        self, hook_name: str, features: list[str] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Generic hook trigger that calls subscribed features.

        Args:
            hook_name: Name of the hook (e.g., "on_agents_changed")
            features: List of features to check (defaults to all installed)
            **kwargs: Arguments to pass to hook handlers

        Returns:
            Dictionary with hook execution results per feature
        """
        results: dict[str, Any] = {}

        target_features = features if features is not None else self.list_installed_features()

        for feature_name in target_features:
            manifest = self.get_feature_manifest(feature_name)
            if not manifest:
                continue

            # Get the hook spec from the manifest using getattr
            hook_spec = getattr(manifest.hooks, hook_name, None)
            if not hook_spec:
                continue

            try:
                hook_result = self._execute_hook(hook_spec, **kwargs)
                results[feature_name] = {"success": True, "result": hook_result}
            except Exception as e:
                results[feature_name] = {"success": False, "error": str(e)}

        return results

    # --- Agent Lifecycle ---

    def trigger_agents_changed_hooks(
        self, agents_added: list[str], agents_removed: list[str]
    ) -> dict[str, Any]:
        """Trigger on_agents_changed hooks for all installed features.

        Called when agents are added or removed via 'oak init'.

        Args:
            agents_added: List of newly added agent types
            agents_removed: List of removed agent types

        Returns:
            Dictionary with hook execution results per feature
        """
        return self._trigger_hook(
            "on_agents_changed",
            agents_added=agents_added,
            agents_removed=agents_removed,
        )

    # --- IDE Lifecycle ---

    def trigger_ides_changed_hooks(
        self, ides_added: list[str], ides_removed: list[str]
    ) -> dict[str, Any]:
        """Trigger on_ides_changed hooks for all installed features.

        Called when IDEs are added or removed via 'oak init'.

        Args:
            ides_added: List of newly added IDE types
            ides_removed: List of removed IDE types

        Returns:
            Dictionary with hook execution results per feature
        """
        return self._trigger_hook(
            "on_ides_changed",
            ides_added=ides_added,
            ides_removed=ides_removed,
        )

    # --- Upgrade Lifecycle ---

    def trigger_pre_upgrade_hooks(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Trigger on_pre_upgrade hooks before upgrade applies changes.

        Called at the start of 'oak upgrade' before any changes are made.
        Features can use this to prepare or backup data.

        Args:
            plan: The upgrade plan from UpgradeService.plan_upgrade()

        Returns:
            Dictionary with hook execution results per feature
        """
        return self._trigger_hook("on_pre_upgrade", plan=plan)

    def trigger_post_upgrade_hooks(self, results: dict[str, Any]) -> dict[str, Any]:
        """Trigger on_post_upgrade hooks after upgrade completes.

        Called after 'oak upgrade' completes successfully.
        Features can use this to migrate data or notify users.

        Args:
            results: The upgrade results from UpgradeService.execute_upgrade()

        Returns:
            Dictionary with hook execution results per feature
        """
        return self._trigger_hook("on_post_upgrade", results=results)

    # --- Removal Lifecycle ---

    def trigger_pre_remove_hooks(self) -> dict[str, Any]:
        """Trigger on_pre_remove hooks before oak remove starts.

        Called at the start of 'oak remove' before any files are removed.
        Features can use this to clean up external resources.

        Returns:
            Dictionary with hook execution results per feature
        """
        return self._trigger_hook("on_pre_remove")

    # --- Feature Lifecycle ---

    def trigger_feature_enabled_hook(self, feature_name: str) -> dict[str, Any]:
        """Trigger on_feature_enabled hook for a specific feature.

        Called when a feature is enabled (added to the project).

        Args:
            feature_name: Name of the feature being enabled

        Returns:
            Dictionary with hook execution result for this feature
        """
        return self._trigger_hook(
            "on_feature_enabled",
            features=[feature_name],
            feature_name=feature_name,
        )

    def trigger_feature_disabled_hook(self, feature_name: str) -> dict[str, Any]:
        """Trigger on_feature_disabled hook for a specific feature.

        Called when a feature is about to be disabled (removed from project).

        Args:
            feature_name: Name of the feature being disabled

        Returns:
            Dictionary with hook execution result for this feature
        """
        # Get configured agents so cleanup can remove hooks
        config = self.config_service.load_config()
        return self._trigger_hook(
            "on_feature_disabled",
            features=[feature_name],
            feature_name=feature_name,
            agents=config.agents,
        )

    # --- Project Lifecycle ---

    def trigger_init_complete_hooks(
        self, is_fresh_install: bool, agents: list[str], features: list[str]
    ) -> dict[str, Any]:
        """Trigger on_init_complete hooks after oak init finishes.

        Called after 'oak init' completes (both fresh install and updates).

        Args:
            is_fresh_install: True if this was a fresh install, False if update
            agents: List of configured agents
            features: List of enabled features

        Returns:
            Dictionary with hook execution results per feature
        """
        return self._trigger_hook(
            "on_init_complete",
            is_fresh_install=is_fresh_install,
            agents=agents,
            features=features,
        )

    # --- Hook Execution ---

    def _execute_hook(self, hook_spec: str, **kwargs: Any) -> Any:
        """Execute a feature hook by its specification.

        Hook spec format: "feature:action" (e.g., "constitution:sync_agent_files")

        Args:
            hook_spec: Hook specification string
            **kwargs: Arguments to pass to the hook handler

        Returns:
            Result from the hook handler

        Raises:
            ValueError: If hook spec is invalid or handler not found
        """
        if ":" not in hook_spec:
            raise ValueError(f"Invalid hook spec format: {hook_spec} (expected 'feature:action')")

        feature_name, action = hook_spec.split(":", 1)

        # Dispatch to appropriate service based on feature
        if feature_name == "constitution":
            return self._execute_constitution_hook(action, **kwargs)
        elif feature_name == "rfc":
            return self._execute_rfc_hook(action, **kwargs)
        elif feature_name == "codebase-intelligence":
            return self._execute_codebase_intelligence_hook(action, **kwargs)
        else:
            raise ValueError(f"Unknown feature for hook: {feature_name}")

    def _execute_constitution_hook(self, action: str, **kwargs: Any) -> Any:
        """Execute a constitution feature hook.

        Args:
            action: Hook action name
            **kwargs: Arguments for the action

        Returns:
            Result from the action
        """
        from open_agent_kit.features.rules_management.constitution import ConstitutionService

        constitution_service = ConstitutionService(self.project_root)

        if action == "sync_agent_files":
            return constitution_service.sync_agent_instruction_files(
                agents_added=kwargs.get("agents_added", []),
                agents_removed=kwargs.get("agents_removed", []),
            )
        else:
            raise ValueError(f"Unknown constitution hook action: {action}")

    def _execute_rfc_hook(self, action: str, **kwargs: Any) -> Any:
        """Execute an RFC feature hook.

        Args:
            action: Hook action name
            **kwargs: Arguments for the action

        Returns:
            Result from the action
        """
        # RFC hooks can be added here as needed
        raise ValueError(f"Unknown rfc hook action: {action}")

    def _execute_codebase_intelligence_hook(self, action: str, **kwargs: Any) -> Any:
        """Execute a codebase-intelligence feature hook.

        Args:
            action: Hook action name
            **kwargs: Arguments for the action

        Returns:
            Result from the action
        """
        from open_agent_kit.features.codebase_intelligence.service import execute_hook

        # Map kwargs to expected format for certain hooks
        if action == "update_agent_hooks":
            # on_agents_changed passes agents_added and agents_removed
            # We need to:
            # 1. Update hooks for current agents
            # 2. Remove hooks for removed agents
            config = self.config_service.load_config()
            kwargs["agents"] = config.agents

            # First, remove hooks for removed agents
            agents_removed = kwargs.get("agents_removed", [])
            if agents_removed:
                execute_hook("remove_agent_hooks", self.project_root, agents_removed=agents_removed)
                execute_hook("remove_mcp_servers", self.project_root, agents_removed=agents_removed)

        return execute_hook(action, self.project_root, **kwargs)


def get_feature_service(project_root: Path | None = None) -> FeatureService:
    """Get a FeatureService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        FeatureService instance
    """
    return FeatureService(project_root)
