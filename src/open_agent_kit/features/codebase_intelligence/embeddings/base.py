"""Base embedding provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    """Result from embedding operation."""

    embeddings: list[list[float]]
    model: str
    provider: str
    dimensions: int


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    Embedding providers transform text into dense vector representations
    suitable for semantic similarity search.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and identification."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensionality of the embedding vectors."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is currently available.

        Returns:
            True if the provider can be used, False otherwise.
        """
        ...

    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult containing the embeddings and metadata.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        ...

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query.

        This is a convenience method that calls embed() for a single text.
        Some providers may optimize single-query embedding differently.

        Args:
            query: The query text to embed.

        Returns:
            A single embedding vector.
        """
        result = self.embed([query])
        return result.embeddings[0]


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""

    def __init__(self, message: str, provider: str, cause: Exception | None = None):
        """Initialize embedding error.

        Args:
            message: Error description.
            provider: Name of the provider that failed.
            cause: Optional underlying exception.
        """
        super().__init__(message)
        self.provider = provider
        self.cause = cause
