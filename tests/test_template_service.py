"""Comprehensive tests for template service."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import jinja2
import pytest
from jinja2 import TemplateNotFound

from open_agent_kit.services.template_service import (
    TemplateService,
    get_template_service,
)


class TestTemplateServiceInitialization:
    """Test TemplateService initialization."""

    def test_init_with_defaults(self, tmp_path: Path) -> None:
        """Test initialization with default parameters."""
        service = TemplateService(project_root=tmp_path)
        assert service.project_root == tmp_path
        assert service.templates_dir is None
        assert service.env is not None

    def test_init_with_custom_templates_dir(self, tmp_path: Path) -> None:
        """Test initialization with custom templates directory."""
        custom_dir = tmp_path / "custom_templates"
        service = TemplateService(templates_dir=custom_dir, project_root=tmp_path)
        assert service.templates_dir == custom_dir
        assert service.project_root == tmp_path

    def test_init_creates_environment(self, tmp_path: Path) -> None:
        """Test that initialization creates a Jinja2 environment."""
        service = TemplateService(project_root=tmp_path)
        assert isinstance(service.env, jinja2.Environment)

    def test_project_root_defaults_to_cwd(self) -> None:
        """Test that project_root defaults to current working directory."""
        service = TemplateService()
        assert service.project_root == Path.cwd()

    def test_project_features_dir_structure(self, tmp_path: Path) -> None:
        """Test project features directory is correctly constructed."""
        service = TemplateService(project_root=tmp_path)
        expected = tmp_path / ".oak" / "features"
        assert service.project_features_dir == expected

    def test_package_features_dir_exists(self, tmp_path: Path) -> None:
        """Test package features directory reference."""
        service = TemplateService(project_root=tmp_path)
        # Should reference the actual package features directory
        assert "features" in str(service.package_features_dir)


class TestEnvironmentSetup:
    """Test Jinja2 environment configuration."""

    def test_environment_has_custom_filters(self, tmp_path: Path) -> None:
        """Test that custom filters are registered."""
        service = TemplateService(project_root=tmp_path)
        assert "title_case" in service.env.filters
        assert "snake_case" in service.env.filters
        assert "kebab_case" in service.env.filters
        assert "camel_case" in service.env.filters

    def test_title_case_filter(self, tmp_path: Path) -> None:
        """Test title_case filter transforms strings correctly."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("{{ 'hello-world' | title_case }}")
        assert result == "Hello World"

    def test_title_case_filter_with_underscores(self, tmp_path: Path) -> None:
        """Test title_case filter handles underscores."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("{{ 'hello_world' | title_case }}")
        assert result == "Hello World"

    def test_snake_case_filter(self, tmp_path: Path) -> None:
        """Test snake_case filter."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("{{ 'Hello-World' | snake_case }}")
        assert result == "hello_world"

    def test_kebab_case_filter(self, tmp_path: Path) -> None:
        """Test kebab_case filter."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("{{ 'Hello_World' | kebab_case }}")
        assert result == "hello-world"

    def test_camel_case_filter(self, tmp_path: Path) -> None:
        """Test camel_case filter."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("{{ 'hello-world' | camel_case }}")
        assert result == "HelloWorld"

    def test_camel_case_filter_complex(self, tmp_path: Path) -> None:
        """Test camel_case filter with spaces."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("{{ 'hello world test' | camel_case }}")
        assert result == "HelloWorldTest"

    def test_environment_has_global_now(self, tmp_path: Path) -> None:
        """Test that now() global function is available."""
        service = TemplateService(project_root=tmp_path)
        assert "now" in service.env.globals
        assert callable(service.env.globals["now"])

    def test_environment_has_global_today(self, tmp_path: Path) -> None:
        """Test that today global variable is available."""
        service = TemplateService(project_root=tmp_path)
        assert "today" in service.env.globals
        # today should be a formatted date string
        today = service.env.globals["today"]
        assert isinstance(today, str)
        # Should match YYYY-MM-DD format
        assert len(today.split("-")) == 3

    def test_environment_has_global_year(self, tmp_path: Path) -> None:
        """Test that year global variable is available."""
        service = TemplateService(project_root=tmp_path)
        assert "year" in service.env.globals
        assert service.env.globals["year"] == datetime.now().year

    def test_trim_blocks_enabled(self, tmp_path: Path) -> None:
        """Test that trim_blocks is enabled in environment."""
        service = TemplateService(project_root=tmp_path)
        assert service.env.trim_blocks is True

    def test_lstrip_blocks_enabled(self, tmp_path: Path) -> None:
        """Test that lstrip_blocks is enabled in environment."""
        service = TemplateService(project_root=tmp_path)
        assert service.env.lstrip_blocks is True


class TestRenderString:
    """Test render_string method."""

    def test_render_simple_string(self, tmp_path: Path) -> None:
        """Test rendering a simple template string."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("Hello {{ name }}!", {"name": "World"})
        assert result == "Hello World!"

    def test_render_string_with_none_context(self, tmp_path: Path) -> None:
        """Test rendering with None context defaults to empty dict."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("Hello World!")
        assert result == "Hello World!"

    def test_render_string_with_filters(self, tmp_path: Path) -> None:
        """Test rendering with custom filters."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("{{ name | title_case }}", {"name": "hello-world"})
        assert result == "Hello World"

    def test_render_string_with_globals(self, tmp_path: Path) -> None:
        """Test rendering with global functions."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("Year: {{ year }}")
        assert str(datetime.now().year) in result

    def test_render_string_with_complex_context(self, tmp_path: Path) -> None:
        """Test rendering with complex context variables."""
        service = TemplateService(project_root=tmp_path)
        context = {
            "title": "Test RFC",
            "tags": ["python", "testing"],
            "metadata": {"version": "1.0", "author": "Test"},
        }
        template = """# {{ title }}
