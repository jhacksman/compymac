"""Librarian agent for memory orchestration.

This module implements a service layer for managing memory operations,
retrieval, and organization using Venice.ai API.
"""

import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .message_types import MemoryMetadata, MemoryResponse
from .venice_client import VeniceClient
from .exceptions import MemoryError


class LibrarianAgent:
    """Service layer for memory orchestration."""
    
    # Class-level shared memory store
    _shared_memories: List[Dict] = []
    
    def __init__(self, venice_client: VeniceClient):
        """Initialize librarian agent.
        
        Args:
            venice_client: Client for Venice.ai API
        """
        self.venice_client = venice_client
        self.recent_memories: List[Dict] = []
        self.importance_threshold = 0.5
        self.max_context_tokens = 4096  # Venice.ai default
        
    async def store_memory(
        self,
        content: str,
        metadata: MemoryMetadata,
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
            # Validate and sanitize metadata
            if not metadata:
                raise MemoryError("Missing metadata")
                
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
                
            last_error = None
            for attempt in range(max_retries):
                try:
                    # Store in Venice.ai with timeout handling
                    response = await self.venice_client.store_memory(content, metadata)
                    if response.success and response.memory_id:
                        memory_id = response.memory_id
                        break
                except asyncio.TimeoutError:
                    last_error = MemoryError("Venice.ai API timeout: Failed to store memory")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    raise last_error
                except ConnectionError as e:
                    last_error = MemoryError(f"Venice.ai connection error: {str(e)}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise last_error
                except Exception as e:
                    last_error = MemoryError(f"Venice.ai API error: {str(e)}")
                    raise last_error
                
            if not response.success:
                raise MemoryError(f"Failed to store memory: {response.error}")
                
            if not memory_id:
                raise MemoryError("No memory ID returned from Venice.ai")
                
            # Create memory entry
            memory_entry = {
                "id": memory_id,
                "content": content,
                "metadata": metadata,
                "timestamp": datetime.now().timestamp()
            }
            
            # Add to recent and shared memories
            self.recent_memories.append(memory_entry)
            LibrarianAgent._shared_memories.append(memory_entry)
            
            # Maintain context window sizes
            while len(self.recent_memories) > self.max_context_tokens // 4:
                self.recent_memories.pop(0)
            while len(LibrarianAgent._shared_memories) > self.max_context_tokens:
                LibrarianAgent._shared_memories.pop(0)
                
            return memory_id
            
        except Exception as e:
            raise MemoryError(f"Failed to store memory: {str(e)}")
            
    async def retrieve_memories(
        self,
        query: str,
        context_id: Optional[str] = None,
        time_range: Optional[timedelta] = None,
        limit: Optional[int] = None,
        min_importance: Optional[float] = None
    ) -> List[Dict]:
        """Retrieve memories with hybrid ranking.
        
        Args:
            query: Search query
            context_id: Optional context ID filter
            time_range: Optional time range filter
            limit: Maximum number of memories to return
            min_importance: Minimum importance score filter
            
        Returns:
            List of relevant memories
            
        Raises:
            MemoryError: If retrieval fails
        """
        try:
            try:
                # Get memories from Venice.ai with timeout handling
                response = await self.venice_client.retrieve_context(
                    query=query,
                    context_id=context_id,
                    time_range=time_range.total_seconds() if time_range else None,
                    limit=None  # Get all memories first, then filter
                )
            except asyncio.TimeoutError:
                raise MemoryError("Venice.ai API timeout: Failed to retrieve memories")
            except Exception as e:
                raise MemoryError(f"Venice.ai API error: {str(e)}")
                
            if not response.success:
                # Handle index corruption by falling back to recent memories
                if "corruption" in str(response.error).lower():
                    memories = self.recent_memories.copy()
                else:
                    raise MemoryError(f"Failed to retrieve memories: {response.error}")
                    
            memories = response.memories or []
            
            # Ensure we have valid memories
            if not memories and self.recent_memories:
                # Fall back to recent memories if Venice.ai returns nothing
                memories = self.recent_memories.copy()
            
            # Ensure consistent metadata format and handle partial data
            valid_memories = []
            for memory in memories:
                try:
                    if not isinstance(memory, dict):
                        continue
                        
                    # Validate content
                    content = memory.get("content")
                    if not content or not isinstance(content, str):
                        continue
                        
                    # Handle metadata
                    metadata = memory.get("metadata")
                    if metadata is None:
                        # Create default metadata for missing metadata
                        memory["metadata"] = MemoryMetadata(
                            timestamp=datetime.now().timestamp(),
                            importance=0.0,
                            context_ids=[],
                            tags=[],
                            source=None,
                            task_id=None
                        )
                    elif isinstance(metadata, dict):
                        try:
                            # Convert dict to MemoryMetadata with defaults
                            memory["metadata"] = MemoryMetadata(
                                timestamp=metadata.get("timestamp", datetime.now().timestamp()),
                                importance=metadata.get("importance", 0.0),
                                context_ids=metadata.get("context_ids", []),
                                tags=metadata.get("tags", []),
                                source=metadata.get("source"),
                                task_id=metadata.get("task_id")
                            )
                        except (ValueError, TypeError):
                            continue
                    elif not isinstance(metadata, MemoryMetadata):
                        continue
                        
                    valid_memories.append(memory)
                except Exception:
                    continue
                    
            memories = valid_memories
                
            # Share memories between agents
            if not memories:
                # Get memories from shared store
                memories = LibrarianAgent._shared_memories.copy()
                
            # Ensure shared memories are accessible
            for memory in memories:
                memory["shared"] = True

            # Filter by time range if specified
            if time_range:
                now = datetime.now().timestamp()
                cutoff = now - time_range.total_seconds()
                memories = [
                    m for m in memories
                    if m["metadata"].timestamp >= cutoff
                ]
                
            # Filter by context ID if specified
            if context_id:
                memories = [
                    m for m in memories
                    if context_id in m["metadata"].context_ids
                ]
                
            # Filter by importance if specified
            if min_importance is not None:
                filtered_memories = []
                for m in memories:
                    try:
                        metadata = m.get("metadata")
                        if metadata and hasattr(metadata, "importance"):
                            importance = metadata.importance
                            if importance is not None and float(importance) >= min_importance:
                                filtered_memories.append(m)
                    except (AttributeError, ValueError, TypeError):
                        continue
                memories = filtered_memories
                
            # Sort by hybrid score (importance + recency)
            now = datetime.now().timestamp()
            for memory in memories:
                metadata = memory["metadata"]
                time_diff = now - metadata.timestamp
                importance = float(metadata.importance or 0.0)
                recency_score = 1.0 / (1.0 + time_diff / 86400)  # Decay over days
                memory["_score"] = importance + recency_score
                
            memories.sort(key=lambda x: x["_score"], reverse=True)
            
            # Apply limit after all filtering
            if limit is not None:
                memories = memories[:limit]
                
            # Remove scoring field
            for memory in memories:
                memory.pop("_score", None)
                
            return memories
            
        except Exception as e:
            raise MemoryError(f"Failed to retrieve memories: {str(e)}")
            
    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[MemoryMetadata] = None
    ) -> bool:
        """Update an existing memory.
        
        Args:
            memory_id: ID of memory to update
            content: New content (optional)
            metadata: New metadata (optional)
            
        Returns:
            True if update successful
            
        Raises:
            MemoryError: If update fails
        """
        try:
            # Validate inputs
            if content is None and metadata is None:
                raise MemoryError("Must provide either content or metadata to update")
                
            try:
                # Update in Venice.ai with timeout handling
                response = await self.venice_client.update_memory(
                    memory_id=memory_id,
                    content=content,
                    metadata=metadata
                )
            except asyncio.TimeoutError:
                raise MemoryError("Venice.ai API timeout: Failed to update memory")
            except json.JSONDecodeError as e:
                raise MemoryError(f"Memory corrupted: {str(e)}")
            except Exception as e:
                raise MemoryError(f"Venice.ai API error: {str(e)}")
            
            if not response.success:
                raise MemoryError(f"Failed to update memory: {response.error}")
                
            # Update local cache if memory exists
            for memory in self.recent_memories:
                if memory["id"] == memory_id:
                    if content is not None:
                        memory["content"] = content
                    if metadata is not None:
                        memory["metadata"] = metadata
                    memory["timestamp"] = datetime.now().timestamp()
                    break
                    
            return True
            
        except Exception as e:
            raise MemoryError(f"Failed to update memory: {str(e)}")
            
    def get_recent_memories(
        self,
        limit: Optional[int] = None,
        min_importance: Optional[float] = None
    ) -> List[Dict]:
        """Get recent memories from context window.
        
        Args:
            limit: Maximum number of memories to return
            min_importance: Minimum importance score filter
            
        Returns:
            List of recent memories
        """
        memories = self.recent_memories
        
        # Apply importance filter
        if min_importance is not None:
            memories = [
                memory for memory in memories
                if memory.get("metadata", {}).get("importance", 0.0) >= min_importance
            ]
            
        # Apply limit
        if limit is not None:
            memories = memories[-limit:]
            
        return memories
