"""Codebase indexer for automatic file discovery and indexing."""

import fnmatch
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.config import DEFAULT_EXCLUDE_PATTERNS
from open_agent_kit.features.codebase_intelligence.indexing.chunker import (
    ChunkerConfig,
    CodeChunker,
)
from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)

# Sensitive file patterns to block from indexing
# These are DATA files that may contain secrets, not code files that handle secrets.
# Patterns are intentionally specific to avoid false positives on SDK/API client files.
SENSITIVE_FILE_PATTERNS = [
    # Environment and config files with secrets
    ".env",
    ".env.*",
    "*.env",
    # Key and certificate files
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.crt",
    "*.cer",
    # SSH keys
    "id_rsa",
    "id_rsa.*",
    "id_dsa",
    "id_dsa.*",
    "id_ecdsa",
    "id_ecdsa.*",
    "id_ed25519",
    "id_ed25519.*",
    # Credential data files (not code files)
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
    "credentials.xml",
    "credentials.toml",
    # Secret data files
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "secrets.xml",
    "secrets.toml",
    ".secrets",
    # Password files
    "passwords.txt",
    "passwords.json",
    ".htpasswd",
    # Token files
    "token.json",
    "tokens.json",
    ".token",
    # AWS/Cloud credentials
    ".aws_credentials",
    "aws_credentials",
    # Specific service account files
    "service_account.json",
    "service-account.json",
    "serviceaccount.json",
    # Private key exports
    "*.keystore",
    "*.jks",
]

# File extensions we index
INDEXABLE_EXTENSIONS = {
    ".py",
    ".pyi",  # Python
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",  # JavaScript
    ".ts",
    ".tsx",  # TypeScript
    ".go",  # Go
    ".rs",  # Rust
    ".java",  # Java
    ".rb",  # Ruby
    ".php",  # PHP
    ".c",
    ".cpp",
    ".h",
    ".hpp",  # C/C++
    ".cs",  # C#
    ".swift",  # Swift
    ".kt",  # Kotlin
    ".scala",  # Scala
    ".sh",
    ".bash",
    ".zsh",  # Shell
    ".yaml",
    ".yml",  # YAML
    ".json",  # JSON
    ".toml",  # TOML
    ".md",  # Markdown
}


@dataclass
class IndexStats:
    """Statistics from an indexing operation."""

    files_processed: int = 0
    files_skipped: int = 0
    chunks_indexed: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    last_indexed: datetime | None = None
    # AST chunking statistics
    ast_success: int = 0
    ast_fallback: int = 0
    line_based: int = 0


@dataclass
class IndexerConfig:
    """Configuration for the indexer."""

    ignore_patterns: list[str] = field(default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy())
    max_file_size_kb: int = 500  # Skip files larger than this
    batch_size: int = 50  # Index files in batches


