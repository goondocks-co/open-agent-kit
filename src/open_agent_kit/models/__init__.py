"""Data models for open-agent-kit"""

from .agent_manifest import (
    AgentCapabilities,
    AgentInstallation,
    AgentManifest,
    AgentRequirements,
)
from .constitution import (
    Amendment,
    AmendmentType,
    ConstitutionDocument,
    ConstitutionMetadata,
    ConstitutionSection,
    ConstitutionStatus,
)
from .enums import AmendmentType as AmendmentTypeEnum
from .enums import (
    RFCNumberFormat,
    RFCStatus,
)
from .exceptions import (
    ConfigurationError,
    ConstitutionServiceError,
    MigrationError,
    OakError,
    RFCServiceError,
    ServiceError,
    TemplateError,
    ValidationError,
)
from .feature import FeatureManifest, LifecycleHooks
from .project import ProjectConfig, ProjectState
from .results import (
    BatchOperationResult,
    DaemonStatus,
    FeatureInstallResult,
    SearchResult,
    UpgradePlanData,
)
from .rfc import RFCDocument, RFCIndex
from .skill import SkillManifest
from .state import OakState
from .template import Template, TemplateConfig, TemplateHooks

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
    # Results
    "DaemonStatus",
    "SearchResult",
    "FeatureInstallResult",
    "BatchOperationResult",
    "UpgradePlanData",
    # Exceptions
    "OakError",
    "ConfigurationError",
    "ValidationError",
    "ServiceError",
    "RFCServiceError",
    "ConstitutionServiceError",
    "TemplateError",
    "MigrationError",
]
