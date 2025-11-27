"""Constitution document models."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any


class AmendmentType(str, Enum):
    """Amendment types for versioning."""

    MAJOR = "major"  # Breaking changes (X.0.0)
    MINOR = "minor"  # New requirements (0.X.0)
    PATCH = "patch"  # Clarifications (0.0.X)


class ConstitutionStatus(str, Enum):
    """Constitution lifecycle status."""

    DRAFT = "draft"
    RATIFIED = "ratified"
    AMENDED = "amended"
    DEPRECATED = "deprecated"


@dataclass
class ConstitutionMetadata:
    """Constitution metadata."""

    project_name: str
    version: str
    ratification_date: date
    author: str
    last_amendment: date | None = None
    status: ConstitutionStatus = ConstitutionStatus.DRAFT
    tech_stack: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "project_name": self.project_name,
            "version": self.version,
            "ratification_date": self.ratification_date.isoformat(),
            "last_amendment": self.last_amendment.isoformat() if self.last_amendment else "N/A",
            "author": self.author,
            "status": self.status.value,
            "tech_stack": self.tech_stack or "N/A",
            "description": self.description or "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstitutionMetadata":
        """Create from dictionary."""
        # Parse dates
        ratification_date_str = data.get("ratification_date")
        if isinstance(ratification_date_str, str):
            ratification_date = date.fromisoformat(ratification_date_str)
        elif isinstance(ratification_date_str, date):
            ratification_date = ratification_date_str
        else:
            ratification_date = date.today()

        last_amendment_str = data.get("last_amendment")
        if last_amendment_str and last_amendment_str != "N/A":
            if isinstance(last_amendment_str, str):
                last_amendment = date.fromisoformat(last_amendment_str)
            else:
                last_amendment = last_amendment_str
        else:
            last_amendment = None

        # Parse status
        status_str = data.get("status", "draft")
        try:
            status = ConstitutionStatus(status_str)
        except ValueError:
            status = ConstitutionStatus.DRAFT

        return cls(
            project_name=data["project_name"],
            version=data["version"],
            ratification_date=ratification_date,
            author=data["author"],
            last_amendment=last_amendment,
            status=status,
            tech_stack=data.get("tech_stack"),
            description=data.get("description"),
        )


@dataclass
class Amendment:
    """Constitution amendment."""

    version: str
    date: date
    type: AmendmentType
    summary: str
    rationale: str
    author: str
    section: str | None = None
    impact: str | None = None

    def to_markdown(self) -> str:
        """Convert amendment to markdown format."""
        lines = [
            f"## Amendment {self.version} ({self.date.isoformat()})",
            "",
            f"**Type:** {self.type.value.capitalize()}",
            f"**Author:** {self.author}",
            "",
            f"**Summary:** {self.summary}",
            "",
            f"**Rationale:** {self.rationale}",
            "",
        ]

        if self.section:
            lines.extend(["", f"**Section:** {self.section}"])

        if self.impact:
            lines.extend(["", f"**Impact:** {self.impact}"])

        lines.append("")  # Blank line at end
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "date": self.date.isoformat(),
            "type": self.type.value,
            "summary": self.summary,
            "rationale": self.rationale,
            "author": self.author,
            "section": self.section,
            "impact": self.impact,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Amendment":
        """Create from dictionary."""
        # Parse date
        date_str = data.get("date")
        if isinstance(date_str, str):
            amendment_date = date.fromisoformat(date_str)
        elif isinstance(date_str, date):
            amendment_date = date_str
        else:
            amendment_date = date.today()

        # Parse type
        type_str = data.get("type", "patch")
        try:
            amendment_type = AmendmentType(type_str)
        except ValueError:
            amendment_type = AmendmentType.PATCH

        return cls(
            version=data["version"],
            date=amendment_date,
            type=amendment_type,
            summary=data["summary"],
            rationale=data["rationale"],
            author=data["author"],
            section=data.get("section"),
            impact=data.get("impact"),
        )


@dataclass
class ConstitutionSection:
    """Constitution section."""

    title: str
    content: str
    order: int
    required: bool = True

    def to_markdown(self) -> str:
        """Convert section to markdown."""
        return f"## {self.title}\n\n{self.content}\n"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "content": self.content,
            "order": self.order,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstitutionSection":
        """Create from dictionary."""
        return cls(
            title=data["title"],
            content=data["content"],
            order=data["order"],
            required=data.get("required", True),
        )


@dataclass
class ConstitutionDocument:
    """Complete constitution document."""

    metadata: ConstitutionMetadata
    sections: list[ConstitutionSection]
    amendments: list[Amendment] = field(default_factory=list)
    file_path: Path | None = None

    def get_section(self, title: str) -> ConstitutionSection | None:
        """Get section by title."""
        for section in self.sections:
            if section.title.lower() == title.lower():
                return section
        return None

    def add_amendment(self, amendment: Amendment) -> None:
        """Add amendment to constitution."""
        self.amendments.append(amendment)
        self.metadata.last_amendment = amendment.date
        self.metadata.version = amendment.version
        self.metadata.status = ConstitutionStatus.AMENDED

    def get_latest_version(self) -> str:
        """Get latest version number."""
        return self.metadata.version

    def to_markdown(self) -> str:
        """Convert entire constitution to markdown."""
        lines = [
            f"# {self.metadata.project_name} Engineering Constitution",
            "",
            "## Metadata",
            "",
            f"- **Project:** {self.metadata.project_name}",
            f"- **Version:** {self.metadata.version}",
            f"- **Status:** {self.metadata.status.value.capitalize()}",
            f"- **Ratification Date:** {self.metadata.ratification_date.isoformat()}",
            f"- **Last Amendment:** {self.metadata.last_amendment.isoformat() if self.metadata.last_amendment else 'N/A'}",
            f"- **Author:** {self.metadata.author}",
        ]

        if self.metadata.tech_stack:
            lines.append(f"- **Tech Stack:** {self.metadata.tech_stack}")

        if self.metadata.description:
            lines.extend(["", f"**Description:** {self.metadata.description}"])

        lines.extend(["", "---", ""])

        # Add sections
        for section in sorted(self.sections, key=lambda s: s.order):
            lines.append(section.to_markdown())

        # Add amendments section if any exist
        if self.amendments:
            lines.extend(["---", "", "# Amendments", ""])
            for amendment in self.amendments:
                lines.append(amendment.to_markdown())

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "amendments": [a.to_dict() for a in self.amendments],
            "file_path": str(self.file_path) if self.file_path else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConstitutionDocument":
        """Create from dictionary."""
        metadata = ConstitutionMetadata.from_dict(data["metadata"])
        sections = [ConstitutionSection.from_dict(s) for s in data.get("sections", [])]
        amendments = [Amendment.from_dict(a) for a in data.get("amendments", [])]

        file_path_str = data.get("file_path")
        file_path = Path(file_path_str) if file_path_str else None

        return cls(
            metadata=metadata,
            sections=sections,
            amendments=amendments,
            file_path=file_path,
        )

    @property
    def is_ratified(self) -> bool:
        """Check if constitution is ratified."""
        return self.metadata.status in [
            ConstitutionStatus.RATIFIED,
            ConstitutionStatus.AMENDED,
        ]

    @property
    def has_amendments(self) -> bool:
        """Check if constitution has amendments."""
        return len(self.amendments) > 0
