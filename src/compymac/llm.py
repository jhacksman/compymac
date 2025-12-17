"""
LLM Client - Abstraction over LLM backends.

This client works with any OpenAI-compatible API:
- vLLM (http://localhost:8000/v1)
- Ollama (http://localhost:11434/v1)
- Venice.ai
- OpenAI itself

The abstraction is intentionally thin - we're not hiding complexity,
we're just making the backend swappable via configuration.
"""

import json
import logging
from typing import Any

import httpx

from compymac.config import LLMConfig
from compymac.types import ToolCall

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Client for OpenAI-compatible LLM APIs.

    This is a synchronous client for simplicity in the baseline.
    The important thing is that it demonstrates the interface,
    not that it's optimized for production.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        """Initialize the client with configuration."""
        self.config = config or LLMConfig.from_env()
        self._client = httpx.Client(
            base_url=self.config.base_url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> "ChatResponse":
        """
        Send a chat completion request.

        Args:
            messages: The conversation history in OpenAI format
            tools: Optional list of tool definitions
            tool_choice: Optional tool choice constraint

        Returns:
            ChatResponse with the assistant's response
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

        logger.debug(f"Sending chat request with {len(messages)} messages")

        try:
            response = self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return ChatResponse.from_api_response(data)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise LLMError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise LLMError(f"Request failed: {e}") from e

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


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
    ) -> None:
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.raw_response = raw_response

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

        return cls(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            raw_response=data,
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
