"""LM Studio embedding provider.

LM Studio uses a specific naming convention for embedding models:
- Embedding models must have the 'text-embedding-' prefix
- JIT (Just-in-Time) loading is supported but may need explicit model loading
"""

import logging

import httpx

from open_agent_kit.features.codebase_intelligence.embeddings.base import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResult,
)

logger = logging.getLogger(__name__)

# Character limit for embeddings
MAX_CHARS_PER_TEXT = 6000

# Default port for LM Studio
DEFAULT_PORT = 1234


class LMStudioProvider(EmbeddingProvider):
    """Embedding provider for LM Studio.

    LM Studio requires embedding models to have the 'text-embedding-' prefix.
    This provider handles the prefix automatically and supports JIT loading.

    Attributes:
        model: The model name to use for embeddings.
        base_url: The API base URL (default: http://localhost:1234).
    """

    def __init__(
        self,
        model: str = "text-embedding-nomic-embed-text-v1.5",
        base_url: str = f"http://localhost:{DEFAULT_PORT}",
        dimensions: int | None = None,
        timeout: float = 60.0,  # Longer timeout for JIT loading
    ):
        """Initialize LM Studio provider.

        Args:
            model: Model name for embeddings (text-embedding- prefix added if missing).
            base_url: API base URL (default http://localhost:1234).
            dimensions: Embedding dimensions (auto-detected if not specified).
            timeout: Request timeout in seconds (default 60s for JIT loading).
        """
        # LM Studio requires text-embedding- prefix for embedding models
        self._model = self._normalize_model_name(model)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._available: bool | None = None

        # Determine dimensions from model name heuristics
        if dimensions:
            self._dimensions = dimensions
        else:
            self._dimensions = self._guess_dimensions(self._model)

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        """Ensure model name has the text-embedding- prefix if it's an embedding model.

        Args:
            model: Original model name.

        Returns:
            Model name with text-embedding- prefix if needed.
        """
        if model.lower().startswith("text-embedding-"):
            return model
        # Don't add prefix to models that clearly aren't embeddings
        if any(x in model.lower() for x in ["llama", "mistral", "qwen", "gpt", "phi"]):
            return model
        # Add prefix for embedding models
        return f"text-embedding-{model}"

    @staticmethod
    def _guess_dimensions(model: str) -> int:
        """Look up dimensions from shared metadata, with heuristic fallback.

        Args:
            model: Model name.

        Returns:
            Estimated dimensions.
        """
        from open_agent_kit.features.codebase_intelligence.embeddings.metadata import (
            get_known_dimensions,
        )

        return get_known_dimensions(model)

    @property
    def name(self) -> str:
        """Provider name."""
        return f"lmstudio:{self._model}"

    @property
    def dimensions(self) -> int:
        """Embedding dimensions for the configured model."""
        return self._dimensions

    @property
    def is_available(self) -> bool:
        """Check if LM Studio is running."""
        if self._available is not None:
            return self._available

        try:
            response = self._client.get(f"{self._base_url}/v1/models")
            self._available = response.status_code == 200
            return self._available
        except (httpx.RequestError, httpx.TimeoutException):
            self._available = False
            return False

    def check_availability(self) -> tuple[bool, str]:
        """Check if LM Studio and the model are available.

        Returns:
            Tuple of (available, reason).
        """
        try:
            response = self._client.get(f"{self._base_url}/v1/models")
            if response.status_code != 200:
                return False, f"LM Studio returned status {response.status_code}"

            # Check if model exists
            data = response.json()
            models = [m.get("id", "") for m in data.get("data", [])]
            if self._model not in models:
                # Check without prefix
                base_model = self._model.replace("text-embedding-", "")
                if base_model not in models and f"text-embedding-{base_model}" not in models:
                    return False, f"Model '{self._model}' not found in LM Studio"

            return True, "LM Studio is available"

        except httpx.ConnectError:
            return False, f"Cannot connect to LM Studio at {self._base_url}"
        except httpx.TimeoutException:
            return False, "Connection to LM Studio timed out"
        except (httpx.RequestError, ValueError) as e:
            return False, f"Error checking LM Studio: {e}"

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using LM Studio.

        Handles JIT loading by using a longer timeout.

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResult with embeddings.

        Raises:
            EmbeddingError: If embedding fails.
        """
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                model=self._model,
                provider=self.name,
                dimensions=self._dimensions,
            )

        # Truncate texts that exceed the limit
        truncated_texts = []
        for text in texts:
            if len(text) > MAX_CHARS_PER_TEXT:
                logger.debug(f"Truncating text from {len(text)} to {MAX_CHARS_PER_TEXT} chars")
                truncated_texts.append(text[:MAX_CHARS_PER_TEXT])
            else:
                truncated_texts.append(text)

        headers = {"Content-Type": "application/json"}

        try:
            response = self._client.post(
                f"{self._base_url}/v1/embeddings",
                headers=headers,
                json={
                    "model": self._model,
                    "input": truncated_texts,
                },
            )

            if response.status_code != 200:
                error_text = response.text
                # Check for specific LM Studio errors
                if "no models loaded" in error_text.lower():
                    raise EmbeddingError(
                        f"Model '{self._model}' not loaded. Load it in LM Studio first.",
                        provider=self.name,
                    )
                if "not embedding" in error_text.lower():
                    raise EmbeddingError(
                        f"Model '{self._model}' is not an embedding model. "
                        "Use a model with 'text-embedding-' prefix.",
                        provider=self.name,
                    )
                raise EmbeddingError(
                    f"API returned status {response.status_code}: {error_text}",
                    provider=self.name,
                )

            data = response.json()
            embeddings_data = data.get("data", [])

            if not embeddings_data:
                raise EmbeddingError(
                    f"No embeddings in API response: {data}",
                    provider=self.name,
                )

            # Sort by index to ensure correct order
            embeddings_data.sort(key=lambda x: x.get("index", 0))
            embeddings = [item["embedding"] for item in embeddings_data]

            # Update dimensions if different
            if len(embeddings) > 0 and len(embeddings[0]) != self._dimensions:
                self._dimensions = len(embeddings[0])
                logger.info(f"Detected embedding dimensions: {self._dimensions}")

            return EmbeddingResult(
                embeddings=embeddings,
                model=self._model,
                provider=self.name,
                dimensions=self._dimensions,
            )

        except httpx.TimeoutException as e:
            raise EmbeddingError(
                "Request timed out. Model may be loading - try again in a moment.",
                provider=self.name,
                cause=e,
            ) from e
        except httpx.RequestError as e:
            raise EmbeddingError(
                f"Failed to connect to LM Studio: {e}",
                provider=self.name,
                cause=e,
            ) from e

    def __del__(self) -> None:
        """Clean up HTTP client."""
        if hasattr(self, "_client"):
            self._client.close()
