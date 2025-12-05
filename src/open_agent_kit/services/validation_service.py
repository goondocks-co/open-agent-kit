"""Validation service for constitution checking."""

import re
from datetime import date

from open_agent_kit.config.settings import validation_settings
from open_agent_kit.constants import (
    CONSTITUTION_DATE_PATTERN,
    CONSTITUTION_METADATA_PROJECT_NAME,
    CONSTITUTION_NORMATIVE_KEYWORDS,
    CONSTITUTION_NORMATIVE_SECTIONS,
    CONSTITUTION_REQUIRED_METADATA,
    CONSTITUTION_REQUIRED_SECTIONS,
    CONSTITUTION_TOKENS,
    CONSTITUTION_VAGUE_POLICY_PATTERNS,
    CONSTITUTION_VERSION_PATTERN,
    NON_DECLARATIVE_PATTERNS,
)
from open_agent_kit.models.constitution import ConstitutionDocument
from open_agent_kit.models.validation import (
    ValidationCategory,
    ValidationIssue,
    ValidationPriority,
    ValidationResult,
)


class ValidationService:
    """Service for validating constitution documents."""

    def validate(self, constitution: ConstitutionDocument) -> ValidationResult:
        """Validate constitution document.

        Args:
            constitution: Constitution to validate

        Returns:
            ValidationResult with issues categorized by priority
        """
        result = ValidationResult(is_valid=True)

        # Run all validation checks
        self._validate_structure(constitution, result)
        self._validate_metadata(constitution, result)
        self._validate_tokens(constitution, result)
        self._validate_dates(constitution, result)
        self._validate_language(constitution, result)
        self._validate_versioning(constitution, result)
        self._assess_quality(constitution, result)
        self._check_consistency(constitution, result)

        # Calculate statistics
        result.calculate_stats()

        return result

    def _validate_structure(
        self,
        constitution: ConstitutionDocument,
        result: ValidationResult,
    ) -> None:
        """Validate constitution structure.

        Args:
            constitution: Constitution to validate
            result: ValidationResult to update with issues
        """
        # Check for required sections
        section_titles = [s.title for s in constitution.sections]

        for required_section in CONSTITUTION_REQUIRED_SECTIONS:
            if required_section not in section_titles:
                result.add_issue(
                    ValidationIssue(
                        category=ValidationCategory.STRUCTURE,
                        priority=ValidationPriority.HIGH,
                        message=f"Missing required section: {required_section}",
                        suggested_fix=f"Add '## {required_section}' section to constitution",
                        auto_fixable=False,
                    )
                )

        # Check for empty sections
        for section in constitution.sections:
            if not section.content.strip():
                result.add_issue(
                    ValidationIssue(
                        category=ValidationCategory.STRUCTURE,
                        priority=ValidationPriority.MEDIUM,
                        message=f"Empty section: {section.title}",
                        location=section.title,
                        suggested_fix="Add content to section based on codebase analysis",
                        auto_fixable=False,
                    )
                )

    def _validate_metadata(
        self,
        constitution: ConstitutionDocument,
        result: ValidationResult,
    ) -> None:
        """Validate constitution metadata.

        Args:
            constitution: Constitution to validate
            result: ValidationResult to update with issues
        """
        metadata = constitution.metadata

        # Check required metadata fields
        for field in CONSTITUTION_REQUIRED_METADATA:
            value = getattr(metadata, field, None)
            is_missing = value is None
            if isinstance(value, str) and not value.strip():
                is_missing = True

            if not is_missing:
                continue

            if field == CONSTITUTION_METADATA_PROJECT_NAME:
                message = "Project name cannot be empty"
                suggested_fix = "Set metadata.project_name to the official project name."
            else:
                message = f"Missing required metadata: {field}"
                suggested_fix = f"Provide a value for '{field}' in the Metadata section."

            result.add_issue(
                ValidationIssue(
                    category=ValidationCategory.METADATA,
                    priority=ValidationPriority.HIGH,
                    message=message,
                    location="Metadata section",
                    suggested_fix=suggested_fix,
                    auto_fixable=False,
                )
            )

    def _validate_tokens(
        self,
        constitution: ConstitutionDocument,
        result: ValidationResult,
    ) -> None:
        """Validate that all template tokens are replaced.

        Args:
            constitution: Constitution to validate
            result: ValidationResult to update with issues
        """
        content = constitution.to_markdown()

        for token in CONSTITUTION_TOKENS:
            if token in content:
                result.add_issue(
                    ValidationIssue(
                        category=ValidationCategory.TOKENS,
                        priority=ValidationPriority.HIGH,
                        message=f"Unreplaced token: {token}",
                        suggested_fix=f"Replace {token} with actual value",
                        auto_fixable=False,
                    )
                )

    def _validate_dates(
        self,
        constitution: ConstitutionDocument,
        result: ValidationResult,
    ) -> None:
        """Validate date formats.

        Args:
            constitution: Constitution to validate
            result: ValidationResult to update with issues
        """
        metadata = constitution.metadata

        # Validate ratification date format
        date_str = metadata.ratification_date.isoformat()
        if not re.match(CONSTITUTION_DATE_PATTERN, date_str):
            result.add_issue(
                ValidationIssue(
                    category=ValidationCategory.DATES,
                    priority=ValidationPriority.MEDIUM,
                    message=f"Invalid ratification date format: {date_str}",
                    location="Metadata section",
                    suggested_fix="Use ISO date format (YYYY-MM-DD)",
                    auto_fixable=True,
                )
            )

        # Validate last amendment date if present
        if metadata.last_amendment:
            amendment_date_str = metadata.last_amendment.isoformat()
            if not re.match(CONSTITUTION_DATE_PATTERN, amendment_date_str):
                result.add_issue(
                    ValidationIssue(
                        category=ValidationCategory.DATES,
                        priority=ValidationPriority.MEDIUM,
                        message=f"Invalid amendment date format: {amendment_date_str}",
                        location="Metadata section",
                        suggested_fix="Use ISO date format (YYYY-MM-DD)",
                        auto_fixable=True,
                    )
                )

        # Check for future dates
        today = date.today()
        if metadata.ratification_date > today:
            result.add_issue(
                ValidationIssue(
                    category=ValidationCategory.DATES,
                    priority=ValidationPriority.LOW,
                    message=f"Ratification date is in the future: {date_str}",
                    location="Metadata section",
                    suggested_fix=f"Use current date: {today.isoformat()}",
                    auto_fixable=True,
                )
            )

    def _validate_language(
        self,
        constitution: ConstitutionDocument,
        result: ValidationResult,
    ) -> None:
        """Validate language style (declarative, imperative).

        Args:
            constitution: Constitution to validate
            result: ValidationResult to update with issues
        """
        # Check for non-declarative language patterns
        # Note: We do NOT use re.IGNORECASE here because uppercase keywords
        # like "SHOULD" are valid RFC 2119 language. We only want to flag
        # lowercase informal usage like "should", "could", etc.
        for section in constitution.sections:
            for pattern in NON_DECLARATIVE_PATTERNS:
                matches = list(re.finditer(pattern, section.content))
                for match in matches:
                    # Find line number
                    line_num = section.content[: match.start()].count("\n") + 1

                    result.add_issue(
                        ValidationIssue(
                            category=ValidationCategory.LANGUAGE,
                            priority=ValidationPriority.LOW,
                            message=f"Non-declarative language: '{match.group()}'",
                            location=section.title,
                            line_number=line_num,
                            suggested_fix="Use RFC 2119 keywords in uppercase (MUST, SHOULD, MAY) for requirements",
                            auto_fixable=False,
                        )
                    )

    def _validate_versioning(
        self,
        constitution: ConstitutionDocument,
        result: ValidationResult,
    ) -> None:
        """Validate version format and consistency.

        Args:
            constitution: Constitution to validate
            result: ValidationResult to update with issues
        """
        version = constitution.metadata.version

        # Check version format
        if not re.match(CONSTITUTION_VERSION_PATTERN, version):
            result.add_issue(
                ValidationIssue(
                    category=ValidationCategory.VERSIONING,
                    priority=ValidationPriority.HIGH,
                    message=f"Invalid version format: {version}",
                    location="Metadata section",
                    suggested_fix="Use semantic versioning (e.g., 1.0.0)",
                    auto_fixable=False,
                )
            )

        # Check version consistency with amendments
        if constitution.amendments:
            latest_amendment = constitution.amendments[-1]
            if latest_amendment.version != version:
                result.add_issue(
                    ValidationIssue(
                        category=ValidationCategory.VERSIONING,
                        priority=ValidationPriority.HIGH,
                        message=f"Version mismatch: metadata shows {version}, "
                        f"latest amendment shows {latest_amendment.version}",
                        location="Amendments section",
                        suggested_fix=f"Update metadata version to {latest_amendment.version}",
                        auto_fixable=True,
                    )
                )

    def _assess_quality(
        self,
        constitution: ConstitutionDocument,
        result: ValidationResult,
    ) -> None:
        """Assess qualitative aspects of the constitution."""

        for section in constitution.sections:
            content = section.content.strip()

            if section.required:
                sentence_count = self._count_substantive_sentences(content)
                if sentence_count < validation_settings.constitution_min_sentences:
                    result.add_issue(
                        ValidationIssue(
                            category=ValidationCategory.QUALITY,
                            priority=ValidationPriority.MEDIUM,
                            message=(
                                f"Section '{section.title}' is thin ({sentence_count} "
                                "actionable statements)."
                            ),
                            location=section.title,
                            suggested_fix=(
                                "Expand the section with specific, testable policies "
                                f"(target ≥ {validation_settings.constitution_min_sentences} sentences or bullets)."
                            ),
                            auto_fixable=False,
                        )
                    )

            if section.title in CONSTITUTION_NORMATIVE_SECTIONS:
                upper_content = content.upper()
                if not any(keyword in upper_content for keyword in CONSTITUTION_NORMATIVE_KEYWORDS):
                    result.add_issue(
                        ValidationIssue(
                            category=ValidationCategory.QUALITY,
                            priority=ValidationPriority.MEDIUM,
                            message=(
                                f"Section '{section.title}' lacks normative language (MUST/SHALL/MAY)."
                            ),
                            location=section.title,
                            suggested_fix=(
                                "Introduce declarative requirements using MUST, MUST NOT, SHALL, "
                                "or MAY to clarify enforceability."
                            ),
                            auto_fixable=False,
                        )
                    )

            for pattern in CONSTITUTION_VAGUE_POLICY_PATTERNS:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    line_num = content[: match.start()].count("\n") + 1
                    result.add_issue(
                        ValidationIssue(
                            category=ValidationCategory.QUALITY,
                            priority=ValidationPriority.LOW,
                            message=(f"Vague commitment '{match.group()}' weakens enforceability."),
                            location=section.title,
                            line_number=line_num,
                            suggested_fix=(
                                "Replace with explicit requirements (e.g., use MUST with measurable criteria)."
                            ),
                            auto_fixable=False,
                        )
                    )

    def _check_consistency(
        self,
        constitution: ConstitutionDocument,
        result: ValidationResult,
    ) -> None:
        """Check consistency across amendments and metadata."""

        amendments = constitution.amendments
        if not amendments:
            return

        # Ensure amendments are chronological
        for index in range(1, len(amendments)):
            if amendments[index].date < amendments[index - 1].date:
                result.add_issue(
                    ValidationIssue(
                        category=ValidationCategory.CONSISTENCY,
                        priority=ValidationPriority.MEDIUM,
                        message="Amendments are out of chronological order.",
                        location="Amendments section",
                        suggested_fix="Sort amendments by effective date ascending.",
                        auto_fixable=False,
                    )
                )
                break

        # Ensure amendment versions increase monotonically when parsable
        previous_version = self._parse_version(amendments[0].version)
        for amendment in amendments[1:]:
            current_version = self._parse_version(amendment.version)
            if previous_version and current_version and current_version < previous_version:
                result.add_issue(
                    ValidationIssue(
                        category=ValidationCategory.CONSISTENCY,
                        priority=ValidationPriority.MEDIUM,
                        message="Amendment versions do not increase monotonically.",
                        location="Amendments section",
                        suggested_fix=(
                            "Ensure amendment versions follow semantic version ordering (e.g., 1.1.0 → 1.2.0)."
                        ),
                        auto_fixable=False,
                    )
                )
                break
            if current_version:
                previous_version = current_version

        # Validate metadata last amendment alignment
        latest_amendment_date = max(amendment.date for amendment in amendments)
        metadata_last_amendment = constitution.metadata.last_amendment
        if metadata_last_amendment is None:
            result.add_issue(
                ValidationIssue(
                    category=ValidationCategory.CONSISTENCY,
                    priority=ValidationPriority.MEDIUM,
                    message="Metadata missing last amendment date despite recorded amendments.",
                    location="Metadata section",
                    suggested_fix="Update metadata.last_amendment to match the most recent amendment date.",
                    auto_fixable=True,
                )
            )
        elif metadata_last_amendment != latest_amendment_date:
            result.add_issue(
                ValidationIssue(
                    category=ValidationCategory.CONSISTENCY,
                    priority=ValidationPriority.MEDIUM,
                    message=(
                        "Metadata last amendment date does not match the latest amendment entry."
                    ),
                    location="Metadata section",
                    suggested_fix=(
                        f"Set last_amendment to {latest_amendment_date.isoformat()} to reflect the latest change."
                    ),
                    auto_fixable=True,
                )
            )

    @staticmethod
    def _count_substantive_sentences(content: str) -> int:
        """Count substantive sentences or bullet points in content."""

        text = content.strip()
        if not text:
            return 0

        sentence_candidates = [
            segment.strip() for segment in re.split(r"[.!?]+\s+|\n+", text) if segment.strip()
        ]
        bullet_count = sum(1 for line in text.splitlines() if line.strip().startswith(("-", "*")))

        if bullet_count > len(sentence_candidates):
            return bullet_count
        return len(sentence_candidates)

    @staticmethod
    def _parse_version(version: str) -> tuple[int, int, int] | None:
        """Parse semantic version string into tuple."""

        try:
            major, minor, patch = version.split(".")
            return int(major), int(minor), int(patch)
        except (ValueError, AttributeError):
            return None

    @classmethod
    def from_config(cls) -> "ValidationService":
        """Create service instance.

        Returns:
            Configured ValidationService
        """
        return cls()
