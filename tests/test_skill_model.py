"""Tests for SkillManifest model."""

import pytest

from open_agent_kit.models.skill import SkillManifest


class TestSkillManifestValidation:
    """Tests for SkillManifest field validators."""

    # Name validation tests
    def test_valid_name_simple(self):
        """Simple lowercase name is valid."""
        manifest = SkillManifest(name="planning", description="A planning skill")
        assert manifest.name == "planning"

    def test_valid_name_with_hyphens(self):
        """Name with hyphens is valid."""
        manifest = SkillManifest(name="planning-workflow", description="A planning skill")
        assert manifest.name == "planning-workflow"

    def test_valid_name_with_numbers(self):
        """Name with numbers is valid."""
        manifest = SkillManifest(name="api-v2-client", description="An API client skill")
        assert manifest.name == "api-v2-client"

    def test_valid_name_single_char(self):
        """Single character name is valid."""
        manifest = SkillManifest(name="a", description="A skill")
        assert manifest.name == "a"

    def test_invalid_name_uppercase(self):
        """Uppercase name is rejected."""
        with pytest.raises(ValueError, match="lowercase"):
            SkillManifest(name="Planning", description="A skill")

    def test_invalid_name_with_underscores(self):
        """Name with underscores is rejected."""
        with pytest.raises(ValueError, match="alphanumeric"):
            SkillManifest(name="planning_workflow", description="A skill")

    def test_invalid_name_with_spaces(self):
        """Name with spaces is rejected."""
        with pytest.raises(ValueError, match="alphanumeric"):
            SkillManifest(name="planning workflow", description="A skill")

    def test_invalid_name_starts_with_hyphen(self):
        """Name starting with hyphen is rejected."""
        with pytest.raises(ValueError, match="start and end"):
            SkillManifest(name="-planning", description="A skill")

    def test_invalid_name_ends_with_hyphen(self):
        """Name ending with hyphen is rejected."""
        with pytest.raises(ValueError, match="start and end"):
            SkillManifest(name="planning-", description="A skill")

    def test_invalid_name_empty(self):
        """Empty name is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            SkillManifest(name="", description="A skill")

    def test_invalid_name_too_long(self):
        """Name over 64 chars is rejected."""
        long_name = "a" * 65
        with pytest.raises(ValueError, match="too long"):
            SkillManifest(name=long_name, description="A skill")

    def test_valid_name_at_max_length(self):
        """Name exactly 64 chars is valid."""
        max_name = "a" * 64
        manifest = SkillManifest(name=max_name, description="A skill")
        assert len(manifest.name) == 64

    # Description validation tests
    def test_valid_description(self):
        """Normal description is valid."""
        manifest = SkillManifest(name="test", description="A test skill description")
        assert manifest.description == "A test skill description"

    def test_description_whitespace_trimmed(self):
        """Description whitespace is trimmed."""
        manifest = SkillManifest(name="test", description="  A skill  ")
        assert manifest.description == "A skill"

    def test_invalid_description_empty(self):
        """Empty description is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            SkillManifest(name="test", description="")

    def test_invalid_description_whitespace_only(self):
        """Whitespace-only description is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            SkillManifest(name="test", description="   ")

    def test_invalid_description_too_long(self):
        """Description over 1024 chars is rejected."""
        long_desc = "a" * 1025
        with pytest.raises(ValueError, match="too long"):
            SkillManifest(name="test", description=long_desc)

    def test_valid_description_at_max_length(self):
        """Description exactly 1024 chars is valid."""
        max_desc = "a" * 1024
        manifest = SkillManifest(name="test", description=max_desc)
        assert len(manifest.description) == 1024

    # Location validation tests
    def test_valid_location_package(self):
        """Location 'package' is valid."""
        manifest = SkillManifest(name="test", description="A skill", location="package")
        assert manifest.location == "package"

    def test_valid_location_project(self):
        """Location 'project' is valid."""
        manifest = SkillManifest(name="test", description="A skill", location="project")
        assert manifest.location == "project"

    def test_valid_location_user(self):
        """Location 'user' is valid."""
        manifest = SkillManifest(name="test", description="A skill", location="user")
        assert manifest.location == "user"

    def test_invalid_location(self):
        """Invalid location is rejected."""
        with pytest.raises(ValueError, match="Invalid location"):
            SkillManifest(name="test", description="A skill", location="invalid")


class TestSkillManifestParsing:
    """Tests for SkillManifest file parsing."""

    def test_parse_basic_skill_file(self):
        """Parse a basic SKILL.md format."""
        content = """---
