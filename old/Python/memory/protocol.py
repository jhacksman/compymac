"""WebSocket protocol extensions for memory operations."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional

class MemoryMessage:
    """Standard message format for memory operations."""
    
    @staticmethod
    def create(
        role: str,
        content: str,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        tags: Optional[list] = None,
        importance: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a standardized memory message.
        
        Args:
            role: Message role (system/user/assistant/agentName)
            content: Message content
            agent_id: Optional agent identifier
            conversation_id: Optional conversation reference
            tags: Optional contextual tags
            importance: Optional importance score
            
        Returns:
            Formatted message dictionary
        """
        return {
            "role": role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": content,
            "metadata": {
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "tags": tags or [],
                "importance": importance
            }
        }
    
    @staticmethod
    def parse(message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate a memory message.
        
        Args:
            message: Raw message dictionary
            
        Returns:
            Validated message dictionary
            
        Raises:
            ValueError: If message format is invalid
        """
        required_fields = {"role", "timestamp", "content", "metadata"}
        if not all(field in message for field in required_fields):
            raise ValueError(
                f"Message missing required fields. Must have: {required_fields}"
            )
            
        metadata = message["metadata"]
        if not isinstance(metadata, dict):
            raise ValueError("Message metadata must be a dictionary")
            
        return {
            "role": message["role"],
            "timestamp": message["timestamp"],
            "content": message["content"],
            "metadata": {
                "agent_id": metadata.get("agent_id"),
                "conversation_id": metadata.get("conversation_id"),
                "tags": metadata.get("tags", []),
                "importance": metadata.get("importance")
            }
        }
