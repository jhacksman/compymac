"""Librarian agent for memory orchestration.

This module implements a service layer for managing memory operations,
retrieval, and organization using Venice.ai API.
"""

import json
import uuid
import time
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
                    if response.success and response.memory_id:
                        memory_id = response.memory_id
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
                raise MemoryError(f"Failed to store memory: {last_error or 'No memory ID returned'}")
                
            # Convert metadata to dict format for consistent access
            metadata_dict = {
                "timestamp": metadata.timestamp,
                "importance": metadata.importance or 0.0,
                "context_ids": metadata.context_ids or [],
                "tags": metadata.tags or [],
                "source": metadata.source,
                "task_id": metadata.task_id
            }
            
            # No need to stream again since we already have memory_id
            if not memory_id:
                raise MemoryError("Failed to store memory: No memory ID returned")
                    
            if not memory_id:
                raise MemoryError("Failed to store memory: No memory ID returned")
                
            # Create memory entry with consistent metadata format
            memory_entry = {
                "id": memory_id,
                "content": content,
                "metadata": dict(metadata_dict),  # Store as dict for consistent access
                "timestamp": datetime.now().timestamp()
            }
            
            # Add to recent memories with deep copy
            recent_entry = dict(memory_entry)  # Deep copy entire entry
            recent_entry["metadata"] = dict(metadata_dict)  # Store as dict
            self.recent_memories.append(recent_entry)
            
            # Add to shared memories with deep copy
            shared_entry = dict(memory_entry)  # Deep copy entire entry
            shared_entry["metadata"] = dict(metadata_dict)  # Store as dict
            LibrarianAgent._shared_memories.append(shared_entry)
            
            # Update importance based on surprise score
            if surprise_score and surprise_score > 0.5:
                memory_entry["metadata"]["importance"] = max(
                    memory_entry["metadata"]["importance"],
                    surprise_score
                )
            
            # Update shared memories with context_ids
            for m in LibrarianAgent._shared_memories:
                if isinstance(m["metadata"], MemoryMetadata):
                    m["metadata"] = {
                        "timestamp": m["metadata"].timestamp,
                        "importance": m["metadata"].importance or 0.0,
                        "context_ids": m["metadata"].context_ids or [],
                        "tags": m["metadata"].tags or [],
                        "source": m["metadata"].source,
                        "task_id": m["metadata"].task_id
                    }
            
            # Maintain context window sizes and preserve important memories
            while len(self.recent_memories) > self.max_context_tokens // 4:
                # Keep memories with high importance
                metadata = self.recent_memories[0]["metadata"]
                if isinstance(metadata, dict):
                    importance = metadata.get("importance", 0.0)
                else:
                    importance = metadata.importance or 0.0
                if importance >= 0.8:
                    break
                self.recent_memories.pop(0)
                
            while len(LibrarianAgent._shared_memories) > self.max_context_tokens:
                # Keep memories with high importance
                metadata = LibrarianAgent._shared_memories[0]["metadata"]
                if isinstance(metadata, dict):
                    importance = metadata.get("importance", 0.0)
                else:
                    importance = metadata.importance or 0.0
                if importance >= 0.8:
                    break
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
            except TimeoutError:
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
            
            # Handle error cases
            if not response.success:
                if "corruption" in str(response.error).lower():
                    # Handle index corruption by returning empty list
                    return []
                raise MemoryError(f"Failed to retrieve memories: {response.error}")
                
            # Handle empty or None memories
            if not memories:
                return []
                
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
                
            # Ensure consistent metadata format
            for memory in memories:
                metadata = memory.get("metadata")
                if isinstance(metadata, dict):
                    memory["metadata"] = MemoryMetadata(
                        timestamp=metadata.get("timestamp", datetime.now().timestamp()),
                        importance=metadata.get("importance", 0.0),
                        context_ids=metadata.get("context_ids", []),
                        tags=metadata.get("tags", []),
                        source=metadata.get("source"),
                        task_id=metadata.get("task_id")
                    )
                elif not isinstance(metadata, MemoryMetadata):
                    memory["metadata"] = MemoryMetadata(
                        timestamp=datetime.now().timestamp(),
                        importance=0.0,
                        context_ids=[],
                        tags=[],
                        source=None,
                        task_id=None
                    )
                memory["shared"] = True

            # Convert all metadata to dict format and ensure deep copies
            normalized_memories = []
            for memory in memories:
                if not isinstance(memory, dict):
                    continue
                    
                if "metadata" not in memory:
                    continue
                    
                metadata = memory["metadata"]
                if isinstance(metadata, MemoryMetadata):
                    metadata_dict = {
                        "timestamp": metadata.timestamp,
                        "importance": metadata.importance or 0.0,
                        "context_ids": metadata.context_ids or [],
                        "tags": metadata.tags or [],
                        "source": metadata.source,
                        "task_id": metadata.task_id
                    }
                elif isinstance(metadata, dict):
                    metadata_dict = dict(metadata)  # Make a copy
                    metadata_dict.setdefault("timestamp", datetime.now().timestamp())
                    metadata_dict.setdefault("importance", 0.0)
                    metadata_dict.setdefault("context_ids", [])
                    metadata_dict.setdefault("tags", [])
                    metadata_dict.setdefault("source", None)
                    metadata_dict.setdefault("task_id", None)
                else:
                    continue
                    
                # Create normalized memory entry
                normalized_memory = {
                    "id": memory.get("id", str(uuid.uuid4())),
                    "content": memory.get("content", ""),
                    "metadata": dict(metadata_dict),  # Deep copy metadata
                    "timestamp": memory.get("timestamp", datetime.now().timestamp())
                }
                normalized_memories.append(normalized_memory)
                
            memories = normalized_memories
            
            # Share memories between agents
            if not memories:
                # Get memories from shared store
                memories = []
                for m in LibrarianAgent._shared_memories:
                    # Convert metadata to dict for consistent access
                    metadata = m["metadata"]
                    if isinstance(metadata, MemoryMetadata):
                        metadata_dict = {
                            "timestamp": metadata.timestamp,
                            "importance": metadata.importance or 0.0,
                            "context_ids": metadata.context_ids or [],
                            "tags": metadata.tags or [],
                            "source": metadata.source,
                            "task_id": metadata.task_id
                        }
                    else:
                        metadata_dict = dict(metadata)  # Make a copy
                        
                    # Ensure all fields exist with defaults
                    metadata_dict.setdefault("timestamp", datetime.now().timestamp())
                    metadata_dict.setdefault("importance", 0.0)
                    metadata_dict.setdefault("context_ids", [])
                    metadata_dict.setdefault("tags", [])
                    metadata_dict.setdefault("source", None)
                    metadata_dict.setdefault("task_id", None)
                        
                    # Filter by context_id if specified
                    if context_id:
                        context_ids = metadata_dict["context_ids"]
                        if not any(cid == context_id or str(context_id) in str(cid) for cid in context_ids):
                            continue
                        
                    # Filter by min_importance if specified
                    if min_importance and metadata_dict["importance"] < min_importance:
                        continue
                        
                    # Create memory entry with consistent metadata format
                    memory_entry = {
                        "id": m["id"],
                        "content": m["content"],
                        "metadata": dict(metadata_dict),  # Store as dict for consistent access
                        "timestamp": m["timestamp"],
                        "shared": True
                    }
                    memories.append(memory_entry)
                
            # Filter by time range if specified
            if time_range:
                now = datetime.now().timestamp()
                cutoff = now - time_range.total_seconds()
                memories = [
                    m for m in memories
                    if m["metadata"]["timestamp"] >= cutoff
                ]
                
            # Filter by context ID if specified
            if context_id:
                memories = [
                    m for m in memories
                    if context_id in m["metadata"]["context_ids"]
                ]
                
            # Filter by importance if specified
            if min_importance is not None:
                filtered_memories = []
                for m in memories:
                    try:
                        importance = float(m["metadata"]["importance"])
                        if importance >= min_importance:
                            filtered_memories.append(m)
                    except (ValueError, TypeError, KeyError):
                        continue
                memories = filtered_memories
                
            # Sort by hybrid score (importance + recency)
            now = datetime.now().timestamp()
            for memory in memories:
                metadata = memory["metadata"]
                if isinstance(metadata, MemoryMetadata):
                    time_diff = now - metadata.timestamp
                    importance = float(metadata.importance or 0.0)
                else:
                    time_diff = now - metadata.get("timestamp", now)
                    importance = float(metadata.get("importance", 0.0))
                recency_score = 1.0 / (1.0 + time_diff / 86400)  # Decay over days
                memory["_score"] = importance + recency_score
                
            memories.sort(key=lambda x: x["_score"], reverse=True)
            
            # Apply limit after all filtering
            if limit is not None:
                memories = memories[:limit]
                
            # Remove scoring field and ensure consistent metadata format
            for memory in memories:
                memory.pop("_score", None)
                if isinstance(memory["metadata"], dict):
                    memory["metadata"] = MemoryMetadata(
                        timestamp=memory["metadata"].get("timestamp", now),
                        importance=memory["metadata"].get("importance", 0.0),
                        context_ids=memory["metadata"].get("context_ids", []),
                        tags=memory["metadata"].get("tags", []),
                        source=memory["metadata"].get("source"),
                        task_id=memory["metadata"].get("task_id")
                    )
                
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
            except TimeoutError:
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
