"""Template service for rendering templates with Jinja2."""

from datetime import datetime
from pathlib import Path
from typing import Any

import jinja2
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from open_agent_kit.config.paths import FEATURES_DIR
from open_agent_kit.constants import SUPPORTED_FEATURES
from open_agent_kit.utils import file_exists, write_file


class TemplateService:
    """Service for managing and rendering templates."""

    def __init__(
        self,
        templates_dir: Path | None = None,
        project_root: Path | None = None,
    ):
        """Initialize template service.

        Args:
            templates_dir: Custom templates directory (optional, for backward compatibility)
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()

        # Use custom templates dir if provided (for backward compatibility)
        self.templates_dir: Path | None = templates_dir

        # Package features directory (templates are read directly from here)
        # Templates are no longer copied to .oak/features/ - they stay in the package
        self.package_features_dir = Path(__file__).parent.parent.parent.parent / FEATURES_DIR

        # Setup Jinja2 environment
        self.env = self._create_environment()

    def _create_environment(self) -> Environment:
        """Create Jinja2 environment with custom filters and globals.

        Returns:
            Configured Jinja2 Environment
        """
        # Build list of template directories
        # Templates are read directly from the package - no project copies
        template_dirs = []

        # Add custom templates dir if provided (for backward compatibility)
        if self.templates_dir:
            template_dirs.append(str(self.templates_dir))

        # Add package feature template directories (source of truth)
        for feature_name in SUPPORTED_FEATURES:
            package_feature_templates = self.package_features_dir / feature_name / "templates"
            if package_feature_templates.exists():
                template_dirs.append(str(package_feature_templates))

        loader = FileSystemLoader(template_dirs)
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
            template_name: Template filename (e.g., "rfc/engineering.md" or "engineering.md")
            context: Template context variables

        Returns:
            Rendered template string

        Raises:
            TemplateNotFound: If template doesn't exist
        """
        if context is None:
            context = {}

        # Normalize template name - strip feature prefix if present
        # since Jinja2 loader sees templates as flat structure
        normalized_name = template_name
        if "/" in template_name:
            # Extract just the filename (e.g., "rfc/engineering.md" -> "engineering.md")
            parts = template_name.split("/", 1)
            if len(parts) == 2:
                normalized_name = parts[1]

        try:
            template = self.env.get_template(normalized_name)
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

        Templates are read directly from the installed package.

        Args:
            template_name: Template filename (e.g., "rfc/engineering.md" or "engineering.md")

        Returns:
            Path to template file if it exists, None otherwise
        """
        # Parse template name to determine feature
        # Format: "feature/filename.ext" or just "filename.ext"
        parts = template_name.split("/", 1)

        if len(parts) == 2:
            feature_name, filename = parts

            # Check package feature templates
            package_feature_path = self.package_features_dir / feature_name / "templates" / filename
            if file_exists(package_feature_path):
                return package_feature_path
        else:
            # Search all package feature directories
            for feature_name in SUPPORTED_FEATURES:
                package_feature_path = (
                    self.package_features_dir / feature_name / "templates" / template_name
                )
                if file_exists(package_feature_path):
                    return package_feature_path

        # Fallback to custom templates dir if provided (backward compatibility)
        if self.templates_dir:
            custom_path = self.templates_dir / template_name
            if file_exists(custom_path):
                return custom_path

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

        Templates are listed from the installed package.

        Args:
            category: Optional category/feature to filter by (e.g., "rfc", "constitution")

        Returns:
            List of template names in format "feature/filename"
        """
        templates = []

        # Template file extensions to include
        extensions = ["*.md", "*.yaml", "*.json"]

        # List from package feature templates (source of truth)
        for feature_name in SUPPORTED_FEATURES:
            package_feature_templates_dir = self.package_features_dir / feature_name / "templates"
            if package_feature_templates_dir.exists():
                for ext in extensions:
                    for path in package_feature_templates_dir.glob(ext):
                        template_name = f"{feature_name}/{path.name}"
                        if template_name not in templates:
                            templates.append(template_name)

        # List from custom templates dir if provided (backward compatibility)
        if self.templates_dir and self.templates_dir.exists():
            for ext in extensions:
                for path in self.templates_dir.rglob(ext):
                    rel_path = path.relative_to(self.templates_dir)
                    template_name = str(rel_path)
                    if template_name not in templates:
                        templates.append(template_name)

        # Filter by category/feature if provided
        if category:
            templates = [t for t in templates if t.startswith(f"{category}/")]

        return sorted(templates)

    def get_template_source_path(self, template_name: str) -> Path:
        """Get path to template in package (source of truth).

        Args:
            template_name: Template filename (e.g., "rfc/engineering.md")

        Returns:
            Path to template in package

        Raises:
            FileNotFoundError: If template doesn't exist
        """
        # Parse template name: "feature/filename"
        parts = template_name.split("/", 1)

        if len(parts) == 2:
            feature_name, filename = parts
            package_path = self.package_features_dir / feature_name / "templates" / filename
            if file_exists(package_path):
                return package_path
        else:
            # Search all features
            for feature_name in SUPPORTED_FEATURES:
                package_path = (
                    self.package_features_dir / feature_name / "templates" / template_name
                )
                if file_exists(package_path):
                    return package_path

        raise FileNotFoundError(f"Template not found in package: {template_name}")

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
            template_name: Template filename (e.g., "rfc/engineering.md" or "engineering.md")

        Returns:
            Set of variable names used in the template
        """
        # Normalize template name - strip feature prefix if present
        normalized_name = template_name
        if "/" in template_name:
            parts = template_name.split("/", 1)
            if len(parts) == 2:
                normalized_name = parts[1]

        try:
            # Get template source from the loader
            if self.env.loader is None:
                return set()
            source, _, _ = self.env.loader.get_source(self.env, normalized_name)
            # Get undeclared variables (variables used but not defined in template)
            ast = self.env.parse(source)
            return set(ast.find_all(jinja2.nodes.Name))  # type: ignore[arg-type]  # jinja2.nodes.Node.find_all() returns Iterator but type stubs are incomplete
        except Exception:
            return set()

    def validate_template_syntax(self, template_name: str) -> tuple[bool, str | None]:
        """Validate template syntax.

        Args:
            template_name: Template filename (e.g., "rfc/engineering.md" or "engineering.md")

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Normalize template name - strip feature prefix if present
        normalized_name = template_name
        if "/" in template_name:
            parts = template_name.split("/", 1)
            if len(parts) == 2:
                normalized_name = parts[1]

        try:
            self.env.get_template(normalized_name)
            return (True, None)
        except Exception as e:
            return (False, str(e))


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