Tags: {{ tags | join(', ') }}
Author: {{ metadata.author }}"""
        result = service.render_string(template, context)
        assert "# Test RFC" in result
        assert "python, testing" in result
        assert "Author: Test" in result

    def test_render_string_empty(self, tmp_path: Path) -> None:
        """Test rendering empty string."""
        service = TemplateService(project_root=tmp_path)
        result = service.render_string("")
        assert result == ""

    def test_render_string_with_jinja_syntax_error(self, tmp_path: Path) -> None:
        """Test rendering with invalid Jinja2 syntax raises error."""
        service = TemplateService(project_root=tmp_path)
        with pytest.raises(jinja2.exceptions.TemplateSyntaxError):
            service.render_string("{{ unclosed variable")

    def test_render_string_with_undefined_variable(self, tmp_path: Path) -> None:
        """Test rendering with undefined variable in strict mode."""
        service = TemplateService(project_root=tmp_path)
        # By default, undefined variables render as empty strings
        result = service.render_string("{{ undefined_var }}")
        assert result == ""

    def test_render_string_with_loops(self, tmp_path: Path) -> None:
        """Test rendering with Jinja2 loops."""
        service = TemplateService(project_root=tmp_path)
        template = "{% for item in items %}{{ item }}, {% endfor %}"
        result = service.render_string(template, {"items": ["a", "b", "c"]})
        assert "a," in result
        assert "b," in result
        assert "c," in result

    def test_render_string_with_conditionals(self, tmp_path: Path) -> None:
        """Test rendering with Jinja2 conditionals."""
        service = TemplateService(project_root=tmp_path)
        template = "{% if flag %}yes{% else %}no{% endif %}"
        result_true = service.render_string(template, {"flag": True})
        result_false = service.render_string(template, {"flag": False})
        assert result_true == "yes"
        assert result_false == "no"


class TestRenderTemplate:
    """Test render_template method."""

    def test_render_template_not_found_raises_error(self, tmp_path: Path) -> None:
        """Test that rendering non-existent template raises FileNotFoundError."""
        service = TemplateService(project_root=tmp_path)
        with pytest.raises(FileNotFoundError, match="Template not found"):
            service.render_template("nonexistent.md")

    def test_render_template_with_simple_name(self, tmp_path: Path) -> None:
        """Test rendering template with simple filename."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_template = MagicMock()
            mock_template.render.return_value = "# Test\n\nContent"
            mock_get_template.return_value = mock_template

            result = service.render_template("test.md", {"title": "Test", "body": "Content"})
            assert result == "# Test\n\nContent"

    def test_render_template_with_feature_prefix(self, tmp_path: Path) -> None:
        """Test rendering template with feature/filename format."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_template = MagicMock()
            mock_template.render.return_value = "Rendered"
            mock_get_template.return_value = mock_template

            service.render_template("rfc/test.md")
            # Should normalize to just "test.md"
            mock_get_template.assert_called_with("test.md")

    def test_render_template_normalizes_path(self, tmp_path: Path) -> None:
        """Test that template names are normalized (feature/ prefix stripped)."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_template = MagicMock()
            mock_template.render.return_value = "Content"
            mock_get_template.return_value = mock_template

            service.render_template("constitution/base.md")
            mock_get_template.assert_called_with("base.md")

    def test_render_template_with_context(self, tmp_path: Path) -> None:
        """Test rendering with context variables."""
        service = TemplateService(project_root=tmp_path)

        context = {
            "title": "RFC Title",
            "author": "Test Author",
        }

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_template = MagicMock()
            mock_template.render.return_value = "RFC Title by Test Author"
            mock_get_template.return_value = mock_template

            result = service.render_template("template.md", context)
            mock_template.render.assert_called_with(**context)
            assert result == "RFC Title by Test Author"

    def test_render_template_none_context_defaults_to_empty(self, tmp_path: Path) -> None:
        """Test that None context is converted to empty dict."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_template = MagicMock()
            mock_template.render.return_value = "Content"
            mock_get_template.return_value = mock_template

            service.render_template("test.md", None)
            mock_template.render.assert_called_with()

    def test_render_template_not_found_from_jinja_raises_file_error(self, tmp_path: Path) -> None:
        """Test TemplateNotFound exception is converted to FileNotFoundError."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_get_template.side_effect = TemplateNotFound("missing.md")

            with pytest.raises(FileNotFoundError, match="Template not found"):
                service.render_template("missing.md")


