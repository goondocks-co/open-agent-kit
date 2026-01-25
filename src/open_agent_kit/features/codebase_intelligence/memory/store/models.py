"""Data models for vector store.

Dataclasses representing code chunks, memory observations, and plan observations.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from open_agent_kit.features.codebase_intelligence.memory.store.classification import (
    classify_doc_type,
    get_short_path,
)


@dataclass
class CodeChunk:
    """A chunk of code for indexing."""

    id: str
    content: str
    filepath: str
    language: str
    chunk_type: str
    name: str | None
    start_line: int
    end_line: int
    parent_id: str | None = None
    docstring: str | None = None
    signature: str | None = None

    @property
    def token_estimate(self) -> int:
        """Estimate tokens (~4 chars per token)."""
        return len(self.content) // 4

    @property
    def doc_type(self) -> str:
        """Classify document type based on filepath."""
        return classify_doc_type(self.filepath)

    @property
    def file_name(self) -> str:
        """Get just the filename from path."""
        return Path(self.filepath).name

    @property
    def short_path(self) -> str:
        """Get shortened path (last 3 segments)."""
        return get_short_path(self.filepath)

    def get_embedding_text(self) -> str:
        """Generate document envelope text for embedding.

        Creates a structured text that includes semantic anchors:
        - File name
        - Symbol names (function/class)
        - Kind (function, class, module)
        - Docstring if present
        - The actual code

        This improves embedding quality by including metadata that
        developers naturally search for.
        """
        parts = []

        # File context (short path to avoid noise)
        parts.append(f"file: {self.file_name}")

        # Symbol name if present
        if self.name:
            parts.append(f"symbol: {self.name}")

        # Kind/type
        parts.append(f"kind: {self.chunk_type}")

        # Language
        parts.append(f"language: {self.language}")

        # Separator
        parts.append("---")

        # Docstring if present (important semantic signal)
        if self.docstring:
            parts.append(self.docstring.strip())
            parts.append("---")

        # The actual code
        parts.append(self.content)

        return "\n".join(parts)

    def to_metadata(self) -> dict[str, Any]:
        """Convert to ChromaDB metadata format."""
        return {
            "filepath": self.filepath,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "name": self.name or "",
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent_id": self.parent_id or "",
            "has_docstring": bool(self.docstring),
            "token_estimate": self.token_estimate,
            "doc_type": self.doc_type,
        }

    @staticmethod
    def generate_id(filepath: str, start_line: int, content: str) -> str:
        """Generate stable ID from content."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"{filepath}:{start_line}:{content_hash}"


@dataclass
class MemoryObservation:
    """A memory observation."""

    id: str
    observation: str
    memory_type: str
    context: str | None = None
    tags: list[str] | None = None
    created_at: datetime | None = None

    @property
    def token_estimate(self) -> int:
        """Estimate tokens."""
        return len(self.observation) // 4

    def to_metadata(self) -> dict[str, Any]:
        """Convert to ChromaDB metadata format."""
        return {
            "memory_type": self.memory_type,
            "context": self.context or "",
            "tags": ",".join(self.tags) if self.tags else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "token_estimate": self.token_estimate,
        }


@dataclass
class PlanObservation:
    """A plan to be indexed for semantic search.

    Plans are stored in prompt_batches (SQLite) and indexed in oak_memory (ChromaDB)
    with memory_type='plan'. This enables semantic search of plans alongside
    code and memories to understand the "why" behind code changes.
    """

    id: str
    session_id: str
    title: str  # Extracted from filename or first heading
    content: str  # Full plan text
    file_path: str | None = None
    created_at: datetime | None = None

    @property
    def token_estimate(self) -> int:
        """Estimate tokens (~4 chars per token)."""
        return len(self.content) // 4

    def get_embedding_text(self) -> str:
        """Generate text for embedding.

        Plans are already LLM-generated, so we embed the full content
        with a title prefix for better semantic matching.
        """
        return f"Plan: {self.title}\n\n{self.content}"

    def to_metadata(self) -> dict[str, Any]:
        """Convert to ChromaDB metadata format."""
        return {
            "memory_type": "plan",
            "context": self.file_path or "",
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "token_estimate": self.token_estimate,
            "tags": "",  # Plans don't have tags
        }
