"""Constants for Open Agent Kit (OAK).

This module contains:
- VERSION: Package version
- Feature configuration (SUPPORTED_FEATURES, FEATURE_CONFIG, etc.)
- Issue provider and IDE configuration derived from enums
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
from open_agent_kit.models.enums import IssueProvider, RFCNumberFormat

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
# Issue Provider Configuration (derived from enums)
# =============================================================================

SUPPORTED_ISSUE_PROVIDERS = IssueProvider.values()
ISSUE_PROVIDER_DISPLAY_NAMES = {p.value: p.display_name for p in IssueProvider}
ISSUE_PROVIDER_CONFIG_MAP = {p.value: p.config_key for p in IssueProvider}
ISSUE_PROVIDER_DEFAULTS = {
    "ado": {"organization": ""},
    "github": {"owner": ""},
}

# RFC number formats
RFC_NUMBER_FORMATS = {f.value: f.pattern for f in RFCNumberFormat}
DEFAULT_RFC_FORMAT = RFCNumberFormat.SEQUENTIAL.value

# =============================================================================
# Validation Patterns and Heuristics
# =============================================================================

# Issue plan section headings
ISSUE_PLAN_SECTION_HEADINGS = {
    "Objectives": "### Objectives",
    "Environment / Constraints": "### Environment / Constraints",
    "Risks & Mitigations": "### Risks & Mitigations",
    "Dependencies": "### Dependencies",
    "Definition of Done": "### Definition of Done",
}

# Plan section headings
PLAN_SECTION_HEADINGS = {
    "Overview": "## Overview",
    "Goals": "## Goals",
    "Success Criteria": "## Success Criteria",
    "Scope": "## Scope",
    "Constraints": "## Constraints",
    "Research Topics": "## Research Topics",
}

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
# Feature Configuration
# =============================================================================

SUPPORTED_FEATURES = ["codebase-intelligence", "rules-management", "strategic-planning"]
DEFAULT_FEATURES = ["codebase-intelligence"]
CORE_FEATURE = "core"

# Legacy feature name mapping for backward compatibility during migration
LEGACY_FEATURE_NAMES = {
    "constitution": "rules-management",
    "rfc": "strategic-planning",
    "plan": "strategic-planning",
}

FEATURE_CONFIG = {
    "codebase-intelligence": {
        "name": "Codebase Intelligence",
        "description": "Semantic search and persistent memory for AI assistants. Provides context-aware code retrieval and cross-session knowledge management via MCP tools.",
        "default_enabled": True,
        "dependencies": ["rules-management"],
        "commands": ["backend-python-expert"],  # Sub-agent command
        "pip_extras": ["codebase-intelligence"],
    },
    "rules-management": {
        "name": "Rules Management",
        "description": "Create, validate, and maintain AI agent rules files (constitution.md)",
        "default_enabled": True,
        "dependencies": [],
        "commands": [],  # Skills only - no sub-agent commands
    },
    "strategic-planning": {
        "name": "Strategic Planning",
        "description": "Unified SDD workflow supporting RFCs and ADRs for formal planning documentation",
        "default_enabled": False,
        "dependencies": ["rules-management"],
        "commands": [],  # Skills only - no sub-agent commands
    },
}

FEATURE_DISPLAY_NAMES = {
    "codebase-intelligence": "Codebase Intelligence",
    "rules-management": "Rules Management",
    "strategic-planning": "Strategic Planning",
}

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

# Issue provider configuration
issue:
  provider:
  azure_devops:
    organization:
    project:
    team:
    area_path:
    pat_env:
  github:
    owner:
    repo:
    token_env:
"""