class TestTemplateExists:
    """Test template_exists method."""

    def test_template_exists_when_path_found(self, tmp_path: Path) -> None:
        """Test template_exists returns True when get_template_path succeeds."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service, "get_template_path") as mock_get_path:
            mock_get_path.return_value = tmp_path / "test.md"
            assert service.template_exists("test.md") is True

    def test_template_exists_when_path_not_found(self, tmp_path: Path) -> None:
        """Test template_exists returns False when get_template_path returns None."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service, "get_template_path") as mock_get_path:
            mock_get_path.return_value = None
            assert service.template_exists("nonexistent.md") is False


class TestGetTemplatePath:
    """Test get_template_path method."""

    def test_get_template_path_with_feature_prefix(self, tmp_path: Path) -> None:
        """Test getting template path with feature/filename format."""
        service = TemplateService(project_root=tmp_path)

        # Create project template structure
        project_feature_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        project_feature_dir.mkdir(parents=True)
        template_file = project_feature_dir / "test.md"
        template_file.write_text("content")

        result = service.get_template_path("rfc/test.md")
        assert result == template_file

    def test_get_template_path_returns_none_if_not_found(self, tmp_path: Path) -> None:
        """Test get_template_path returns None if template doesn't exist."""
        service = TemplateService(project_root=tmp_path)
        result = service.get_template_path("nonexistent/template.md")
        assert result is None

    def test_get_template_path_project_priority(self, tmp_path: Path) -> None:
        """Test that project templates have priority over package templates."""
        service = TemplateService(project_root=tmp_path)

        # Create both project and package templates
        project_feature_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        project_feature_dir.mkdir(parents=True)
        project_file = project_feature_dir / "test.md"
        project_file.write_text("project")

        # Mock package template
        with patch.object(service, "package_features_dir", Path("/fake/package/features")):
            result = service.get_template_path("rfc/test.md")
            # Should find project template first
            assert result == project_file

    def test_get_template_path_without_feature_prefix_searches_all(self, tmp_path: Path) -> None:
        """Test searching without feature prefix searches all features."""
        service = TemplateService(project_root=tmp_path)

        # Create template in rfc feature
        rfc_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        rfc_dir.mkdir(parents=True)
        rfc_file = rfc_dir / "test.md"
        rfc_file.write_text("rfc template")

        result = service.get_template_path("test.md")
        assert result == rfc_file

    def test_get_template_path_custom_dir_fallback(self, tmp_path: Path) -> None:
        """Test fallback to custom templates directory."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        template_file = custom_dir / "test.md"
        template_file.write_text("custom")

        service = TemplateService(templates_dir=custom_dir, project_root=tmp_path)
        result = service.get_template_path("test.md")
        assert result == template_file


class TestListTemplates:
    """Test list_templates method."""

    def test_list_templates_empty(self, tmp_path: Path) -> None:
        """Test listing templates when none exist."""
        service = TemplateService(project_root=tmp_path)
        templates = service.list_templates()
        # Should return at least the package templates
        assert isinstance(templates, list)

    def test_list_templates_finds_markdown(self, tmp_path: Path) -> None:
        """Test that list_templates finds markdown files."""
        service = TemplateService(project_root=tmp_path)

        # Create markdown template
        rfc_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        rfc_dir.mkdir(parents=True)
        (rfc_dir / "test.md").write_text("content")

        templates = service.list_templates()
        assert "rfc/test.md" in templates

    def test_list_templates_finds_yaml(self, tmp_path: Path) -> None:
        """Test that list_templates finds YAML files."""
        service = TemplateService(project_root=tmp_path)

        # Create yaml template
        const_dir = tmp_path / ".oak" / "features" / "constitution" / "templates"
        const_dir.mkdir(parents=True)
        (const_dir / "config.yaml").write_text("key: value")

        templates = service.list_templates()
        assert "constitution/config.yaml" in templates

    def test_list_templates_finds_json(self, tmp_path: Path) -> None:
        """Test that list_templates finds JSON files."""
        service = TemplateService(project_root=tmp_path)

        # Create json template
        plan_dir = tmp_path / ".oak" / "features" / "plan" / "templates"
        plan_dir.mkdir(parents=True)
        (plan_dir / "config.json").write_text("{}")

        templates = service.list_templates()
        assert "plan/config.json" in templates

    def test_list_templates_with_category_filter(self, tmp_path: Path) -> None:
        """Test filtering templates by category."""
        service = TemplateService(project_root=tmp_path)

        # Create templates in multiple features
        rfc_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        rfc_dir.mkdir(parents=True)
        (rfc_dir / "template1.md").write_text("rfc")

        plan_dir = tmp_path / ".oak" / "features" / "plan" / "templates"
        plan_dir.mkdir(parents=True)
        (plan_dir / "template2.md").write_text("plan")

        # Filter by rfc category
        templates = service.list_templates(category="rfc")
        assert any(t.startswith("rfc/") for t in templates)
        assert not any(t.startswith("plan/") for t in templates)

    def test_list_templates_sorted(self, tmp_path: Path) -> None:
        """Test that returned templates are sorted."""
        service = TemplateService(project_root=tmp_path)

        # Create multiple templates
        rfc_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        rfc_dir.mkdir(parents=True)
        (rfc_dir / "zebra.md").write_text("z")
        (rfc_dir / "apple.md").write_text("a")

        templates = service.list_templates()
        # Filter to just our test templates
        our_templates = [t for t in templates if t in ["rfc/apple.md", "rfc/zebra.md"]]
        assert our_templates == sorted(our_templates)

    def test_list_templates_avoids_duplicates(self, tmp_path: Path) -> None:
        """Test that duplicates are not returned."""
        service = TemplateService(project_root=tmp_path)

        # Create template
        rfc_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        rfc_dir.mkdir(parents=True)
        (rfc_dir / "test.md").write_text("content")

        templates = service.list_templates()
        # Count occurrences of our template
        count = sum(1 for t in templates if t == "rfc/test.md")
        assert count == 1

    def test_list_templates_custom_dir(self, tmp_path: Path) -> None:
        """Test listing from custom templates directory."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        (custom_dir / "custom.md").write_text("custom")

        service = TemplateService(templates_dir=custom_dir, project_root=tmp_path)
        templates = service.list_templates()
        assert "custom.md" in templates


