"""RFC service for managing RFC documents.

This module provides comprehensive RFC (Request for Comments) document management,
including creation, validation, listing, and lifecycle operations. RFCs are stored
in the oak/rfc/ directory as markdown files with structured metadata.

Key Classes:
    RFCService: Main service for RFC CRUD operations and validation

Dependencies:
    - TemplateService: For rendering RFC document templates
    - ConfigService: For RFC configuration (auto-numbering, formats, templates)
    - ValidationService: For content and markdown syntax validation

RFC Lifecycle:
    draft → review → approved → adopted → (deprecated/superseded)

Filename Format:
    - Sequential: RFC-001-title-slug.md, RFC-002-title-slug.md
    - Date-based: RFC-2024-001-title-slug.md

Features:
    - Auto-numbering (sequential or date-based)
    - Template-based generation (engineering, architecture, feature, process)
    - Validation (syntax, content completeness, placeholder detection)
    - Status tracking and lifecycle management
    - Tag-based organization
    - Supersession tracking (RFC-002 supersedes RFC-001)

Example:
    >>> service = RFCService(project_root=Path.cwd())
    >>> rfc = service.create_rfc(
    ...     title="API Rate Limiting",
    ...     author="Jane Doe",
    ...     template_name="engineering"
    ... )
    >>> is_valid, issues = service.validate_rfc(rfc.path)
    >>> rfcs = service.list_rfcs(status="approved")
"""

import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from open_agent_kit.config.paths import RFC_FILE_EXTENSION
from open_agent_kit.config.settings import validation_settings
from open_agent_kit.constants import RFC_FILENAME_PATTERN, RFC_PLACEHOLDER_KEYWORDS
from open_agent_kit.models.enums import RFCStatus
from open_agent_kit.models.rfc import RFCDocument
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.template_service import TemplateService
from open_agent_kit.utils import (
    ensure_dir,
    file_exists,
    list_files,
    read_file,
    sanitize_title,
    validate_markdown_syntax,
    validate_rfc_content,
    write_file,
)


