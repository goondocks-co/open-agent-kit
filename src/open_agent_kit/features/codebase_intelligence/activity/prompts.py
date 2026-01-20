"""Prompt template system for activity observation extraction.

Templates are loaded from markdown files with YAML frontmatter.
Default templates are in features/codebase-intelligence/prompts/.

Template file format:
```
---
name: extraction
description: General observation extraction
activity_filter: Read,Edit  # optional
min_activities: 1
---

Your prompt content here with {{placeholders}}
```

Placeholder syntax:
- {{activities}} - Formatted list of activities
- {{files_read}} - List of files read
- {{files_modified}} - List of files modified
- {{files_created}} - List of files created
- {{errors}} - List of errors encountered
- {{session_duration}} - Session duration in minutes
- {{observation_types}} - Schema-defined observation types with descriptions
- {{classification_types}} - Schema-defined activity classification types
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Default paths (relative to package)
# Config is now co-located with Python code in the same feature directory
# Path: activity/prompts.py -> activity/ -> codebase_intelligence/
DEFAULT_FEATURE_DIR = Path(__file__).parent.parent
DEFAULT_PROMPTS_DIR = DEFAULT_FEATURE_DIR / "prompts"
DEFAULT_SCHEMA_PATH = DEFAULT_FEATURE_DIR / "schema.yaml"


@dataclass
class ObservationTypeSchema:
    """Schema for a single observation type."""

    name: str
    description: str
    examples: list[str] = field(default_factory=list)
    icon: str = ""


@dataclass
class ClassificationTypeSchema:
    """Schema for an activity classification type."""

    name: str
    description: str
    indicators: list[str] = field(default_factory=list)


@dataclass
class CISchema:
    """Codebase Intelligence schema loaded from schema.yaml.

    This is the single source of truth for observation and classification types.
    """

    observation_types: list[ObservationTypeSchema] = field(default_factory=list)
    classification_types: list[ClassificationTypeSchema] = field(default_factory=list)
    version: str = "1.0"

    @classmethod
    def load(cls, schema_path: Path | None = None) -> "CISchema":
        """Load schema from YAML file.

        Args:
            schema_path: Path to schema.yaml. Defaults to DEFAULT_SCHEMA_PATH.

        Returns:
            Loaded CISchema instance.
        """
        if schema_path is None:
            schema_path = DEFAULT_SCHEMA_PATH

        if not schema_path.exists():
            logger.warning(f"Schema file not found at {schema_path}, using defaults")
            return cls._get_default_schema()

        try:
            with open(schema_path) as f:
                data = yaml.safe_load(f)

            observation_types = []
            for name, type_data in data.get("observation_types", {}).items():
                observation_types.append(
                    ObservationTypeSchema(
                        name=name,
                        description=type_data.get("description", ""),
                        examples=type_data.get("examples", []),
                        icon=type_data.get("icon", ""),
                    )
                )

            classification_types = []
            for name, type_data in data.get("activity_classifications", {}).items():
                classification_types.append(
                    ClassificationTypeSchema(
                        name=name,
                        description=type_data.get("description", ""),
                        indicators=type_data.get("indicators", []),
                    )
                )

            return cls(
                observation_types=observation_types,
                classification_types=classification_types,
                version=data.get("version", "1.0"),
            )
        except (OSError, yaml.YAMLError, ValueError, TypeError, KeyError) as e:
            logger.error(f"Failed to load schema from {schema_path}: {e}", exc_info=True)
            return cls._get_default_schema()

    @staticmethod
    def _get_default_schema() -> "CISchema":
        """Get minimal default schema if file not found."""
        return CISchema(
            observation_types=[
                ObservationTypeSchema("gotcha", "Non-obvious behaviors or edge cases"),
                ObservationTypeSchema("bug_fix", "Bugs identified and fixed"),
                ObservationTypeSchema("decision", "Architecture or design decisions"),
                ObservationTypeSchema("discovery", "Facts learned about the codebase"),
            ],
            classification_types=[
                ClassificationTypeSchema("exploration", "Reading and understanding code"),
                ClassificationTypeSchema("debugging", "Investigating errors"),
                ClassificationTypeSchema("implementation", "Writing new code"),
                ClassificationTypeSchema("refactoring", "Modifying code structure"),
            ],
        )

    def get_observation_type_names(self) -> list[str]:
        """Get list of valid observation type names."""
        return [t.name for t in self.observation_types]

    def get_classification_type_names(self) -> list[str]:
        """Get list of valid classification type names."""
        return [t.name for t in self.classification_types]

    def format_observation_types_for_prompt(self) -> str:
        """Format observation types for injection into prompts.

        Returns:
            Formatted string describing each observation type with examples.
        """
        lines = []
        for t in self.observation_types:
            lines.append(f"- **{t.name}**: {t.description}")
            if t.examples:
                for ex in t.examples[:2]:  # Limit examples to save tokens
                    lines.append(f'  - Example: "{ex}"')
        return "\n".join(lines)

    def format_classification_types_for_prompt(self) -> str:
        """Format classification types for injection into prompts.

        Returns:
            Formatted string describing each classification type.
        """
        lines = []
        for t in self.classification_types:
            lines.append(f"- **{t.name}**: {t.description}")
        return "\n".join(lines)

    def get_type_names_json(self) -> str:
        """Get observation type names as JSON array for prompts.

        Returns:
            String like 'gotcha|bug_fix|decision|discovery'
        """
        return "|".join(self.get_observation_type_names())


# Global schema instance (loaded once)
_schema: CISchema | None = None


def get_schema(schema_path: Path | None = None) -> CISchema:
    """Get the global CI schema, loading it if necessary.

    Args:
        schema_path: Optional path to schema.yaml.

    Returns:
        The loaded CISchema instance.
    """
    global _schema
    if _schema is None:
        _schema = CISchema.load(schema_path)
    return _schema


def reload_schema(schema_path: Path | None = None) -> CISchema:
    """Force reload the schema from disk.

    Args:
        schema_path: Optional path to schema.yaml.

    Returns:
        The freshly loaded CISchema instance.
    """
    global _schema
    _schema = CISchema.load(schema_path)
    return _schema


@dataclass
class PromptTemplate:
    """A configurable prompt template."""

    name: str
    description: str
    prompt: str
    activity_filter: str | None = None  # Tool names to include (comma-separated)
    min_activities: int = 1  # Minimum activities to trigger this prompt

    def matches_activities(self, tool_names: list[str]) -> bool:
        """Check if activities match this template's filter.

        Args:
            tool_names: List of tool names in the activity batch.

        Returns:
            True if activities match the filter.
        """
        if not self.activity_filter:
            return True

        filter_tools = {t.strip().lower() for t in self.activity_filter.split(",")}
        activity_tools = {t.lower() for t in tool_names}

        # Check if any filter tools are present
        return bool(filter_tools & activity_tools)

    @classmethod
    def from_file(cls, path: Path) -> "PromptTemplate | None":
        """Load a template from a markdown file with YAML frontmatter.

        Args:
            path: Path to the .md template file.

        Returns:
            PromptTemplate if valid, None otherwise.
        """
        try:
            content = path.read_text()

            # Parse YAML frontmatter (between --- markers)
            if not content.startswith("---"):
                logger.warning(f"Template {path} missing YAML frontmatter")
                return None

            parts = content.split("---", 2)
            if len(parts) < 3:
                logger.warning(f"Template {path} has invalid frontmatter format")
                return None

            frontmatter = yaml.safe_load(parts[1])
            prompt_body = parts[2].strip()

            if not frontmatter.get("name"):
                logger.warning(f"Template {path} missing 'name' in frontmatter")
                return None

            return cls(
                name=frontmatter["name"],
                description=frontmatter.get("description", ""),
                prompt=prompt_body,
                activity_filter=frontmatter.get("activity_filter"),
                min_activities=frontmatter.get("min_activities", 1),
            )

        except (OSError, yaml.YAMLError, ValueError, TypeError, KeyError, AttributeError) as e:
            logger.warning(f"Failed to load template {path}: {e}")
            return None


@dataclass
class PromptTemplateConfig:
    """Configuration for prompt templates."""

    templates: list[PromptTemplate] = field(default_factory=list)
    default_template: str = "extraction"

    @classmethod
    def load_from_directory(cls, prompts_dir: Path | None = None) -> "PromptTemplateConfig":
        """Load all templates from a directory.

        Args:
            prompts_dir: Directory containing .md template files.
                        Defaults to features/codebase-intelligence/prompts/.

        Returns:
            Loaded configuration with all templates.
        """
        if prompts_dir is None:
            prompts_dir = DEFAULT_PROMPTS_DIR

        templates = []

        if prompts_dir.exists():
            for path in prompts_dir.glob("*.md"):
                template = PromptTemplate.from_file(path)
                if template:
                    templates.append(template)
                    logger.debug(f"Loaded prompt template: {template.name}")

        if not templates:
            logger.warning(f"No templates found in {prompts_dir}, using fallback")
            templates = [cls._get_fallback_template()]

        return cls(templates=templates, default_template="extraction")

    @staticmethod
    def _get_fallback_template() -> PromptTemplate:
        """Get a minimal fallback template if no files found."""
        return PromptTemplate(
            name="extraction",
            description="Fallback extraction template",
            prompt="""Extract observations from this coding session.