name: test-skill
description: A test skill
---

# Test Skill

Body content here.
"""
        frontmatter, body = SkillManifest._parse_skill_file(content)
        assert frontmatter["name"] == "test-skill"
        assert frontmatter["description"] == "A test skill"
        assert "# Test Skill" in body
        assert "Body content here." in body

    def test_parse_skill_with_allowed_tools_string(self):
        """Parse skill with comma-separated allowed-tools."""
        content = """---
name: test-skill
description: A test skill
allowed-tools: Read, Write, Bash
---

Body content.
"""
        frontmatter, body = SkillManifest._parse_skill_file(content)
        assert frontmatter["allowed_tools"] == ["Read", "Write", "Bash"]
        # Verify hyphenated version was removed
        assert "allowed-tools" not in frontmatter

    def test_parse_skill_with_allowed_tools_list(self):
        """Parse skill with YAML list allowed-tools."""
        content = """---
name: test-skill
description: A test skill
allowed-tools:
  - Read
  - Write
---

Body content.
"""
        frontmatter, body = SkillManifest._parse_skill_file(content)
        assert frontmatter["allowed_tools"] == ["Read", "Write"]

    def test_parse_skill_empty_body(self):
        """Parse skill with no body content."""
        content = """---
name: test-skill
description: A test skill
---
"""
        frontmatter, body = SkillManifest._parse_skill_file(content)
        assert frontmatter["name"] == "test-skill"
        assert body == ""

    def test_parse_missing_frontmatter_start(self):
        """Reject file not starting with ---."""
        content = """name: test-skill
description: A test skill
---
"""
        with pytest.raises(ValueError, match="must start with YAML frontmatter"):
            SkillManifest._parse_skill_file(content)

    def test_parse_missing_frontmatter_end(self):
        """Reject file with unclosed frontmatter."""
        content = """---
name: test-skill
description: A test skill

Body content
"""
        with pytest.raises(ValueError, match="not properly closed"):
            SkillManifest._parse_skill_file(content)

    def test_parse_missing_name(self):
        """Reject frontmatter without name."""
        content = """---
description: A test skill
---

Body
"""
        with pytest.raises(ValueError, match="missing required field.*name"):
            SkillManifest._parse_skill_file(content)

    def test_parse_missing_description(self):
        """Reject frontmatter without description."""
        content = """---
name: test-skill
---

Body
"""
        with pytest.raises(ValueError, match="missing required field.*description"):
            SkillManifest._parse_skill_file(content)

    def test_parse_empty_frontmatter(self):
        """Reject empty frontmatter."""
        content = "---\n\n---\n\nBody\n"
        with pytest.raises(ValueError, match="Frontmatter is empty"):
            SkillManifest._parse_skill_file(content)


class TestSkillManifestLoad:
    """Tests for SkillManifest.load() method."""

    def test_load_from_file(self, tmp_path):
        """Load a valid SKILL.md file."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            """---
name: test-skill
description: A test skill for loading
---

# Test Skill

This is the body.
"""
        )
        manifest = SkillManifest.load(skill_file)
        assert manifest.name == "test-skill"
        assert manifest.description == "A test skill for loading"
        assert "# Test Skill" in manifest.body
        assert manifest.source_path == skill_file

    def test_load_sets_location_project(self, tmp_path):
        """Loading from .claude/skills sets location to 'project'."""
        skills_dir = tmp_path / ".claude" / "skills" / "test-skill"
        skills_dir.mkdir(parents=True)
        skill_file = skills_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: test-skill
description: A test skill
---

Body
"""
        )
        manifest = SkillManifest.load(skill_file)
        assert manifest.location == "project"

    def test_load_sets_location_user(self, tmp_path):
        """Loading from unknown location sets location to 'user'."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(
            """---