class RFCService:
    """Service for managing RFC documents."""

    def __init__(self, project_root: Path | None = None):
        """Initialize RFC service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.template_service = TemplateService(project_root=project_root)

    def get_rfc_dir(self) -> Path:
        """Get RFC directory path.

        Returns:
            Path to RFC directory
        """
        return self.config_service.get_rfc_dir()

    def list_rfcs(self, status: str | None = None) -> list[RFCDocument]:
        """List all RFC documents.

        Args:
            status: Optional status filter

        Returns:
            List of RFCDocument objects
        """
        rfc_dir = self.get_rfc_dir()

        if not rfc_dir.exists():
            return []

        # Find all RFC markdown files
        rfc_files = list_files(rfc_dir, "RFC-*" + RFC_FILE_EXTENSION, recursive=True)

        rfcs = []
        for rfc_file in rfc_files:
            try:
                rfc = self._parse_rfc_file(rfc_file)
                if status is None or rfc.status.value == status.lower():
                    rfcs.append(rfc)
            except (ValueError, FileNotFoundError, KeyError):
                # Skip files that can't be parsed (invalid filename format, missing file, or malformed content)
                # This allows listing to continue even if some RFCs are corrupted
                continue

        # Sort by RFC number
        rfcs.sort(key=lambda x: x.number)

        return rfcs

    def get_rfc(self, rfc_number: str) -> RFCDocument | None:
        """Get RFC by number.

        Args:
            rfc_number: RFC number (e.g., "001", "2024-001")

        Returns:
            RFCDocument if found, None otherwise
        """
        rfcs = self.list_rfcs()

        for rfc in rfcs:
            if rfc.number == rfc_number:
                return rfc

        return None

    def get_next_rfc_number(self) -> str:
        """Get next RFC number based on existing RFCs.

        Returns:
            Next RFC number (e.g., "001", "002")
        """
        rfcs = self.list_rfcs()

        if not rfcs:
            return "001"

        # Extract numeric parts and find max
        numbers = []
        for rfc in rfcs:
            # Handle different number formats
            if "-" in rfc.number:
                # Year-based: 2024-001
                parts = rfc.number.split("-")
                if len(parts) == 2:
                    year, num = parts
                    if year == str(datetime.now().year):
                        numbers.append(int(num))
            else:
                # Sequential: 001, 0001
                try:
                    numbers.append(int(rfc.number))
                except ValueError:
                    continue

        if not numbers:
            return "001"

        next_num = max(numbers) + 1
        return f"{next_num:03d}"

    def create_rfc(
        self,
        title: str,
        author: str,
        template_name: str = "engineering",
        tags: list[str] | None = None,
        rfc_number: str | None = None,
    ) -> RFCDocument:
        """Create a new RFC document.

        Args:
            title: RFC title
            author: RFC author name
            template_name: Template to use (default: "engineering")
            tags: Optional list of tags
            rfc_number: Optional custom RFC number (auto-generated if not provided)

        Returns:
            Created RFCDocument

        Raises:
            FileExistsError: If RFC file already exists
        """
        # Generate RFC number if not provided
        if rfc_number is None:
            rfc_number = self.get_next_rfc_number()

        # Sanitize title for filename
        safe_title = sanitize_title(title)

        # Create RFC filename
        filename = f"RFC-{rfc_number}-{safe_title}{RFC_FILE_EXTENSION}"

        # Get RFC directory and ensure it exists
        rfc_dir = self.get_rfc_dir()
        ensure_dir(rfc_dir)

        # Full path
        rfc_path = rfc_dir / filename

        # Check if file already exists
        if file_exists(rfc_path):
            raise FileExistsError(f"RFC already exists: {filename}")

        # Prepare template context
        date_str = datetime.now().strftime("%Y-%m-%d")
        context = {
            "rfc_number": rfc_number,
            "title": title,
            "author": author,
            "date": date_str,
            "status": "draft",
            "tags": tags or [],
        }

        # Render template
        template_path = f"rfc/{template_name}.md"
        try:
            content = self.template_service.render_template(template_path, context)
        except FileNotFoundError:
            # Fall back to basic template if custom template not found
            content = self._get_default_rfc_template(context)

        # Write RFC file
        write_file(rfc_path, content)

        # Create and return RFCDocument
        rfc = RFCDocument(
            number=rfc_number,
            title=title,
            author=author,
            date=date_str,
            status=RFCStatus.DRAFT,
            tags=tags or [],
            path=rfc_path,
        )

        return rfc

    def validate_rfc(
        self,
        rfc_path: Path,
        strict: bool = False,
    ) -> tuple[bool, list[str]]:
        """Validate RFC document.

        Args:
            rfc_path: Path to RFC file
            strict: Whether to enforce strict validation

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        if not file_exists(rfc_path):
            return (False, ["RFC file not found"])

        issues = []

        try:
            # Read content
            content = read_file(rfc_path)

            # Validate filename format
            filename = rfc_path.name
            if not re.match(RFC_FILENAME_PATTERN, filename):
                issues.append(f"Invalid RFC filename format: {filename}")

            # Validate markdown syntax
            syntax_valid, syntax_issues = validate_markdown_syntax(content)
            if not syntax_valid:
                issues.extend(syntax_issues)

            # Validate RFC content structure
            content_valid, missing_sections = validate_rfc_content(content, strict)
            if not content_valid:
                issues.append("Missing required sections:")
                issues.extend([f"  - {section}" for section in missing_sections])

            # Detect placeholder content
            placeholders = self._detect_placeholders(content)
            for placeholder in placeholders:
                issues.append(f"Placeholder content detected: {placeholder}")

            return (len(issues) == 0, issues)

        except Exception as e:
            return (False, [f"Validation error: {str(e)}"])

    def update_rfc_status(
        self,
        rfc_number: str,
        new_status: RFCStatus,
    ) -> RFCDocument | None:
        """Update RFC status.

        Args:
            rfc_number: RFC number
            new_status: New status

        Returns:
            Updated RFCDocument if found, None otherwise
        """
        rfc = self.get_rfc(rfc_number)
        if not rfc or not rfc.path:
            return None

        try:
            # Read current content
            content = read_file(rfc.path)

            # Update status in frontmatter
            status_pattern = r"(?m)^status:\s*\w+$"
            new_status_line = f"status: {new_status.value}"

            if re.search(status_pattern, content):
                # Replace existing status
                content = re.sub(status_pattern, new_status_line, content)
            else:
                # Add status if not present (after title)
                title_pattern = r"(^#\s+.+$)"
                match = re.search(title_pattern, content, re.MULTILINE)
                if match:
                    insert_pos = match.end()
                    content = (
                        content[:insert_pos]
                        + f"\n\n**Status:** {new_status.value}"
                        + content[insert_pos:]
                    )

            # Write updated content
            write_file(rfc.path, content)

            # Update and return RFC object
            rfc.status = new_status
            return rfc

        except Exception:
            return None

    def adopt_rfc(self, rfc_number: str) -> RFCDocument | None:
        """Mark an RFC as adopted and move it to the adopted folder."""

        return self._relocate_rfc(rfc_number, RFCStatus.ADOPTED, "adopted")

    def abandon_rfc(self, rfc_number: str) -> RFCDocument | None:
        """Mark an RFC as abandoned and move it to the abandoned folder."""

        return self._relocate_rfc(rfc_number, RFCStatus.ABANDONED, "abandoned")

    def delete_rfc(self, rfc_number: str) -> bool:
        """Delete RFC document.

        Args:
            rfc_number: RFC number

        Returns:
            True if deleted, False if not found
        """
        rfc = self.get_rfc(rfc_number)
        if not rfc or not rfc.path:
            return False

        try:
            rfc.path.unlink()
            return True
        except Exception:
            return False

    def search_rfcs(
        self,
        query: str | None = None,
        status: RFCStatus | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
    ) -> list[RFCDocument]:
        """Search RFCs by title or content.

        Args:
            query: Search query
            status: Optional status filter
            author: Optional author filter
            tags: Optional list of tags to match (intersection)

        Returns:
            List of matching RFCDocument objects
        """
        status_filter = status.value if isinstance(status, RFCStatus) else status
        rfcs = self.list_rfcs(status=status_filter)
        query_lower = query.lower().strip() if query else None
        author_lower = author.lower().strip() if author else None
        tag_set = {tag.lower() for tag in tags} if tags else None

        results = []
        for rfc in rfcs:
            if author_lower and author_lower not in rfc.author.lower():
                continue

            if tag_set and not any(tag.lower() in tag_set for tag in rfc.tags):
                continue

            if not query_lower:
                results.append(rfc)
                continue

            # Search in title and summary
            title_hit = query_lower in rfc.title.lower()
            summary_hit = query_lower in (rfc.summary or "").lower()

            if title_hit or summary_hit:
                results.append(rfc)
                continue

            # Search in tags
            if any(query_lower in tag.lower() for tag in rfc.tags):
                results.append(rfc)
                continue

            # Search in content
            if rfc.path and file_exists(rfc.path):
                try:
                    content = read_file(rfc.path)
                    if query_lower in content.lower():
                        results.append(rfc)
                except Exception:
                    continue

        return results

    def find_related_rfcs(
        self,
        title: str,
        tags: list[str] | None = None,
        exclude_number: str | None = None,
        statuses: list[RFCStatus] | None = None,
        limit: int = 5,
    ) -> list[RFCDocument]:
        """Find RFCs related to the provided title and tags."""

        keywords = self._extract_keywords(title)
        tags_lower = {tag.lower() for tag in tags or []}
        status_set = set(statuses) if statuses else None

        related: list[RFCDocument] = []
        seen_numbers: set[str] = set()

        for rfc in self.list_rfcs():
            if exclude_number and rfc.number == exclude_number:
                continue

            if status_set and rfc.status not in status_set:
                continue

            if tags_lower and not any(tag.lower() in tags_lower for tag in rfc.tags):
                continue

            lower_title = rfc.title.lower()
            lower_summary = (rfc.summary or "").lower()

            if keywords and not any(
                keyword in lower_title or keyword in lower_summary for keyword in keywords
            ):
                continue

            if rfc.number in seen_numbers:
                continue

            related.append(rfc)
            seen_numbers.add(rfc.number)

            if len(related) >= limit:
                break

        return related

    def get_rfc_statistics(self, rfcs: list[RFCDocument] | None = None) -> dict[str, Any]:
        """Compute aggregate RFC statistics for reporting."""

        if rfcs is None:
            rfcs = self.list_rfcs()

        stats: dict[str, Any] = {
            "total": len(rfcs),
            "by_status": {},
            "by_author": {},
            "by_tag": {},
            "stale_drafts": [],
            "latest_number": rfcs[-1].number if rfcs else None,
        }

        cutoff = datetime.now() - timedelta(days=validation_settings.rfc_stale_draft_days)

        for rfc in rfcs:
            status_key = rfc.status.value if isinstance(rfc.status, RFCStatus) else str(rfc.status)
            stats["by_status"][status_key] = stats["by_status"].get(status_key, 0) + 1

            stats["by_author"].setdefault(rfc.author, []).append(rfc.number)

            for tag in rfc.tags:
                stats["by_tag"].setdefault(tag, []).append(rfc.number)

            if rfc.status == RFCStatus.DRAFT:
                try:
                    created_date = datetime.strptime(rfc.date, "%Y-%m-%d")
                    if created_date < cutoff:
                        stats["stale_drafts"].append(
                            {
                                "number": rfc.number,
                                "title": rfc.title,
                                "date": rfc.date,
                            }
                        )
                except ValueError:
                    continue

        stats["stale_drafts"].sort(key=lambda item: item["date"])
        return stats

    def _parse_rfc_file(self, rfc_path: Path) -> RFCDocument:
        """Parse RFC file to extract metadata.

        Args:
            rfc_path: Path to RFC file

        Returns:
            RFCDocument object

        Raises:
            ValueError: If RFC file cannot be parsed
        """
        content = read_file(rfc_path)

        # Extract number and title from filename
        filename = rfc_path.name
        match = re.match(RFC_FILENAME_PATTERN, filename)
        if not match:
            raise ValueError(f"Invalid RFC filename: {filename}")

        number = match.group(1)
        title_from_filename = match.group(2).replace("-", " ")

        # Try to extract metadata from content
        # Look for frontmatter-style metadata or structured headers
        metadata: dict[str, Any] = {
            "number": number,
            "title": title_from_filename,
            "author": "Unknown",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "status": RFCStatus.DRAFT,
            "tags": [],
        }

        # Extract title from first heading
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            title_text = title_match.group(1).strip()
            # Strip "RFC-XXX: " prefix if present
            rfc_prefix_pattern = r"^RFC-\d+:\s*"
            title_text = re.sub(rfc_prefix_pattern, "", title_text)
            metadata["title"] = title_text

        # Extract author
        author_match = re.search(r"^\*\*Author:\*\*\s*(.+)$", content, re.MULTILINE)
        if author_match:
            metadata["author"] = author_match.group(1).strip()

        # Extract date
        date_match = re.search(r"^\*\*Date:\*\*\s*(.+)$", content, re.MULTILINE)
        if date_match:
            metadata["date"] = date_match.group(1).strip()

        # Extract status
        status_match = re.search(r"^\*\*Status:\*\*\s*(\w+)$", content, re.MULTILINE)
        if status_match:
            try:
                metadata["status"] = RFCStatus(status_match.group(1).lower())
            except ValueError:
                pass

        # Extract tags
        tags_match = re.search(r"^\*\*Tags:\*\*\s*(.+)$", content, re.MULTILINE)
        if tags_match:
            tags_str = tags_match.group(1).strip()
            metadata["tags"] = [tag.strip() for tag in tags_str.split(",")]

        return RFCDocument(
            number=metadata["number"],
            title=metadata["title"],
            author=metadata["author"],
            date=metadata["date"],
            status=metadata["status"],
            tags=metadata["tags"],
            path=rfc_path,
        )

    def _get_default_rfc_template(self, context: dict) -> str:
        """Get default RFC template content.

        Args:
            context: Template context

        Returns:
            RFC template content
        """
        return f"""# RFC-{context['rfc_number']}: {context['title']}

**Author:** {context['author']}
**Date:** {context['date']}
**Status:** {context['status']}
**Tags:** {', '.join(context['tags'])}

## Summary

[Brief summary of the proposal]

## Motivation

[Why are we doing this? What problem does it solve?]

## Detailed Design

[Detailed explanation of the proposal]

## Drawbacks

[Why should we *not* do this?]

## Alternatives

[What other approaches were considered?]

## Unresolved Questions

[What questions remain to be answered?]
"""

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract normalized keywords from text for related RFC searches."""

        words = re.findall(r"\w+", text.lower())
        return [word for word in words if len(word) >= 4]

    @staticmethod
    def _detect_placeholders(content: str) -> list[str]:
        """Detect placeholder strings that should be replaced before finalization."""

        found: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()

            if stripped.startswith(">"):
                if any(keyword in lower for keyword in RFC_PLACEHOLDER_KEYWORDS):
                    found.append(stripped)
                    continue

            if stripped.startswith("- ["):
                if (
                    "…" in stripped
                    or "..." in stripped
                    or "goal" in lower
                    or "requirement" in lower
                ):
                    found.append(stripped)
                    continue

            if "…" in stripped or "..." in stripped:
                found.append(stripped)
                continue

        return found

    def _relocate_rfc(
        self,
        rfc_number: str,
        target_status: RFCStatus,
        target_directory_name: str,
    ) -> RFCDocument | None:
        """Move an RFC to a status-specific directory after updating its status."""

        rfc = self.get_rfc(rfc_number)
        if not rfc or not rfc.path:
            return None

        updated = self.update_rfc_status(rfc_number, target_status) or rfc
        source_path = updated.path
        if source_path is None or not source_path.exists():
            return None

        target_dir = self.get_rfc_dir() / target_directory_name
        ensure_dir(target_dir)
        target_path = target_dir / source_path.name

        if target_path.exists():
            raise FileExistsError(f"Target RFC already exists at {target_path}")

        shutil.move(str(source_path), str(target_path))

        return self._parse_rfc_file(target_path)


def get_rfc_service(project_root: Path | None = None) -> RFCService:
    """Get an RFCService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        RFCService instance
    """
    return RFCService(project_root)