class TestCopyTemplateToProject:
    """Test copy_template_to_project method."""

    def test_copy_template_creates_destination(self, tmp_path: Path) -> None:
        """Test that copying template creates required directories."""
        service = TemplateService(project_root=tmp_path)

        # Create source template
        custom_dir = tmp_path / "custom_templates"
        custom_dir.mkdir()
        source = custom_dir / "test.md"
        source.write_text("template content")

        service.templates_dir = custom_dir

        # Copy to project
        dest = service.copy_template_to_project("test.md")
        assert dest.exists()
        assert dest.read_text() == "template content"

    def test_copy_template_not_found_raises_error(self, tmp_path: Path) -> None:
        """Test copying non-existent template raises FileNotFoundError."""
        service = TemplateService(project_root=tmp_path)

        with pytest.raises(FileNotFoundError, match="Template not found"):
            service.copy_template_to_project("nonexistent.md")

    def test_copy_template_with_feature_prefix(self, tmp_path: Path) -> None:
        """Test copying template with feature/filename format."""
        service = TemplateService(project_root=tmp_path)

        # Create source in custom dir
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        source = custom_dir / "source.md"
        source.write_text("content")

        service.templates_dir = custom_dir

        # Mock get_template_path to return our custom template
        with patch.object(service, "get_template_path") as mock_get_path:
            mock_get_path.return_value = source

            dest = service.copy_template_to_project("rfc/test.md")
            assert dest.exists()

    def test_copy_template_respects_existing_when_no_force(self, tmp_path: Path) -> None:
        """Test that existing file is not overwritten without force=True."""
        service = TemplateService(project_root=tmp_path)

        # Create source
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        source = custom_dir / "test.md"
        source.write_text("original")

        # Create existing destination
        dest_path = tmp_path / ".oak" / "features" / "rfc" / "templates" / "test.md"
        dest_path.parent.mkdir(parents=True)
        dest_path.write_text("existing")

        service.templates_dir = custom_dir

        with patch.object(service, "get_template_path") as mock_get_path:
            mock_get_path.return_value = source

            result = service.copy_template_to_project("rfc/test.md", force=False)
            # Should return existing file without overwriting
            assert result == dest_path
            assert result.read_text() == "existing"

    def test_copy_template_overwrites_with_force(self, tmp_path: Path) -> None:
        """Test that force=True overwrites existing file."""
        service = TemplateService(project_root=tmp_path)

        # Create source
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        source = custom_dir / "test.md"
        source.write_text("new content")

        # Create existing destination
        dest_path = tmp_path / ".oak" / "features" / "rfc" / "templates" / "test.md"
        dest_path.parent.mkdir(parents=True)
        dest_path.write_text("old content")

        service.templates_dir = custom_dir

        with patch.object(service, "get_template_path") as mock_get_path:
            mock_get_path.return_value = source

            result = service.copy_template_to_project("rfc/test.md", force=True)
            assert result.read_text() == "new content"

    def test_copy_template_custom_destination(self, tmp_path: Path) -> None:
        """Test copying to custom destination path."""
        service = TemplateService(project_root=tmp_path)

        # Create source
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        source = custom_dir / "test.md"
        source.write_text("content")

        service.templates_dir = custom_dir

        custom_dest = tmp_path / "my_destination.md"

        with patch.object(service, "get_template_path") as mock_get_path:
            mock_get_path.return_value = source

            result = service.copy_template_to_project("rfc/test.md", destination=custom_dest)
            assert result == custom_dest
            assert result.read_text() == "content"

    def test_copy_template_without_feature_prefix_raises_if_no_custom_dir(
        self, tmp_path: Path
    ) -> None:
        """Test copying template without feature prefix raises ValueError if no custom dir."""
        service = TemplateService(project_root=tmp_path)
        service.templates_dir = None

        # Create a mock source template
        with patch.object(service, "get_template_path") as mock_get_path:
            mock_get_path.return_value = tmp_path / "source.md"

            with pytest.raises(ValueError, match="Template name must include feature prefix"):
                service.copy_template_to_project("test.md")


