"""Configuration for agent system."""

from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class AgentConfig:
    """Configuration for agent system."""
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds
    max_retry_delay: float = 30.0  # seconds
    planning_timeout: float = 60.0  # seconds
    execution_timeout: float = 300.0  # seconds
    reflection_interval: float = 10.0  # seconds
