"""Librarian agent for memory management."""
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from .message_types import MemoryMetadata
from .venice_client import VeniceClient
from .exceptions import MemoryError

class LibrarianAgent:
    """Agent responsible for memory storage and retrieval."""
    
    def __init__(
        self,
        venice_client: VeniceClient,
        importance_threshold: float = 0.5,
        max_context_size: int = 10
    ):
        """Initialize librarian agent.
        
        Args:
            venice_client: Venice.ai API client
            importance_threshold: Minimum importance score for memories
            max_context_size: Maximum number of memories to keep in context
        """
        self.venice_client = venice_client
        self.importance_threshold = importance_threshold
        self.max_context_size = max_context_size
        self.recent_memories = []  # Cache of recent memories
        
    async def store_memory(
        self,
        content: str,
        metadata: Optional[MemoryMetadata] = None,
        surprise_score: float = 0.0,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> str:
        """Store memory with surprise-based filtering and retry logic.
        
        Args:
            content: Memory content to store
            metadata: Associated metadata
            surprise_score: Score indicating how surprising/novel the content is
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        
        Returns:
            ID of stored memory
        
        Raises:
            MemoryError: If storage fails after all retries
        """
        try:
            # Create default metadata if none provided
            if metadata is None:
                metadata = MemoryMetadata(
                    timestamp=datetime.now().timestamp(),
                    importance=0.0,
                    context_ids=[],
                    tags=[],
                    source=None,
                    task_id=None
                )
            
            # Sanitize tags to prevent XSS
            if metadata.tags:
                sanitized_tags = []
                for tag in metadata.tags:
                    # Remove potential script tags and other dangerous content
                    sanitized = tag.replace("<", "&lt;").replace(">", "&gt;")
                    sanitized = sanitized.replace("javascript:", "")
                    sanitized = sanitized.replace("data:", "")
                    sanitized_tags.append(sanitized)
                metadata.tags = sanitized_tags
            
            # Validate timestamp
            try:
                if not metadata.timestamp or not isinstance(metadata.timestamp, (int, float)):
                    raise MemoryError("Invalid timestamp format")
            except (AttributeError, TypeError):
                raise MemoryError("Invalid timestamp format")
            
            # Apply surprise-based filtering
            if surprise_score > self.importance_threshold:
                metadata.importance = max(metadata.importance or 0.0, surprise_score)
            
            memory_id = None
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    # Store in Venice.ai with timeout handling
                    response = await self.venice_client.store_memory(content, metadata)
                    
                    # Handle dict response
                    if isinstance(response, dict):
                        if response.get("success") and response.get("memory_id"):
                            memory_id = response["memory_id"]
                            # Cache the memory
                            self.recent_memories.append({
                                "id": memory_id,
                                "content": content,
                                "metadata": metadata.to_dict() if metadata else {}
                            })
                            # Trim cache if needed
                            if len(self.recent_memories) > self.max_context_size:
                                self.recent_memories.pop(0)
                            break
                    else:
                        if response.success and response.memory_id:
                            memory_id = response.memory_id
                            # Cache the memory
                            self.recent_memories.append({
                                "id": memory_id,
                                "content": content,
                                "metadata": metadata.to_dict() if metadata else {}
                            })
                            # Trim cache if needed
                            if len(self.recent_memories) > self.max_context_size:
                                self.recent_memories.pop(0)
                            break
                            
                except (TimeoutError, ConnectionError) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    raise MemoryError(f"Venice.ai API error after {max_retries} retries: {str(e)}")
                except Exception as e:
                    raise MemoryError(f"Venice.ai API error: {str(e)}")
                    
            if not memory_id:
                raise MemoryError("Failed to store memory after retries")
                
            return memory_id
            
        except Exception as e:
            raise MemoryError(f"Memory storage error: {str(e)}")
            
    async def retrieve_memories(
        self,
        query: str,
        context_id: Optional[str] = None,
        time_range: Optional[float] = None,
        limit: Optional[int] = None,
        min_importance: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories based on query and filters.
        
        Args:
            query: Search query
            context_id: Optional context to filter by
            time_range: Optional time range in seconds
            limit: Maximum number of memories to return
            min_importance: Minimum importance score filter
            
        Returns:
            List of matching memories
        """
        try:
            response = await self.venice_client.retrieve_context(
                query,
                context_id=context_id,
                time_range=time_range,
                limit=limit or self.max_context_size
            )
            
            # Handle dict response
            memories = []
            if isinstance(response, dict):
                if response.get("success"):
                    memories = response.get("memories", [])
            else:
                if response.success:
                    memories = response.memories
                    
            # Apply importance filter if specified
            if min_importance is not None:
                memories = [
                    m for m in memories 
                    if m.get("metadata", {}).get("importance", 0) >= min_importance
                ]
                    
            return memories
            
        except Exception as e:
            raise MemoryError(f"Memory retrieval error: {str(e)}")
