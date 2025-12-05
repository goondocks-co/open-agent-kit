"""Configuration modules for open-agent-kit.

This package organizes configuration into domain-specific modules:
- paths: Directory structure and file paths
- messages: UI strings, error messages, success messages
- settings: Runtime configuration (Pydantic Settings)
- patterns: Regex patterns and validation rules
"""

from open_agent_kit.config.messages import *  # noqa: F401, F403
from open_agent_kit.config.paths import *  # noqa: F401, F403
from open_agent_kit.config.settings import IssueProviderSettings  # noqa: F401
