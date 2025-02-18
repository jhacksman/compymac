"""Protocol definitions for agent system."""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

class AgentRole(Enum):
    """Roles in the agent system."""
    MANAGER = "manager"
    EXECUTOR = "executor"
    PLANNER = "planner"
    REFLECTOR = "reflector"

@dataclass
class AgentMessage:
    """Message between agents."""
    sender: AgentRole
    recipient: AgentRole
    content: str
    metadata: Optional[Dict] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.metadata is None:
            self.metadata = {}

@dataclass
class TaskResult:
    """Result of a task execution."""
    success: bool
    message: str
    artifacts: Dict
    error: Optional[str] = None
