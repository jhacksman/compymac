"""Librarian agent for memory management."""
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from .message_types import MemoryMetadata, MemoryResponse
from .venice_client import VeniceClient
from .exceptions import MemoryError

class LibrarianAgent:
    """Agent responsible for memory storage and retrieval."""
    
    _shared_memories: List[Dict[str, Any]] = []  # Class-level shared memories
    
    def __init__(
        self,
        venice_client: VeniceClient,
        importance_threshold: float = 0.5,
        max_context_size: int = 10,
        max_context_tokens: int = 2000
    ):
        """Initialize librarian agent.
        
        Args:
            venice_client: Venice.ai API client
            importance_threshold: Minimum importance score for memories
            max_context_size: Maximum number of memories to keep in context
            max_context_tokens: Maximum tokens in context window
        """
        self.venice_client = venice_client
        self.importance_threshold = importance_threshold
        self.max_context_size = max_context_size
        self.max_context_tokens = max_context_tokens
        self.recent_memories = []  # Instance-level recent memories
        
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
            
            # Apply surprise-based filtering
            if surprise_score > self.importance_threshold:
                metadata.importance = max(metadata.importance or 0.0, surprise_score)
            
            # Store in Venice.ai with retry logic
            for attempt in range(max_retries):
                try:
                    response = await self.venice_client.store_memory(content, metadata)
                    
                    # Handle dict response
                    if isinstance(response, dict):
                        if response.get("success") and response.get("memory_id"):
                            memory_id = response["memory_id"]
                            # Cache the memory
                            memory_entry = {
                                "id": memory_id,
                                "content": content,
                                "metadata": metadata
                            }
                            self.recent_memories.append(memory_entry)
                            self._shared_memories.append(memory_entry)
                            
                            # Trim caches if needed
                            if len(self.recent_memories) > self.max_context_size:
                                self.recent_memories.pop(0)
                            if len(self._shared_memories) > self.max_context_size * 2:
                                self._shared_memories = self._shared_memories[-self.max_context_size:]
                                
                            return memory_id
                    else:
                        if response.success and response.memory_id:
                            memory_id = response.memory_id
                            # Cache the memory
                            memory_entry = {
                                "id": memory_id,
                                "content": content,
                                "metadata": metadata
                            }
                            self.recent_memories.append(memory_entry)
                            self._shared_memories.append(memory_entry)
                            
                            # Trim caches if needed
                            if len(self.recent_memories) > self.max_context_size:
                                self.recent_memories.pop(0)
                            if len(self._shared_memories) > self.max_context_size * 2:
                                self._shared_memories = self._shared_memories[-self.max_context_size:]
                                
                            return memory_id
                            
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise MemoryError(f"Venice.ai API error after {max_retries} retries: {str(e)}")
                    
            raise MemoryError("Failed to store memory after retries")
            
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
            
    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Union[Dict[str, Any], MemoryMetadata]] = None
    ) -> Dict[str, Any]:
        """Update an existing memory's content or metadata.
        
        Args:
            memory_id: ID of memory to update
            content: Optional new content
            metadata: Optional metadata updates (can be dict or MemoryMetadata)
            
        Returns:
            Updated memory entry
            
        Raises:
            MemoryError: If update fails
        """
        try:
            # Find memory in cache first
            memory = None
            for mem in self._shared_memories:
                if mem["id"] == memory_id:
                    memory = mem
                    break
                    
            if not memory:
                raise MemoryError(f"Memory {memory_id} not found")
                
            # Update content if provided
            if content is not None:
                memory["content"] = content
                
            # Update metadata if provided
            if metadata is not None:
                if isinstance(metadata, MemoryMetadata):
                    memory["metadata"] = metadata
                else:
                    if isinstance(memory["metadata"], MemoryMetadata):
                        memory["metadata"] = memory["metadata"].to_dict()
                    memory["metadata"].update(metadata)
                
            # Update in Venice.ai
            response = await self.venice_client.update_memory(
                memory_id,
                content=content,
                metadata=memory["metadata"]
            )
            
            if isinstance(response, dict):
                if not response.get("success"):
                    raise MemoryError(f"Failed to update memory: {response.get('error')}")
            else:
                if not response.success:
                    raise MemoryError(f"Failed to update memory: {response.error}")
                    
            return memory
            
        except Exception as e:
            raise MemoryError(f"Memory update error: {str(e)}")
