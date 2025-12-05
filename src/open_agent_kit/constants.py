"""Constants for Open Agent Kit (OAK).

This module contains:
- VERSION: Package version
- Feature configuration (SUPPORTED_FEATURES, FEATURE_CONFIG, etc.)
- Issue provider and IDE configuration derived from enums
- Validation patterns and heuristics
- Decision context keys for constitution generation
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
from open_agent_kit.models.enums import IDE, IssueProvider, RFCNumberFormat

# =============================================================================
# Version
# =============================================================================

VERSION = __version__

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

# =============================================================================
# IDE Configuration (derived from enums)
# =============================================================================

SUPPORTED_IDES = IDE.values() + ["none"]
IDE_DISPLAY_NAMES = {i.value: i.display_name for i in IDE}

# RFC number formats
RFC_NUMBER_FORMATS = {f.value: f.pattern for f in RFCNumberFormat}
DEFAULT_RFC_FORMAT = RFCNumberFormat.SEQUENTIAL.value

# =============================================================================
# IDE Settings JSON Structure
# =============================================================================

IDE_SETTINGS_JSON_KEY_PROMPT_RECOMMENDATIONS = "chat.promptFilesRecommendations"
IDE_SETTINGS_JSON_KEY_AUTO_APPROVE = "chat.tools.terminal.autoApprove"
IDE_SETTINGS_OAK_PROMPT_PREFIX = "oak."
IDE_SETTINGS_OAK_AUTO_APPROVE_KEYS = ["oak"]

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

# Constitution sections
# Note: "Metadata" is NOT in this list because it's parsed separately
# and validated via _validate_metadata() in validation_service.py
CONSTITUTION_REQUIRED_SECTIONS = [
    "Principles",
    "Architecture",
    "Code Standards",
    "Testing",
    "Documentation",
    "Governance",
]

# Constitution metadata
CONSTITUTION_METADATA_PROJECT_NAME = "project_name"
CONSTITUTION_METADATA_VERSION = "version"
CONSTITUTION_METADATA_RATIFICATION_DATE = "ratification_date"
CONSTITUTION_METADATA_LAST_AMENDMENT = "last_amendment"

CONSTITUTION_REQUIRED_METADATA = [
    CONSTITUTION_METADATA_PROJECT_NAME,
    CONSTITUTION_METADATA_VERSION,
    CONSTITUTION_METADATA_RATIFICATION_DATE,
]

CONSTITUTION_METADATA_OPTIONAL = [
    CONSTITUTION_METADATA_LAST_AMENDMENT,
]

# Regex patterns
CONSTITUTION_VERSION_PATTERN = r"^\d+\.\d+\.\d+$"
CONSTITUTION_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
RFC_NUMBER_PATTERN = r"^(?:RFC-)?(\d{3,4}|20\d{2}-\d{3})$"
RFC_FILENAME_PATTERN = r"^RFC-(\d{3,4}|20\d{2}-\d{3})-(.+)\.md$"

# Quality heuristics
CONSTITUTION_NORMATIVE_SECTIONS = [
    "Principles",
    "Architecture",
    "Code Standards",
    "Testing",
    "Governance",
]

CONSTITUTION_NORMATIVE_KEYWORDS = [
    "MUST",
    "MUST NOT",
    "SHALL",
    "SHALL NOT",
    "MAY",
]

CONSTITUTION_VAGUE_POLICY_PATTERNS = [
    r"\btry to\b",
    r"\bstrive\b",
    r"\bendeavor\b",
    r"\baspire\b",
    r"\bideally\b",
    r"\bencourage\b",
]

NON_DECLARATIVE_PATTERNS = [
    r"\bshould\b",
    r"\bcould\b",
    r"\bmight\b",
    r"\bmaybe\b",
    r"\bperhaps\b",
    r"\bpossibly\b",
]

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

# Constitution tokens
CONSTITUTION_TOKENS = [
    "{{PROJECT_NAME}}",
    "{{PROJECT_DESCRIPTION}}",
    "{{VERSION}}",
    "{{DATE}}",
    "{{AUTHOR}}",
    "{{TECH_STACK}}",
]

# =============================================================================
# Constitution Decision Context
# =============================================================================

DECISION_TESTING_STRATEGY = "testing_strategy"
DECISION_COVERAGE_TARGET = "coverage_target"
DECISION_COVERAGE_STRICT = "coverage_strict"
DECISION_HAS_E2E_INFRASTRUCTURE = "has_e2e_infrastructure"
DECISION_E2E_PLANNED = "e2e_planned"
DECISION_CRITICAL_INTEGRATION_POINTS = "critical_integration_points"
DECISION_TDD_REQUIRED = "tdd_required"
DECISION_TESTING_RATIONALE = "testing_rationale"
DECISION_CODE_REVIEW_POLICY = "code_review_policy"
DECISION_NUM_REVIEWERS = "num_reviewers"
DECISION_REVIEWER_QUALIFICATIONS = "reviewer_qualifications"
DECISION_HOTFIX_DEFINITION = "hotfix_definition"
DECISION_DOCUMENTATION_LEVEL = "documentation_level"
DECISION_ADR_REQUIRED = "adr_required"
DECISION_DOCSTRING_STYLE = "docstring_style"
DECISION_CI_ENFORCEMENT = "ci_enforcement"
DECISION_REQUIRED_CHECKS = "required_checks"
DECISION_CI_PLATFORM = "ci_platform"
DECISION_ARCHITECTURAL_PATTERN = "architectural_pattern"
DECISION_ERROR_HANDLING_PATTERN = "error_handling_pattern"
DECISION_DEPENDENCY_INJECTION = "dependency_injection"
DECISION_DOMAIN_EVENTS = "domain_events"
DECISION_FEATURE_ORGANIZATION = "feature_organization"
DECISION_LAYER_ORGANIZATION = "layer_organization"
DECISION_CODING_PRINCIPLES = "coding_principles"
DECISION_ARCHITECTURAL_RATIONALE = "architectural_rationale"

# Decision defaults
DECISION_DEFAULT_TESTING_STRATEGY = "balanced"
DECISION_DEFAULT_CODE_REVIEW_POLICY = "standard"
DECISION_DEFAULT_NUM_REVIEWERS = 1
DECISION_DEFAULT_DOCUMENTATION_LEVEL = "standard"
DECISION_DEFAULT_DOCSTRING_STYLE = "google"
DECISION_DEFAULT_CI_ENFORCEMENT = "standard"
DECISION_DEFAULT_TESTING_RATIONALE = (
    "Balanced approach to testing ensures reliability while maintaining velocity"
)

# =============================================================================
# Feature Configuration
# =============================================================================

SUPPORTED_FEATURES = ["constitution", "rfc", "plan"]
DEFAULT_FEATURES = ["constitution", "rfc", "plan"]
CORE_FEATURE = "core"

FEATURE_CONFIG = {
    "constitution": {
        "name": "Constitution Management",
        "description": "Create, validate, and maintain project constitutions",
        "default_enabled": True,
        "dependencies": [],
        "commands": ["constitution-create", "constitution-validate", "constitution-amend"],
    },
    "rfc": {
        "name": "RFC Management",
        "description": "Create, list, and validate Request for Comments documents",
        "default_enabled": True,
        "dependencies": ["constitution"],
        "commands": ["rfc-create", "rfc-list", "rfc-validate"],
    },
    "plan": {
        "name": "Planning",
        "description": "Unified SDD workflow supporting both issue-first (GitHub/Azure DevOps) and idea-first planning with research phases, structured task generation, and export to issue trackers",
        "default_enabled": True,
        "dependencies": ["constitution"],
        "commands": [
            "plan-create",
            "plan-research",
            "plan-tasks",
            "plan-implement",
            "plan-export",
            "plan-issue",
            "plan-validate",
        ],
    },
}

FEATURE_DISPLAY_NAMES = {
    "constitution": "Constitution Management",
    "rfc": "RFC Management",
    "plan": "Planning",
}

# =============================================================================
# Upgrade Configuration
# =============================================================================

UPGRADE_TEMPLATE_CATEGORIES = ["rfc", "constitution", "commands"]
UPGRADE_IDE_SETTINGS = ["vscode", "cursor"]

UPGRADE_COMMAND_NAMES = [
    "rfc-create",
    "rfc-list",
    "rfc-validate",
    "constitution-create",
    "constitution-validate",
    "constitution-amend",
    "plan-create",
    "plan-research",
    "plan-tasks",
    "plan-implement",
    "plan-export",
    "plan-issue",
    "plan-validate",
]

# =============================================================================
# Default Configuration Template
# =============================================================================

DEFAULT_CONFIG_YAML = """# Open Agent Kit (OAK) configuration
version: {version}

# AI Agent configuration (supports multiple agents)
agents: {agents}

# IDE configuration (supports multiple IDEs)
ides: {ides}

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
