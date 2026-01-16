"""Code chunking for semantic indexing.

Provides both line-based chunking (fallback) and AST-aware chunking
for supported languages (Python, JavaScript/TypeScript).
"""

import importlib.util
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from open_agent_kit.features.codebase_intelligence.memory.store import CodeChunk

logger = logging.getLogger(__name__)

# Language detection by extension
LANGUAGE_MAP = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
}

# Default chunk settings
DEFAULT_CHUNK_SIZE = 100  # lines
DEFAULT_CHUNK_OVERLAP = 10  # lines
MAX_CHUNK_SIZE = 500  # lines

# Character limit for embedding models
# Use conservative limit (~0.75 chars per token) as code tokenizes aggressively
# BERT tokenizers often produce 1 token per 1-2 chars for code
MAX_CHUNK_CHARS = 3072  # Safe default for ~4096 token context


@dataclass
class ChunkerConfig:
    """Configuration for code chunking."""

    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    max_chunk_size: int = MAX_CHUNK_SIZE
    max_chunk_chars: int = MAX_CHUNK_CHARS
    use_ast: bool = True  # Try AST-based chunking when available


# Tree-sitter language packages map
# Maps language name to the Python package name
TREE_SITTER_PACKAGES = {
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "go": "tree_sitter_go",
    "rust": "tree_sitter_rust",
    "java": "tree_sitter_java",
    "ruby": "tree_sitter_ruby",
    "c": "tree_sitter_c",
    "cpp": "tree_sitter_cpp",
    "csharp": "tree_sitter_c_sharp",
    "kotlin": "tree_sitter_kotlin",
    "scala": "tree_sitter_scala",
    "php": "tree_sitter_php",
    "swift": "tree_sitter_swift",
}

# Declarative AST configuration for each language
# This drives the generic _chunk_with_ast method
LANGUAGE_AST_CONFIG: dict[str, dict[str, Any]] = {
    "python": {
        "package": "tree_sitter_python",
        "node_map": {
            "function_definition": "function",
            "class_definition": "class",
        },
        "container_types": {"class_definition"},
        "extract_docstring": True,
        "extract_signature": True,
    },
    "javascript": {
        "package": "tree_sitter_javascript",
        "node_map": {
            "function_declaration": "function",
            "arrow_function": "function",
            "function": "function",
            "class_declaration": "class",
            "method_definition": "method",
        },
        "container_types": {"class_declaration"},
    },
    "typescript": {
        "package": "tree_sitter_javascript",  # TS uses JS parser for basic chunking
        "node_map": {
            "function_declaration": "function",
            "arrow_function": "function",
            "function": "function",
            "class_declaration": "class",
            "method_definition": "method",
        },
        "container_types": {"class_declaration"},
    },
    "go": {
        "package": "tree_sitter_go",
        "node_map": {
            "function_declaration": "function",
            "method_declaration": "method",
            "type_declaration": "type",
        },
    },
    "rust": {
        "package": "tree_sitter_rust",
        "node_map": {
            "function_item": "function",
            "impl_item": "impl",
            "struct_item": "struct",
            "enum_item": "enum",
            "trait_item": "trait",
        },
        "container_types": {"impl_item"},
        "name_nodes": ["identifier", "type_identifier"],
    },
    "csharp": {
        "package": "tree_sitter_c_sharp",
        "node_map": {
            "class_declaration": "class",
            "struct_declaration": "struct",
            "interface_declaration": "interface",
            "method_declaration": "method",
            "property_declaration": "property",
            "constructor_declaration": "constructor",
        },
        "container_types": {"class_declaration", "struct_declaration", "interface_declaration"},
        "traverse_only": {"namespace_declaration"},
    },
    "java": {
        "package": "tree_sitter_java",
        "node_map": {
            "class_declaration": "class",
            "interface_declaration": "interface",
            "enum_declaration": "enum",
            "method_declaration": "method",
            "constructor_declaration": "constructor",
        },
        "container_types": {"class_declaration", "interface_declaration", "enum_declaration"},
    },
}


