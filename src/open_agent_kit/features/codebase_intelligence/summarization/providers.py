"""LLM-based session summarization providers.

Uses OpenAI-compatible API for all providers (Ollama, LM Studio, vLLM, OpenAI, etc.).
Any server that implements the OpenAI chat completions API will work.
"""

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_SUMMARIZATION_BASE_URL,
    DEFAULT_SUMMARIZATION_TIMEOUT,
    SUMMARIZATION_PROVIDER_OLLAMA,
    WARMUP_TIMEOUT_MULTIPLIER,
)
from open_agent_kit.features.codebase_intelligence.summarization.base import (
    BaseSummarizer,
    SummarizationResult,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.config import SummarizationConfig

logger = logging.getLogger(__name__)


SUMMARIZATION_PROMPT = """You are analyzing a coding session to extract important observations that should be remembered for future sessions.

Session Activity:
- Duration: {duration:.1f} minutes
- Files created: {files_created}
- Files modified: {files_modified}
- Files explored: {files_read}
- Commands run: {commands}

Extract meaningful observations from this session. Focus on:
1. **Gotchas**: Non-obvious behaviors, edge cases, or things that could trip someone up
2. **Decisions**: Design choices, architecture decisions, or approach selections
3. **Bug fixes**: What was broken and how it was fixed
4. **Discoveries**: Important facts learned about the codebase

Respond with a JSON object containing:
{{
  "observations": [
    {{
      "type": "gotcha|decision|bug_fix|discovery",
      "observation": "concise description of what was learned",
      "context": "relevant file or feature name"
    }}
  ],
  "summary": "one sentence describing what the session accomplished"
}}

Only include genuinely useful observations that would help in future sessions. If the session was just exploration without meaningful learnings, return empty observations.

Respond ONLY with valid JSON, no markdown or explanation."""


@dataclass
class ModelInfo:
    """Information about an available model."""

    id: str
    name: str
    context_window: int | None = None
    owned_by: str | None = None


class OpenAICompatSummarizer(BaseSummarizer):
    """Summarizer using OpenAI-compatible API.

    Works with:
    - Ollama (via /v1/* endpoints)
    - LM Studio
    - vLLM
    - OpenAI
    - Any OpenAI-compatible server
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "",
        api_key: str | None = None,
        timeout: float = DEFAULT_SUMMARIZATION_TIMEOUT,
    ):
        """Initialize the OpenAI-compatible summarizer.

        Args:
            base_url: API base URL (e.g., http://localhost:11434/v1 for Ollama).
            model: Model name/identifier (must be configured).
            api_key: API key (optional for local servers).
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        # Use timeout for regular client, warmup timeout for first LLM call
        self._client = httpx.Client(timeout=timeout)
        self._available: bool | None = None
        self._resolved_model: str | None = None
        self._context_window: int | None = None
        # Track warmup state - first LLM call may need model loading
        self._warmed_up: bool = False
        self._warmup_timeout = timeout * WARMUP_TIMEOUT_MULTIPLIER

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with optional auth."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def list_models(self) -> list[ModelInfo]:
        """List available models from the provider.

        Returns:
            List of ModelInfo with available models.
        """
        try:
            response = self._client.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
            )
            if response.status_code != 200:
                logger.debug(f"Failed to list models: {response.status_code}")
                return []

            data = response.json()
            models = []

            # Common embedding model patterns to filter out
            embedding_patterns = [
                "embed",
                "embedding",  # Generic
                "bge-",
                "gte-",
                "e5-",  # Popular embedding model families
                "nomic-embed",
                "arctic-embed",
                "mxbai-embed",  # Specific models
            ]
            for m in data.get("data", []):
                model_id = m.get("id", "")
                # Skip embedding models (they can't do chat completions)
                if any(x in model_id.lower() for x in embedding_patterns):
                    continue

                models.append(
                    ModelInfo(
                        id=model_id,
                        name=model_id.split("/")[-1].split(":")[0],  # Clean name
                        context_window=m.get("context_window") or m.get("context_length"),
                        owned_by=m.get("owned_by"),
                    )
                )

            return models

        except (httpx.HTTPError, ValueError, KeyError) as e:
            logger.debug(f"Error listing models: {e}")
            return []

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a specific model.

        Args:
            model_id: Model identifier.

        Returns:
            ModelInfo if found, None otherwise.
        """
        try:
            response = self._client.get(
                f"{self.base_url}/models/{model_id}",
                headers=self._get_headers(),
            )
            if response.status_code != 200:
                return None

            m = response.json()
            return ModelInfo(
                id=m.get("id", model_id),
                name=m.get("id", model_id).split("/")[-1].split(":")[0],
                context_window=m.get("context_window") or m.get("context_length"),
                owned_by=m.get("owned_by"),
            )

        except (httpx.HTTPError, ValueError, KeyError):
            return None

    def _find_model(self) -> str | None:
        """Find the configured model or a matching one.

        Returns:
            Resolved model ID or None if not found.
        """
        models = self.list_models()
        if not models:
            return None

        # Exact match
        for m in models:
            if m.id == self.model:
                self._context_window = m.context_window
                return m.id

        # Base name match (handles namespaced models)
        model_base = self.model.split("/")[-1].split(":")[0].lower()
        for m in models:
            if m.name.lower() == model_base:
                self._context_window = m.context_window
                return m.id

        # Partial match
        for m in models:
            if model_base in m.id.lower():
                self._context_window = m.context_window
                return m.id

        return None

    def is_available(self) -> bool:
        """Check if the API is available and the model exists."""
        if self._available is not None:
            return self._available

        try:
            self._resolved_model = self._find_model()
            self._available = self._resolved_model is not None

            if self._available:
                logger.debug(
                    f"Resolved model '{self.model}' to '{self._resolved_model}' "
                    f"(context: {self._context_window})"
                )
            else:
                models = self.list_models()
                available = [m.id for m in models[:5]]
                logger.debug(f"Model '{self.model}' not found. Available: {available}")

            return self._available

        except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
            logger.debug(f"API not available: {e}")
            self._available = False
            return False

    def post_chat_completion(
        self,
        json_data: dict,
    ) -> httpx.Response:
        """Make a POST request to chat completions with warmup handling.

        This is the public interface for making LLM requests with warmup-aware
        timeout handling. Use this instead of accessing _client directly.

        Args:
            json_data: JSON body for the chat completions request.

        Returns:
            httpx.Response from the request.

        Raises:
            httpx.TimeoutException: If request times out even with extended warmup timeout.
        """
        return self._post_with_warmup(
            f"{self.base_url}/chat/completions",
            json_data=json_data,
            headers=self._get_headers(),
        )

    def _post_with_warmup(
        self,
        url: str,
        json_data: dict,
        headers: dict[str, str],
    ) -> httpx.Response:
        """Make a POST request with warmup timeout handling.

        On first LLM request, uses extended timeout to account for model loading.
        After first successful request, uses normal timeout.

        Args:
            url: Request URL.
            json_data: JSON body.
            headers: Request headers.

        Returns:
            httpx.Response from the request.

        Raises:
            httpx.TimeoutException: If request times out even with warmup retry.
        """
        # Use warmup timeout if model hasn't been loaded yet
        current_timeout = self.timeout if self._warmed_up else self._warmup_timeout

        try:
            if not self._warmed_up:
                logger.debug(
                    f"First LLM request - using warmup timeout ({current_timeout:.0f}s) "
                    "to allow for model loading"
                )

            response = self._client.post(
                url,
                headers=headers,
                json=json_data,
                timeout=current_timeout,
            )

            # Mark as warmed up after any successful request to chat endpoint
            if "/chat/completions" in url and response.status_code == 200:
                if not self._warmed_up:
                    logger.debug(
                        "Model warmup complete - subsequent requests will use normal timeout"
                    )
                    self._warmed_up = True

            return response

        except httpx.TimeoutException:
            if not self._warmed_up:
                logger.warning(
                    f"LLM request timed out after {current_timeout:.0f}s during warmup. "
                    "Local models may need more time to load. "
                    "Consider increasing summarization.timeout in config if this persists."
                )
            raise

    def summarize_session(
        self,
        files_created: list[str],
        files_modified: list[str],
        files_read: list[str],
        commands_run: list[str],
        duration_minutes: float,
    ) -> SummarizationResult:
        """Summarize session using the LLM.

        Args:
            files_created: List of created files.
            files_modified: List of modified files.
            files_read: List of read files.
            commands_run: List of commands run.
            duration_minutes: Session duration.

        Returns:
            SummarizationResult with extracted observations.
        """
        # Skip if nothing meaningful happened
        if not files_created and not files_modified and len(commands_run) < 2:
            return SummarizationResult(
                observations=[],
                session_summary="Brief exploration session",
                success=True,
            )

        # Build the prompt
        prompt = SUMMARIZATION_PROMPT.format(
            duration=duration_minutes,
            files_created=", ".join(files_created[:10]) or "none",
            files_modified=", ".join(files_modified[:10]) or "none",
            files_read=", ".join(files_read[:10]) or "none",
            commands=", ".join(commands_run[:10]) or "none",
        )

        model_to_use = self._resolved_model or self.model

        try:
            response = self._post_with_warmup(
                f"{self.base_url}/chat/completions",
                json_data={
                    "model": model_to_use,
                    "messages": [
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
                headers=self._get_headers(),
            )

            if response.status_code != 200:
                logger.warning(f"API request failed: {response.status_code}")
                logger.debug(f"Response body: {response.text[:500]}")
                return SummarizationResult(
                    success=False,
                    error=f"API returned {response.status_code}",
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                logger.debug(f"API returned no choices. Full response: {data}")
                return SummarizationResult(
                    observations=[],
                    session_summary="",
                    success=True,
                )

            raw_response = choices[0].get("message", {}).get("content", "")

            # Strip reasoning/chain-of-thought tokens from reasoning models
            from open_agent_kit.features.codebase_intelligence.activity.processor.llm import (
                strip_reasoning_tokens,
            )

            raw_response = strip_reasoning_tokens(raw_response)
            return _parse_llm_response(raw_response)

        except httpx.TimeoutException:
            logger.warning("Summarization timed out")
            return SummarizationResult(
                success=False,
                error="Summarization timed out",
            )
        except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
            logger.warning(f"Summarization failed: {e}")
            return SummarizationResult(
                success=False,
                error=str(e),
            )

    def __del__(self) -> None:
        """Clean up HTTP client."""
        if hasattr(self, "_client"):
            self._client.close()


# Aliases for backwards compatibility
OllamaSummarizer = OpenAICompatSummarizer
OpenAISummarizer = OpenAICompatSummarizer


def _parse_llm_response(raw_response: str) -> SummarizationResult:
    """Parse LLM response into SummarizationResult.

    Args:
        raw_response: Raw text from LLM.

    Returns:
        Parsed SummarizationResult.
    """
    import re

    # Log raw response for debugging
    if not raw_response or not raw_response.strip():
        logger.debug("LLM returned empty response")
        return SummarizationResult(
            observations=[],
            session_summary="",
            success=True,
        )

    logger.debug(f"LLM raw response ({len(raw_response)} chars): {raw_response[:500]}")

    # Try multiple extraction strategies
    json_str = None

    # Strategy 1: Extract JSON from markdown code block (```json ... ``` or ``` ... ```)
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_response, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()
        logger.debug("Extracted JSON from markdown code block")

    # Strategy 2: Find JSON object directly (look for { ... } pattern)
    if not json_str:
        json_match = re.search(r"\{[\s\S]*\}", raw_response)
        if json_match:
            json_str = json_match.group(0)
            logger.debug("Extracted JSON object from response")

    # Strategy 3: Try the whole response stripped
    if not json_str:
        json_str = raw_response.strip()

    if not json_str:
        logger.debug("No JSON content found in LLM response")
        return SummarizationResult(
            observations=[],
            session_summary=raw_response[:200] if raw_response else "",
            success=True,
        )

    try:
        data = json.loads(json_str)

        observations = []
        for obs in data.get("observations", []):
            if isinstance(obs, dict) and obs.get("observation"):
                observations.append(
                    {
                        "type": obs.get("type", "discovery"),
                        "observation": obs.get("observation", ""),
                        "context": obs.get("context", ""),
                    }
                )

        # Normalize summary to string — some models return a list of strings
        raw_summary = data.get("summary", "")
        if isinstance(raw_summary, list):
            raw_summary = " ".join(str(item) for item in raw_summary if item)
        session_summary = str(raw_summary).strip()

        return SummarizationResult(
            observations=observations,
            session_summary=session_summary,
            success=True,
        )

    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse JSON: {e}")
        logger.debug(f"Attempted to parse: {json_str[:300]}")
        return SummarizationResult(
            observations=[],
            session_summary=raw_response[:200] if raw_response else "",
            success=True,
        )


def ensure_v1_url(base_url: str) -> str:
    """Ensure base URL has /v1 suffix for OpenAI-compatible API.

    Args:
        base_url: Provider base URL (e.g., http://localhost:11434).

    Returns:
        URL with /v1 suffix (e.g., http://localhost:11434/v1).
    """
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        return f"{base}/v1"
    return base


# Backwards compatibility alias
get_ollama_v1_url = ensure_v1_url


def list_available_models(
    base_url: str = DEFAULT_SUMMARIZATION_BASE_URL,
    api_key: str | None = None,
    provider: str = SUMMARIZATION_PROVIDER_OLLAMA,
) -> list[ModelInfo]:
    """List available models from a provider.

    Args:
        base_url: Provider base URL.
        api_key: Optional API key.
        provider: Provider type (ollama or openai).

    Returns:
        List of available ModelInfo.
    """
    # Ensure URL has /v1 for OpenAI-compatible API
    v1_url = ensure_v1_url(base_url)

    summarizer = OpenAICompatSummarizer(
        base_url=v1_url,
        model="dummy",  # Just for listing
        api_key=api_key,
    )
    return summarizer.list_models()


def discover_model_context(
    model: str,
    base_url: str = DEFAULT_SUMMARIZATION_BASE_URL,
    provider: str = SUMMARIZATION_PROVIDER_OLLAMA,
    api_key: str | None = None,
) -> int | None:
    """Discover the context window size for a model.

    Works with any OpenAI-compatible local provider (Ollama, LM Studio, vLLM, etc.).
    Tries multiple discovery methods in order of reliability.

    Args:
        model: Model name/identifier.
        base_url: Provider base URL.
        provider: Provider type (used for logging, discovery tries all methods).
        api_key: Optional API key.

    Returns:
        Context window size in tokens, or None if unable to discover.
    """
    import re

    import httpx

    base = base_url.rstrip("/")
    v1_base = ensure_v1_url(base_url)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with httpx.Client(timeout=10.0) as client:
        # Method 1: Try OpenAI-compatible /v1/models endpoint
        # Works for LM Studio, vLLM, and other OpenAI-compatible servers
        try:
            response = client.get(f"{v1_base}/models", headers=headers)
            if response.status_code == 200:
                data = response.json()
                models_list = data.get("data", [])
                for m in models_list:
                    model_id = m.get("id", "")
                    # Match by exact ID or by model name being contained in ID
                    if model_id == model or model in model_id or model_id in model:
                        ctx = (
                            m.get("context_window")
                            or m.get("context_length")
                            or m.get("max_tokens")
                        )
                        if ctx and isinstance(ctx, int):
                            logger.debug(f"Found context for {model}: {ctx} (from /v1/models)")
                            return int(ctx)
        except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
            logger.debug(f"OpenAI /v1/models failed: {e}")

        # Method 2: Try OpenAI-compatible /v1/models/{model} endpoint
        try:
            response = client.get(f"{v1_base}/models/{model}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                ctx = (
                    data.get("context_window")
                    or data.get("context_length")
                    or data.get("max_tokens")
                )
                if ctx and isinstance(ctx, int):
                    logger.debug(f"Found context for {model}: {ctx} (from /v1/models/{model})")
                    return int(ctx)
        except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
            logger.debug(f"OpenAI /v1/models/{model} failed: {e}")

        # Method 3: Try Ollama's native /api/show endpoint (fallback for Ollama)
        # Remove /v1 suffix if present to get native endpoint
        native_base = base[:-3] if base.endswith("/v1") else base
        try:
            response = client.post(
                f"{native_base}/api/show",
                json={"name": model},
            )
            if response.status_code == 200:
                data = response.json()

                # Check model_info for context keys
                model_info = data.get("model_info", {})
                for key in model_info:
                    if "context" in key.lower():
                        value = model_info[key]
                        if isinstance(value, int):
                            logger.debug(
                                f"Found context for {model}: {value} (from /api/show {key})"
                            )
                            return value

                # Check parameters block for num_ctx
                params = data.get("parameters", "")
                if params and "num_ctx" in params:
                    match = re.search(r"num_ctx\s+(\d+)", params)
                    if match:
                        ctx = int(match.group(1))
                        logger.debug(
                            f"Found context for {model}: {ctx} (from /api/show parameters)"
                        )
                        return ctx
        except (httpx.HTTPError, ValueError, KeyError, OSError) as e:
            logger.debug(f"Ollama /api/show failed: {e}")

    logger.debug(f"Could not discover context window for {model}")
    return None


def create_summarizer_from_config(
    config: "SummarizationConfig",
) -> BaseSummarizer | None:
    """Create a summarizer from SummarizationConfig.

    Args:
        config: Summarization configuration.

    Returns:
        Configured summarizer or None if not available or disabled.
    """
    if not config.enabled:
        logger.info("LLM summarization is disabled in config")
        return None

    return create_summarizer(
        provider=config.provider,
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout=config.timeout,
    )


def create_summarizer(
    provider: str = SUMMARIZATION_PROVIDER_OLLAMA,
    base_url: str = DEFAULT_SUMMARIZATION_BASE_URL,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = DEFAULT_SUMMARIZATION_TIMEOUT,
) -> BaseSummarizer | None:
    """Create a summarizer based on configuration.

    All providers use OpenAI-compatible API. The base URL is automatically
    converted to use the /v1 endpoint if needed.

    Args:
        provider: Summarization provider (ollama, openai, lmstudio, etc.).
        base_url: Provider base URL.
        model: Model name (required - must be configured by user).
        api_key: API key for authenticated providers.
        timeout: Request timeout in seconds.

    Returns:
        Configured summarizer or None if not available or not configured.
    """
    # Model must be configured
    if not model:
        logger.debug("Summarization model not configured - skipping summarizer creation")
        return None

    # Ensure URL has /v1 for OpenAI-compatible API
    v1_url = ensure_v1_url(base_url)

    summarizer = OpenAICompatSummarizer(
        base_url=v1_url,
        model=model,
        api_key=api_key,
        timeout=timeout,
    )

    if summarizer.is_available():
        logger.info(f"Using {provider} summarizer with model {summarizer._resolved_model or model}")
        return summarizer

    # Show available models for debugging
    models = summarizer.list_models()
    if models:
        model_names = [m.id for m in models[:5]]
        logger.info(f"Model '{model}' not available. Available models: {model_names}")
    else:
        logger.info(
            f"Summarizer not available at {base_url}. "
            "Session summaries will use pattern-based extraction."
        )

    return None
