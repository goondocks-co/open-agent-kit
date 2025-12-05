"""Constitution service for managing engineering constitutions.

This module provides constitution document management for defining project standards,
patterns, and governance. Constitutions serve as the central reference for how projects
are designed, built, and maintained.

Key Classes:
    ConstitutionService: Main service for constitution creation, validation, and amendment

Dependencies:
    - TemplateService: For rendering constitution templates
    - ValidationService: For content validation
    - AgentFileService: For generating/updating agent instruction files

Constitution Structure:
    - Version-controlled markdown document at oak/constitution.md
    - Semantic versioning (MAJOR.MINOR.PATCH)
    - Amendment history tracking
    - Agent instruction files reference the constitution

Amendment Types:
    - major: Breaking changes requiring re-review
    - minor: Backward-compatible additions
    - patch: Small corrections or clarifications

Workflow:
    1. Create initial constitution: `oak constitution create`
    2. Generate agent files: `oak constitution generate-agent-files`
    3. Amend as needed: `oak constitution amend`
    4. Update agent files: `oak constitution update-agent-files`

Example:
    >>> service = ConstitutionService(project_root=Path.cwd())
    >>> constitution = service.create_constitution(
    ...     title="MyProject Constitution",
    ...     author="Engineering Team",
    ...     description="Standards and practices for MyProject"
    ... )
    >>> service.add_amendment(
    ...     amendment_type="minor",
    ...     summary="Added code review checklist",
    ...     content="## Code Review\n\n..."
    ... )
"""

import re
from datetime import date
from pathlib import Path

from open_agent_kit.config.paths import (
    CONSTITUTION_FILENAME,
    CONSTITUTION_TEMPLATE_BASE,
)
from open_agent_kit.constants import CONSTITUTION_REQUIRED_SECTIONS
from open_agent_kit.models.constitution import (
    Amendment,
    AmendmentType,
    ConstitutionDocument,
    ConstitutionMetadata,
    ConstitutionSection,
    ConstitutionStatus,
    DecisionContext,
)
from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.template_service import TemplateService
from open_agent_kit.utils import ensure_dir, file_exists, read_file, write_file
from open_agent_kit.utils.version import increment_version


