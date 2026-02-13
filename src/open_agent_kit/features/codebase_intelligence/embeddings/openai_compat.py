"""OpenAI-compatible embedding provider.

Works with any OpenAI API-compatible endpoint including:
- LMStudio
- vLLM
- text-generation-webui
- LocalAI
- Ollama (with /v1 endpoint)
"""

import logging
import os

import httpx

from open_agent_kit.features.codebase_intelligence.embeddings.base import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResult,
)

logger = logging.getLogger(__name__)

# Character limit for embeddings (conservative estimate)
MAX_CHARS_PER_TEXT = 6000


class OpenAICompatProvider(EmbeddingProvider):
    """Embedding provider for OpenAI-compatible APIs.

    Works with any service that implements the OpenAI embeddings API,
    including local servers like LMStudio, vLLM, and LocalAI.

    Attributes:
        model: The model name to use for embeddings.
        base_url: The API base URL (e.g., http://localhost:1234/v1).
        api_key: Optional API key for authentication.
    """

    def __init__(
        self,
        model: str = "nomic-embed-code",
        base_url: str = "http://localhost:1234/v1",
        api_key: str | None = None,
        dimensions: int | None = None,
        timeout: float = 30.0,
    ):
        """Initialize OpenAI-compatible provider.

        Args:
            model: Model name for embeddings.
            base_url: API base URL (should end with /v1 for OpenAI compat).
            api_key: Optional API key (reads from OPENAI_API_KEY env if not set).
            dimensions: Embedding dimensions (auto-detected if not specified).
            timeout: Request timeout in seconds.
        """
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        self._available: bool | None = None

        # Determine dimensions from shared metadata registry
        if dimensions:
            self._dimensions = dimensions
        else:
            from open_agent_kit.features.codebase_intelligence.embeddings.metadata import (
                get_known_model_metadata,
            )

            known = get_known_model_metadata(model)
            if known["dimensions"] is not None:
                self._dimensions = known["dimensions"]
            else:
                # Unknown model: default to 768, will be updated on first embed
                self._dimensions = 768
                self._dimensions_detected = False

    @property
    def name(self) -> str:
        """Provider name."""
        return f"openai:{self._model}"

    @property
    def dimensions(self) -> int:
        """Embedding dimensions for the configured model."""
        return self._dimensions

    @property
    def is_available(self) -> bool:
        """Check if the API endpoint is available."""
        if self._available is not None:
            return self._available

        try:
            # Try to hit the models endpoint
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            response = self._client.get(
                f"{self._base_url}/v1/models",
                headers=headers,
            )
            self._available = response.status_code == 200
            return self._available

        except (httpx.RequestError, httpx.TimeoutException):
            self._available = False
            return False

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using OpenAI-compatible API.

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
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

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
                raise EmbeddingError(
                    f"API returned status {response.status_code}: {response.text}",
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

            # Update dimensions if we detected them
            if len(embeddings) > 0 and len(embeddings[0]) != self._dimensions:
                self._dimensions = len(embeddings[0])
                logger.info(f"Detected embedding dimensions: {self._dimensions}")

            return EmbeddingResult(
                embeddings=embeddings,
                model=self._model,
                provider=self.name,
                dimensions=self._dimensions,
            )

        except httpx.RequestError as e:
            raise EmbeddingError(
                f"Failed to connect to API: {e}",
                provider=self.name,
                cause=e,
            ) from e

    def __del__(self) -> None:
        """Clean up HTTP client."""
        if hasattr(self, "_client"):
            self._client.close()
