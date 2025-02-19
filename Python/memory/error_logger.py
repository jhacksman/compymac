"""Error logging system for CompyMac."""

from typing import Dict, Any, Optional
from datetime import datetime

from .message_types import MemoryMetadata
from .manager import MemoryManager

class ErrorLogger:
    """Handles error logging through memory system."""
    
    def __init__(self, memory_manager: MemoryManager):
        """Initialize error logger.
        
        Args:
            memory_manager: Memory manager instance for storing errors
        """
        self.memory_manager = memory_manager
        
    async def log_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        severity: str = "error",
        agent: Optional[str] = None
    ) -> None:
        """Log error to memory system.
        
        Args:
            error: Exception that occurred
            context: Context about the error
            severity: Error severity level
            agent: Optional agent name that encountered error
        """
        metadata = {
            "type": "error_log",
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        
        if agent:
            metadata["agent"] = agent
            
        await self.memory_manager.store_memory(
            content=str(error),
            metadata=MemoryMetadata(**{
                **metadata,
                "context": context
            })
        )
