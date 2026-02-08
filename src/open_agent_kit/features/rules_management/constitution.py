"""Constitution service for managing engineering constitutions.

This module provides constitution document management for defining project standards,
patterns, and governance. Constitutions serve as the central reference for how projects
are designed, built, and maintained.

Key Classes:
    ConstitutionService: Service for loading, parsing, and managing constitutions

Constitution Structure:
    - Version-controlled markdown document (typically at .constitution.md or oak/constitution.md)
    - Created and maintained by agents using the project-governance skill
    - Agent instruction files reference the constitution

Note:
    Constitution creation and editing is handled by agents using the project-governance skill,
    which provides examples of well-structured constitutions. This service handles:
    - Loading and parsing existing constitutions
    - Project analysis for classification
    - Syncing agent instruction files with constitution

Example:
    >>> service = ConstitutionService(project_root=Path.cwd())
    >>> if service.exists():
    ...     constitution = service.load()
    ...     print(f"Version: {constitution.metadata.version}")
"""

import logging
import re
from datetime import date
from pathlib import Path

from open_agent_kit.config.paths import CONSTITUTION_FILENAME
from open_agent_kit.constants import CONSTITUTION_REQUIRED_SECTIONS
from open_agent_kit.models.constitution import (
    Amendment,
    ConstitutionDocument,
    ConstitutionMetadata,
    ConstitutionSection,
)
from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.utils import ensure_dir, file_exists, read_file, write_file

logger = logging.getLogger(__name__)


class ConstitutionService:
    """Service for managing constitution documents."""

    def __init__(self, project_root: Path | None = None):
        """Initialize constitution service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)

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

        # Extract project name from title (various formats)
        title_patterns = [
            r"^# (.+?) Engineering Constitution",
            r"^# (.+?) Constitution",
            r"^# Project Constitution.*?Project:\*\* (.+?)$",
        ]
        for pattern in title_patterns:
            title_match = re.search(pattern, content, re.MULTILINE)
            if title_match:
                metadata_dict["project_name"] = title_match.group(1).strip()
                break

        # Extract metadata fields
        version_match = re.search(r"^- \*\*Version:\*\* (.+)$", content, re.MULTILINE)
        if version_match:
            metadata_dict["version"] = version_match.group(1).strip()

        ratification_match = re.search(
            r"^- \*\*Ratification Date:\*\* (.+)$", content, re.MULTILINE
        )
        if ratification_match:
            try:
                metadata_dict["ratification_date"] = date.fromisoformat(
                    ratification_match.group(1).strip()
                )
            except ValueError:
                pass  # Invalid date format, skip

        # Also check for "Last Updated" format
        if "ratification_date" not in metadata_dict:
            updated_match = re.search(r"^- \*\*Last Updated:\*\* (.+)$", content, re.MULTILINE)
            if updated_match:
                try:
                    metadata_dict["ratification_date"] = date.fromisoformat(
                        updated_match.group(1).strip()
                    )
                except ValueError:
                    pass

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
                try:
                    metadata_dict["last_amendment"] = date.fromisoformat(last_amend)
                except ValueError:
                    pass

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

            # Check if this is a required section (from old model - kept for compatibility)
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
            except (ValueError, KeyError) as e:
                # Skip invalid amendments
                logger.warning(
                    f"Failed to parse amendment at version {amendment_dict.get('version')}: {e}"
                )
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
        greenfield, brownfield-minimal, or brownfield-mature. This helps agents
        understand the project context before creating a constitution.

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
        agent_instruction_patterns: list[tuple[str, bool]] = [
            ("AGENTS.md", False),
            ("CLAUDE.md", False),
            (".claude/CLAUDE.md", False),
            (".github/copilot-instructions.md", False),
            (".github/instructions/*.instructions.md", True),
            ("GEMINI.md", False),
            (".windsurf/rules/rules.md", False),
            (".cursor/rules/*.mdc", True),
        ]

        def analyze_instruction_file(file_path: Path, display_path: str) -> None:
            try:
                content = read_file(file_path)
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
            except OSError as e:
                logger.warning(f"Failed to analyze instruction file {display_path}: {e}")

        for pattern, is_glob in agent_instruction_patterns:
            if is_glob:
                for matched_file in self.project_root.glob(pattern):
                    if matched_file.is_file():
                        relative_path = str(matched_file.relative_to(self.project_root))
                        analyze_instruction_file(matched_file, relative_path)
            else:
                file_path = self.project_root / pattern
                if file_path.exists():
                    analyze_instruction_file(file_path, pattern)

        # Check for non-OAK agent commands
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
                                "non_oak_lines": -1,
                            }
                        )

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

        # Detect application code directories
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

    def sync_agent_instruction_files(
        self,
        agents_added: list[str] | None = None,
        agents_removed: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """Sync agent instruction files with constitution.

        This method ensures all configured agents have instruction files that
        reference the constitution. Called when agents are added/removed.

        Behavior:
        - For added agents: Creates instruction file if missing, or appends
          constitution reference if file exists without one
        - For removed agents: Does NOT remove files (may have user modifications)

        Args:
            agents_added: Newly added agent types (optional)
            agents_removed: Removed agent types (optional, for logging only)

        Returns:
            Dictionary with sync results:
            {
                "created": ["claude", ...],  # New files created
                "updated": ["copilot", ...],  # Existing files updated with reference
                "skipped": ["cursor", ...],   # Already had reference
                "errors": ["error message", ...]
            }
        """
        results: dict[str, list[str]] = {
            "created": [],
            "updated": [],
            "skipped": [],
            "not_removed": [],
            "errors": [],
        }

        # Check if constitution exists
        if not self.exists():
            results["skipped"].append("(no constitution exists)")
            return results

        constitution_path = self.get_constitution_path()
        agent_service = AgentService(self.project_root)

        # Note removed agents but don't delete files (may have user content)
        if agents_removed:
            for agent in agents_removed:
                results["not_removed"].append(agent)

        if agents_added:
            update_results = agent_service.update_agent_instructions_from_constitution(
                constitution_path, mode="additive"
            )

            results["created"] = update_results.get("created", [])
            results["updated"] = update_results.get("updated", [])
            results["skipped"] = update_results.get("skipped", [])
            results["errors"] = update_results.get("errors", [])

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
