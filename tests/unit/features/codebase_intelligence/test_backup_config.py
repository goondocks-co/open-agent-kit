"""Tests for BackupConfig dataclass.

Tests cover:
- BackupConfig initialization with defaults
- BackupConfig.from_dict() with custom values
- BackupConfig.to_dict() serialization
- Validation: interval_minutes min/max
- Round-trip through CIConfig
- BackupConfig wired into USER_CLASSIFIED_PATHS
"""

import pytest

from open_agent_kit.features.codebase_intelligence.config import (
    USER_CLASSIFIED_PATHS,
    BackupConfig,
    CIConfig,
    _split_by_classification,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    BACKUP_AUTO_ENABLED_DEFAULT,
    BACKUP_CONFIG_KEY,
    BACKUP_INCLUDE_ACTIVITIES_DEFAULT,
    BACKUP_INTERVAL_MINUTES_DEFAULT,
    BACKUP_INTERVAL_MINUTES_MAX,
    BACKUP_INTERVAL_MINUTES_MIN,
    BACKUP_ON_UPGRADE_DEFAULT,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)

# =============================================================================
# BackupConfig Initialization
# =============================================================================


class TestBackupConfigInit:
    """Test BackupConfig initialization and defaults."""

    def test_init_with_defaults(self):
        """Test default values are applied correctly."""
        config = BackupConfig()
        assert config.auto_enabled is BACKUP_AUTO_ENABLED_DEFAULT
        assert config.include_activities is BACKUP_INCLUDE_ACTIVITIES_DEFAULT
        assert config.interval_minutes == BACKUP_INTERVAL_MINUTES_DEFAULT
        assert config.on_upgrade is BACKUP_ON_UPGRADE_DEFAULT

    def test_init_with_custom_values(self):
        """Test initialization with explicit values."""
        config = BackupConfig(
            auto_enabled=False,
            include_activities=False,
            interval_minutes=60,
            on_upgrade=False,
        )
        assert config.auto_enabled is False
        assert config.include_activities is False
        assert config.interval_minutes == 60
        assert config.on_upgrade is False


# =============================================================================
# BackupConfig Validation
# =============================================================================


class TestBackupConfigValidation:
    """Test BackupConfig validation rules."""

    def test_interval_below_min_raises_error(self):
        """Test that interval_minutes below minimum raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BackupConfig(interval_minutes=BACKUP_INTERVAL_MINUTES_MIN - 1)
        assert "interval_minutes" in str(exc_info.value)
        assert exc_info.value.field == "interval_minutes"

    def test_interval_above_max_raises_error(self):
        """Test that interval_minutes above maximum raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BackupConfig(interval_minutes=BACKUP_INTERVAL_MINUTES_MAX + 1)
        assert "interval_minutes" in str(exc_info.value)
        assert exc_info.value.field == "interval_minutes"

    def test_interval_at_min_is_valid(self):
        """Test that interval_minutes at minimum boundary is accepted."""
        config = BackupConfig(interval_minutes=BACKUP_INTERVAL_MINUTES_MIN)
        assert config.interval_minutes == BACKUP_INTERVAL_MINUTES_MIN

    def test_interval_at_max_is_valid(self):
        """Test that interval_minutes at maximum boundary is accepted."""
        config = BackupConfig(interval_minutes=BACKUP_INTERVAL_MINUTES_MAX)
        assert config.interval_minutes == BACKUP_INTERVAL_MINUTES_MAX


# =============================================================================
# BackupConfig from_dict / to_dict
# =============================================================================


class TestBackupConfigFromDict:
    """Test BackupConfig.from_dict factory method."""

    def test_from_dict_with_empty_dict(self):
        """Test from_dict with empty dictionary uses defaults."""
        config = BackupConfig.from_dict({})
        assert config.auto_enabled is BACKUP_AUTO_ENABLED_DEFAULT
        assert config.include_activities is BACKUP_INCLUDE_ACTIVITIES_DEFAULT
        assert config.interval_minutes == BACKUP_INTERVAL_MINUTES_DEFAULT
        assert config.on_upgrade is BACKUP_ON_UPGRADE_DEFAULT

    def test_from_dict_with_custom_values(self):
        """Test from_dict with fully specified dictionary."""
        data = {
            "auto_enabled": False,
            "include_activities": False,
            "interval_minutes": 120,
            "on_upgrade": False,
        }
        config = BackupConfig.from_dict(data)
        assert config.auto_enabled is False
        assert config.include_activities is False
        assert config.interval_minutes == 120
        assert config.on_upgrade is False

    def test_from_dict_partial_values(self):
        """Test from_dict with partial dictionary fills in defaults."""
        data = {"interval_minutes": 60}
        config = BackupConfig.from_dict(data)
        assert config.interval_minutes == 60
        assert config.auto_enabled is BACKUP_AUTO_ENABLED_DEFAULT
        assert config.include_activities is BACKUP_INCLUDE_ACTIVITIES_DEFAULT

    def test_from_dict_invalid_interval_raises(self):
        """Test from_dict with invalid interval raises ValidationError."""
        with pytest.raises(ValidationError):
            BackupConfig.from_dict({"interval_minutes": 0})


