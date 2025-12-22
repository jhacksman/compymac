"""
Configuration for the agent system.

All configuration is loaded from environment variables. This keeps the
system flexible across different LLM backends (vLLM, Ollama, Venice)
without hardcoding any specific values.

The token budget is configurable but MUST be enforced - this is a
fundamental constraint, not a suggestion.
"""

import os
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for the LLM client."""
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables."""
        return cls(
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:8000/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", ""),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        )


@dataclass
class ContextConfig:
    """
    Configuration for context management.

    The token_budget is the hard limit on context size. When exceeded,
    the oldest messages are dropped (naive truncation). This is a
    fundamental constraint of LLM-based systems.

    Note: We approximate tokens as chars/4 for simplicity. A real
    implementation would use a proper tokenizer, but the important
    thing is that the budget is ENFORCED.
    """
    token_budget: int = 128000
    chars_per_token: float = 4.0
    reserved_for_response: int = 4096

    @classmethod
    def from_env(cls) -> "ContextConfig":
        """Load configuration from environment variables."""
        return cls(
            token_budget=int(os.getenv("CONTEXT_TOKEN_BUDGET", "128000")),
            chars_per_token=float(os.getenv("CONTEXT_CHARS_PER_TOKEN", "4.0")),
            reserved_for_response=int(os.getenv("CONTEXT_RESERVED_FOR_RESPONSE", "4096")),
        )

    @property
    def available_budget(self) -> int:
        """Tokens available for context (excluding response reservation)."""
        return self.token_budget - self.reserved_for_response


@dataclass
class LoopConfig:
    """
    Configuration for the agent loop.

    max_steps is a safety limit to prevent runaway loops. This is an
    operational constraint that exists in real agent systems.
    """
    max_steps: int = 20

    @classmethod
    def from_env(cls) -> "LoopConfig":
        """Load configuration from environment variables."""
        return cls(
            max_steps=int(os.getenv("AGENT_MAX_STEPS", "20")),
        )


@dataclass
class AgentConfig:
    """Combined configuration for the entire agent system."""
    llm: LLMConfig
    context: ContextConfig
    loop: LoopConfig

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load all configuration from environment variables."""
        return cls(
            llm=LLMConfig.from_env(),
            context=ContextConfig.from_env(),
            loop=LoopConfig.from_env(),
        )
