"""Project configuration and state models"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ProjectType(str, Enum):
    """Project type enumeration"""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    GENERIC = "generic"


@dataclass
class ProjectConfig:
    """Project configuration model"""

    name: str
    template: str = "generic"
    project_type: ProjectType = ProjectType.GENERIC
    default_agent: str | None = None
    initialized_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0"

    # Paths configuration
    rfc_output_dir: str = "oak/rfc"
    docs_output_dir: str = "oak/docs"
    specs_output_dir: str = "oak/specs"

    # RFC configuration
    rfc_template: str = "default"
    rfc_auto_index: bool = True
    rfc_number_format: str = "YYYY-NNN"  # YYYY-NNN, NNNN, or sequential

    # Agent configuration
    enabled_agents: list[str] = field(
        default_factory=lambda: ["claude", "copilot", "cursor", "codex"]
    )
    agent_timeout: int = 30  # seconds

    # Template configuration
    template_sources: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"type": "local", "path": ".oak/templates"},
            {"type": "built-in", "path": "templates"},
        ]
    )

    # Logging configuration
    log_level: str = "INFO"
    log_file: str = ".oak/logs/oak.log"
    log_rotate: bool = True
    log_max_size: str = "10MB"

    # Command configuration
    custom_command_paths: list[str] = field(default_factory=lambda: [".oak/commands"])

    # Cache configuration
    cache_enabled: bool = True
    cache_dir: str = ".oak/cache"
    cache_ttl: int = 3600  # seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "version": self.version,
            "project": {
                "name": self.name,
                "type": (
                    self.project_type.value
                    if isinstance(self.project_type, ProjectType)
                    else self.project_type
                ),
                "template": self.template,
                "initialized_at": self.initialized_at.isoformat(),
            },
            "agents": {
                "default": self.default_agent,
                "enabled": self.enabled_agents,
                "timeout": self.agent_timeout,
            },
            "templates": {
                "sources": self.template_sources,
            },
            "rfc": {
                "output_dir": self.rfc_output_dir,
                "template": self.rfc_template,
                "auto_index": self.rfc_auto_index,
                "number_format": self.rfc_number_format,
            },
            "commands": {
                "custom_paths": self.custom_command_paths,
            },
            "logging": {
                "level": self.log_level,
                "file": self.log_file,
                "rotate": self.log_rotate,
                "max_size": self.log_max_size,
            },
            "cache": {
                "enabled": self.cache_enabled,
                "dir": self.cache_dir,
                "ttl": self.cache_ttl,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectConfig":
        """Create from dictionary"""
        project = data.get("project", {})
        agents = data.get("agents", {})
        templates = data.get("templates", {})
        rfc = data.get("rfc", {})
        commands = data.get("commands", {})
        logging = data.get("logging", {})
        cache = data.get("cache", {})

        # Parse initialized_at
        initialized_at = project.get("initialized_at")
        if initialized_at and isinstance(initialized_at, str):
            initialized_at = datetime.fromisoformat(initialized_at)
        else:
            initialized_at = datetime.now()

        # Parse project type
        project_type_str = project.get("type", "generic")
        try:
            project_type = ProjectType(project_type_str)
        except ValueError:
            project_type = ProjectType.GENERIC

        return cls(
            name=project.get("name", "unnamed"),
            template=project.get("template", "generic"),
            project_type=project_type,
            default_agent=agents.get("default"),
            initialized_at=initialized_at,
            version=data.get("version", "1.0"),
            rfc_output_dir=rfc.get("output_dir", "oak/rfc"),
            rfc_template=rfc.get("template", "default"),
            rfc_auto_index=rfc.get("auto_index", True),
            rfc_number_format=rfc.get("number_format", "YYYY-NNN"),
            enabled_agents=agents.get("enabled", ["claude", "copilot", "cursor", "codex"]),
            agent_timeout=agents.get("timeout", 30),
            template_sources=templates.get(
                "sources",
                [
                    {"type": "local", "path": ".oak/templates"},
                    {"type": "built-in", "path": "templates"},
                ],
            ),
            custom_command_paths=commands.get("custom_paths", [".oak/commands"]),
            log_level=logging.get("level", "INFO"),
            log_file=logging.get("file", ".oak/logs/oak.log"),
            log_rotate=logging.get("rotate", True),
            log_max_size=logging.get("max_size", "10MB"),
            cache_enabled=cache.get("enabled", True),
            cache_dir=cache.get("dir", ".oak/cache"),
            cache_ttl=cache.get("ttl", 3600),
        )


@dataclass
class ProjectState:
    """Runtime project state"""

    root_dir: Path
    config: ProjectConfig
    oak_dir: Path
    is_initialized: bool = False
    active_agent: str | None = None

    @property
    def config_file(self) -> Path:
        """Get config file path"""
        return self.oak_dir / "config.yaml"

    @property
    def agents_dir(self) -> Path:
        """Get agents directory"""
        return self.oak_dir / "agents"

    @property
    def templates_dir(self) -> Path:
        """Get templates directory"""
        return self.oak_dir / "templates"

    @property
    def commands_dir(self) -> Path:
        """Get commands directory"""
        return self.oak_dir / "commands"

    @property
    def cache_dir(self) -> Path:
        """Get cache directory"""
        return self.oak_dir / "cache"

    @property
    def logs_dir(self) -> Path:
        """Get logs directory"""
        return self.oak_dir / "logs"

    @property
    def rfc_dir(self) -> Path:
        """Get RFC output directory"""
        return self.root_dir / self.config.rfc_output_dir

    def get_agent_dir(self, agent_name: str) -> Path:
        """Get specific agent directory"""
        return self.agents_dir / agent_name