class TestBackupConfigToDict:
    """Test BackupConfig.to_dict serialization."""

    def test_to_dict_contains_all_fields(self):
        """Test that to_dict includes all configuration fields."""
        config = BackupConfig()
        d = config.to_dict()
        assert "auto_enabled" in d
        assert "include_activities" in d
        assert "interval_minutes" in d
        assert "on_upgrade" in d

    def test_to_dict_round_trip(self):
        """Test that to_dict output can recreate the config."""
        original = BackupConfig(
            auto_enabled=False,
            include_activities=False,
            interval_minutes=15,
            on_upgrade=False,
        )
        recreated = BackupConfig.from_dict(original.to_dict())
        assert recreated.auto_enabled == original.auto_enabled
        assert recreated.include_activities == original.include_activities
        assert recreated.interval_minutes == original.interval_minutes
        assert recreated.on_upgrade == original.on_upgrade


# =============================================================================
# BackupConfig in CIConfig
# =============================================================================


class TestBackupConfigInCIConfig:
    """Test BackupConfig wired into CIConfig."""

    def test_ci_config_has_backup_field(self):
        """Test that CIConfig has a backup field with defaults."""
        config = CIConfig()
        assert isinstance(config.backup, BackupConfig)
        assert config.backup.auto_enabled is BACKUP_AUTO_ENABLED_DEFAULT

    def test_ci_config_from_dict_with_backup(self):
        """Test CIConfig.from_dict parses backup section."""
        data = {
            BACKUP_CONFIG_KEY: {
                "auto_enabled": False,
                "interval_minutes": 60,
            }
        }
        config = CIConfig.from_dict(data)
        assert config.backup.auto_enabled is False
        assert config.backup.interval_minutes == 60

    def test_ci_config_from_dict_without_backup(self):
        """Test CIConfig.from_dict uses defaults when backup is absent."""
        config = CIConfig.from_dict({})
        assert config.backup.auto_enabled is BACKUP_AUTO_ENABLED_DEFAULT

    def test_ci_config_to_dict_includes_backup(self):
        """Test CIConfig.to_dict includes the backup section."""
        config = CIConfig()
        d = config.to_dict()
        assert BACKUP_CONFIG_KEY in d
        assert d[BACKUP_CONFIG_KEY]["auto_enabled"] is BACKUP_AUTO_ENABLED_DEFAULT

    def test_ci_config_round_trip_with_backup(self):
        """Test CIConfig round-trip preserves backup settings."""
        original = CIConfig(
            backup=BackupConfig(interval_minutes=10),
        )
        recreated = CIConfig.from_dict(original.to_dict())
        assert recreated.backup.interval_minutes == 10


# =============================================================================
# BackupConfig in USER_CLASSIFIED_PATHS
# =============================================================================


class TestBackupConfigClassification:
    """Test BackupConfig keys in USER_CLASSIFIED_PATHS."""

    def test_backup_user_paths_present(self):
        """Test that backup user-classified paths are registered."""
        assert "backup.auto_enabled" in USER_CLASSIFIED_PATHS
        assert "backup.include_activities" in USER_CLASSIFIED_PATHS
        assert "backup.interval_minutes" in USER_CLASSIFIED_PATHS

    def test_backup_split_classification(self):
        """Test that backup section splits into user and project parts."""
        ci_dict = CIConfig().to_dict()
        user, project = _split_by_classification(ci_dict)

        # User-classified backup keys
        assert BACKUP_CONFIG_KEY in user
        backup_user = user[BACKUP_CONFIG_KEY]
        assert "auto_enabled" in backup_user
        assert "include_activities" in backup_user
        assert "interval_minutes" in backup_user

        # Project-classified backup keys
        assert BACKUP_CONFIG_KEY in project
        backup_project = project[BACKUP_CONFIG_KEY]
        assert "on_upgrade" in backup_project
