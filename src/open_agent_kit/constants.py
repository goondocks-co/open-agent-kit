"""Constants for Open Agent Kit (OAK).

This module contains:
- VERSION: Package version
- Feature configuration (SUPPORTED_FEATURES, FEATURE_CONFIG, etc.)
- Validation patterns and heuristics
- Upgrade configuration
- Default config template

For paths, messages, and runtime settings, import from:
- open_agent_kit.config.paths
- open_agent_kit.config.messages
- open_agent_kit.config.settings

For type-safe enums, import from:
- open_agent_kit.models.enums
"""

from open_agent_kit import __version__
from open_agent_kit.models.enums import RFCNumberFormat
from open_agent_kit.models.feature import FeatureConfigEntry, LanguageConfig

# =============================================================================
# Version
# =============================================================================

VERSION = __version__

# =============================================================================
# File Scanning Configuration
# =============================================================================

# Directories to skip during file scanning and language detection
SKIP_DIRECTORIES: tuple[str, ...] = (
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".oak",
)

# Limits for various operations
MAX_SCAN_FILES = 1000
MAX_SEARCH_RESULTS = 50
MAX_MEMORY_RESULTS = 100
JSON_INDENT = 2

# =============================================================================
# RFC Configuration
# =============================================================================

# RFC number formats
RFC_NUMBER_FORMATS = {f.value: f.pattern for f in RFCNumberFormat}
DEFAULT_RFC_FORMAT = RFCNumberFormat.SEQUENTIAL.value

# =============================================================================
# Validation Patterns and Heuristics
# =============================================================================

# Constitution validation
CONSTITUTION_RULE_SECTIONS = frozenset(
    {
        "Code Standards",
        "Testing",
        "Documentation",
        "Architecture",
        "Best Practices",
    }
)

CONSTITUTION_RULE_KEYWORDS = ("must", "should", "always", "require", "ensure")

VALIDATION_STOPWORDS = frozenset(
    {
        "the",
        "that",
        "this",
        "with",
        "from",
        "have",
        "will",
        "must",
        "should",
        "ensure",
        "always",
        "require",
    }
)

# Constitution sections used for parsing
CONSTITUTION_REQUIRED_SECTIONS = [
    "Principles",
    "Architecture",
    "Code Standards",
    "Testing",
    "Documentation",
    "Governance",
]

# RFC regex patterns
RFC_NUMBER_PATTERN = r"^(?:RFC-)?(\d{3,4}|20\d{2}-\d{3})$"
RFC_FILENAME_PATTERN = r"^RFC-(\d{3,4}|20\d{2}-\d{3})-(.+)\.md$"

# RFC quality
RFC_PLACEHOLDER_KEYWORDS = [
    "provide",
    "explain",
    "describe",
    "summarize",
    "outline",
    "identify",
    "state",
    "list",
    "detail",
    "define",
    "specify",
    "capture",
    "link",
    "note",
]

RFC_TEMPLATES = {
    "engineering": "Engineering RFC Template",
    "architecture": "Architecture Decision Record",
    "feature": "Feature Proposal",
    "process": "Process Improvement",
}

DEFAULT_RFC_TEMPLATE = "engineering"

REQUIRED_RFC_SECTIONS = [
    "# Summary",
    "## Motivation",
    "## Detailed Design",
    "## Drawbacks",
    "## Alternatives",
    "## Unresolved Questions",
]

# =============================================================================
# Feature Configuration (Internal)
# =============================================================================

# Features are always installed - not user-selectable
# This list defines the internal features that OAK manages
SUPPORTED_FEATURES = [
    "rules-management",
    "strategic-planning",
    "codebase-intelligence",
]

# Core feature that's always required (has no dependencies)
CORE_FEATURE = "rules-management"

# Feature display names for UI/logging
FEATURE_DISPLAY_NAMES = {
    "rules-management": "Rules Management",
    "strategic-planning": "Strategic Planning",
    "codebase-intelligence": "Codebase Intelligence",
}

# Feature configuration metadata
# Used by FeatureService when manifest.yaml doesn't exist
FEATURE_CONFIG: dict[str, FeatureConfigEntry] = {
    "rules-management": {
        "name": "Rules Management",
        "description": "Project constitution and rules for AI agents",
        "default_enabled": True,
        "dependencies": [],
        "commands": [
            "add-project-rule",
            "constitution-amend",
            "constitution-create",
            "constitution-validate",
        ],
    },
    "strategic-planning": {
        "name": "Strategic Planning",
        "description": "RFCs and Architecture Decision Records",
        "default_enabled": True,
        "dependencies": ["rules-management"],
        "commands": [
            "rfc-create",
            "rfc-list",
            "rfc-validate",
        ],
    },
    "codebase-intelligence": {
        "name": "Codebase Intelligence",
        "description": "AI-powered code analysis and search",
        "default_enabled": True,
        "dependencies": ["rules-management"],
        "commands": [
            "backend-python-expert",
        ],
    },
}

# =============================================================================
# Language Parser Configuration
# =============================================================================

# Supported languages for code intelligence
# Keys are language identifiers, values contain display name and pip extra
SUPPORTED_LANGUAGES: dict[str, LanguageConfig] = {
    "python": {"display": "Python", "extra": "parser-python", "package": "tree-sitter-python"},
    "javascript": {
        "display": "JavaScript",
        "extra": "parser-javascript",
        "package": "tree-sitter-javascript",
    },
    "typescript": {
        "display": "TypeScript",
        "extra": "parser-typescript",
        "package": "tree-sitter-typescript",
    },
    "java": {"display": "Java", "extra": "parser-java", "package": "tree-sitter-java"},
    "csharp": {"display": "C#", "extra": "parser-csharp", "package": "tree-sitter-c-sharp"},
    "go": {"display": "Go", "extra": "parser-go", "package": "tree-sitter-go"},
    "rust": {"display": "Rust", "extra": "parser-rust", "package": "tree-sitter-rust"},
    "c": {"display": "C", "extra": "parser-c", "package": "tree-sitter-c"},
    "cpp": {"display": "C++", "extra": "parser-cpp", "package": "tree-sitter-cpp"},
    "ruby": {"display": "Ruby", "extra": "parser-ruby", "package": "tree-sitter-ruby"},
    "php": {"display": "PHP", "extra": "parser-php", "package": "tree-sitter-php"},
    "kotlin": {"display": "Kotlin", "extra": "parser-kotlin", "package": "tree-sitter-kotlin"},
    "scala": {"display": "Scala", "extra": "parser-scala", "package": "tree-sitter-scala"},
}

# Default languages installed on fresh init
DEFAULT_LANGUAGES = ["python", "javascript", "typescript"]

# Language display names for UI
LANGUAGE_DISPLAY_NAMES = {lang: info["display"] for lang, info in SUPPORTED_LANGUAGES.items()}

# =============================================================================
# Upgrade Configuration
# =============================================================================

UPGRADE_TEMPLATE_CATEGORIES = ["rules-management", "strategic-planning", "commands"]
UPGRADE_COMMAND_NAMES = [
    # Sub-agent commands (codebase-intelligence feature)
    "backend-python-expert",
]

# =============================================================================
# Default Configuration Template
# =============================================================================

DEFAULT_CONFIG_YAML = """# Open Agent Kit (OAK) configuration
version: {version}

# AI Agent configuration (supports multiple agents)
agents: {agents}

# RFC configuration
rfc:
  directory: oak/rfc
  template: engineering
  auto_number: true
  number_format: sequential
  validate_on_create: true
"""
