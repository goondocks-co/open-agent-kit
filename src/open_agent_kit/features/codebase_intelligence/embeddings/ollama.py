"""Ollama embedding provider."""

import logging

import httpx

from open_agent_kit.features.codebase_intelligence.embeddings.base import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResult,
)

logger = logging.getLogger(__name__)

DEFAULT_DIMENSIONS = 768  # Common default for embedding models
DEFAULT_MAX_CHARS = 6000  # ~3000-4000 tokens worst case


class OllamaProvider(EmbeddingProvider):
    """Embedding provider using Ollama's local embedding models.

    Ollama provides local inference for embedding models, offering privacy
    and no API costs. Model must be specified - use the Ollama API to
    discover available embedding models.

    Attributes:
        model: The Ollama model to use for embeddings.
        base_url: The Ollama API base URL.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
        max_chars: int | None = None,
        dimensions: int | None = None,
    ):
        """Initialize Ollama provider.

        Args:
            model: Ollama model name for embeddings.
            base_url: Ollama API base URL.
            timeout: Request timeout in seconds.
            max_chars: Maximum characters per text chunk.
            dimensions: Embedding dimensions (auto-detected on first embed if not set).
        """
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_chars = max_chars or DEFAULT_MAX_CHARS
        self._dimensions = dimensions or DEFAULT_DIMENSIONS
        self._client = httpx.Client(timeout=timeout)
        self._available: bool | None = None
        self._resolved_model: str | None = None  # Actual model name from Ollama

    @property
    def name(self) -> str:
        """Provider name."""
        return f"ollama:{self._model}"

    @property
    def dimensions(self) -> int:
        """Embedding dimensions for the configured model."""
        return self._dimensions

    def check_availability(self) -> tuple[bool, str]:
        """Check if Ollama is running and the model is available.

        Returns:
            Tuple of (is_available, reason_if_not).
        """
        try:
            # Check if Ollama is running
            response = self._client.get(f"{self._base_url}/api/tags")
            if response.status_code != 200:
                return False, f"Ollama returned status {response.status_code}"

            # Check if our model is available
            data = response.json()
            available_models = data.get("models", [])
            full_names = [m.get("name", "") for m in available_models]

            # Extract base names without tags and namespaces
            # e.g., "manutic/nomic-embed-code:latest" -> "nomic-embed-code"
            def get_base_name(full_name: str) -> str:
                # Remove tag (e.g., ":latest")
                name_without_tag = full_name.split(":")[0]
                # Remove namespace (e.g., "manutic/")
                if "/" in name_without_tag:
                    return name_without_tag.split("/")[-1]
                return name_without_tag

            base_names = [get_base_name(n) for n in full_names]

            # Try exact match first, then base name match
            model_found = (
                self._model in full_names  # Exact match with full name
                or f"{self._model}:latest" in full_names  # With :latest tag
                or self._model in base_names  # Base name match (handles namespaced models)
            )

            if not model_found:
                # Show available models with their base names for clarity
                display_names = [f"{get_base_name(n)} ({n})" for n in full_names[:5]]
                available_str = ", ".join(display_names) if display_names else "none"
                return (
                    False,
                    f"Model '{self._model}' not found in Ollama (available: {available_str})",
                )

            # Store the actual model name to use (prefer namespaced version if available)
            for full_name in full_names:
                if get_base_name(full_name) == self._model or full_name.startswith(self._model):
                    self._resolved_model = full_name.split(":")[0]  # Without :latest
                    logger.debug(f"Resolved model '{self._model}' to '{self._resolved_model}'")
                    break

            return True, "ok"

        except httpx.ConnectError:
            return False, f"Cannot connect to Ollama at {self._base_url}"
        except httpx.TimeoutException:
            return False, f"Connection to Ollama timed out at {self._base_url}"
        except (httpx.RequestError, Exception) as e:
            return False, f"Error checking Ollama: {e}"

    @property
    def is_available(self) -> bool:
        """Check if Ollama is running and the model is available."""
        if self._available is not None:
            return self._available

        available, _ = self.check_availability()
        self._available = available
        return self._available

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using Ollama.

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResult with embeddings.

        Raises:
            EmbeddingError: If Ollama is unavailable or embedding fails.
        """
        if not self.is_available:
            raise EmbeddingError(
                f"Ollama is not available or model '{self._model}' is not installed",
                provider=self.name,
            )

        # Filter and truncate texts
        truncated_texts = []
        for text in texts:
            # Skip empty or whitespace-only texts (Ollama returns empty embedding)
            if not text or not text.strip():
                logger.debug("Skipping empty text for embedding")
                continue
            if len(text) > self._max_chars:
                logger.debug(f"Truncating text from {len(text)} to {self._max_chars} chars")
                truncated_texts.append(text[: self._max_chars])
            else:
                truncated_texts.append(text)

        # If all texts were empty, return empty result
        if not truncated_texts:
            return EmbeddingResult(
                embeddings=[],
                model=self._resolved_model or self._model,
                dimensions=self.dimensions,
                provider=self.name,
            )

        embeddings = []
        # Use resolved model name if available (handles namespaced models like manutic/nomic-embed-code)
        model_name = self._resolved_model or self._model
        try:
            for text in truncated_texts:
                response = self._client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": model_name, "prompt": text},
                )

                if response.status_code != 200:
                    error_text = response.text
                    # Check for known Ollama model issues
                    if "-Inf" in error_text or "Inf" in error_text:
                        raise EmbeddingError(
                            f"Model '{model_name}' produced invalid values (infinity). "
                            "This model may be unstable for embeddings. "
                            "Try using 'nomic-embed-text' instead.",
                            provider=self.name,
                        )
                    raise EmbeddingError(
                        f"Ollama returned status {response.status_code}: {error_text}",
                        provider=self.name,
                    )

                data = response.json()
                embedding = data.get("embedding")
                if not embedding:
                    raise EmbeddingError(
                        f"No embedding in Ollama response: {data}",
                        provider=self.name,
                    )
                embeddings.append(embedding)

        except httpx.RequestError as e:
            raise EmbeddingError(
                f"Failed to connect to Ollama: {e}",
                provider=self.name,
                cause=e,
            ) from e

        return EmbeddingResult(
            embeddings=embeddings,
            model=self._model,
            provider=self.name,
            dimensions=self._dimensions,
        )

    def ensure_model(self) -> bool:
        """Ensure the model is pulled and available.

        Returns:
            True if model is available, False if pull failed.
        """
        try:
            response = self._client.post(
                f"{self._base_url}/api/pull",
                json={"name": self._model},
                timeout=300.0,  # Model download can take a while
            )
            self._available = response.status_code == 200
            return self._available
        except (httpx.RequestError, httpx.TimeoutException):
            return False

    def __del__(self) -> None:
        """Clean up HTTP client."""
        if hasattr(self, "_client"):
            self._client.close()
