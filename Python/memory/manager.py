"""Memory manager for compymac."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from .venice_api import VeniceAPI
from .exceptions import ContextWindowExceededError

class MemoryManager:
    """Manages the three-component memory system."""
    
    def __init__(self, venice_api: VeniceAPI, max_tokens: int = 30000):
        """Initialize memory manager.
        
        Args:
            venice_api: Venice.ai API client
            max_tokens: Maximum number of tokens in context window (default: 30k)
        """
        self.venice_api = venice_api
        self.max_tokens = max_tokens
        self.context_window: List[Dict[str, Any]] = []
    
    def store_memory(
        self,
        content: str,
        metadata: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store a new memory.
        
        Args:
            content: Raw memory content
            metadata: Additional memory metadata
            task_id: Optional task-specific context ID
            
        Returns:
            Stored memory record
            
        Raises:
            ContextWindowExceededError: If context window limit is exceeded
            VeniceAPIError: If API request fails
        """
        if task_id:
            metadata["task_id"] = task_id
            
        memory = self.venice_api.store_memory(content, metadata)
        self.context_window.append(memory)
        
        # Prune context window if needed
        while len(self.context_window) > 0 and self._estimate_tokens() > self.max_tokens:
            self.context_window.pop(0)  # Remove oldest memory
            
        return memory
    
    def retrieve_context(
        self,
        query: str,
        task_id: Optional[str] = None,
        time_range: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve context using hybrid query approach.
        
        Args:
            query: Search query for semantic similarity
            task_id: Optional task-specific context ID
            time_range: Optional time range filter (e.g., "1d", "7d")
            
        Returns:
            List of relevant memory records
            
        Raises:
            VeniceAPIError: If API request fails
        """
        filters = {}
        if task_id:
            filters["task_id"] = task_id
        if time_range:
            filters["time_range"] = time_range
            
        return self.venice_api.retrieve_context(query, filters)
    
    def update_memory(
        self,
        memory_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing memory record.
        
        Args:
            memory_id: ID of the memory to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated memory record
            
        Raises:
            VeniceAPIError: If API request fails
        """
        memory = self.venice_api.update_memory(memory_id, updates)
        
        # Update context window if memory exists there
        for i, ctx_memory in enumerate(self.context_window):
            if ctx_memory["id"] == memory_id:
                self.context_window[i] = memory
                break
                
        return memory
    
    def delete_memory(self, memory_id: str) -> None:
        """Delete a memory record.
        
        Args:
            memory_id: ID of the memory to delete
            
        Raises:
            VeniceAPIError: If API request fails
        """
        self.venice_api.delete_memory(memory_id)
        
        # Remove from context window if exists
        self.context_window = [
            m for m in self.context_window
            if m["id"] != memory_id
        ]
    
    def _estimate_tokens(self) -> int:
        """Estimate total tokens in context window.
        
        This is a simple estimation based on character count.
        A more accurate implementation would use a proper tokenizer.
        
        Returns:
            Estimated token count
        """
        total_chars = sum(
            len(str(memory.get("content", "")))
            for memory in self.context_window
        )
        # Rough estimation: 1 token ≈ 4 characters
        return total_chars // 4
