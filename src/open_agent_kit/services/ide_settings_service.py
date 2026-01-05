"""Service for managing IDE settings installation and upgrades."""

import json
from pathlib import Path
from typing import Any

from open_agent_kit.config.paths import (
    CURSOR_SETTINGS_FILE,
    FEATURES_DIR,
    IDE_SETTINGS_TEMPLATES,
    VSCODE_SETTINGS_FILE,
)
from open_agent_kit.constants import (
    IDE_SETTINGS_JSON_KEY_AUTO_APPROVE,
    IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS,
    IDE_SETTINGS_OAK_AUTO_APPROVE_KEYS,
    IDE_SETTINGS_OAK_PROMPT_PREFIX,
)
from open_agent_kit.utils import (
    cleanup_empty_directories,
    ensure_dir,
    file_exists,
    read_file,
    write_file,
)


class IDESettingsService:
    """Service for installing and upgrading IDE settings."""

    def __init__(self, project_root: Path | None = None):
        """Initialize IDE settings service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()

        # Package features/core/ide directory (source of IDE templates)
        # Templates are read directly from here - no copying to .oak/
        self.package_ide_dir = (
            Path(__file__).parent.parent.parent.parent / FEATURES_DIR / "core" / "ide"
        )

        # Map IDE names to their settings file paths
        self.settings_files = {
            "vscode": self.project_root / VSCODE_SETTINGS_FILE,
            "cursor": self.project_root / CURSOR_SETTINGS_FILE,
        }

    def install_settings(self, ide: str, force: bool = False) -> bool:
        """Install IDE settings from template.

        Merges template settings with existing settings if file exists.

        Args:
            ide: IDE name (vscode, cursor)
            force: If True, overwrite existing settings

        Returns:
            True if settings were installed/updated, False otherwise

        Raises:
            ValueError: If IDE is not supported
            FileNotFoundError: If template not found
        """
        if ide not in IDE_SETTINGS_TEMPLATES:
            raise ValueError(f"Unsupported IDE: {ide}")

        settings_file = self.settings_files[ide]
        template_name = IDE_SETTINGS_TEMPLATES[ide]

        # Get template content from features/core/ide directory in the package
        # Templates are read directly from the package - no copying to .oak/
        template_filename = Path(template_name).name
        package_template_path = self.package_ide_dir / template_filename

        try:
            if not package_template_path.exists():
                raise FileNotFoundError(f"Template not found: {package_template_path}")
            template_content = read_file(package_template_path)
            template_settings = json.loads(template_content)
        except FileNotFoundError as err:
            raise FileNotFoundError(f"Template not found: {template_name}") from err
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in template {template_name}: {e}") from e

        # If file doesn't exist, create it
        if not file_exists(settings_file):
            ensure_dir(settings_file.parent)
            self._write_settings(settings_file, template_settings)
            return True

        # File exists - merge settings unless force
        if force:
            self._write_settings(settings_file, template_settings)
            return True

        # Merge with existing settings
        existing_settings = self._read_settings(settings_file)
        merged_settings = self._merge_settings(existing_settings, template_settings)

        # Remove orphaned open-agent-kit keys (keys we added before but removed from template)
        cleaned_settings = self._remove_orphaned_oak_keys(merged_settings, template_settings)

        # Only write if settings changed
        if cleaned_settings != existing_settings:
            self._write_settings(settings_file, cleaned_settings)
            return True

        return False

    def needs_upgrade(self, ide: str) -> bool:
        """Check if IDE settings need upgrading.

        Args:
            ide: IDE name (vscode, cursor)

        Returns:
            True if settings need upgrading, False otherwise
        """
        if ide not in IDE_SETTINGS_TEMPLATES:
            return False

        settings_file = self.settings_files[ide]
        if not file_exists(settings_file):
            # File doesn't exist - needs installation
            return True

        # Compare with template
        template_name = IDE_SETTINGS_TEMPLATES[ide]
        template_filename = Path(template_name).name
        template_path = self.package_ide_dir / template_filename
        try:
            if not template_path.exists():
                return False
            template_content = read_file(template_path)
            template_settings = json.loads(template_content)
        except (FileNotFoundError, json.JSONDecodeError):
            return False

        existing_settings = self._read_settings(settings_file)

        # Check if template adds new keys
        merged_settings = self._merge_settings(existing_settings, template_settings)
        if merged_settings != existing_settings:
            return True

        # Check if user has open-agent-kit keys that were removed from template
        # This handles when we remove settings from the template
        if self._has_orphaned_oak_keys(existing_settings, template_settings):
            return True

        return False

    def get_upgradeable_settings(self) -> list[str]:
        """Get list of IDE settings that need upgrading.

        Returns:
            List of IDE names that need upgrading
        """
        upgradeable = []
        for ide in IDE_SETTINGS_TEMPLATES.keys():
            if self.needs_upgrade(ide):
                upgradeable.append(ide)
        return upgradeable

    def _read_settings(self, settings_file: Path) -> dict[str, Any]:
        """Read and parse JSON settings file.

        Args:
            settings_file: Path to settings file

        Returns:
            Parsed settings dictionary
        """
        try:
            content = read_file(settings_file)
            result: dict[str, Any] = json.loads(content)
            return result
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_settings(self, settings_file: Path, settings: dict[str, Any]) -> None:
        """Write settings to JSON file with proper formatting.

        Args:
            settings_file: Path to settings file
            settings: Settings dictionary to write
        """
        content = json.dumps(settings, indent=2, ensure_ascii=False)
        # Add trailing newline for better git diffs
        content += "\n"
        write_file(settings_file, content)

    def _merge_settings(self, existing: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
        """Merge template settings into existing settings.

        Recursively merges nested dictionaries. Template values are added if missing,
        but existing user values are preserved.

        Args:
            existing: Existing settings dictionary
            template: Template settings to merge in

        Returns:
            Merged settings dictionary
        """
        result = existing.copy()

        for key, value in template.items():
            if key not in result:
                # Key doesn't exist - add it
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                # Both are dicts - merge recursively
                result[key] = self._merge_settings(result[key], value)
            # else: key exists and is not dict - keep existing value

        return result

    def _has_orphaned_oak_keys(self, existing: dict[str, Any], template: dict[str, Any]) -> bool:
        """Check if existing settings have open-agent-kit keys not in template.

        This detects when we've removed settings from our template that are
        still in the user's file.

        Args:
            existing: Existing settings dictionary
            template: Template settings dictionary

        Returns:
            True if orphaned open-agent-kit keys exist, False otherwise
        """
        # Check prompt recommendations for oak.* keys
        if IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS in existing:
            existing_recs = existing[IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS]
            template_recs = template.get(IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS, {})

            if isinstance(existing_recs, dict):
                # Find oak.* keys in existing that aren't in template
                for key in existing_recs.keys():
                    if key.startswith(IDE_SETTINGS_OAK_PROMPT_PREFIX) and key not in template_recs:
                        return True

        # Check auto-approve for open-agent-kit specific keys
        if IDE_SETTINGS_JSON_KEY_AUTO_APPROVE in existing:
            existing_approve = existing[IDE_SETTINGS_JSON_KEY_AUTO_APPROVE]
            template_approve = template.get(IDE_SETTINGS_JSON_KEY_AUTO_APPROVE, {})

            if isinstance(existing_approve, dict):
                for key in IDE_SETTINGS_OAK_AUTO_APPROVE_KEYS:
                    if key in existing_approve and key not in template_approve:
                        return True

        return False

    def _remove_orphaned_oak_keys(
        self, settings: dict[str, Any], template: dict[str, Any]
    ) -> dict[str, Any]:
        """Remove open-agent-kit keys from settings that are no longer in template.

        This cleans up keys we added in previous versions but have now removed
        from the template, while preserving all user's custom settings.

        Args:
            settings: Current settings dictionary
            template: Template settings dictionary

        Returns:
            Cleaned settings dictionary
        """
        result = settings.copy()

        # Clean prompt recommendations - remove oak.* keys not in template
        if IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS in result:
            recommendations = result[IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS]
            template_recs = template.get(IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS, {})

            if isinstance(recommendations, dict):
                keys_to_remove = []
                for key in recommendations.keys():
                    # Remove oak.* keys that aren't in template
                    if key.startswith(IDE_SETTINGS_OAK_PROMPT_PREFIX) and key not in template_recs:
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    del recommendations[key]

                # Remove section if empty
                if not recommendations:
                    del result[IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS]

        # Clean auto-approve - remove open-agent-kit keys not in template
        if IDE_SETTINGS_JSON_KEY_AUTO_APPROVE in result:
            auto_approve = result[IDE_SETTINGS_JSON_KEY_AUTO_APPROVE]
            template_approve = template.get(IDE_SETTINGS_JSON_KEY_AUTO_APPROVE, {})

            if isinstance(auto_approve, dict):
                keys_to_remove = []
                for key in IDE_SETTINGS_OAK_AUTO_APPROVE_KEYS:
                    if key in auto_approve and key not in template_approve:
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    del auto_approve[key]

                # Remove section if empty
                if not auto_approve:
                    del result[IDE_SETTINGS_JSON_KEY_AUTO_APPROVE]

        return result

    def remove_settings(self, ide: str) -> bool:
        """Remove open-agent-kit settings from IDE settings file.

        Only removes open-agent-kit specific settings, preserving all other user settings.

        Args:
            ide: IDE name (e.g., "vscode", "cursor")

        Returns:
            True if settings were removed, False if no changes needed
        """
        if ide not in IDE_SETTINGS_TEMPLATES:
            return False

        settings_file = self.settings_files.get(ide)
        if not settings_file:
            return False

        if not settings_file.exists():
            # Settings file doesn't exist, nothing to remove
            return False

        # Read existing settings
        current_settings = self._read_settings(settings_file)
        if not current_settings:
            return False

        modified = False

        # Remove open-agent-kit entries from prompt recommendations
        if IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS in current_settings:
            recommendations = current_settings[IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS]
            if isinstance(recommendations, dict):
                # Remove all keys starting with open-agent-kit prefix
                keys_to_remove = [
                    k
                    for k in recommendations.keys()
                    if k.startswith(IDE_SETTINGS_OAK_PROMPT_PREFIX)
                ]
                for key in keys_to_remove:
                    del recommendations[key]
                    modified = True

                # If the section is now empty, remove it entirely
                if not recommendations:
                    del current_settings[IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS]
                    modified = True

        # Remove open-agent-kit entries from auto-approve
        if IDE_SETTINGS_JSON_KEY_AUTO_APPROVE in current_settings:
            auto_approve = current_settings[IDE_SETTINGS_JSON_KEY_AUTO_APPROVE]
            if isinstance(auto_approve, dict):
                # Remove open-agent-kit specific entries
                for key in IDE_SETTINGS_OAK_AUTO_APPROVE_KEYS:
                    if key in auto_approve:
                        del auto_approve[key]
                        modified = True

                # If the section is now empty, remove it entirely
                if not auto_approve:
                    del current_settings[IDE_SETTINGS_JSON_KEY_AUTO_APPROVE]
                    modified = True

        if modified:
            # Write updated settings back
            if current_settings:
                # Still have user settings, write them
                self._write_settings(settings_file, current_settings)
            else:
                # No settings left, delete the file
                try:
                    settings_file.unlink()
                    # Clean up empty parent directory if we created it
                    cleanup_empty_directories(settings_file.parent, self.project_root)
                except Exception:
                    pass

        return modified


def get_ide_settings_service(project_root: Path | None = None) -> IDESettingsService:
    """Get an IDESettingsService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        IDESettingsService instance
    """
    return IDESettingsService(project_root)