class ConstitutionService:
    """Service for managing constitution documents."""

    def __init__(self, project_root: Path | None = None):
        """Initialize constitution service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.template_service = TemplateService(project_root=project_root)

    def gather_existing_conventions_context(self) -> dict[str, str | None]:
        """Gather existing agent instructions to use as context for constitution generation.

        This method detects existing agent instruction files (like .github/copilot-instructions.md)
        and returns their content so AI agents can incorporate existing team conventions
        into the generated constitution.

        Returns:
            Dictionary mapping agent_type to instruction file content:
            {
                'copilot': '# Copilot Instructions\n...',
                'claude': None,  # (file doesn't exist)
            }

        Example:
            >>> service = ConstitutionService()
            >>> context = service.gather_existing_conventions_context()
            >>> if context.get('copilot'):
            >>>     print("Found existing Copilot instructions to incorporate")
        """
        agent_service = AgentService(self.project_root)
        existing_instructions = agent_service.detect_existing_agent_instructions()

        # Extract just the content for each agent
        context: dict[str, str | None] = {}
        for agent_type, info in existing_instructions.items():
            if info["exists"] and info["content"]:
                context[agent_type] = info["content"]
            else:
                context[agent_type] = None

        return context

    def get_constitution_path(self) -> Path:
        """Get constitution file path.

        Returns:
            Path to constitution file
        """
        constitution_dir = self.config_service.get_constitution_dir()
        return constitution_dir / CONSTITUTION_FILENAME

    def exists(self) -> bool:
        """Check if constitution exists.

        Returns:
            True if constitution file exists, False otherwise
        """
        return file_exists(self.get_constitution_path())

    def load(self) -> ConstitutionDocument:
        """Load existing constitution from file.

        Returns:
            Loaded ConstitutionDocument

        Raises:
            FileNotFoundError: If constitution doesn't exist
        """
        constitution_path = self.get_constitution_path()

        if not file_exists(constitution_path):
            raise FileNotFoundError(f"Constitution not found at {constitution_path}")

        content = read_file(constitution_path)
        return self._parse_constitution(content, constitution_path)

    def create(
        self,
        project_name: str,
        author: str,
        tech_stack: str | None = None,
        description: str | None = None,
        decision_context: DecisionContext | None = None,
    ) -> ConstitutionDocument:
        """Create a new constitution document with optional decision context.

        Args:
            project_name: Name of the project
            author: Author name
            tech_stack: Optional technology stack description
            description: Optional project description
            decision_context: Decision context as DecisionContext model.
                            If not provided, sensible defaults are used.
                            See decision_points.yaml for available options.

        Returns:
            Created ConstitutionDocument

        Raises:
            FileExistsError: If constitution already exists
        """
        constitution_path = self.get_constitution_path()

        if file_exists(constitution_path):
            raise FileExistsError(f"Constitution already exists at {constitution_path}")

        # Create metadata
        metadata = ConstitutionMetadata(
            project_name=project_name,
            version="1.0.0",
            ratification_date=date.today(),
            author=author,
            last_amendment=None,
            status=ConstitutionStatus.RATIFIED,
            tech_stack=tech_stack,
            description=description,
        )

        # Use provided decision context or defaults
        decisions = decision_context if decision_context else DecisionContext.get_defaults()

        # Render template with decision context
        template_context = metadata.to_dict()
        template_context.update(
            {
                "generation_date": date.today().isoformat(),
            }
        )

        # Merge validated decision context using the model's to_template_context method
        template_context.update(decisions.to_template_context())

        content = self.template_service.render_template(
            CONSTITUTION_TEMPLATE_BASE, template_context
        )

        # Parse sections from rendered content
        sections = self._parse_sections(content)

        # Create document
        constitution = ConstitutionDocument(
            metadata=metadata,
            sections=sections,
            file_path=constitution_path,
        )

        # Save to file
        self._save(constitution)

        return constitution

    def add_amendment(
        self,
        summary: str,
        rationale: str,
        amendment_type: str,
        author: str,
        section: str | None = None,
        impact: str | None = None,
    ) -> Amendment:
        """Add amendment to constitution.

        Args:
            summary: One-line amendment summary
            rationale: Detailed amendment rationale
            amendment_type: Type of amendment ("major", "minor", or "patch")
            author: Amendment author
            section: Optional section being amended
            impact: Optional impact description

        Returns:
            Created Amendment

        Raises:
            FileNotFoundError: If constitution doesn't exist
            ValueError: If amendment type is invalid
        """
        constitution = self.load()

        # Validate and convert amendment type
        try:
            amend_type = AmendmentType(amendment_type.lower())
        except ValueError as error:
            raise ValueError(
                f"Invalid amendment type: {amendment_type}. Must be 'major', 'minor', or 'patch'"
            ) from error

        # Increment version based on amendment type
        current_version = constitution.get_latest_version()
        new_version = increment_version(current_version, amendment_type)

        # Create amendment
        amendment = Amendment(
            version=new_version,
            date=date.today(),
            type=amend_type,
            summary=summary,
            rationale=rationale,
            author=author,
            section=section,
            impact=impact,
        )

        # Add to constitution
        constitution.add_amendment(amendment)

        # Save updated constitution
        self._save(constitution)

        return amendment

    def get_content(self) -> str:
        """Get raw constitution content.

        Returns:
            Constitution file content as string

        Raises:
            FileNotFoundError: If constitution doesn't exist
        """
        constitution_path = self.get_constitution_path()

        if not file_exists(constitution_path):
            raise FileNotFoundError(f"Constitution not found at {constitution_path}")

        return read_file(constitution_path)

    def update_content(self, content: str) -> None:
        """Update constitution content.

        Args:
            content: New constitution content

        Raises:
            FileNotFoundError: If constitution doesn't exist
        """
        constitution_path = self.get_constitution_path()

        if not file_exists(constitution_path):
            raise FileNotFoundError(f"Constitution not found at {constitution_path}")

        write_file(constitution_path, content)

    def get_current_version(self) -> str:
        """Get current constitution version.

        Returns:
            Version string (e.g., "1.2.3")

        Raises:
            FileNotFoundError: If constitution doesn't exist
        """
        constitution = self.load()
        return constitution.get_latest_version()

    def _parse_constitution(self, content: str, file_path: Path) -> ConstitutionDocument:
        """Parse constitution from markdown content.

        Args:
            content: Markdown content
            file_path: Path to constitution file

        Returns:
            Parsed ConstitutionDocument
        """
        # Parse metadata
        metadata = self._parse_metadata(content)

        # Parse sections
        sections = self._parse_sections(content)

        # Parse amendments
        amendments = self._parse_amendments(content)

        return ConstitutionDocument(
            metadata=metadata,
            sections=sections,
            amendments=amendments,
            file_path=file_path,
        )

    def _parse_metadata(self, content: str) -> ConstitutionMetadata:
        """Parse metadata from constitution content.

        Args:
            content: Constitution content

        Returns:
            Parsed ConstitutionMetadata
        """
        metadata_dict = {}

        # Extract project name from title
        title_match = re.search(r"^# (.+?) Engineering Constitution", content, re.MULTILINE)
        if title_match:
            metadata_dict["project_name"] = title_match.group(1).strip()

        # Extract metadata fields
        version_match = re.search(r"^- \*\*Version:\*\* (.+)$", content, re.MULTILINE)
        if version_match:
            metadata_dict["version"] = version_match.group(1).strip()

        ratification_match = re.search(
            r"^- \*\*Ratification Date:\*\* (.+)$", content, re.MULTILINE
        )
        if ratification_match:
            metadata_dict["ratification_date"] = date.fromisoformat(
                ratification_match.group(1).strip()
            )

        author_match = re.search(r"^- \*\*Author:\*\* (.+)$", content, re.MULTILINE)
        if author_match:
            metadata_dict["author"] = author_match.group(1).strip()

        status_match = re.search(r"^- \*\*Status:\*\* (.+)$", content, re.MULTILINE)
        if status_match:
            metadata_dict["status"] = status_match.group(1).strip().lower()

        last_amendment_match = re.search(r"^- \*\*Last Amendment:\*\* (.+)$", content, re.MULTILINE)
        if last_amendment_match:
            last_amend = last_amendment_match.group(1).strip()
            if last_amend != "N/A":
                metadata_dict["last_amendment"] = date.fromisoformat(last_amend)

        tech_stack_match = re.search(r"^- \*\*Tech Stack:\*\* (.+)$", content, re.MULTILINE)
        if tech_stack_match:
            tech_stack = tech_stack_match.group(1).strip()
            if tech_stack != "N/A":
                metadata_dict["tech_stack"] = tech_stack

        return ConstitutionMetadata.from_dict(metadata_dict)

    def _parse_sections(self, content: str) -> list[ConstitutionSection]:
        """Parse sections from markdown content.

        Args:
            content: Markdown content

        Returns:
            List of parsed ConstitutionSection objects
        """
        sections: list[ConstitutionSection] = []

        # Find where amendments section starts to exclude it
        amendments_match = re.search(r"^# Amendments\s*$", content, re.MULTILINE)
        content_end = amendments_match.start() if amendments_match else len(content)

        # Split by ## headers (section markers) up to amendments
        section_pattern = re.compile(r"^## (.+)$", re.MULTILINE)
        matches = list(section_pattern.finditer(content[:content_end]))

        for i, match in enumerate(matches):
            title = match.group(1).strip()

            # Skip Metadata and Amendments sections
            if title in ["Metadata", "Amendments"]:
                continue

            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else content_end
            section_content = content[start_pos:end_pos].strip()

            # Check if this is a required section
            required = title in CONSTITUTION_REQUIRED_SECTIONS

            section = ConstitutionSection(
                title=title,
                content=section_content,
                order=i,
                required=required,
            )
            sections.append(section)

        return sections

    def _parse_amendments(self, content: str) -> list[Amendment]:
        """Parse amendments from constitution content.

        Args:
            content: Constitution content

        Returns:
            List of parsed Amendment objects
        """
        amendments: list[Amendment] = []

        # Find Amendments section
        amendments_pattern = r"^# Amendments\s*$"
        match = re.search(amendments_pattern, content, re.MULTILINE)

        if not match:
            return amendments

        # Extract amendments section
        amendments_content = content[match.end() :]

        # Parse individual amendments
        amendment_pattern = r"## Amendment (\d+\.\d+\.\d+) \((\d{4}-\d{2}-\d{2})\)"
        matches = list(re.finditer(amendment_pattern, amendments_content))

        for i, amend_match in enumerate(matches):
            version = amend_match.group(1)
            date_str = amend_match.group(2)

            # Extract amendment content
            start = amend_match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(amendments_content)
            amendment_text = amendments_content[start:end].strip()

            # Parse amendment fields
            amendment_dict = {
                "version": version,
                "date": date_str,
            }

            type_match = re.search(r"\*\*Type:\*\* (.+)", amendment_text)
            if type_match:
                amendment_dict["type"] = type_match.group(1).strip().lower()

            author_match = re.search(r"\*\*Author:\*\* (.+)", amendment_text)
            if author_match:
                amendment_dict["author"] = author_match.group(1).strip()

            summary_match = re.search(r"\*\*Summary:\*\* (.+)", amendment_text)
            if summary_match:
                amendment_dict["summary"] = summary_match.group(1).strip()

            rationale_match = re.search(
                r"\*\*Rationale:\*\*\s+(.+?)(?=\n\n|\*\*|$)", amendment_text, re.DOTALL
            )
            if rationale_match:
                amendment_dict["rationale"] = rationale_match.group(1).strip()

            section_match = re.search(r"\*\*Section:\*\* (.+)", amendment_text)
            if section_match:
                amendment_dict["section"] = section_match.group(1).strip()

            impact_match = re.search(r"\*\*Impact:\*\* (.+)", amendment_text)
            if impact_match:
                amendment_dict["impact"] = impact_match.group(1).strip()

            try:
                amendment = Amendment.from_dict(amendment_dict)
                amendments.append(amendment)
            except Exception:
                # Skip invalid amendments
                continue

        return amendments

    def _save(self, constitution: ConstitutionDocument) -> None:
        """Save constitution to file.

        Args:
            constitution: Constitution document to save
        """
        # Ensure directory exists
        constitution_path = self.get_constitution_path()
        ensure_dir(constitution_path.parent)

        # Write constitution
        content = constitution.to_markdown()
        write_file(constitution_path, content)

    def analyze_project(self) -> dict:
        """Analyze project for constitution creation workflow.

        Performs comprehensive project analysis to determine if the project is
        greenfield, brownfield-minimal, or brownfield-mature. This replaces
        multiple bash commands in the agent prompt with a single CLI call.

        Returns:
            Dictionary with analysis results:
            {
                "classification": "greenfield" | "brownfield-minimal" | "brownfield-mature",
                "has_constitution": bool,
                "constitution_path": str | None,
                "test_infrastructure": {
                    "found": bool,
                    "directories": ["tests/", "spec/", ...]
                },
                "ci_cd": {
                    "found": bool,
                    "workflows": [".github/workflows/ci.yml", ...]
                },
                "agent_instructions": {
                    "found": bool,
                    "files": [
                        {"path": "AGENTS.md", "has_content": true, "oak_only": false},
                        ...
                    ]
                },
                "project_files": {
                    "found": bool,
                    "files": ["package.json", "pyproject.toml", ...]
                },
                "application_code": {
                    "found": bool,
                    "directories": ["src/", "lib/", ...]
                },
                "oak_installed": bool,
                "summary": "Human-readable summary of findings"
            }

        Note:
            This method explicitly excludes OAK-installed files (.oak/, oak.* commands)
            from the analysis to avoid false positives on projects that only have
            OAK tooling installed.
        """
        results: dict = {
            "classification": "greenfield",
            "has_constitution": self.exists(),
            "constitution_path": str(self.get_constitution_path()) if self.exists() else None,
            "test_infrastructure": {"found": False, "directories": []},
            "ci_cd": {"found": False, "workflows": []},
            "agent_instructions": {"found": False, "files": []},
            "project_files": {"found": False, "files": []},
            "application_code": {"found": False, "directories": []},
            "oak_installed": False,
            "summary": "",
        }

        # Check if OAK is installed
        oak_dir = self.project_root / ".oak"
        results["oak_installed"] = oak_dir.exists()

        # Detect test infrastructure (excluding .oak/)
        test_dirs = ["tests", "test", "__tests__", "spec", "TestResults", "xunit"]
        for test_dir in test_dirs:
            test_path = self.project_root / test_dir
            if test_path.exists() and test_path.is_dir():
                results["test_infrastructure"]["directories"].append(test_dir)
        results["test_infrastructure"]["found"] = (
            len(results["test_infrastructure"]["directories"]) > 0
        )

        # Detect CI/CD workflows (actual workflow files, not just directories)
        ci_patterns = [
            (".github/workflows", "*.yml"),
            (".github/workflows", "*.yaml"),
            (".gitlab-ci.yml", None),
            (".circleci/config.yml", None),
            ("azure-pipelines.yml", None),
            (".travis.yml", None),
            ("Jenkinsfile", None),
            (".buildkite", "*.yml"),
        ]
        for pattern_path, glob_pattern in ci_patterns:
            full_path = self.project_root / pattern_path
            if glob_pattern:
                if full_path.exists() and full_path.is_dir():
                    workflows = list(full_path.glob(glob_pattern))
                    for wf in workflows:
                        results["ci_cd"]["workflows"].append(str(wf.relative_to(self.project_root)))
            else:
                if full_path.exists():
                    results["ci_cd"]["workflows"].append(pattern_path)
        results["ci_cd"]["found"] = len(results["ci_cd"]["workflows"]) > 0

        # Detect agent instruction files WITH content analysis
        # Format: (path_or_pattern, is_glob)
        # - Static files: ("AGENTS.md", False)
        # - Glob patterns: (".cursor/rules/*.mdc", True)
        agent_instruction_patterns: list[tuple[str, bool]] = [
            ("AGENTS.md", False),
            ("CLAUDE.md", False),
            (".claude/CLAUDE.md", False),
            (".github/copilot-instructions.md", False),  # Copilot repo-wide
            (".github/instructions/*.instructions.md", True),  # Copilot path-specific
            ("GEMINI.md", False),
            (".windsurf/rules/rules.md", False),
            (".cursor/rules/*.mdc", True),  # Cursor supports multiple .mdc files
        ]

        # Helper function to analyze instruction file content
        def analyze_instruction_file(file_path: Path, display_path: str) -> None:
            try:
                content = read_file(file_path)
                # Check if content has substantial non-OAK content
                # Filter out OAK references, empty lines, and comment-only lines
                lines = content.split("\n")
                non_oak_lines = [
                    line
                    for line in lines
                    if line.strip()
                    and not line.strip().startswith("#")
                    and "oak/constitution" not in line.lower()
                    and "open agent kit" not in line.lower()
                ]
                has_substantial_content = len(non_oak_lines) > 3
                oak_only = not has_substantial_content

                results["agent_instructions"]["files"].append(
                    {
                        "path": display_path,
                        "has_content": bool(content.strip()),
                        "oak_only": oak_only,
                        "non_oak_lines": len(non_oak_lines),
                    }
                )
            except Exception:
                pass

        # Process all instruction patterns (both static files and globs)
        for pattern, is_glob in agent_instruction_patterns:
            if is_glob:
                # Glob pattern - find all matching files
                for matched_file in self.project_root.glob(pattern):
                    if matched_file.is_file():
                        relative_path = str(matched_file.relative_to(self.project_root))
                        analyze_instruction_file(matched_file, relative_path)
            else:
                # Static file path
                file_path = self.project_root / pattern
                if file_path.exists():
                    analyze_instruction_file(file_path, pattern)

        # Check for non-OAK agent commands (team-created prompts)
        agent_command_dirs = [
            (".github/agents", "*.prompt.md"),
            (".claude/commands", "*.md"),
            (".cursor/commands", "*.md"),
            (".codex/prompts", "*.md"),
            (".gemini/commands", "*.md"),
            (".windsurf/commands", "*.md"),
        ]
        for cmd_dir, pattern in agent_command_dirs:
            dir_path = self.project_root / cmd_dir
            if dir_path.exists():
                commands = list(dir_path.glob(pattern))
                non_oak_commands = [c for c in commands if not c.name.startswith("oak.")]
                if non_oak_commands:
                    for cmd in non_oak_commands:
                        results["agent_instructions"]["files"].append(
                            {
                                "path": str(cmd.relative_to(self.project_root)),
                                "has_content": True,
                                "oak_only": False,
                                "non_oak_lines": -1,  # Not analyzed
                            }
                        )

        # Determine if agent instructions have meaningful non-OAK content
        meaningful_instructions = [
            f for f in results["agent_instructions"]["files"] if not f["oak_only"]
        ]
        results["agent_instructions"]["found"] = len(meaningful_instructions) > 0

        # Detect project type files
        project_files = [
            "package.json",
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "Gemfile",
            "composer.json",
            "*.csproj",
            "*.sln",
            "CMakeLists.txt",
            "Makefile",
        ]
        for proj_file in project_files:
            if "*" in proj_file:
                matches = list(self.project_root.glob(proj_file))
                for match in matches:
                    results["project_files"]["files"].append(match.name)
            else:
                if (self.project_root / proj_file).exists():
                    results["project_files"]["files"].append(proj_file)
        results["project_files"]["found"] = len(results["project_files"]["files"]) > 0

        # Detect application code directories (excluding .oak/, node_modules, etc.)
        code_dirs = ["src", "lib", "app", "pkg", "cmd", "internal", "api", "core"]
        excluded_dirs = {
            ".oak",
            "node_modules",
            ".git",
            "__pycache__",
            "venv",
            ".venv",
            "dist",
            "build",
        }
        for code_dir in code_dirs:
            dir_path = self.project_root / code_dir
            if dir_path.exists() and dir_path.is_dir() and code_dir not in excluded_dirs:
                results["application_code"]["directories"].append(code_dir)
        results["application_code"]["found"] = len(results["application_code"]["directories"]) > 0

        # Classify project
        has_tests = results["test_infrastructure"]["found"]
        has_ci = results["ci_cd"]["found"]
        has_meaningful_instructions = results["agent_instructions"]["found"]
        has_code = results["application_code"]["found"]

        if has_tests and has_ci and has_meaningful_instructions:
            results["classification"] = "brownfield-mature"
        elif has_code or has_tests or has_ci:
            results["classification"] = "brownfield-minimal"
        else:
            results["classification"] = "greenfield"

        # Generate summary
        summary_parts = []
        if results["oak_installed"]:
            summary_parts.append("OAK installed (files excluded from analysis)")
        if results["test_infrastructure"]["found"]:
            summary_parts.append(
                f"Tests: {', '.join(results['test_infrastructure']['directories'])}"
            )
        else:
            summary_parts.append("Tests: None found")
        if results["ci_cd"]["found"]:
            summary_parts.append(f"CI/CD: {len(results['ci_cd']['workflows'])} workflow(s)")
        else:
            summary_parts.append("CI/CD: None found")
        if results["agent_instructions"]["found"]:
            summary_parts.append(
                f"Agent instructions: {len(meaningful_instructions)} with non-OAK content"
            )
        else:
            summary_parts.append("Agent instructions: None found (or OAK-only)")
        if results["application_code"]["found"]:
            summary_parts.append(f"Code: {', '.join(results['application_code']['directories'])}")
        else:
            summary_parts.append("Code: None found")

        results["summary"] = "; ".join(summary_parts)

        return results

    @classmethod
    def from_config(cls, project_root: Path | None = None) -> "ConstitutionService":
        """Create service from configuration.

        Args:
            project_root: Project root directory

        Returns:
            Configured ConstitutionService
        """
        return cls(project_root)
