"""Stage ordering constants and utilities."""


class StageOrder:
    """Stage execution order constants.

    Stages are grouped into ranges of 100 to allow for easy insertion
    of new stages without renumbering existing ones.

    Order ranges:
    - 0-99: Setup (directory creation, validation)
    - 100-199: Configuration (load/create config)
    - 200-299: Agent setup (command installation)
    - 300-399: Feature installation
    - 400-499: Reserved for future use
    - 500-599: Skill installation
    - 600-699: Lifecycle hooks
    - 700-799: Migrations and repairs
    - 800-899: Finalization (cleanup, version update)
    - 900-999: Output (success messages, next steps)
    """

    # Setup phase (0-99)
    VALIDATE_ENVIRONMENT = 10
    CREATE_OAK_DIR = 20

    # Configuration phase (100-199)
    LOAD_EXISTING_CONFIG = 100
    CREATE_CONFIG = 110
    UPDATE_CONFIG_AGENTS = 120
    UPDATE_CONFIG_FEATURES = 140
    SAVE_CONFIG = 150
    MARK_MIGRATIONS_COMPLETE = 160  # For fresh installs

    # Agent phase (200-299)
    VALIDATE_AGENTS = 200
    CREATE_AGENT_DIRS = 210
    INSTALL_AGENT_COMMANDS = 220
    REMOVE_AGENT_COMMANDS = 230  # For removed agents
    UPDATE_AGENT_CAPABILITIES = 240
    REMOVE_AGENT_SETTINGS = 250  # For removed agents
    INSTALL_AGENT_SETTINGS = 260  # Auto-approve settings for agents

    # Feature phase (300-399)
    RESOLVE_FEATURE_DEPENDENCIES = 300
    REMOVE_FEATURES = 310
    INSTALL_FEATURES = 320

    # Reserved (400-499)
    UPGRADE_AGENT_SETTINGS = 425  # Agent auto-approval settings (upgrade pipeline)

    # Skill phase (500-599)
    INSTALL_SKILLS = 500
    REFRESH_SKILLS = 510

    # Hook phase (600-699)
    TRIGGER_AGENTS_CHANGED = 600
    TRIGGER_FEATURES_CHANGED = 620
    TRIGGER_INIT_COMPLETE = 650

    # Migration phase (700-799)
    STRUCTURAL_REPAIRS = 700  # For upgrade
    RUN_MIGRATIONS = 710

    # Finalization (800-899)
    UPDATE_VERSION = 800
    ENSURE_GITIGNORE = 810

    # Output (900-999)
    DISPLAY_SUMMARY = 900
    DISPLAY_NEXT_STEPS = 910

    # Removal phase (1000-1099) - separate range for removal pipeline
    VALIDATE_REMOVAL = 1000
    PLAN_REMOVAL = 1010
    TRIGGER_PRE_REMOVE_HOOKS = 1020
    CLEANUP_CI_ARTIFACTS = 1025  # Clean up CI hooks/MCP files even if feature not installed
    REMOVE_SKILLS = 1030
    REMOVE_CREATED_FILES = 1040
    REMOVE_AGENT_SETTINGS_CLEANUP = 1050  # Clean up agent settings files
    CLEANUP_DIRECTORIES = 1060
    REMOVE_OAK_DIR = 1070
