"""RFC document models"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from open_agent_kit.models.enums import RFCStatus


@dataclass
class RFCDocument:
    """RFC document model"""

    number: str
    title: str
    author: str
    date: str  # ISO format date string
    status: RFCStatus = RFCStatus.DRAFT
    tags: list[str] = field(default_factory=list)
    path: Path | None = None

    # Metadata
    summary: str | None = None
    superseded_by: str | None = None  # RFC number that supersedes this one
    supersedes: str | None = None  # RFC number that this supersedes
    references: list[str] = field(default_factory=list)  # Related RFC numbers

    # Review information
    reviewers: list[str] = field(default_factory=list)
    review_date: str | None = None
    approval_date: str | None = None
    implementation_date: str | None = None

    # Content sections (optional, for indexing)
    motivation: str | None = None
    detailed_design: str | None = None
    alternatives: str | None = None
    impact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = {
            "number": self.number,
            "title": self.title,
            "author": self.author,
            "date": self.date,
            "status": self.status.value if isinstance(self.status, RFCStatus) else self.status,
            "tags": self.tags,
        }

        # Add optional fields if they have values
        if self.path:
            data["path"] = str(self.path)
        if self.summary:
            data["summary"] = self.summary
        if self.superseded_by:
            data["superseded_by"] = self.superseded_by
        if self.supersedes:
            data["supersedes"] = self.supersedes
        if self.references:
            data["references"] = self.references
        if self.reviewers:
            data["reviewers"] = self.reviewers
        if self.review_date:
            data["review_date"] = self.review_date
        if self.approval_date:
            data["approval_date"] = self.approval_date
        if self.implementation_date:
            data["implementation_date"] = self.implementation_date

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RFCDocument":
        """Create from dictionary"""
        # Parse status
        status_str = data.get("status", "draft")
        try:
            status = RFCStatus(status_str)
        except ValueError:
            status = RFCStatus.DRAFT

        # Parse path if present
        path = data.get("path")
        if path:
            path = Path(path)

        return cls(
            number=data["number"],
            title=data["title"],
            author=data["author"],
            date=data["date"],
            status=status,
            tags=data.get("tags", []),
            path=path,
            summary=data.get("summary"),
            superseded_by=data.get("superseded_by"),
            supersedes=data.get("supersedes"),
            references=data.get("references", []),
            reviewers=data.get("reviewers", []),
            review_date=data.get("review_date"),
            approval_date=data.get("approval_date"),
            implementation_date=data.get("implementation_date"),
        )

    @property
    def is_active(self) -> bool:
        """Check if RFC is in active status (not yet merged)"""
        return self.status in [RFCStatus.DRAFT, RFCStatus.REVIEW, RFCStatus.APPROVED]

    @property
    def is_final(self) -> bool:
        """Check if RFC is in final status (merged or completed)"""
        return self.status in [
            RFCStatus.ADOPTED,
            RFCStatus.ABANDONED,
            RFCStatus.IMPLEMENTED,
            RFCStatus.WONT_IMPLEMENT,
        ]

    def get_filename(self) -> str:
        """Generate filename for RFC"""
        import re

        safe_title = re.sub(r"[^\w\s-]", "", self.title.lower())
        safe_title = re.sub(r"[-\s]+", "-", safe_title)
        return f"{self.number}-{safe_title}.md"


@dataclass
class RFCIndex:
    """RFC index containing all RFC metadata"""

    rfcs: dict[str, RFCDocument] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)
    total_count: int = 0

    # Statistics
    by_status: dict[str, int] = field(default_factory=dict)
    by_author: dict[str, list[str]] = field(default_factory=dict)
    by_tag: dict[str, list[str]] = field(default_factory=dict)
    by_year: dict[int, list[str]] = field(default_factory=dict)

    def add_rfc(self, rfc: RFCDocument) -> None:
        """Add RFC to index"""
        self.rfcs[rfc.number] = rfc
        self._update_statistics()

    def remove_rfc(self, number: str) -> None:
        """Remove RFC from index"""
        if number in self.rfcs:
            del self.rfcs[number]
            self._update_statistics()

    def get_rfc(self, number: str) -> RFCDocument | None:
        """Get RFC by number"""
        return self.rfcs.get(number)

    def search(
        self,
        status: RFCStatus | None = None,
        author: str | None = None,
        tag: str | None = None,
        year: int | None = None,
        text: str | None = None,
    ) -> list[RFCDocument]:
        """Search RFCs with filters"""
        results = list(self.rfcs.values())

        if status:
            results = [r for r in results if r.status == status]

        if author:
            author_lower = author.lower()
            results = [r for r in results if author_lower in r.author.lower()]

        if tag:
            results = [r for r in results if tag in r.tags]

        if year:
            results = [r for r in results if r.date.startswith(str(year))]

        if text:
            text_lower = text.lower()
            results = [
                r
                for r in results
                if text_lower in r.title.lower() or text_lower in (r.summary or "").lower()
            ]

        return results

    def _update_statistics(self) -> None:
        """Update index statistics"""
        self.total_count = len(self.rfcs)
        self.last_updated = datetime.now()

        # Reset statistics
        self.by_status = {}
        self.by_author = {}
        self.by_tag = {}
        self.by_year = {}

        # Calculate statistics
        for rfc in self.rfcs.values():
            # By status
            status_key = rfc.status.value if isinstance(rfc.status, RFCStatus) else rfc.status
            self.by_status[status_key] = self.by_status.get(status_key, 0) + 1

            # By author
            if rfc.author not in self.by_author:
                self.by_author[rfc.author] = []
            self.by_author[rfc.author].append(rfc.number)

            # By tag
            for tag in rfc.tags:
                if tag not in self.by_tag:
                    self.by_tag[tag] = []
                self.by_tag[tag].append(rfc.number)

            # By year
            try:
                year = int(rfc.date[:4])
                if year not in self.by_year:
                    self.by_year[year] = []
                self.by_year[year].append(rfc.number)
            except (ValueError, IndexError):
                pass

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "rfcs": {number: rfc.to_dict() for number, rfc in self.rfcs.items()},
            "metadata": {
                "last_updated": self.last_updated.isoformat(),
                "total_count": self.total_count,
                "by_status": self.by_status,
                "by_author": self.by_author,
                "by_tag": self.by_tag,
                "by_year": self.by_year,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RFCIndex":
        """Create from dictionary"""
        index = cls()

        # Load RFCs
        rfcs_data = data.get("rfcs", {})
        for number, rfc_data in rfcs_data.items():
            rfc = RFCDocument.from_dict(rfc_data)
            index.rfcs[number] = rfc

        # Load metadata if present
        metadata = data.get("metadata", {})
        if metadata:
            if "last_updated" in metadata:
                index.last_updated = datetime.fromisoformat(metadata["last_updated"])
            index.total_count = metadata.get("total_count", len(index.rfcs))
            index.by_status = metadata.get("by_status", {})
            index.by_author = metadata.get("by_author", {})
            index.by_tag = metadata.get("by_tag", {})
            index.by_year = metadata.get("by_year", {})
        else:
            # Recalculate statistics
            index._update_statistics()

        return index

    def get_next_number(self, format: str = "YYYY-NNN") -> str:
        """Generate next RFC number based on format"""
        if format == "YYYY-NNN":
            # Year-based numbering
            year = datetime.now().year
            year_rfcs = self.by_year.get(year, [])
            next_num = len(year_rfcs) + 1
            return f"{year}-{next_num:03d}"
        elif format == "NNNN":
            # Four-digit numbering
            return f"{self.total_count + 1:04d}"
        else:
            # Simple sequential
            return str(self.total_count + 1)