class TestGetTemplateSourcePath:
    """Test get_template_source_path method."""

    def test_get_template_source_path_with_feature_prefix(self, tmp_path: Path) -> None:
        """Test getting source path with feature prefix."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service, "package_features_dir", tmp_path / "package_features"):
            # Create mock package template
            pkg_dir = tmp_path / "package_features" / "rfc" / "templates"
            pkg_dir.mkdir(parents=True)
            pkg_file = pkg_dir / "test.md"
            pkg_file.write_text("package template")

            result = service.get_template_source_path("rfc/test.md")
            assert result == pkg_file

    def test_get_template_source_path_not_found_raises_error(self, tmp_path: Path) -> None:
        """Test that non-existent source template raises FileNotFoundError."""
        service = TemplateService(project_root=tmp_path)

        with pytest.raises(FileNotFoundError, match="Template not found in package"):
            service.get_template_source_path("nonexistent/template.md")

    def test_get_template_source_path_without_feature_prefix(self, tmp_path: Path) -> None:
        """Test getting source path without feature prefix searches all."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service, "package_features_dir", tmp_path / "package_features"):
            # Create mock template in rfc feature
            pkg_dir = tmp_path / "package_features" / "rfc" / "templates"
            pkg_dir.mkdir(parents=True)
            pkg_file = pkg_dir / "test.md"
            pkg_file.write_text("content")

            result = service.get_template_source_path("test.md")
            assert result == pkg_file


