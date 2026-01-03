"""
LLM Client - Abstraction over LLM backends.

This client works with any OpenAI-compatible API:
- vLLM (http://localhost:8000/v1) - DEFAULT, optimized for high-throughput serving
- Venice.ai (https://api.venice.ai/api/v1) - hosted option with function calling
- Ollama (http://localhost:11434/v1) - local development, simpler setup
- OpenAI (https://api.openai.com/v1) - original API

The abstraction is intentionally thin - we're not hiding complexity,
we're just making the backend swappable via configuration.

Includes:
- Fail-fast validation for required config (LLM_MODEL, LLM_BASE_URL)
- Connection refused detection (no 60s retry waits)
- Timeout and retry logic for transient errors
"""

import json
import logging
import time
from typing import Any

import httpx

from compymac.config import LLMConfig
from compymac.types import ToolCall

logger = logging.getLogger(__name__)

# Default timeout configuration (in seconds)
DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 180.0  # LLM responses can take a while
DEFAULT_WRITE_TIMEOUT = 10.0
DEFAULT_POOL_TIMEOUT = 10.0

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 60.0  # Wait 60 seconds before retry (as user requested)


class LLMClient:
    """
    Client for OpenAI-compatible LLM APIs.

    This is a synchronous client for simplicity in the baseline.
    The important thing is that it demonstrates the interface,
    not that it's optimized for production.

    Includes timeout and retry logic for resilience against API hangs.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        validate_config: bool = True,
    ) -> None:
        """Initialize the client with configuration.

        Args:
            config: LLM configuration (model, API key, etc.)
            max_retries: Maximum number of retries for timeout/network errors
            retry_delay: Seconds to wait before retrying after a timeout
            validate_config: If True, validate required config fields on init

        Raises:
            LLMConfigError: If required configuration is missing
        """
        self.config = config or LLMConfig.from_env()
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Fail-fast validation for required configuration
        if validate_config:
            self._validate_config()

        # Use layered timeouts for better control
        timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=DEFAULT_READ_TIMEOUT,
            write=DEFAULT_WRITE_TIMEOUT,
            pool=DEFAULT_POOL_TIMEOUT,
        )

        # Only include Authorization header if api_key is set
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        self._client = httpx.Client(
            base_url=self.config.base_url,
            headers=headers,
            timeout=timeout,
        )

    def _validate_config(self) -> None:
        """Validate required configuration fields.

        Raises:
            LLMConfigError: If required configuration is missing
        """
        errors: list[str] = []

        if not self.config.model:
            errors.append(
                "LLM_MODEL is not set. Set it to the model name your LLM server is serving.\n"
                "  Examples:\n"
                "    - vLLM: LLM_MODEL=meta-llama/Llama-3.1-8B-Instruct\n"
                "    - Venice.ai: LLM_MODEL=qwen3-coder-480b-a35b-instruct\n"
                "    - Ollama: LLM_MODEL=llama3.2"
            )

        if not self.config.base_url:
            errors.append(
                "LLM_BASE_URL is not set. Set it to your LLM server's API endpoint.\n"
                "  Examples:\n"
                "    - vLLM: LLM_BASE_URL=http://localhost:8000/v1\n"
                "    - Venice.ai: LLM_BASE_URL=https://api.venice.ai/api/v1\n"
                "    - Ollama: LLM_BASE_URL=http://localhost:11434/v1"
            )

        if errors:
            raise LLMConfigError(
                "LLM configuration is incomplete:\n\n" + "\n\n".join(errors)
            )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> "ChatResponse":
        """
        Send a chat completion request with automatic retry on timeout.

        Args:
            messages: The conversation history in OpenAI format
            tools: Optional list of tool definitions
            tool_choice: Optional tool choice constraint

        Returns:
            ChatResponse with the assistant's response

        Raises:
            LLMError: If all retries are exhausted or a non-retryable error occurs
        """
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
                logger.info(f"[TOOL_CHOICE] Setting tool_choice={tool_choice} with {len(tools)} tools available")

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{self.max_retries} after {self.retry_delay}s delay...")
                time.sleep(self.retry_delay)

            logger.debug(f"Sending chat request with {len(messages)} messages (attempt {attempt + 1})")
            if tools:
                logger.debug(f"  - Tools: {len(tools)}, tool_choice: {tool_choice}")

            try:
                response = self._client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                chat_response = ChatResponse.from_api_response(data)

                # Log warning if tool_choice was "required" but no tool calls were made
                if tool_choice == "required" and not chat_response.has_tool_calls:
                    logger.warning(f"[TOOL_CHOICE_VIOLATION] Model ignored tool_choice='required' - "
                                 f"returned text-only response: {chat_response.content[:100]}")
                elif tool_choice == "required" and chat_response.has_tool_calls:
                    logger.debug(f"[TOOL_CHOICE_SUCCESS] Model correctly made {len(chat_response.tool_calls)} tool call(s)")

                return chat_response

            except httpx.TimeoutException as e:
                # Timeout errors are retryable
                logger.warning(f"Request timed out (attempt {attempt + 1}): {e}")
                last_error = e
                continue

            except httpx.HTTPStatusError as e:
                # Check if it's a rate limit error (429) - retryable
                if e.response.status_code == 429:
                    # Try to get Retry-After header
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait_time = float(retry_after)
                            logger.warning(f"Rate limited. Waiting {wait_time}s (from Retry-After header)")
                            time.sleep(wait_time)
                        except ValueError:
                            logger.warning(f"Rate limited. Waiting {self.retry_delay}s")
                            time.sleep(self.retry_delay)
                    else:
                        logger.warning(f"Rate limited. Waiting {self.retry_delay}s")
                        time.sleep(self.retry_delay)
                    last_error = e
                    continue

                # 503 Service Unavailable is also retryable
                if e.response.status_code == 503:
                    logger.warning(f"Service unavailable (attempt {attempt + 1}): {e}")
                    last_error = e
                    continue

                # Other HTTP errors are not retryable
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
                raise LLMError(f"HTTP {e.response.status_code}: {e.response.text}") from e

            except httpx.ConnectError as e:
                # Connection refused - fail fast, don't retry
                # This usually means the server isn't running
                error_str = str(e)
                if "Connection refused" in error_str or "ConnectError" in error_str:
                    raise LLMConnectionError(
                        f"Cannot connect to LLM server at {self.config.base_url}\n\n"
                        f"The server appears to be offline or not listening.\n\n"
                        f"Troubleshooting:\n"
                        f"  1. Check if your LLM server is running\n"
                        f"  2. Verify LLM_BASE_URL is correct: {self.config.base_url}\n"
                        f"  3. For vLLM: python -m vllm.entrypoints.openai.api_server --model <model>\n"
                        f"  4. For Ollama: ollama serve\n"
                        f"  5. For Venice.ai: Use LLM_BASE_URL=https://api.venice.ai/api/v1"
                    ) from e
                # Other connect errors might be transient
                logger.warning(f"Connect error (attempt {attempt + 1}): {e}")
                last_error = e
                continue

            except httpx.RequestError as e:
                # Other network errors are retryable
                logger.warning(f"Request error (attempt {attempt + 1}): {e}")
                last_error = e
                continue

        # All retries exhausted
        logger.error(f"All {self.max_retries + 1} attempts failed. Last error: {last_error}")
        raise LLMError(f"Request failed after {self.max_retries + 1} attempts: {last_error}") from last_error

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class TokenUsage:
    """Token usage statistics from an LLM response."""

    def __init__(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_api_response(cls, usage: dict[str, Any] | None) -> "TokenUsage":
        """Parse usage from API response."""
        if not usage:
            return cls()
        return cls(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )


class ChatResponse:
    """
    Response from a chat completion request.

    This wraps the API response and provides convenient access to
    the content and any tool calls.
    """

    def __init__(
        self,
        content: str | None,
        tool_calls: list[ToolCall] | None,
        finish_reason: str,
        raw_response: dict[str, Any],
        usage: TokenUsage | None = None,
    ) -> None:
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.raw_response = raw_response
        self.usage = usage or TokenUsage()

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "ChatResponse":
        """Parse an API response into a ChatResponse."""
        choice = data["choices"][0]
        message = choice["message"]

        content = message.get("content")
        finish_reason = choice.get("finish_reason", "stop")

        tool_calls: list[ToolCall] = []
        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {"raw": tc["function"]["arguments"]}

                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=arguments,
                ))

        # Parse token usage from API response
        usage = TokenUsage.from_api_response(data.get("usage"))

        return cls(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            raw_response=data,
            usage=usage,
        )

    @property
    def has_tool_calls(self) -> bool:
        """Check if the response includes tool calls."""
        return len(self.tool_calls) > 0

    @property
    def is_complete(self) -> bool:
        """Check if this is a complete response (no tool calls pending)."""
        return not self.has_tool_calls and self.finish_reason == "stop"


class LLMError(Exception):
    """Error from the LLM client."""
    pass


class LLMConfigError(LLMError):
    """Error from missing or invalid LLM configuration."""
    pass


class LLMConnectionError(LLMError):
    """Error connecting to the LLM server (e.g., connection refused)."""
    pass
