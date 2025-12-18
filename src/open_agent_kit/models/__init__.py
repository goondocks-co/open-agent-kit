"""Data models for open-agent-kit"""

from .agent_manifest import (
    AgentCapabilities,
    AgentInstallation,
    AgentManifest,
    AgentRequirements,
)
from .config import AgentCapabilitiesConfig
from .constitution import (
    Amendment,
    AmendmentType,
    ConstitutionDocument,
    ConstitutionMetadata,
    ConstitutionSection,
    ConstitutionStatus,
)
from .enums import (
    IDE,
    ExportMode,
    IssueProvider,
    PlanStatus,
    ResearchDepth,
    RFCNumberFormat,
    RFCStatus,
    TaskPriority,
    TaskType,
)
from .enums import AmendmentType as AmendmentTypeEnum
from .enums import ValidationCategory as ValidationCategoryEnum
from .enums import ValidationPriority as ValidationPriorityEnum
from .exceptions import (
    ConfigurationError,
    ConstitutionServiceError,
    IssueProviderError,
    MigrationError,
    OakError,
    PlanServiceError,
    RFCServiceError,
    ServiceError,
    TemplateError,
    ValidationError,
)
from .feature import FeatureManifest, LifecycleHooks
from .project import ProjectConfig, ProjectState
from .rfc import RFCDocument, RFCIndex
from .skill import SkillManifest
from .state import OakState
from .template import Template, TemplateConfig, TemplateHooks
from .validation import (
    ValidationCategory,
    ValidationFix,
    ValidationIssue,
    ValidationPriority,
    ValidationResult,
)

__all__ = [
    # State and config
    "OakState",
    "ProjectConfig",
    "ProjectState",
    "Template",
    "TemplateConfig",
    "TemplateHooks",
    # Agent manifests
    "AgentManifest",
    "AgentCapabilities",
    "AgentCapabilitiesConfig",
    "AgentInstallation",
    "AgentRequirements",
    # Features
    "FeatureManifest",
    "LifecycleHooks",
    # Skills
    "SkillManifest",
    # RFC
    "RFCDocument",
    "RFCIndex",
    "RFCStatus",
    "RFCNumberFormat",
    # Constitution
    "Amendment",
    "AmendmentType",
    "AmendmentTypeEnum",
    "ConstitutionDocument",
    "ConstitutionMetadata",
    "ConstitutionSection",
    "ConstitutionStatus",
    # Validation
    "ValidationCategory",
    "ValidationCategoryEnum",
    "ValidationFix",
    "ValidationIssue",
    "ValidationPriority",
    "ValidationPriorityEnum",
    "ValidationResult",
    # Enums (new)
    "ExportMode",
    "IDE",
    "IssueProvider",
    "PlanStatus",
    "ResearchDepth",
    "TaskPriority",
    "TaskType",
    # Exceptions
    "OakError",
    "ConfigurationError",
    "ValidationError",
    "ServiceError",
    "PlanServiceError",
    "RFCServiceError",
    "ConstitutionServiceError",
    "IssueProviderError",
    "TemplateError",
    "MigrationError",
]