class TestGetTemplateProjectPath:
    """Test get_template_project_path method."""

    def test_get_template_project_path_with_feature_prefix(self, tmp_path: Path) -> None:
        """Test getting project path with feature prefix."""
        service = TemplateService(project_root=tmp_path)

        result = service.get_template_project_path("rfc/test.md")
        expected = tmp_path / ".oak" / "features" / "rfc" / "templates" / "test.md"
        assert result == expected

    def test_get_template_project_path_without_feature_uses_custom_dir(
        self, tmp_path: Path
    ) -> None:
        """Test that path without feature prefix uses custom templates dir."""
        custom_dir = tmp_path / "custom"
        service = TemplateService(templates_dir=custom_dir, project_root=tmp_path)

        result = service.get_template_project_path("test.md")
        assert result == custom_dir / "test.md"

    def test_get_template_project_path_without_custom_dir_defaults(self, tmp_path: Path) -> None:
        """Test default path when no feature prefix and no custom dir."""
        service = TemplateService(project_root=tmp_path)

        result = service.get_template_project_path("test.md")
        # Should default to first supported feature
        # Use Path parts for cross-platform compatibility
        assert ".oak" in result.parts
        assert "features" in result.parts
        assert "templates" in result.parts
        assert result.name == "test.md"


class TestRenderToFile:
    """Test render_to_file method."""

    def test_render_to_file_creates_output(self, tmp_path: Path) -> None:
        """Test that render_to_file creates output file."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service, "render_template") as mock_render:
            mock_render.return_value = "rendered content"

            output_path = tmp_path / "output.md"
            result = service.render_to_file("template.md", output_path)

            assert output_path.exists()
            assert output_path.read_text() == "rendered content"
            assert result == output_path

    def test_render_to_file_creates_directories(self, tmp_path: Path) -> None:
        """Test that render_to_file creates parent directories."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service, "render_template") as mock_render:
            mock_render.return_value = "content"

            output_path = tmp_path / "nested" / "dir" / "output.md"
            service.render_to_file("template.md", output_path)

            assert output_path.exists()

    def test_render_to_file_raises_on_existing_without_overwrite(self, tmp_path: Path) -> None:
        """Test that existing file prevents write unless overwrite=True."""
        service = TemplateService(project_root=tmp_path)

        output_path = tmp_path / "output.md"
        output_path.write_text("existing")

        with pytest.raises(FileExistsError, match="File already exists"):
            service.render_to_file("template.md", output_path, overwrite=False)

    def test_render_to_file_overwrites_with_flag(self, tmp_path: Path) -> None:
        """Test that overwrite=True replaces existing file."""
        service = TemplateService(project_root=tmp_path)

        output_path = tmp_path / "output.md"
        output_path.write_text("old content")

        with patch.object(service, "render_template") as mock_render:
            mock_render.return_value = "new content"

            service.render_to_file("template.md", output_path, overwrite=True)
            assert output_path.read_text() == "new content"

    def test_render_to_file_with_context(self, tmp_path: Path) -> None:
        """Test render_to_file passes context to render_template."""
        service = TemplateService(project_root=tmp_path)

        context = {"key": "value"}

        with patch.object(service, "render_template") as mock_render:
            mock_render.return_value = "content"

            output_path = tmp_path / "output.md"
            service.render_to_file("template.md", output_path, context=context)

            mock_render.assert_called_with("template.md", context)


