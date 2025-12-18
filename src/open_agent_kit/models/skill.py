"""Skill models for open-agent-kit."""

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class SkillManifest(BaseModel):
    """Skill manifest model representing a Claude Agent Skill's metadata and content.

    Skills are Claude Agent's native capability system that provides domain knowledge
    and expertise to enhance agent performance. Each skill is a SKILL.md file with
    YAML frontmatter containing metadata and markdown body containing the skill content.

    The name field must follow strict naming conventions to ensure compatibility
    with Claude's skill system. The description provides Claude with context about
    when and how to use the skill.

    Example SKILL.md structure:
        ---
        name: planning-workflow
        description: Guide strategic implementation planning with structured phases
        allowed-tools: Read, Write, Bash
        ---

        # Planning Workflow

        This skill provides guidance on...
    """

    name: str = Field(
        ...,
        description="Skill identifier (lowercase, hyphens, max 64 chars, pattern: ^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$)",
    )
    description: str = Field(..., description="Skill description (non-empty, max 1024 chars)")
    allowed_tools: list[str] = Field(
        default_factory=list,
        description="Optional list of tool names this skill is allowed to use",
    )
    body: str = Field(default="", description="Markdown content after frontmatter (skill content)")

    # Metadata fields
    source_path: Path | None = Field(default=None, description="Path to the source SKILL.md file")
    location: str = Field(
        default="package",
        description="Installation location: 'package', 'project', or 'user'",
    )
    associated_feature: str | None = Field(
        default=None, description="Feature this skill is associated with (if any)"
    )
    version: str = Field(default="1.0.0", description="Skill version")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate skill name follows Claude naming conventions.

        Skill names must:
        - Be lowercase
        - Use hyphens as separators (no underscores or spaces)
        - Be 64 characters or less
        - Start and end with alphanumeric (or be a single alphanumeric)
        - Match pattern: ^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$

        Args:
            v: Skill name to validate

        Returns:
            Validated skill name

        Raises:
            ValueError: If name doesn't meet requirements
        """
        if not v:
            raise ValueError("Skill name cannot be empty")

        if len(v) > 64:
            raise ValueError(f"Skill name too long: {len(v)} chars (max 64). Got: '{v}'")

        # Pattern allows either:
        # - Single alphanumeric character: ^[a-z0-9]$
        # - Multi-char with start/end alphanumeric: ^[a-z0-9][a-z0-9-]*[a-z0-9]$
        pattern = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Skill name must be lowercase alphanumeric with hyphens, "
                f"start and end with alphanumeric. Got: '{v}'. "
                f"Pattern: {pattern}"
            )

        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate skill description is non-empty and within length limits.

        Args:
            v: Description to validate

        Returns:
            Validated description

        Raises:
            ValueError: If description is empty or too long
        """
        if not v or not v.strip():
            raise ValueError("Skill description cannot be empty")

        if len(v) > 1024:
            raise ValueError(f"Skill description too long: {len(v)} chars (max 1024)")

        return v.strip()

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        """Validate location is one of the allowed values.

        Args:
            v: Location to validate

        Returns:
            Validated location

        Raises:
            ValueError: If location is not valid
        """
        valid_locations = {"package", "project", "user"}
        if v not in valid_locations:
            raise ValueError(f"Invalid location: '{v}'. Must be one of {valid_locations}")
        return v

    @classmethod
    def load(cls, skill_path: Path) -> "SkillManifest":
        """Load skill manifest from SKILL.md file.

        Parses a SKILL.md file with YAML frontmatter and markdown body.
        The frontmatter is delimited by --- markers at the beginning of the file.

        Example SKILL.md:
            ---
            name: my-skill
            description: My skill description
            allowed-tools: Read, Write
            ---

            # Skill Content

            This is the skill body...

        Args:
            skill_path: Path to SKILL.md file

        Returns:
            SkillManifest instance

        Raises:
            FileNotFoundError: If skill file doesn't exist
            ValueError: If skill file is invalid or missing required fields
        """
        if not skill_path.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_path}")

        if not skill_path.is_file():
            raise ValueError(f"Skill path is not a file: {skill_path}")

        with open(skill_path, encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            raise ValueError(f"Skill file is empty: {skill_path}")

        try:
            frontmatter, body = cls._parse_skill_file(content)
        except ValueError as e:
            raise ValueError(f"Failed to parse skill file {skill_path}: {e}") from e

        # Add metadata
        frontmatter["body"] = body
        frontmatter["source_path"] = skill_path

        # Determine location from path (use as_posix() for cross-platform consistency)
        path_str = skill_path.as_posix()
        if ".oak/skills/" in path_str or ".claude/skills/" in path_str:
            frontmatter["location"] = "project"
        elif "open-agent-kit/skills/" in path_str or "open_agent_kit/skills/" in path_str:
            frontmatter["location"] = "package"
        else:
            frontmatter["location"] = "user"

        return cls(**frontmatter)

    @staticmethod
    def _parse_skill_file(content: str) -> tuple[dict[str, Any], str]:
        """Parse SKILL.md file content into frontmatter dict and body string.

        Expected format:
            ---
            name: skill-name
            description: Skill description
            allowed-tools: tool1, tool2
            ---

            # Body content here

        Args:
            content: Raw SKILL.md file content

        Returns:
            Tuple of (frontmatter_dict, body_string)

        Raises:
            ValueError: If frontmatter is missing or invalid
        """
        # Check for frontmatter markers
        if not content.startswith("---\n"):
            raise ValueError("SKILL.md must start with YAML frontmatter (--- delimiter)")

        # Find end of frontmatter
        end_marker_pos = content.find("\n---\n", 4)
        if end_marker_pos == -1:
            # Try alternative format with --- at end of file
            end_marker_pos = content.find("\n---", 4)
            if end_marker_pos == -1:
                raise ValueError("SKILL.md frontmatter not properly closed (missing closing ---)")

        # Extract frontmatter and body
        frontmatter_text = content[4:end_marker_pos]
        body = content[end_marker_pos + 5 :].strip()  # Skip past "\n---\n"

        # Parse YAML frontmatter
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in frontmatter: {e}") from e

        if not frontmatter:
            raise ValueError("Frontmatter is empty")

        if not isinstance(frontmatter, dict):
            raise ValueError(f"Frontmatter must be a YAML object, got: {type(frontmatter)}")

        # Validate required fields
        if "name" not in frontmatter:
            raise ValueError("Frontmatter missing required field: 'name'")
        if "description" not in frontmatter:
            raise ValueError("Frontmatter missing required field: 'description'")

        # Parse allowed-tools if present (comma-separated string -> list)
        if "allowed-tools" in frontmatter:
            tools = frontmatter["allowed-tools"]
            if isinstance(tools, str):
                # Parse comma-separated string
                frontmatter["allowed_tools"] = [
                    tool.strip() for tool in tools.split(",") if tool.strip()
                ]
            elif isinstance(tools, list):
                # Already a list
                frontmatter["allowed_tools"] = tools
            else:
                raise ValueError(f"allowed-tools must be a string or list, got: {type(tools)}")
            # Remove the hyphenated version
            del frontmatter["allowed-tools"]
        else:
            frontmatter["allowed_tools"] = []

        return frontmatter, body

    def to_skill_file(self) -> str:
        """Serialize manifest back to SKILL.md format.

        Generates a properly formatted SKILL.md file with YAML frontmatter
        and markdown body content.

        Returns:
            SKILL.md file content as string
        """
        # Build frontmatter dict (only include fields that go in YAML)
        frontmatter_dict = {
            "name": self.name,
            "description": self.description,
        }

        # Add allowed-tools if present (convert list to comma-separated string)
        if self.allowed_tools:
            frontmatter_dict["allowed-tools"] = ", ".join(self.allowed_tools)

        # Add version if not default
        if self.version != "1.0.0":
            frontmatter_dict["version"] = self.version

        # Serialize to YAML
        frontmatter_yaml = yaml.safe_dump(
            frontmatter_dict,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

        # Build complete SKILL.md content
        content_parts = [
            "---",
            frontmatter_yaml.rstrip(),
            "---",
        ]

        # Add body if present
        if self.body:
            content_parts.extend(["", self.body])

        return "\n".join(content_parts) + "\n"

    def get_install_dirname(self) -> str:
        """Get the directory name for skill installation.

        The directory name is the skill name, which is already validated
        to be filesystem-safe (lowercase, hyphens only).

        Returns:
            Directory name for installing this skill
        """
        return self.name
