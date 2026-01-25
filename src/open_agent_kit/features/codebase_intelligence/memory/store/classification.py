"""Document type classification for vector store.

Functions and patterns for classifying documents by type.
"""

from pathlib import Path

# Doc types for filtering/weighting search results
DOC_TYPE_CODE = "code"
DOC_TYPE_I18N = "i18n"
DOC_TYPE_CONFIG = "config"
DOC_TYPE_TEST = "test"
DOC_TYPE_DOCS = "docs"

# Patterns for doc_type classification (checked in order)
# More specific patterns should come first
DOC_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    # i18n/localization files (check BEFORE config to catch .json in translation dirs)
    (
        DOC_TYPE_I18N,
        [
            "translations/",
            "locales/",
            "locale/",
            "i18n/",
            "l10n/",
            "/lang/",
            "/languages/",
        ],
    ),
    # Test files
    (
        DOC_TYPE_TEST,
        [
            "tests/",
            "test/",
            "__tests__/",
            "spec/",
            "test_",
            "_test.",
            ".test.",
            ".spec.",
        ],
    ),
    # Documentation (check BEFORE config to catch .md files)
    (
        DOC_TYPE_DOCS,
        [
            "docs/",
            "doc/",
            "documentation/",
            "readme",  # README.md, readme.txt, etc.
            "changelog",
            "contributing",
            "license",
            ".md",  # All markdown files are docs
            ".rst",  # reStructuredText
        ],
    ),
    # Config files (by extension, checked after path patterns)
    (
        DOC_TYPE_CONFIG,
        [
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".env",
            ".config.",
        ],
    ),
]


def classify_doc_type(filepath: str) -> str:
    """Classify a file into a document type based on path patterns.

    Args:
        filepath: The file path to classify.

    Returns:
        One of: code, i18n, config, test, docs
    """
    filepath_lower = filepath.lower()

    for doc_type, patterns in DOC_TYPE_PATTERNS:
        for pattern in patterns:
            if pattern in filepath_lower:
                return doc_type

    return DOC_TYPE_CODE


def get_short_path(filepath: str, max_segments: int = 3) -> str:
    """Get shortened path with last N segments.

    Args:
        filepath: Full file path.
        max_segments: Maximum number of path segments to keep.

    Returns:
        Shortened path like "services/backup_services.py"
    """
    parts = Path(filepath).parts
    if len(parts) <= max_segments:
        return filepath
    return str(Path(*parts[-max_segments:]))