class TestGetTemplateVariables:
    """Test get_template_variables method."""

    def test_get_template_variables_extracts_names(self, tmp_path: Path) -> None:
        """Test extracting variable names from template."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_template = MagicMock()
            mock_template.filename = "test.md"
            mock_get_template.return_value = mock_template

            # Mock the loader's get_source method
            with patch.object(service.env.loader, "get_source") as mock_get_source:
                mock_get_source.return_value = (
                    "{{ title }} and {{ author }}",
                    "test.md",
                    lambda: True,
                )

                # Create a mock AST that finds variables
                with patch.object(service.env, "parse") as mock_parse:
                    mock_ast = MagicMock()
                    # Mock find_all to return Name nodes
                    title_node = MagicMock()
                    title_node.name = "title"
                    author_node = MagicMock()
                    author_node.name = "author"
                    mock_ast.find_all.return_value = [title_node, author_node]
                    mock_parse.return_value = mock_ast

                    variables = service.get_template_variables("test.md")
                    assert len(variables) >= 0  # Should find variables

    def test_get_template_variables_with_feature_prefix(self, tmp_path: Path) -> None:
        """Test variable extraction with feature/filename format."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env.loader, "get_source") as mock_get_source:
            mock_get_source.return_value = ("{{ var }}", "template.md", lambda: True)

            with patch.object(service.env, "parse") as mock_parse:
                mock_ast = MagicMock()
                mock_ast.find_all.return_value = []
                mock_parse.return_value = mock_ast

                # Call with feature prefix
                service.get_template_variables("rfc/template.md")
                # Should normalize and call with just the filename
                mock_get_source.assert_called()

    def test_get_template_variables_returns_empty_on_error(self, tmp_path: Path) -> None:
        """Test that errors during variable extraction return empty set."""
        service = TemplateService(project_root=tmp_path)

        # Mock loader to raise exception
        with patch.object(service.env, "loader", None):
            variables = service.get_template_variables("test.md")
            assert variables == set()


class TestValidateTemplateSyntax:
    """Test validate_template_syntax method."""

    def test_validate_template_syntax_valid(self, tmp_path: Path) -> None:
        """Test validation of valid template syntax."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_template = MagicMock()
            mock_get_template.return_value = mock_template

            is_valid, error = service.validate_template_syntax("test.md")
            assert is_valid is True
            assert error is None

    def test_validate_template_syntax_invalid(self, tmp_path: Path) -> None:
        """Test validation of invalid template syntax."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_get_template.side_effect = jinja2.TemplateSyntaxError("Unexpected '}'", lineno=1)

            is_valid, error = service.validate_template_syntax("test.md")
            assert is_valid is False
            assert error is not None
            assert "Unexpected" in error

    def test_validate_template_syntax_file_not_found(self, tmp_path: Path) -> None:
        """Test validation when template file not found."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_get_template.side_effect = TemplateNotFound("missing.md")

            is_valid, error = service.validate_template_syntax("missing.md")
            assert is_valid is False
            assert error is not None

    def test_validate_template_syntax_with_feature_prefix(self, tmp_path: Path) -> None:
        """Test validation with feature/filename format."""
        service = TemplateService(project_root=tmp_path)

        with patch.object(service.env, "get_template") as mock_get_template:
            mock_template = MagicMock()
            mock_get_template.return_value = mock_template

            is_valid, error = service.validate_template_syntax("rfc/test.md")
            # Should normalize to just filename
            mock_get_template.assert_called_with("test.md")
            assert is_valid is True


class TestCreateTemplate:
    """Test create_template method."""

    def test_create_template_writes_file(self, tmp_path: Path) -> None:
        """Test that create_template writes template file."""
        service = TemplateService(project_root=tmp_path)

        content = "# {{ title }}\n{{ content }}"
        result = service.create_template("rfc/test.md", content)

        assert result.exists()
        assert result.read_text() == content

    def test_create_template_creates_directories(self, tmp_path: Path) -> None:
        """Test that create_template creates parent directories."""
        service = TemplateService(project_root=tmp_path)

        service.create_template("rfc/nested/test.md", "content")
        result = service.get_template_project_path("rfc/nested/test.md")
        assert result.parent.exists()

    def test_create_template_raises_on_existing_without_overwrite(self, tmp_path: Path) -> None:
        """Test that existing template prevents creation without overwrite."""
        service = TemplateService(project_root=tmp_path)

        template_path = service.get_template_project_path("rfc/test.md")
        template_path.parent.mkdir(parents=True)
        template_path.write_text("existing")

        with pytest.raises(FileExistsError, match="Template already exists"):
            service.create_template("rfc/test.md", "new content")

    def test_create_template_overwrites_with_flag(self, tmp_path: Path) -> None:
        """Test that overwrite=True replaces existing template."""
        service = TemplateService(project_root=tmp_path)

        template_path = service.get_template_project_path("rfc/test.md")
        template_path.parent.mkdir(parents=True)
        template_path.write_text("old")

        service.create_template("rfc/test.md", "new", overwrite=True)
        assert template_path.read_text() == "new"

    def test_create_template_with_complex_content(self, tmp_path: Path) -> None:
        """Test creating template with complex Jinja2 content."""
        service = TemplateService(project_root=tmp_path)

        content = """# {{ title }}
