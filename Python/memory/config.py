"""Configuration for Venice.ai API client.

This module loads configuration from environment variables with fallback defaults for testing.

Environment variables:
    VENICE_API_TOKEN: API token for Venice.ai
    VENICE_BASE_URL: Base URL for Venice.ai API (e.g. https://api.venice.ai)
    VENICE_MODEL: Model name to use (e.g. llama-3.3-70b)
"""

import os

def get_env_with_default(name: str, default: str) -> str:
    """Get an environment variable with a default value."""
    return os.getenv(name, default)

# Use defaults for testing, but prefer environment variables if set
VENICE_API_KEY = get_env_with_default("VENICE_API_TOKEN", "test-token")
VENICE_BASE_URL = get_env_with_default("VENICE_BASE_URL", "https://api.venice.ai")
VENICE_MODEL = get_env_with_default("VENICE_MODEL", "llama-3.3-70b")
