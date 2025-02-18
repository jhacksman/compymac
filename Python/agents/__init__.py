"""Agent system for CompyMac."""

from .manager import ManagerAgent as AgentManager
from .executor import ExecutorAgent
from .planner import PlannerAgent
from .reflector import ReflectorAgent

__all__ = [
    'AgentManager',
    'ExecutorAgent',
    'PlannerAgent',
    'ReflectorAgent'
]
