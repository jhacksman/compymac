"""
Memory system for compymac.

This module implements a three-component memory system:
1. Core Module: Immediate context processing
2. Long-term Memory: Historical context
3. Persistent Memory: Task-specific knowledge

The implementation follows the Titans architecture for memory management
and integrates with the venice.ai API for LLM operations.
"""

from .venice_api import VeniceAPI
from .manager import MemoryManager

__all__ = ['VeniceAPI', 'MemoryManager']