name: test-skill
description: A test skill
---

Body
"""
        )
        manifest = SkillManifest.load(skill_file)
        assert manifest.location == "user"

    def test_load_nonexistent_file(self, tmp_path):
        """Load raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="not found"):
            SkillManifest.load(tmp_path / "nonexistent.md")

    def test_load_directory_path(self, tmp_path):
        """Load raises ValueError when given a directory."""
        (tmp_path / "skills").mkdir()
        with pytest.raises(ValueError, match="not a file"):
            SkillManifest.load(tmp_path / "skills")

    def test_load_empty_file(self, tmp_path):
        """Load raises ValueError for empty file."""
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("")
        with pytest.raises(ValueError, match="empty"):
            SkillManifest.load(skill_file)


class TestSkillManifestSerialization:
    """Tests for SkillManifest.to_skill_file() method."""

    def test_serialize_basic(self):
        """Serialize basic manifest to SKILL.md format."""
        manifest = SkillManifest(
            name="test-skill",
            description="A test skill description",
            body="# Test\n\nBody content.",
        )
        content = manifest.to_skill_file()

        # Check frontmatter structure
        assert content.startswith("---\n")
        assert "\n---\n" in content
        assert "name: test-skill" in content
        assert "description: A test skill description" in content

        # Check body is included
        assert "# Test" in content
        assert "Body content." in content

    def test_serialize_with_allowed_tools(self):
        """Serialize manifest with allowed_tools."""
        manifest = SkillManifest(
            name="test-skill",
            description="A skill",
            allowed_tools=["Read", "Write", "Bash"],
            body="Body",
        )
        content = manifest.to_skill_file()
        assert "allowed-tools: Read, Write, Bash" in content

    def test_serialize_with_custom_version(self):
        """Serialize manifest with non-default version."""
        manifest = SkillManifest(
            name="test-skill", description="A skill", version="2.0.0", body="Body"
        )
        content = manifest.to_skill_file()
        assert "version: 2.0.0" in content

    def test_serialize_default_version_omitted(self):
        """Default version (1.0.0) is not included in output."""
        manifest = SkillManifest(
            name="test-skill", description="A skill", version="1.0.0", body="Body"  # Default
        )
        content = manifest.to_skill_file()
        assert "version:" not in content

    def test_serialize_empty_body(self):
        """Serialize manifest with empty body."""
        manifest = SkillManifest(name="test-skill", description="A skill", body="")
        content = manifest.to_skill_file()
        # Should still end with frontmatter closer and newline
        lines = content.strip().split("\n")
        assert lines[-1] == "---"

    def test_roundtrip_serialization(self, tmp_path):
        """Verify serialize then load returns equivalent manifest."""
        original = SkillManifest(
            name="roundtrip-test",
            description="Testing roundtrip serialization",
            allowed_tools=["Read", "Write"],
            body="# Roundtrip\n\nBody content here.",
        )

        # Serialize and write to file
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text(original.to_skill_file())

        # Load back
        loaded = SkillManifest.load(skill_file)

        # Verify equivalence (ignoring metadata fields like source_path)
        assert loaded.name == original.name
        assert loaded.description == original.description
        assert loaded.allowed_tools == original.allowed_tools
        assert loaded.body == original.body


class TestSkillManifestHelpers:
    """Tests for SkillManifest helper methods."""

    def test_get_install_dirname(self):
        """get_install_dirname returns skill name."""
        manifest = SkillManifest(name="test-skill", description="A skill")
        assert manifest.get_install_dirname() == "test-skill"

    def test_default_values(self):
        """Default field values are set correctly."""
        manifest = SkillManifest(name="test", description="A skill")
        assert manifest.allowed_tools == []
        assert manifest.body == ""
        assert manifest.source_path is None
        assert manifest.location == "package"
        assert manifest.associated_feature is None
        assert manifest.version == "1.0.0"