class CodebaseIndexer:
    """Indexes a codebase for semantic search.

    Discovers files, chunks them, generates embeddings, and stores
    them in the vector store. Supports incremental updates.
    """

    def __init__(
        self,
        project_root: Path,
        vector_store: VectorStore,
        config: IndexerConfig | None = None,
        chunker_config: ChunkerConfig | None = None,
    ):
        """Initialize indexer.

        Args:
            project_root: Root directory of the project.
            vector_store: VectorStore for storing embeddings.
            config: Indexer configuration.
            chunker_config: Chunker configuration (chunk size, max chars, etc.).
        """
        self.project_root = project_root
        self.vector_store = vector_store
        self.config = config or IndexerConfig()

        # Note: .gitignore patterns are loaded fresh at index time in discover_files()
        # This ensures gitignore changes are picked up without daemon restart

        self.chunker = CodeChunker(chunker_config)
        self._stats = IndexStats()

    def _load_gitignore(self) -> list[str]:
        """Load patterns from .gitignore and convert to glob patterns."""
        gitignore_path = self.project_root / ".gitignore"
        if not gitignore_path.exists():
            return []

        patterns = []
        try:
            with open(gitignore_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Skip negations for now (complexity)
                    if line.startswith("!"):
                        continue

                    # Handle directories (ending with /)
                    if line.endswith("/"):
                        # 'build/' -> 'build/**', '**/build/**'
                        clean_dir = line.rstrip("/")
                        if clean_dir.startswith("/"):
                            # Rooted: '/build/' -> 'build/**'
                            patterns.append(f"{clean_dir.lstrip('/')}/**")
                        else:
                            # Anywhere: 'build/' -> 'build/**', '**/build/**'
                            patterns.append(f"{clean_dir}/**")
                            patterns.append(f"**/{clean_dir}/**")
                    else:
                        # Handle files
                        if line.startswith("/"):
                            # Rooted file: '/todo.txt' -> 'todo.txt'
                            patterns.append(line.lstrip("/"))
                        else:
                            # Anywhere: 'start.sh' -> 'start.sh', '**/start.sh'
                            patterns.append(line)
                            patterns.append(f"**/{line}")

            logger.info(f"Loaded {len(patterns)} patterns from .gitignore")
            return patterns
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to load .gitignore: {e}")
            return []

    def _is_sensitive_file(self, filepath: Path) -> bool:
        """Check if a file matches sensitive file patterns.

        Args:
            filepath: Path to check.

        Returns:
            True if file is sensitive and should not be indexed.
        """
        filename = filepath.name.lower()
        for pattern in SENSITIVE_FILE_PATTERNS:
            if fnmatch.fnmatch(filename, pattern):
                logger.warning(f"Blocking sensitive file from indexing: {filepath.name}")
                return True
        return False

    def _validate_path_safety(self, filepath: Path) -> bool:
        """Validate that a file path is safe to index.

        Checks for symlink attacks and path traversal attempts.

        Args:
            filepath: Absolute path to validate.

        Returns:
            True if path is safe, False otherwise.
        """
        try:
            # Resolve symlinks and check if path is within project root
            resolved_path = filepath.resolve()
            project_root_resolved = self.project_root.resolve()

            # Check if resolved path is relative to project root
            # This prevents symlink attacks that point outside the project
            if not resolved_path.is_relative_to(project_root_resolved):
                logger.warning(f"Blocked path outside project root: {filepath} -> {resolved_path}")
                return False

            return True
        except (OSError, ValueError, RuntimeError) as e:
            logger.warning(f"Path validation failed for {filepath}: {e}")
            return False

    def _get_ignore_pattern(self, path: Path, patterns: list[str] | None = None) -> str | None:
        """Get the pattern that causes a path to be ignored.

        Args:
            path: Path to check (relative to project root).
            patterns: Optional list of patterns to check against.
                     If None, uses self.config.ignore_patterns.

        Returns:
            The matching pattern, or None if not ignored.
        """
        path_str = str(path)
        path_parts = path.parts

        check_patterns = patterns if patterns is not None else self.config.ignore_patterns
        for pattern in check_patterns:
            # Check full path match (e.g., "docs/**" matches "docs/file.py")
            if fnmatch.fnmatch(path_str, pattern):
                return pattern

            # Check just the filename (e.g., "*.log" matches "app.log")
            if fnmatch.fnmatch(path.name, pattern):
                return pattern

            # Check if any path component matches the pattern exactly
            # This handles simple directory names like "docs" or "vendor"
            # which should exclude files like "docs/file.py" or "vendor/lib/code.py"
            if pattern in path_parts:
                return pattern

            # Check glob pattern against each path component
            # This handles patterns like "node_*" matching "node_modules"
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return pattern

            # Check if pattern is a path prefix (handles patterns like ".claude/commands")
            # This matches files like ".claude/commands/foo.md"
            if "/" in pattern or "\\" in pattern:
                # Normalize pattern to use forward slashes for comparison
                normalized_pattern = pattern.replace("\\", "/")
                normalized_path = path_str.replace("\\", "/")
                # Check if path starts with pattern (as a directory prefix)
                if normalized_path.startswith(normalized_pattern + "/"):
                    return pattern
                # Also check exact match for the directory itself
                if normalized_path == normalized_pattern:
                    return pattern

        return None

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored.

        Args:
            path: Path to check (relative to project root).

        Returns:
            True if path should be ignored.
        """
        return self._get_ignore_pattern(path) is not None

    def _should_index_file(self, filepath: Path) -> bool:
        """Check if a file should be indexed.

        Args:
            filepath: Path to the file.

        Returns:
            True if file should be indexed.
        """
        # Check extension
        if filepath.suffix.lower() not in INDEXABLE_EXTENSIONS:
            return False

        # Check size
        try:
            size_kb = filepath.stat().st_size / 1024
            if size_kb > self.config.max_file_size_kb:
                logger.debug(f"Skipping large file: {filepath} ({size_kb:.1f}KB)")
                return False
        except OSError:
            return False

        return True

    def discover_files(self) -> list[Path]:
        """Discover all indexable files in the project.

        Uses os.walk with in-place directory pruning to skip ignored
        directories early, avoiding descent into large trees like
        node_modules or .git.

        Returns:
            List of file paths to index.
        """
        # Load gitignore patterns fresh each time (picks up changes without restart)
        gitignore_patterns = self._load_gitignore()

        # Merge config patterns with gitignore for this discovery run
        # This ensures gitignore is always respected, even if config patterns change
        all_patterns = list(self.config.ignore_patterns)
        for pattern in gitignore_patterns:
            if pattern not in all_patterns:
                all_patterns.append(pattern)

        files = []

        for root, dirs, filenames in os.walk(self.project_root):
            root_path = Path(root)

            # Get relative root for pattern matching
            try:
                relative_root = root_path.relative_to(self.project_root)
            except ValueError:
                continue

            # Prune ignored directories in-place (prevents descent)
            dirs[:] = [
                d for d in dirs if not self._get_ignore_pattern(relative_root / d, all_patterns)
            ]

            for filename in filenames:
                filepath = root_path / filename
                relative = relative_root / filename

                # Check ignore patterns FIRST - skip early without logging warnings
                ignored_by = self._get_ignore_pattern(relative, all_patterns)
                if ignored_by:
                    if filepath.suffix.lower() in INDEXABLE_EXTENSIONS:
                        logger.debug(f"Excluded {relative} (pattern: {ignored_by})")
                    continue

                # Security: Validate path safety (symlink and traversal protection)
                if not self._validate_path_safety(filepath):
                    continue

                # Security: Block sensitive files (safety net for non-ignored files)
                if self._is_sensitive_file(filepath):
                    continue

                if self._should_index_file(filepath):
                    files.append(filepath)

        logger.info(f"Discovered {len(files)} indexable files")
        return files

    def index_file(self, filepath: Path) -> int:
        """Index a single file.

        Args:
            filepath: Path to the file.

        Returns:
            Number of chunks indexed.
        """
        # Security: Validate path safety
        if not self._validate_path_safety(filepath):
            logger.warning(f"Blocked unsafe path from indexing: {filepath}")
            return 0

        # Security: Block sensitive files
        if self._is_sensitive_file(filepath):
            return 0

        try:
            relative_path = filepath.relative_to(self.project_root)
        except ValueError:
            relative_path = filepath

        try:
            chunks = self.chunker.chunk_file(filepath, display_path=str(relative_path))
            if not chunks:
                return 0

            # Update filepath to be relative
            for chunk in chunks:
                chunk.filepath = str(relative_path)

            self.vector_store.add_code_chunks(chunks)
            return len(chunks)

        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"Failed to index {filepath}: {e}")
            self._stats.errors += 1
            return 0

    def build_index(
        self,
        full_rebuild: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
        use_batched_embedding: bool = True,
    ) -> IndexStats:
        """Build or rebuild the index.

        Args:
            full_rebuild: If True, clear existing index first.
            progress_callback: Optional callback(current, total) for progress.
            use_batched_embedding: If True, accumulate chunks and embed in batches.
                This is more memory-efficient for large codebases.

        Returns:
            IndexStats with results.
        """
        start_time = time.time()
        self._stats = IndexStats()

        # Reset chunker stats for this indexing run
        self.chunker.reset_stats()

        if full_rebuild:
            logger.info("Starting full index rebuild (memories preserved)")
            self.vector_store.clear_code_index()
        else:
            logger.info("Starting incremental index update")

        files = self.discover_files()
        total_files = len(files)

        if use_batched_embedding:
            # Accumulate all chunks first, then embed in batches
            # This is more efficient for embedding APIs that support batching
            all_chunks = []

            for i, filepath in enumerate(files):
                try:
                    chunks = self._chunk_file(filepath)
                    if chunks:
                        all_chunks.extend(chunks)
                        self._stats.files_processed += 1
                    else:
                        self._stats.files_skipped += 1
                except (OSError, ValueError, TypeError) as e:
                    logger.error(f"Error chunking {filepath}: {e}")
                    self._stats.errors += 1
                    self._stats.files_skipped += 1

                # Report file processing progress (first half)
                if progress_callback:
                    progress_callback(i + 1, total_files * 2)

            # Now embed and store all chunks in batches
            if all_chunks:
                logger.info(f"Embedding {len(all_chunks)} chunks in batches...")

                def embedding_progress(current: int, total: int) -> None:
                    if progress_callback:
                        # Second half of progress
                        progress_callback(
                            total_files + (current * total_files // total), total_files * 2
                        )

                self._stats.chunks_indexed = self.vector_store.add_code_chunks_batched(
                    all_chunks,
                    batch_size=self.config.batch_size,
                    progress_callback=embedding_progress,
                )
        else:
            # Original per-file indexing approach
            for i, filepath in enumerate(files):
                try:
                    chunks_added = self.index_file(filepath)
                    if chunks_added > 0:
                        self._stats.files_processed += 1
                        self._stats.chunks_indexed += chunks_added
                    else:
                        self._stats.files_skipped += 1

                except (OSError, ValueError, TypeError) as e:
                    logger.error(f"Error indexing {filepath}: {e}")
                    self._stats.errors += 1
                    self._stats.files_skipped += 1

                # Report progress
                if progress_callback:
                    progress_callback(i + 1, total_files)

        self._stats.duration_seconds = time.time() - start_time
        self._stats.last_indexed = datetime.now()

        # Capture AST statistics from chunker
        chunker_stats = self.chunker.get_stats()
        self._stats.ast_success = chunker_stats["ast_success"]
        self._stats.ast_fallback = chunker_stats["ast_fallback"]
        self._stats.line_based = chunker_stats["line_based"]

        logger.info(
            f"Indexing complete: {self._stats.files_processed} files, "
            f"{self._stats.chunks_indexed} chunks in {self._stats.duration_seconds:.1f}s"
        )

        # Log AST usage statistics
        self.chunker.log_stats_summary()

        return self._stats

    def _chunk_file(self, filepath: Path) -> list:
        """Chunk a file without embedding.

        Args:
            filepath: Path to the file.

        Returns:
            List of CodeChunk objects, or empty list if chunking failed.
        """
        try:
            relative_path = filepath.relative_to(self.project_root)
        except ValueError:
            relative_path = filepath

        try:
            chunks = self.chunker.chunk_file(filepath, display_path=str(relative_path))
            if not chunks:
                return []

            # Update filepath to be relative
            for chunk in chunks:
                chunk.filepath = str(relative_path)

            return chunks

        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"Failed to chunk {relative_path}: {e}")
            self._stats.errors += 1
            return []

    def get_stats(self) -> IndexStats:
        """Get current index statistics."""
        return self._stats

    def index_single_file(self, filepath: Path) -> int:
        """Index or re-index a single file.

        Use this for incremental updates when a file changes.

        Args:
            filepath: Path to the file.

        Returns:
            Number of chunks indexed.
        """
        # Security: Validate path safety
        if not self._validate_path_safety(filepath):
            logger.warning(f"Blocked unsafe path from indexing: {filepath}")
            return 0

        # Security: Block sensitive files
        if self._is_sensitive_file(filepath):
            return 0

        try:
            relative_path = filepath.relative_to(self.project_root)
        except ValueError:
            relative_path = filepath

        # Remove existing chunks for this file
        deleted_count = self.vector_store.delete_code_by_filepath(str(relative_path))
        if deleted_count > 0:
            logger.debug(f"Deleted {deleted_count} existing chunks for {relative_path}")

        # Re-index
        return self.index_file(filepath)

    def remove_file(self, filepath: Path) -> int:
        """Remove a file from the index.

        Args:
            filepath: Path to the file.

        Returns:
            Number of chunks removed.
        """
        try:
            relative_path = filepath.relative_to(self.project_root)
        except ValueError:
            relative_path = filepath

        return self.vector_store.delete_code_by_filepath(str(relative_path))