Activities: {{activities}}
Duration: {{session_duration}} minutes

Return JSON with observations array and summary string.
Each observation has: type (gotcha/decision/bug_fix/discovery), observation, context, importance.

Respond ONLY with valid JSON.""",
        )

    def get_template(self, name: str) -> PromptTemplate | None:
        """Get template by name."""
        for t in self.templates:
            if t.name == name:
                return t
        return None

    def select_template(self, tool_names: list[str], has_errors: bool = False) -> PromptTemplate:
        """Select the best template for given activities.

        Args:
            tool_names: List of tool names in the activity batch.
            has_errors: Whether errors were encountered.

        Returns:
            Best matching PromptTemplate.
        """
        # Prefer debugging template if errors present
        if has_errors:
            debugging = self.get_template("debugging")
            if debugging:
                return debugging

        # Check for implementation pattern (writes/edits dominate)
        edit_count = sum(1 for t in tool_names if t in ("Write", "Edit"))
        if edit_count > len(tool_names) * 0.3:
            impl = self.get_template("implementation")
            if impl:
                return impl

        # Check for exploration pattern (reads/searches dominate)
        explore_count = sum(1 for t in tool_names if t in ("Read", "Grep", "Glob"))
        if explore_count > len(tool_names) * 0.5:
            explore = self.get_template("exploration")
            if explore:
                return explore

        # Fall back to default
        default = self.get_template(self.default_template)
        return default or self.templates[0]


def render_prompt(
    template: PromptTemplate,
    activities: list[dict[str, Any]],
    session_duration: float,
    files_read: list[str],
    files_modified: list[str],
    files_created: list[str],
    errors: list[str],
    max_activities: int = 30,
    schema: CISchema | None = None,
) -> str:
    """Render a prompt template with activity data.

    Args:
        template: Prompt template to render.
        activities: List of activity dictionaries.
        session_duration: Session duration in minutes.
        files_read: List of files read.
        files_modified: List of files modified.
        files_created: List of files created.
        errors: List of error messages.
        max_activities: Maximum activities to include (for context budget).
        schema: Optional CI schema for type definitions.

    Returns:
        Rendered prompt string.
    """
    # Get schema if not provided
    if schema is None:
        schema = get_schema()

    # Format activities as readable text (limit for context budget)
    activity_lines = []
    activities_to_show = activities[:max_activities]
    for i, act in enumerate(activities_to_show, 1):
        tool = act.get("tool_name", "Unknown")
        file_path = act.get("file_path", "")
        summary = act.get("tool_output_summary", "")[:150]  # Truncate summaries

        line = f"{i}. **{tool}**"
        if file_path:
            line += f" - `{file_path}`"
        if summary:
            line += f"\n   {summary}"

        activity_lines.append(line)

    if len(activities) > max_activities:
        activity_lines.append(f"\n... and {len(activities) - max_activities} more activities")

    activities_text = "\n".join(activity_lines) if activity_lines else "(no activities)"

    # Build placeholder values
    placeholders = {
        "activities": activities_text,
        "session_duration": f"{session_duration:.1f}",
        "files_read": ", ".join(files_read[:20]) or "(none)",
        "files_modified": ", ".join(files_modified[:20]) or "(none)",
        "files_created": ", ".join(files_created[:20]) or "(none)",
        "errors": "\n".join(f"- {e}" for e in errors[:10]) or "(none)",
        # Schema-driven placeholders
        "observation_types": schema.format_observation_types_for_prompt(),
        "classification_types": schema.format_classification_types_for_prompt(),
        "type_names": schema.get_type_names_json(),
    }

    # Replace placeholders
    prompt = template.prompt
    for key, value in placeholders.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

    return prompt