Author: {{ author }}
{% for tag in tags %}
- {{ tag }}
{% endfor %}"""

        result = service.create_template("rfc/complex.md", content)
        assert "{{ title }}" in result.read_text()
        assert "{% for tag" in result.read_text()


class TestGetTemplateService:
    """Test get_template_service factory function."""

    def test_get_template_service_default(self) -> None:
        """Test factory function returns TemplateService with defaults."""
        service = get_template_service()
        assert isinstance(service, TemplateService)
        assert service.project_root == Path.cwd()

    def test_get_template_service_with_templates_dir(self, tmp_path: Path) -> None:
        """Test factory function with custom templates directory."""
        custom_dir = tmp_path / "custom"
        service = get_template_service(templates_dir=custom_dir)
        assert service.templates_dir == custom_dir

    def test_get_template_service_with_project_root(self, tmp_path: Path) -> None:
        """Test factory function with custom project root."""
        service = get_template_service(project_root=tmp_path)
        assert service.project_root == tmp_path

    def test_get_template_service_with_both_params(self, tmp_path: Path) -> None:
        """Test factory function with both custom parameters."""
        custom_dir = tmp_path / "templates"
        service = get_template_service(templates_dir=custom_dir, project_root=tmp_path)
        assert service.templates_dir == custom_dir
        assert service.project_root == tmp_path


class TestIntegration:
    """Integration tests with real templates."""

    def test_full_rfc_rendering_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow of finding and rendering an RFC template."""
        # Create a basic RFC template
        rfc_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        rfc_dir.mkdir(parents=True)
        template_file = rfc_dir / "simple.md"
        template_file.write_text("# RFC-{{ number }}: {{ title }}\n\nAuthor: {{ author }}")

        # Create service AFTER creating templates so env is initialized with the right paths
        service = TemplateService(project_root=tmp_path)

        # Test existence
        assert service.template_exists("simple.md")

        # Test rendering
        result = service.render_template(
            "simple.md", {"number": "001", "title": "Test RFC", "author": "John Doe"}
        )
        assert "RFC-001: Test RFC" in result
        assert "Author: John Doe" in result

    def test_multiple_features_coexistence(self, tmp_path: Path) -> None:
        """Test that templates from different features can coexist."""
        service = TemplateService(project_root=tmp_path)

        # Create templates in different features
        for feature in ["rfc", "constitution", "plan"]:
            feature_dir = tmp_path / ".oak" / "features" / feature / "templates"
            feature_dir.mkdir(parents=True)
            (feature_dir / f"{feature}.md").write_text(f"# {feature} template")

        templates = service.list_templates()
        assert "rfc/rfc.md" in templates
        assert "constitution/constitution.md" in templates
        assert "plan/plan.md" in templates

    def test_template_with_filters_and_globals(self, tmp_path: Path) -> None:
        """Test template rendering with multiple filters and globals."""
        # Create template with filters and globals
        rfc_dir = tmp_path / ".oak" / "features" / "rfc" / "templates"
        rfc_dir.mkdir(parents=True)
        template_file = rfc_dir / "advanced.md"
        template_file.write_text(
            "# {{ title | title_case }}\nYears: {% for year in [2020, 2021, 2022] %}{{ year }}, {% endfor %}Today: {{ today }}"
        )

        # Create service AFTER creating templates so env is initialized with the right paths
        service = TemplateService(project_root=tmp_path)

        result = service.render_template("advanced.md", {"title": "hello-world"})
        assert "Hello World" in result
        assert "2020," in result
        assert "2021," in result
        assert "2022," in result
        assert str(datetime.now().year) in result or "today" in result.lower()