class CodeChunker:
    """Chunk code files for semantic indexing.

    Uses AST-based chunking for supported languages to extract
    functions, classes, and methods as semantic units. Falls back
    to line-based chunking for unsupported languages.
    """

    def __init__(self, config: ChunkerConfig | None = None):
        """Initialize chunker.

        Args:
            config: Chunking configuration.
        """
        self.config = config or ChunkerConfig()
        self._has_tree_sitter = importlib.util.find_spec("tree_sitter") is not None
        self._available_languages = self._check_language_support()
        # Statistics tracking for AST usage
        self._stats: dict[str, Any] = {
            "ast_success": 0,
            "ast_fallback": 0,
            "line_based": 0,
            "by_language": {},  # language -> {"ast": count, "lines": count}
        }

    def _check_language_support(self) -> set[str]:
        """Check which tree-sitter language parsers are available.

        Returns:
            Set of language names with available parsers.
        """
        if not self._has_tree_sitter:
            logger.info("tree-sitter not installed, using line-based chunking for all files")
            return set()

        available = set()
        for language, package in TREE_SITTER_PACKAGES.items():
            if importlib.util.find_spec(package) is not None:
                available.add(language)

        if available:
            logger.info(f"tree-sitter AST parsing available for: {', '.join(sorted(available))}")
        else:
            logger.info("No tree-sitter language parsers installed, using line-based chunking")

        return available

    def has_ast_support(self, language: str) -> bool:
        """Check if AST parsing is available for a specific language.

        Args:
            language: Language identifier.

        Returns:
            True if AST parsing is available.
        """
        return language in self._available_languages

    def _track_chunking_method(self, language: str, used_ast: bool) -> None:
        """Track which chunking method was used for a file.

        Args:
            language: Language of the file.
            used_ast: True if AST parsing was used successfully.
        """
        if used_ast:
            self._stats["ast_success"] += 1
        else:
            if language in self._available_languages:
                self._stats["ast_fallback"] += 1
            else:
                self._stats["line_based"] += 1

        # Track by language
        if language not in self._stats["by_language"]:
            self._stats["by_language"][language] = {"ast": 0, "lines": 0}
        if used_ast:
            self._stats["by_language"][language]["ast"] += 1
        else:
            self._stats["by_language"][language]["lines"] += 1

    def get_stats(self) -> dict:
        """Get chunking statistics.

        Returns:
            Dictionary with AST usage statistics.
        """
        return self._stats.copy()

    def reset_stats(self) -> None:
        """Reset chunking statistics."""
        self._stats = {
            "ast_success": 0,
            "ast_fallback": 0,
            "line_based": 0,
            "by_language": {},
        }

    def log_stats_summary(self) -> None:
        """Log a summary of AST usage statistics."""
        total = self._stats["ast_success"] + self._stats["ast_fallback"] + self._stats["line_based"]
        if total == 0:
            return

        logger.info(
            f"Chunking stats: {self._stats['ast_success']} AST, "
            f"{self._stats['ast_fallback']} AST fallback, "
            f"{self._stats['line_based']} line-based (total: {total} files)"
        )

        # Log per-language breakdown at INFO level for visibility
        for lang, counts in sorted(self._stats["by_language"].items()):
            ast_config = LANGUAGE_AST_CONFIG.get(lang)
            if counts["ast"] > 0 and ast_config:
                node_types = ", ".join(ast_config["node_map"].values())
                logger.info(
                    f"  {lang}: {counts['ast']} files via AST "
                    f"(package={ast_config['package']}, extracts: {node_types})"
                )
            elif counts["lines"] > 0:
                if ast_config:
                    logger.info(f"  {lang}: {counts['lines']} files via line-based (AST fallback)")
                else:
                    logger.info(
                        f"  {lang}: {counts['lines']} files via line-based (no AST support)"
                    )

    def _split_oversized_chunk(self, chunk: CodeChunk) -> list[CodeChunk]:
        """Split a chunk that exceeds max_chunk_chars into smaller parts.

        Uses line boundaries to split, preserving some overlap for context.

        Args:
            chunk: The oversized chunk to split.

        Returns:
            List of smaller chunks.
        """
        if len(chunk.content) <= self.config.max_chunk_chars:
            return [chunk]

        lines = chunk.content.split("\n")
        chunks = []
        part_num = 0

        current_lines: list[str] = []
        current_chars = 0
        current_start_line = chunk.start_line

        for i, line in enumerate(lines):
            line_chars = len(line) + 1  # +1 for newline

            # Check if adding this line exceeds the limit
            if current_chars + line_chars > self.config.max_chunk_chars and current_lines:
                # Create chunk from accumulated lines
                chunk_content = "\n".join(current_lines)
                chunks.append(
                    CodeChunk(
                        id=CodeChunk.generate_id(chunk.filepath, current_start_line, chunk_content),
                        content=chunk_content,
                        filepath=chunk.filepath,
                        language=chunk.language,
                        chunk_type=chunk.chunk_type,
                        name=f"{chunk.name}_part{part_num}" if chunk.name else None,
                        start_line=current_start_line,
                        end_line=current_start_line + len(current_lines) - 1,
                        parent_id=chunk.parent_id,
                        docstring=chunk.docstring if part_num == 0 else None,
                        signature=chunk.signature if part_num == 0 else None,
                    )
                )
                part_num += 1

                # Start new chunk with overlap (last few lines)
                overlap_lines = min(self.config.chunk_overlap, len(current_lines))
                current_lines = current_lines[-overlap_lines:] if overlap_lines > 0 else []
                current_chars = sum(len(line) + 1 for line in current_lines)
                current_start_line = chunk.start_line + i - len(current_lines)

            current_lines.append(line)
            current_chars += line_chars

        # Add remaining lines as final chunk
        if current_lines:
            chunk_content = "\n".join(current_lines)
            chunks.append(
                CodeChunk(
                    id=CodeChunk.generate_id(chunk.filepath, current_start_line, chunk_content),
                    content=chunk_content,
                    filepath=chunk.filepath,
                    language=chunk.language,
                    chunk_type=chunk.chunk_type,
                    name=f"{chunk.name}_part{part_num}" if chunk.name else None,
                    start_line=current_start_line,
                    end_line=chunk.end_line,
                    parent_id=chunk.parent_id,
                )
            )

        logger.debug(f"Split oversized chunk ({len(chunk.content)} chars) into {len(chunks)} parts")
        return chunks

    def detect_language(self, filepath: Path) -> str:
        """Detect programming language from file extension.

        Args:
            filepath: Path to the file.

        Returns:
            Language identifier string.
        """
        suffix = filepath.suffix.lower()
        return LANGUAGE_MAP.get(suffix, "unknown")

    def chunk_file(self, filepath: Path, content: str | None = None) -> list[CodeChunk]:
        """Chunk a file into semantic units.

        Args:
            filepath: Path to the file.
            content: Optional pre-loaded content.

        Returns:
            List of code chunks.
        """
        if content is None:
            try:
                content = filepath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read {filepath}: {e}")
                return []

        # Skip empty or whitespace-only files
        if not content or not content.strip():
            logger.debug(f"Skipping empty file: {filepath}")
            return []

        language = self.detect_language(filepath)
        filepath_str = str(filepath)
        attempted_ast = False
        used_ast = False

        # Try AST-based chunking for supported languages
        if self.config.use_ast and language in LANGUAGE_AST_CONFIG:
            attempted_ast = True
            chunks = self._chunk_with_ast(filepath_str, content, language)

            # Check if AST actually produced semantic chunks (not just module chunks from fallback)
            if chunks:
                semantic_types = {
                    "function",
                    "class",
                    "method",
                    "type",
                    "impl",
                    "struct",
                    "enum",
                    "trait",
                    "interface",
                    "property",
                    "constructor",
                }
                used_ast = any(c.chunk_type in semantic_types for c in chunks)
        else:
            # Fall back to line-based chunking
            chunks = self._chunk_by_lines(filepath_str, content, language)

        # Track statistics
        self._track_chunking_method(language, used_ast)

        # Log at debug level for per-file visibility
        if used_ast:
            ast_config = LANGUAGE_AST_CONFIG.get(language, {})
            pkg = ast_config.get("package", "unknown")
            logger.debug(
                f"Chunked {filepath.name}: {len(chunks)} chunks " f"(AST: {language} via {pkg})"
            )
        elif attempted_ast:
            logger.debug(
                f"Chunked {filepath.name}: {len(chunks)} chunks "
                f"(AST fallback→line-based: {language})"
            )
        else:
            logger.debug(
                f"Chunked {filepath.name}: {len(chunks)} chunks " f"(line-based: {language})"
            )

        # Split any oversized chunks to fit within embedding model limits
        result = []
        for chunk in chunks:
            result.extend(self._split_oversized_chunk(chunk))

        return result

    def _chunk_by_lines(
        self,
        filepath: str,
        content: str,
        language: str,
    ) -> list[CodeChunk]:
        """Chunk file by lines with overlap.

        Args:
            filepath: File path string.
            content: File content.
            language: Detected language.

        Returns:
            List of code chunks.
        """
        lines = content.split("\n")
        chunks = []

        if len(lines) <= self.config.chunk_size:
            # File fits in one chunk
            chunks.append(
                CodeChunk(
                    id=CodeChunk.generate_id(filepath, 1, content),
                    content=content,
                    filepath=filepath,
                    language=language,
                    chunk_type="module",
                    name=Path(filepath).stem,
                    start_line=1,
                    end_line=len(lines),
                )
            )
            return chunks

        # Split into overlapping chunks
        start = 0
        chunk_num = 0

        while start < len(lines):
            end = min(start + self.config.chunk_size, len(lines))
            chunk_lines = lines[start:end]
            chunk_content = "\n".join(chunk_lines)

            chunks.append(
                CodeChunk(
                    id=CodeChunk.generate_id(filepath, start + 1, chunk_content),
                    content=chunk_content,
                    filepath=filepath,
                    language=language,
                    chunk_type="module",
                    name=f"{Path(filepath).stem}_part{chunk_num}",
                    start_line=start + 1,
                    end_line=end,
                )
            )

            start += self.config.chunk_size - self.config.chunk_overlap
            chunk_num += 1

        return chunks

    def _chunk_with_ast(
        self,
        filepath: str,
        content: str,
        language: str,
    ) -> list[CodeChunk]:
        """Generic AST chunker using declarative language configuration.

        Uses LANGUAGE_AST_CONFIG to determine how to parse and chunk each language.
        This replaces the individual _chunk_*_ast methods with a single, config-driven
        implementation.

        Args:
            filepath: File path string.
            content: File content.
            language: Language identifier (e.g., 'python', 'javascript').

        Returns:
            List of code chunks, or falls back to line-based chunking.
        """
        lang_config = LANGUAGE_AST_CONFIG.get(language)
        if not lang_config:
            return self._chunk_by_lines(filepath, content, language)

        try:
            # Dynamic import of the language package
            lang_module = importlib.import_module(lang_config["package"])
            from tree_sitter import Language, Parser  # type: ignore[import-not-found]

            ts_language = Language(lang_module.language())
            parser = Parser(ts_language)
            tree = parser.parse(bytes(content, "utf8"))

            chunks: list[CodeChunk] = []
            lines = content.split("\n")

            # Extract config options
            node_map: dict[str, str] = lang_config["node_map"]
            container_types: set[str] = lang_config.get("container_types", set())
            traverse_only: set[str] = lang_config.get("traverse_only", set())
            name_nodes: list[str] = lang_config.get("name_nodes", ["identifier"])
            extract_docstring: bool = lang_config.get("extract_docstring", False)
            extract_signature: bool = lang_config.get("extract_signature", False)

            def get_name(node: Any) -> str | None:
                """Extract name from node using configured name node types."""
                for child in node.children:
                    if child.type in name_nodes:
                        result: str = child.text.decode("utf8")
                        return result
                return None

            def get_docstring(node: Any) -> str | None:
                """Extract docstring from function/class node (Python-style)."""
                if not extract_docstring:
                    return None
                # Look for expression_statement with string as first child in body
                for child in node.children:
                    if child.type == "block":
                        for block_child in child.children:
                            if block_child.type == "expression_statement":
                                for expr_child in block_child.children:
                                    if expr_child.type == "string":
                                        result: str = expr_child.text.decode("utf8")
                                        return result
                return None

            def get_signature(node: Any) -> str | None:
                """Extract function signature (Python-style)."""
                if not extract_signature:
                    return None
                for child in node.children:
                    if child.type == "parameters":
                        name_node = None
                        for n in node.children:
                            if n.type == "identifier":
                                name_node = n
                                break
                        if name_node:
                            return f"{name_node.text.decode('utf8')}{child.text.decode('utf8')}"
                return None

            def process_node(node: Any, parent_id: str | None = None) -> None:
                """Recursively process AST nodes."""
                # Handle traverse-only nodes (like C# namespaces)
                if node.type in traverse_only:
                    for child in node.children:
                        process_node(child, parent_id)
                    return

                chunk_type = node_map.get(node.type)
                if chunk_type:
                    name = get_name(node)
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    chunk_content = "\n".join(lines[start_line - 1 : end_line])

                    # Extract optional metadata
                    docstring = get_docstring(node) if chunk_type in ("function", "class") else None
                    signature = get_signature(node) if chunk_type == "function" else None

                    chunk = CodeChunk(
                        id=CodeChunk.generate_id(filepath, start_line, chunk_content),
                        content=chunk_content,
                        filepath=filepath,
                        language=language,
                        chunk_type=chunk_type,
                        name=name,
                        start_line=start_line,
                        end_line=end_line,
                        parent_id=parent_id,
                        docstring=docstring,
                        signature=signature,
                    )
                    chunks.append(chunk)

                    # Process children for container types (classes, impl blocks, etc.)
                    if node.type in container_types:
                        for child in node.children:
                            process_node(child, chunk.id)
                else:
                    # Continue traversing
                    for child in node.children:
                        process_node(child, parent_id)

            process_node(tree.root_node)

            # Fall back to line-based if no semantic chunks found
            if not chunks:
                return self._chunk_by_lines(filepath, content, language)

            return chunks

        except (ImportError, AttributeError, TypeError, ValueError) as e:
            logger.warning(f"AST parsing failed for {filepath}: {e}")
            return self._chunk_by_lines(filepath, content, language)


def chunk_file(filepath: Path, config: ChunkerConfig | None = None) -> list[CodeChunk]:
    """Convenience function to chunk a single file.

    Args:
        filepath: Path to the file.
        config: Optional chunking configuration.

    Returns:
        List of code chunks.
    """
    chunker = CodeChunker(config)
    return chunker.chunk_file(filepath)
