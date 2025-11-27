"""Template system models"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TemplateType(str, Enum):
    """Template type enumeration"""

    RFC = "rfc"
    PROJECT = "project"
    COMMAND = "command"
    DOCUMENT = "document"
    CUSTOM = "custom"


@dataclass
class TemplateHooks:
    """Template hooks for pre/post processing"""

    pre_generate: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    post_generate: Callable[[str], str] | None = None
    validate: Callable[[dict[str, Any]], bool] | None = None

    # Hook file paths (for loading from filesystem)
    pre_generate_path: Path | None = None
    post_generate_path: Path | None = None
    validate_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = {}
        if self.pre_generate_path:
            data["pre_generate"] = str(self.pre_generate_path)
        if self.post_generate_path:
            data["post_generate"] = str(self.post_generate_path)
        if self.validate_path:
            data["validate"] = str(self.validate_path)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TemplateHooks":
        """Create from dictionary"""
        return cls(
            pre_generate_path=Path(data["pre_generate"]) if "pre_generate" in data else None,
            post_generate_path=Path(data["post_generate"]) if "post_generate" in data else None,
            validate_path=Path(data["validate"]) if "validate" in data else None,
        )


@dataclass
class TemplateConfig:
    """Template configuration"""

    name: str = "unnamed"
    description: str = ""
    version: str = "1.0"
    type: TemplateType = TemplateType.CUSTOM
    author: str | None = None
    tags: list[str] = field(default_factory=list)

    # Template variables
    variables: dict[str, Any] = field(default_factory=dict)
    required_variables: list[str] = field(default_factory=list)
    optional_variables: list[str] = field(default_factory=list)

    # Variable defaults and validation
    defaults: dict[str, Any] = field(default_factory=dict)
    validators: dict[str, str] = field(default_factory=dict)  # Variable name -> regex pattern

    # Template inheritance
    extends: str | None = None  # Parent template to extend
    blocks: list[str] = field(default_factory=list)  # Overridable blocks

    # Hooks
    hooks: TemplateHooks = field(default_factory=TemplateHooks)

    # File patterns (for project templates)
    include_patterns: list[str] = field(default_factory=lambda: ["**/*"])
    exclude_patterns: list[str] = field(
        default_factory=lambda: [
            "*.pyc",
            "__pycache__",
            ".git",
            ".gitignore",
            "node_modules",
            ".env",
        ]
    )

    # Template metadata
    min_oak_version: str | None = None
    max_oak_version: str | None = None
    dependencies: list[str] = field(default_factory=list)  # Other required templates

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        data: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "type": self.type.value if isinstance(self.type, TemplateType) else self.type,
            "tags": self.tags,
        }

        if self.author:
            data["author"] = self.author
        if self.variables:
            data["variables"] = self.variables
        if self.required_variables:
            data["required_variables"] = self.required_variables
        if self.optional_variables:
            data["optional_variables"] = self.optional_variables
        if self.defaults:
            data["defaults"] = self.defaults
        if self.validators:
            data["validators"] = self.validators
        if self.extends:
            data["extends"] = self.extends
        if self.blocks:
            data["blocks"] = self.blocks

        hooks_dict = self.hooks.to_dict()
        if hooks_dict:
            data["hooks"] = hooks_dict

        if self.include_patterns != ["**/*"]:
            data["include_patterns"] = self.include_patterns
        if self.exclude_patterns:
            data["exclude_patterns"] = self.exclude_patterns

        if self.min_oak_version:
            data["min_oak_version"] = self.min_oak_version
        if self.max_oak_version:
            data["max_oak_version"] = self.max_oak_version
        if self.dependencies:
            data["dependencies"] = self.dependencies

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TemplateConfig":
        """Create from dictionary"""
        # Parse type
        type_str = data.get("type", "custom")
        try:
            template_type = TemplateType(type_str)
        except ValueError:
            template_type = TemplateType.CUSTOM

        # Parse hooks
        hooks_data = data.get("hooks", {})
        hooks = TemplateHooks.from_dict(hooks_data) if hooks_data else TemplateHooks()

        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            type=template_type,
            author=data.get("author"),
            tags=data.get("tags", []),
            variables=data.get("variables", {}),
            required_variables=data.get("required_variables", []),
            optional_variables=data.get("optional_variables", []),
            defaults=data.get("defaults", {}),
            validators=data.get("validators", {}),
            extends=data.get("extends"),
            blocks=data.get("blocks", []),
            hooks=hooks,
            include_patterns=data.get("include_patterns", ["**/*"]),
            exclude_patterns=data.get(
                "exclude_patterns",
                ["*.pyc", "__pycache__", ".git", ".gitignore", "node_modules", ".env"],
            ),
            min_oak_version=data.get("min_oak_version"),
            max_oak_version=data.get("max_oak_version"),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class Template:
    """Template instance"""

    name: str
    category: str
    path: Path
    config: TemplateConfig = field(default_factory=TemplateConfig)

    # Runtime properties
    is_loaded: bool = False
    content: str | None = None
    compiled: Any | None = None  # Compiled Jinja2 template

    @property
    def template_file(self) -> Path:
        """Get main template file path"""
        # Check for common template file names
        for filename in ["template.md", "template.txt", "template.html", "template"]:
            file_path = self.path / filename
            if file_path.exists():
                return file_path

        # Check for file with same name as template
        file_path = self.path / f"{self.name}.md"
        if file_path.exists():
            return file_path

        # Default to template.md
        return self.path / "template.md"

    @property
    def config_file(self) -> Path:
        """Get config file path"""
        return self.path / "config.yaml"

    @property
    def hooks_dir(self) -> Path:
        """Get hooks directory path"""
        return self.path / "hooks"

    def load(self) -> None:
        """Load template content from filesystem"""
        if self.template_file.exists():
            with open(self.template_file) as f:
                self.content = f.read()
            self.is_loaded = True
        else:
            raise FileNotFoundError(f"Template file not found: {self.template_file}")

    def validate_context(self, context: dict[str, Any]) -> bool:
        """Validate template context"""
        # Check required variables
        for var in self.config.required_variables:
            if var not in context:
                raise ValueError(f"Required variable missing: {var}")

        # Validate using validators
        import re

        for var, pattern in self.config.validators.items():
            if var in context:
                value = str(context[var])
                if not re.match(pattern, value):
                    raise ValueError(f"Variable {var} does not match pattern: {pattern}")

        # Run custom validation hook if present
        if self.config.hooks.validate:
            return self.config.hooks.validate(context)

        return True

    def apply_defaults(self, context: dict[str, Any]) -> dict[str, Any]:
        """Apply default values to context"""
        for key, default_value in self.config.defaults.items():
            if key not in context:
                context[key] = default_value
        return context

    def get_metadata(self) -> dict[str, Any]:
        """Get template metadata"""
        return {
            "name": self.name,
            "category": self.category,
            "path": str(self.path),
            "description": self.config.description,
            "version": self.config.version,
            "type": (
                self.config.type.value
                if isinstance(self.config.type, TemplateType)
                else self.config.type
            ),
            "author": self.config.author,
            "tags": self.config.tags,
            "required_variables": self.config.required_variables,
            "optional_variables": self.config.optional_variables,
        }


@dataclass
class TemplateRegistry:
    """Registry of available templates"""

    templates: dict[str, Template] = field(default_factory=dict)
    categories: dict[str, list[str]] = field(default_factory=dict)

    def register(self, template: Template) -> None:
        """Register a template"""
        key = f"{template.category}/{template.name}"
        self.templates[key] = template

        # Update category index
        if template.category not in self.categories:
            self.categories[template.category] = []
        if template.name not in self.categories[template.category]:
            self.categories[template.category].append(template.name)

    def get(self, key: str) -> Template | None:
        """Get template by key (category/name)"""
        return self.templates.get(key)

    def get_by_category(self, category: str) -> list[Template]:
        """Get all templates in a category"""
        template_names = self.categories.get(category, [])
        return [
            self.templates[f"{category}/{name}"]
            for name in template_names
            if f"{category}/{name}" in self.templates
        ]

    def search(
        self,
        name: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        type: TemplateType | None = None,
    ) -> list[Template]:
        """Search templates"""
        results = list(self.templates.values())

        if name:
            name_lower = name.lower()
            results = [t for t in results if name_lower in t.name.lower()]

        if category:
            results = [t for t in results if t.category == category]

        if tag:
            results = [t for t in results if tag in t.config.tags]

        if type:
            results = [t for t in results if t.config.type == type]

        return results
