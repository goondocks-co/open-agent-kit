"""Tests for IDE settings service."""

import json
from pathlib import Path

import pytest

from open_agent_kit.services.ide_settings_service import IDESettingsService


@pytest.fixture
def ide_settings_service(temp_project_dir: Path) -> IDESettingsService:
    """Create IDE settings service for testing.

    Args:
        temp_project_dir: Temporary project directory fixture

    Returns:
        IDE settings service instance
    """
    return IDESettingsService(project_root=temp_project_dir)


def test_install_vscode_settings_new_file(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test installing VSCode settings when no file exists."""
    # Install settings
    result = ide_settings_service.install_settings("vscode")

    # Should return True (installed)
    assert result is True

    # Settings file should exist
    settings_file = temp_project_dir / ".vscode" / "settings.json"
    assert settings_file.exists()

    # Read and verify content
    with open(settings_file) as f:
        settings = json.load(f)

    # Should have the expected keys
    assert "chat.promptFilesRecommendations" in settings
    assert "chat.tools.terminal.autoApprove" in settings

    # Verify specific values
    assert settings["chat.promptFilesRecommendations"]["oak.rfc-create"] is True
    assert settings["chat.tools.terminal.autoApprove"][".oak/scripts/bash/"] is True


def test_install_cursor_settings_new_file(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test installing Cursor settings when no file exists."""
    # Install settings
    result = ide_settings_service.install_settings("cursor")

    # Should return True (installed)
    assert result is True

    # Settings file should exist
    settings_file = temp_project_dir / ".cursor" / "settings.json"
    assert settings_file.exists()

    # Read and verify content
    with open(settings_file) as f:
        settings = json.load(f)

    # Should have the expected keys
    assert "chat.promptFilesRecommendations" in settings
    assert "chat.tools.terminal.autoApprove" in settings


def test_install_settings_merge_with_existing(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test that installation merges with existing settings."""
    # Create existing settings file with custom settings
    settings_file = temp_project_dir / ".vscode" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    existing_settings = {
        "editor.fontSize": 14,
        "chat.promptFilesRecommendations": {
            "custom.command": True,
        },
    }

    with open(settings_file, "w") as f:
        json.dump(existing_settings, f)

    # Install settings
    result = ide_settings_service.install_settings("vscode")

    # Should return True (updated)
    assert result is True

    # Read merged settings
    with open(settings_file) as f:
        merged = json.load(f)

    # Should preserve existing custom settings
    assert merged["editor.fontSize"] == 14
    assert merged["chat.promptFilesRecommendations"]["custom.command"] is True

    # Should add new settings from template
    assert merged["chat.promptFilesRecommendations"]["oak.rfc-create"] is True
    assert "chat.tools.terminal.autoApprove" in merged


def test_install_settings_preserves_user_values(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test that existing user values are preserved during merge."""
    # Create existing settings with overlapping keys
    settings_file = temp_project_dir / ".vscode" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    existing_settings = {
        "chat.tools.terminal.autoApprove": {
            ".oak/scripts/bash/": False,  # User explicitly disabled
            "custom/scripts/": True,  # User's custom entry
        },
    }

    with open(settings_file, "w") as f:
        json.dump(existing_settings, f)

    # Install settings
    ide_settings_service.install_settings("vscode")

    # Read merged settings
    with open(settings_file) as f:
        merged = json.load(f)

    # Should preserve user's explicit False value
    assert merged["chat.tools.terminal.autoApprove"][".oak/scripts/bash/"] is False

    # Should preserve user's custom entry
    assert merged["chat.tools.terminal.autoApprove"]["custom/scripts/"] is True

    # Should add new entry from template
    assert ".oak/scripts/powershell/" in merged["chat.tools.terminal.autoApprove"]


def test_install_settings_force_overwrites(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test that force flag overwrites existing settings."""
    # Create existing settings
    settings_file = temp_project_dir / ".vscode" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    existing_settings = {
        "editor.fontSize": 14,
        "custom.setting": "value",
    }

    with open(settings_file, "w") as f:
        json.dump(existing_settings, f)

    # Install with force
    result = ide_settings_service.install_settings("vscode", force=True)

    # Should return True (overwritten)
    assert result is True

    # Read settings
    with open(settings_file) as f:
        settings = json.load(f)

    # Should not have old custom settings
    assert "editor.fontSize" not in settings
    assert "custom.setting" not in settings

    # Should have template settings
    assert "chat.promptFilesRecommendations" in settings


def test_install_settings_no_change_returns_false(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test that installing when settings are up-to-date returns False."""
    # Install settings first time
    ide_settings_service.install_settings("vscode")

    # Install again - should return False (no change)
    result = ide_settings_service.install_settings("vscode")
    assert result is False


def test_needs_upgrade_new_file(ide_settings_service: IDESettingsService) -> None:
    """Test needs_upgrade returns True when file doesn't exist."""
    result = ide_settings_service.needs_upgrade("vscode")
    assert result is True


def test_needs_upgrade_after_install(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test needs_upgrade returns False after installation."""
    # Install settings
    ide_settings_service.install_settings("vscode")

    # Should not need upgrade
    result = ide_settings_service.needs_upgrade("vscode")
    assert result is False


def test_needs_upgrade_with_custom_settings(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test needs_upgrade returns True when template has new settings."""
    # Create settings file with incomplete template settings
    settings_file = temp_project_dir / ".vscode" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    incomplete_settings = {
        "chat.promptFilesRecommendations": {
            "oak.rfc-create": True,
        },
        # Missing chat.tools.terminal.autoApprove
    }

    with open(settings_file, "w") as f:
        json.dump(incomplete_settings, f)

    # Should need upgrade (missing keys)
    result = ide_settings_service.needs_upgrade("vscode")
    assert result is True


def test_get_upgradeable_settings(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test getting list of IDE settings that need upgrading."""
    # Initially both should need installation
    upgradeable = ide_settings_service.get_upgradeable_settings()
    assert "vscode" in upgradeable
    assert "cursor" in upgradeable

    # Install vscode
    ide_settings_service.install_settings("vscode")

    # Only cursor should need upgrade now
    upgradeable = ide_settings_service.get_upgradeable_settings()
    assert "vscode" not in upgradeable
    assert "cursor" in upgradeable

    # Install cursor
    ide_settings_service.install_settings("cursor")

    # Nothing should need upgrade
    upgradeable = ide_settings_service.get_upgradeable_settings()
    assert len(upgradeable) == 0


def test_install_invalid_ide(ide_settings_service: IDESettingsService) -> None:
    """Test that installing invalid IDE raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported IDE"):
        ide_settings_service.install_settings("invalid_ide")


def test_needs_upgrade_invalid_ide(ide_settings_service: IDESettingsService) -> None:
    """Test that checking invalid IDE returns False."""
    result = ide_settings_service.needs_upgrade("invalid_ide")
    assert result is False


def test_settings_file_has_trailing_newline(
    ide_settings_service: IDESettingsService, temp_project_dir: Path
) -> None:
    """Test that written settings file has trailing newline for better git diffs."""
    # Install settings
    ide_settings_service.install_settings("vscode")

    # Read file as raw text
    settings_file = temp_project_dir / ".vscode" / "settings.json"
    content = settings_file.read_text()

    # Should end with newline
    assert content.endswith("\n")


def test_merge_settings_nested_dicts(ide_settings_service: IDESettingsService) -> None:
    """Test that merge_settings handles nested dictionaries correctly."""
    existing = {
        "level1": {
            "level2": {
                "existing_key": "existing_value",
                "shared_key": "user_value",
            },
        },
    }

    template = {
        "level1": {
            "level2": {
                "new_key": "new_value",
                "shared_key": "template_value",
            },
        },
    }

    # Use private method directly for testing
    merged = ide_settings_service._merge_settings(existing, template)

    # Should have both keys at level2
    assert merged["level1"]["level2"]["existing_key"] == "existing_value"
    assert merged["level1"]["level2"]["new_key"] == "new_value"

    # Should preserve user's value for shared key
    assert merged["level1"]["level2"]["shared_key"] == "user_value"


def test_merge_settings_non_dict_values(ide_settings_service: IDESettingsService) -> None:
    """Test that merge_settings preserves existing non-dict values."""
    existing = {
        "string_key": "user_string",
        "number_key": 42,
        "bool_key": True,
    }

    template = {
        "string_key": "template_string",
        "number_key": 100,
        "bool_key": False,
        "new_key": "new_value",
    }

    merged = ide_settings_service._merge_settings(existing, template)

    # Should preserve user values
    assert merged["string_key"] == "user_string"
    assert merged["number_key"] == 42
    assert merged["bool_key"] is True

    # Should add new key
    assert merged["new_key"] == "new_value"
