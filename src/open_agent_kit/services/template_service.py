"""Template service for rendering templates with Jinja2."""

from datetime import datetime
from pathlib import Path
from typing import Any

import jinja2
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from open_agent_kit.constants import TEMPLATES_DIR
from open_agent_kit.utils import ensure_dir, file_exists, read_file, write_file


class TemplateService:
    """Service for managing and rendering templates."""

    def __init__(
        self,
        templates_dir: Path | None = None,
        project_root: Path | None = None,
    ):
        """Initialize template service.

        Args:
            templates_dir: Custom templates directory (optional)
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()

        # Use custom templates dir if provided, otherwise use project .oak/templates
        if templates_dir:
            self.templates_dir = templates_dir
        else:
            self.templates_dir = self.project_root / TEMPLATES_DIR

        # Also include package templates as fallback
        self.package_templates_dir = Path(__file__).parent.parent.parent.parent / "templates"

        # Setup Jinja2 environment with multiple loaders
        self.env = self._create_environment()

    def _create_environment(self) -> Environment:
        """Create Jinja2 environment with custom filters and globals.

        Returns:
            Configured Jinja2 Environment
        """
        # Try to load from project templates first, fall back to package templates
        loader = FileSystemLoader([str(self.templates_dir), str(self.package_templates_dir)])
        env = Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)

        # Add custom filters
        env.filters["title_case"] = lambda x: x.replace("-", " ").replace("_", " ").title()
        env.filters["snake_case"] = lambda x: x.lower().replace("-", "_").replace(" ", "_")
        env.filters["kebab_case"] = lambda x: x.lower().replace("_", "-").replace(" ", "-")
        env.filters["camel_case"] = lambda x: "".join(
            word.capitalize() for word in x.replace("-", " ").replace("_", " ").split()
        )

        # Add global functions
        env.globals["now"] = datetime.now
        env.globals["today"] = datetime.now().strftime("%Y-%m-%d")
        env.globals["year"] = datetime.now().year

        return env

    def render_template(
        self,
        template_name: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Render a template with given context.

        Args:
            template_name: Template filename (e.g., "rfc/engineering.md")
            context: Template context variables

        Returns:
            Rendered template string

        Raises:
            TemplateNotFound: If template doesn't exist
        """
        if context is None:
            context = {}

        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except TemplateNotFound as e:
            raise FileNotFoundError(f"Template not found: {template_name}") from e

    def render_string(
        self,
        template_string: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Render a template string with given context.

        Args:
            template_string: Template content as string
            context: Template context variables

        Returns:
            Rendered template string
        """
        if context is None:
            context = {}

        template = self.env.from_string(template_string)
        return template.render(**context)

    def get_template_path(self, template_name: str) -> Path | None:
        """Get full path to a template file.

        Args:
            template_name: Template filename

        Returns:
            Path to template file if it exists, None otherwise
        """
        # Check project templates first
        project_path = self.templates_dir / template_name
        if file_exists(project_path):
            return project_path

        # Check package templates
        package_path = self.package_templates_dir / template_name
        if file_exists(package_path):
            return package_path

        return None

    def template_exists(self, template_name: str) -> bool:
        """Check if template exists.

        Args:
            template_name: Template filename

        Returns:
            True if template exists, False otherwise
        """
        return self.get_template_path(template_name) is not None

    def list_templates(self, category: str | None = None) -> list[str]:
        """List available templates.

        Args:
            category: Optional category to filter by (e.g., "rfc", "commands")

        Returns:
            List of template names
        """
        templates = []

        # Template file extensions to include
        extensions = ["*.md", "*.yaml", "*.json"]

        # List from project templates
        if self.templates_dir.exists():
            for ext in extensions:
                for path in self.templates_dir.rglob(ext):
                    rel_path = path.relative_to(self.templates_dir)
                    templates.append(str(rel_path))

        # List from package templates
        if self.package_templates_dir.exists():
            for ext in extensions:
                for path in self.package_templates_dir.rglob(ext):
                    rel_path = path.relative_to(self.package_templates_dir)
                    template_name = str(rel_path)
                    if template_name not in templates:  # Don't duplicate
                        templates.append(template_name)

        # Filter by category if provided
        if category:
            templates = [t for t in templates if t.startswith(f"{category}/")]

        return sorted(templates)

    def copy_template_to_project(
        self,
        template_name: str,
        destination: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Copy a template from package to project templates directory.

        Args:
            template_name: Template filename
            destination: Optional custom destination path
            force: If True, overwrite existing files

        Returns:
            Path to copied template

        Raises:
            FileNotFoundError: If template doesn't exist
        """
        source_path = self.get_template_path(template_name)
        if not source_path:
            raise FileNotFoundError(f"Template not found: {template_name}")

        # Determine destination
        if destination:
            dest_path = destination
        else:
            dest_path = self.templates_dir / template_name

        # Check if exists and not forcing
        if not force and file_exists(dest_path):
            return dest_path

        # Ensure destination directory exists
        ensure_dir(dest_path.parent)

        # Copy template
        content = read_file(source_path)
        write_file(dest_path, content)

        return dest_path

    def get_template_source_path(self, template_name: str) -> Path:
        """Get path to template in package (source of truth).

        Args:
            template_name: Template filename

        Returns:
            Path to template in package

        Raises:
            FileNotFoundError: If template doesn't exist
        """
        package_path = self.package_templates_dir / template_name
        if not file_exists(package_path):
            raise FileNotFoundError(f"Template not found in package: {template_name}")
        return package_path

    def get_template_project_path(self, template_name: str) -> Path:
        """Get path to template in project.

        Args:
            template_name: Template filename

        Returns:
            Path to template in project (may not exist)
        """
        return self.templates_dir / template_name

    def render_to_file(
        self,
        template_name: str,
        output_path: Path,
        context: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> Path:
        """Render template and write to file.

        Args:
            template_name: Template filename
            output_path: Output file path
            context: Template context variables
            overwrite: Whether to overwrite existing file

        Returns:
            Path to output file

        Raises:
            FileExistsError: If output file exists and overwrite=False
            TemplateNotFound: If template doesn't exist
        """
        if file_exists(output_path) and not overwrite:
            raise FileExistsError(f"File already exists: {output_path}")

        # Render template
        content = self.render_template(template_name, context)

        # Write to file
        write_file(output_path, content)

        return output_path

    def get_template_variables(self, template_name: str) -> set[str]:
        """Extract variable names from a template.

        Args:
            template_name: Template filename

        Returns:
            Set of variable names used in the template
        """
        try:
            # Get template source from the loader
            if self.env.loader is None:
                return set()
            source, _, _ = self.env.loader.get_source(self.env, template_name)
            # Get undeclared variables (variables used but not defined in template)
            ast = self.env.parse(source)
            return set(ast.find_all(jinja2.nodes.Name))  # type: ignore[arg-type]  # jinja2.nodes.Node.find_all() returns Iterator but type stubs are incomplete
        except Exception:
            return set()

    def validate_template_syntax(self, template_name: str) -> tuple[bool, str | None]:
        """Validate template syntax.

        Args:
            template_name: Template filename

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.env.get_template(template_name)
            return (True, None)
        except Exception as e:
            return (False, str(e))

    def create_template(
        self,
        template_name: str,
        content: str,
        overwrite: bool = False,
    ) -> Path:
        """Create a new template in project templates directory.

        Args:
            template_name: Template filename
            content: Template content
            overwrite: Whether to overwrite existing template

        Returns:
            Path to created template

        Raises:
            FileExistsError: If template exists and overwrite=False
        """
        template_path = self.templates_dir / template_name

        if file_exists(template_path) and not overwrite:
            raise FileExistsError(f"Template already exists: {template_name}")

        write_file(template_path, content)
        return template_path


def get_template_service(
    templates_dir: Path | None = None,
    project_root: Path | None = None,
) -> TemplateService:
    """Get a TemplateService instance.

    Args:
        templates_dir: Custom templates directory (optional)
        project_root: Project root directory (defaults to current directory)

    Returns:
        TemplateService instance
    """
    return TemplateService(templates_dir, project_root)
