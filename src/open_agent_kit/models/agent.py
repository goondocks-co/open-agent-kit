"""Agent configuration and command models"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class AgentType(str, Enum):
    """Agent type enumeration"""

    CLAUDE = "claude"
    COPILOT = "copilot"
    CODEX = "codex"
    CURSOR = "cursor"
    GEMINI = "gemini"
    LLAMA = "llama"
    CUSTOM = "custom"


class AgentCapability(str, Enum):
    """Agent capability enumeration"""

    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    CODE_COMPLETION = "code_completion"
    CHAT = "chat"
    EMBEDDING = "embedding"
    IMAGE_GENERATION = "image_generation"
    FUNCTION_CALLING = "function_calling"


@dataclass
class AgentConfig:
    """Agent configuration model"""

    name: str
    type: AgentType = AgentType.CUSTOM
    enabled: bool = True

    # API configuration
    api_key: str | None = None
    api_key_env: str | None = None  # Environment variable name for API key
    api_url: str | None = None
    api_version: str | None = None
    organization: str | None = None

    # Model configuration
    model: str | None = None
    models: list[str] = field(default_factory=list)  # Available models
    default_model: str | None = None

    # Request configuration
    max_tokens: int = 4000
    temperature: float = 0.7
    top_p: float = 1.0
    timeout: int = 30  # seconds
    retry_count: int = 3
    retry_delay: int = 1  # seconds

    # Rate limiting
    rate_limit: int | None = None  # Requests per minute
    concurrent_requests: int = 1

    # Features and capabilities
    capabilities: list[AgentCapability] = field(default_factory=list)
    supports_streaming: bool = False
    supports_functions: bool = False
    supports_vision: bool = False

    # Custom headers and parameters
    headers: dict[str, str] = field(default_factory=dict)
    extra_params: dict[str, Any] = field(default_factory=dict)

    # Command settings
    command_prefix: str | None = None
    command_suffix: str | None = None
    system_prompt: str | None = None

    # Cost tracking (optional)
    cost_per_1k_input_tokens: float | None = None
    cost_per_1k_output_tokens: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        data: dict[str, Any] = {
            "name": self.name,
            "type": self.type.value if isinstance(self.type, AgentType) else self.type,
            "enabled": self.enabled,
        }

        # API configuration
        if self.api_key:
            data["api_key"] = self.api_key
        if self.api_key_env:
            data["api_key_env"] = self.api_key_env
        if self.api_url:
            data["api_url"] = self.api_url
        if self.api_version:
            data["api_version"] = self.api_version
        if self.organization:
            data["organization"] = self.organization

        # Model configuration
        if self.model:
            data["model"] = self.model
        if self.models:
            data["models"] = self.models
        if self.default_model:
            data["default_model"] = self.default_model

        # Request configuration
        data["max_tokens"] = self.max_tokens
        data["temperature"] = self.temperature
        data["top_p"] = self.top_p
        data["timeout"] = self.timeout
        data["retry_count"] = self.retry_count
        data["retry_delay"] = self.retry_delay

        # Rate limiting
        if self.rate_limit:
            data["rate_limit"] = self.rate_limit
        data["concurrent_requests"] = self.concurrent_requests

        # Features
        if self.capabilities:
            data["capabilities"] = [
                cap.value if isinstance(cap, AgentCapability) else cap for cap in self.capabilities
            ]
        data["supports_streaming"] = self.supports_streaming
        data["supports_functions"] = self.supports_functions
        data["supports_vision"] = self.supports_vision

        # Custom settings
        if self.headers:
            data["headers"] = self.headers
        if self.extra_params:
            data["extra_params"] = self.extra_params

        # Command settings
        if self.command_prefix:
            data["command_prefix"] = self.command_prefix
        if self.command_suffix:
            data["command_suffix"] = self.command_suffix
        if self.system_prompt:
            data["system_prompt"] = self.system_prompt

        # Cost tracking
        if self.cost_per_1k_input_tokens:
            data["cost_per_1k_input_tokens"] = self.cost_per_1k_input_tokens
        if self.cost_per_1k_output_tokens:
            data["cost_per_1k_output_tokens"] = self.cost_per_1k_output_tokens

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        """Create from dictionary"""
        # Parse type
        type_str = data.get("type", "custom")
        try:
            agent_type = AgentType(type_str)
        except ValueError:
            agent_type = AgentType.CUSTOM

        # Parse capabilities
        capabilities = []
        for cap_str in data.get("capabilities", []):
            try:
                capabilities.append(AgentCapability(cap_str))
            except ValueError:
                pass  # Skip invalid capabilities

        return cls(
            name=data["name"],
            type=agent_type,
            enabled=data.get("enabled", True),
            api_key=data.get("api_key"),
            api_key_env=data.get("api_key_env"),
            api_url=data.get("api_url"),
            api_version=data.get("api_version"),
            organization=data.get("organization"),
            model=data.get("model"),
            models=data.get("models", []),
            default_model=data.get("default_model"),
            max_tokens=data.get("max_tokens", 4000),
            temperature=data.get("temperature", 0.7),
            top_p=data.get("top_p", 1.0),
            timeout=data.get("timeout", 30),
            retry_count=data.get("retry_count", 3),
            retry_delay=data.get("retry_delay", 1),
            rate_limit=data.get("rate_limit"),
            concurrent_requests=data.get("concurrent_requests", 1),
            capabilities=capabilities,
            supports_streaming=data.get("supports_streaming", False),
            supports_functions=data.get("supports_functions", False),
            supports_vision=data.get("supports_vision", False),
            headers=data.get("headers", {}),
            extra_params=data.get("extra_params", {}),
            command_prefix=data.get("command_prefix"),
            command_suffix=data.get("command_suffix"),
            system_prompt=data.get("system_prompt"),
            cost_per_1k_input_tokens=data.get("cost_per_1k_input_tokens"),
            cost_per_1k_output_tokens=data.get("cost_per_1k_output_tokens"),
        )

    def get_api_key(self) -> str | None:
        """Get API key from config or environment"""
        if self.api_key:
            return self.api_key

        if self.api_key_env:
            import os

            return os.environ.get(self.api_key_env)

        # Try default environment variable names
        import os

        default_env_names = {
            AgentType.CLAUDE: "CLAUDE_API_KEY",
            AgentType.COPILOT: "GITHUB_TOKEN",
            AgentType.CODEX: "OPENAI_API_KEY",
            AgentType.CURSOR: "CURSOR_API_KEY",
            AgentType.GEMINI: "GEMINI_API_KEY",
            AgentType.LLAMA: "LLAMA_API_KEY",
        }

        if self.type in default_env_names:
            return os.environ.get(default_env_names[self.type])

        return None


@dataclass
class AgentCommand:
    """Agent command definition"""

    name: str
    content: str  # Command template/prompt
    file_path: Path | None = None

    # Command metadata
    description: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)

    # Command configuration
    variables: list[str] = field(default_factory=list)  # Required variables
    optional_variables: list[str] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)

    # Execution settings
    max_tokens: int | None = None
    temperature: float | None = None
    system_prompt: str | None = None

    # Response processing
    response_format: str | None = None  # "text", "json", "markdown", etc.
    extract_pattern: str | None = None  # Regex to extract from response
    post_process: str | None = None  # Script to post-process response

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        data: dict[str, Any] = {
            "name": self.name,
            "content": self.content,
        }

        if self.file_path:
            data["file_path"] = str(self.file_path)
        if self.description:
            data["description"] = self.description
        if self.category:
            data["category"] = self.category
        if self.tags:
            data["tags"] = self.tags
        if self.variables:
            data["variables"] = self.variables
        if self.optional_variables:
            data["optional_variables"] = self.optional_variables
        if self.defaults:
            data["defaults"] = self.defaults
        if self.max_tokens:
            data["max_tokens"] = self.max_tokens
        if self.temperature:
            data["temperature"] = self.temperature
        if self.system_prompt:
            data["system_prompt"] = self.system_prompt
        if self.response_format:
            data["response_format"] = self.response_format
        if self.extract_pattern:
            data["extract_pattern"] = self.extract_pattern
        if self.post_process:
            data["post_process"] = self.post_process

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCommand":
        """Create from dictionary"""
        file_path = data.get("file_path")
        if file_path:
            file_path = Path(file_path)

        return cls(
            name=data["name"],
            content=data["content"],
            file_path=file_path,
            description=data.get("description"),
            category=data.get("category"),
            tags=data.get("tags", []),
            variables=data.get("variables", []),
            optional_variables=data.get("optional_variables", []),
            defaults=data.get("defaults", {}),
            max_tokens=data.get("max_tokens"),
            temperature=data.get("temperature"),
            system_prompt=data.get("system_prompt"),
            response_format=data.get("response_format"),
            extract_pattern=data.get("extract_pattern"),
            post_process=data.get("post_process"),
        )

    def render(self, context: dict[str, Any]) -> str:
        """Render command with context variables"""
        # Apply defaults
        for key, value in self.defaults.items():
            if key not in context:
                context[key] = value

        # Check required variables
        for var in self.variables:
            if var not in context:
                raise ValueError(f"Required variable missing: {var}")

        # Simple string format rendering
        try:
            return self.content.format(**context)
        except KeyError as e:
            raise ValueError(f"Variable not found in context: {e}")


@dataclass
class AgentCapabilities:
    """Agent capabilities and features"""

    agent_type: AgentType
    capabilities: list[AgentCapability] = field(default_factory=list)

    # Model information
    available_models: list[str] = field(default_factory=list)
    default_model: str | None = None

    # Limits
    max_context_length: int = 4096
    max_output_length: int = 4096

    # Features
    supports_streaming: bool = False
    supports_functions: bool = False
    supports_vision: bool = False
    supports_embeddings: bool = False
    supports_fine_tuning: bool = False

    # Cost information
    pricing_model: str | None = None  # "per-token", "per-request", "subscription"
    free_tier: bool = False

    @classmethod
    def get_default_capabilities(cls, agent_type: AgentType) -> "AgentCapabilities":
        """Get default capabilities for agent type"""
        defaults = {
            AgentType.CLAUDE: cls(
                agent_type=AgentType.CLAUDE,
                capabilities=[
                    AgentCapability.TEXT_GENERATION,
                    AgentCapability.CODE_GENERATION,
                    AgentCapability.CHAT,
                    AgentCapability.FUNCTION_CALLING,
                ],
                available_models=[
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307",
                ],
                default_model="claude-3-opus-20240229",
                max_context_length=200000,
                max_output_length=4096,
                supports_streaming=True,
                supports_functions=True,
                supports_vision=True,
                pricing_model="per-token",
            ),
            AgentType.COPILOT: cls(
                agent_type=AgentType.COPILOT,
                capabilities=[
                    AgentCapability.CODE_GENERATION,
                    AgentCapability.CODE_COMPLETION,
                ],
                available_models=["copilot"],
                default_model="copilot",
                max_context_length=8192,
                max_output_length=4096,
                supports_streaming=True,
                pricing_model="subscription",
            ),
            AgentType.CODEX: cls(
                agent_type=AgentType.CODEX,
                capabilities=[
                    AgentCapability.CODE_GENERATION,
                    AgentCapability.CODE_COMPLETION,
                    AgentCapability.TEXT_GENERATION,
                ],
                available_models=["code-davinci-002", "code-cushman-001"],
                default_model="code-davinci-002",
                max_context_length=8001,
                max_output_length=4000,
                supports_streaming=True,
                pricing_model="per-token",
            ),
            AgentType.CURSOR: cls(
                agent_type=AgentType.CURSOR,
                capabilities=[
                    AgentCapability.CODE_GENERATION,
                    AgentCapability.CODE_COMPLETION,
                    AgentCapability.CHAT,
                ],
                available_models=["cursor"],
                default_model="cursor",
                max_context_length=8192,
                max_output_length=4096,
                supports_streaming=True,
                pricing_model="subscription",
            ),
        }

        return defaults.get(agent_type, cls(agent_type=agent_type))
