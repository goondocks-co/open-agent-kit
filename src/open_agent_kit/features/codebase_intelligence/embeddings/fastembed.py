"""FastEmbed fallback provider for CPU-based embeddings."""

from typing import Any

from open_agent_kit.features.codebase_intelligence.embeddings.base import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResult,
)

# Default model that works well for code search
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_DIMENSIONS = 384


class FastEmbedProvider(EmbeddingProvider):
    """Fallback embedding provider using FastEmbed.

    FastEmbed is a lightweight embedding library that runs on CPU without
    requiring GPU or external services. It's used as a fallback when
    Ollama is unavailable.

    Uses ONNX runtime for efficient CPU inference.
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        """Initialize FastEmbed provider.

        Args:
            model: The FastEmbed model to use. Default is a small but
                   effective model for code search.
        """
        self._model_name = model
        self._model: Any = None
        self._available: bool | None = None
        self._dimensions = DEFAULT_DIMENSIONS

    @property
    def name(self) -> str:
        """Provider name."""
        return f"fastembed:{self._model_name}"

    @property
    def dimensions(self) -> int:
        """Embedding dimensions."""
        return self._dimensions

    @property
    def is_available(self) -> bool:
        """Check if FastEmbed is installed and working."""
        if self._available is not None:
            return self._available

        try:
            from fastembed import TextEmbedding  # type: ignore[import-not-found]

            # Try to initialize - this validates the model exists
            self._model = TextEmbedding(model_name=self._model_name)
            self._available = True
            return True

        except ImportError:
            self._available = False
            return False
        except Exception:
            self._available = False
            return False

    def _ensure_model(self) -> None:
        """Ensure the model is loaded."""
        if self._model is None:
            try:
                from fastembed import TextEmbedding  # type: ignore[import-not-found]

                self._model = TextEmbedding(model_name=self._model_name)
            except ImportError as e:
                raise EmbeddingError(
                    "FastEmbed is not installed. Install with: "
                    "pip install open-agent-kit[codebase-intelligence]",
                    provider=self.name,
                    cause=e,
                ) from e

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using FastEmbed.

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResult with embeddings.

        Raises:
            EmbeddingError: If FastEmbed is unavailable or embedding fails.
        """
        if not self.is_available:
            raise EmbeddingError(
                "FastEmbed is not available",
                provider=self.name,
            )

        try:
            self._ensure_model()
            # FastEmbed returns a generator, convert to list
            embeddings = list(self._model.embed(texts))
            # Convert numpy arrays to lists
            embeddings = [emb.tolist() for emb in embeddings]

            return EmbeddingResult(
                embeddings=embeddings,
                model=self._model_name,
                provider=self.name,
                dimensions=len(embeddings[0]) if embeddings else self._dimensions,
            )

        except Exception as e:
            raise EmbeddingError(
                f"FastEmbed embedding failed: {e}",
                provider=self.name,
                cause=e,
            ) from e
