"""Configuration for Venice.ai API client."""

import os

"""Configuration for Venice.ai API client.

This module loads configuration from environment variables. All variables are required
and must be set before running the application.

Required environment variables:
    VENICE_API_TOKEN: API token for Venice.ai
    VENICE_BASE_URL: Base URL for Venice.ai API (e.g. https://api.venice.ai)
    VENICE_MODEL: Model name to use (e.g. llama-3.3-70b)
"""

import os

def get_required_env(name: str) -> str:
    """Get a required environment variable."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value

VENICE_API_KEY = get_required_env("VENICE_API_TOKEN")
VENICE_BASE_URL = get_required_env("VENICE_BASE_URL")
VENICE_MODEL = get_required_env("VENICE_MODEL")
