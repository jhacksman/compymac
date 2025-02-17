"""Venice.ai API client for memory operations.

This module provides a client for interacting with the Venice.ai API for memory operations.
"""

from datetime import datetime
import aiohttp
from typing import Dict, Optional
from .message_types import (
    MemoryMetadata,
    MemoryRequest,
    MemoryResponse,
    validate_memory_request
)

class VeniceClient:
    """Client for interacting with Venice.ai API."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.venice.ai/api/v1"):
        """Initialize Venice client.
        
        Args:
            api_key: Venice.ai API key
            base_url: Base URL for Venice.ai API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    async def store_memory(
        self,
        content: str,
        metadata: MemoryMetadata
    ) -> MemoryResponse:
        """Store a memory using Venice.ai API.
        
        Args:
            content: Memory content to store
            metadata: Associated metadata
            
        Returns:
            MemoryResponse with stored memory details
            
        Raises:
            MemoryValidationError: If request validation fails
            aiohttp.ClientError: If API request fails
        """
        request = MemoryRequest(
            action="store_memory",
            content=content,
            metadata=metadata
        )
        
        # Validate request
        validate_memory_request(request)
        
        # Prepare API payload
        payload = {
            "content": content,
            "metadata": {
                "timestamp": metadata.timestamp,
                "importance": metadata.importance,
                "context_ids": metadata.context_ids,
                "tags": metadata.tags,
                "source": metadata.source,
                "task_id": metadata.task_id
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/memories",
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    return MemoryResponse(
                        action="store_memory",
                        success=False,
                        error=f"API error: {error}"
                    )
                    
                data = await response.json()
                return MemoryResponse(
                    action="store_memory",
                    success=True,
                    memory_id=data["memory_id"],
                    metadata=metadata
                )
                
    async def retrieve_context(
        self,
        query: Optional[str] = None,
        context_id: Optional[str] = None,
        time_range: Optional[float] = None,
        limit: Optional[int] = None
    ) -> MemoryResponse:
        """Retrieve memories based on context.
        
        Args:
            query: Optional search query
            context_id: Optional context ID filter
            time_range: Optional time range filter
            limit: Maximum number of memories to return
            
        Returns:
            MemoryResponse with retrieved memories
            
        Raises:
            aiohttp.ClientError: If API request fails
        """
        # Prepare API payload
        payload = {
            "query": query,
            "context_id": context_id,
            "time_range": time_range,
            "limit": limit
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/memories/search",
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    return MemoryResponse(
                        action="retrieve_context",
                        success=False,
                        error=f"API error: {error}"
                    )
                    
                data = await response.json()
                return MemoryResponse(
                    action="retrieve_context",
                    success=True,
                    memories=data["memories"]
                )
                
    async def update_memory(
        self,
        memory_id: str,
        updates: Dict,
        metadata: MemoryMetadata
    ) -> MemoryResponse:
        """Update an existing memory.
        
        Args:
            memory_id: ID of memory to update
            updates: Dictionary of fields to update
            metadata: Updated metadata
            
        Returns:
            MemoryResponse with update status
            
        Raises:
            aiohttp.ClientError: If API request fails
        """
        request = MemoryRequest(
            action="update_memory",
            memory_id=memory_id,
            metadata=metadata
        )
        
        # Validate request
        validate_memory_request(request)
        
        # Prepare API payload
        payload = {
            "memory_id": memory_id,
            "updates": updates,
            "metadata": {
                "timestamp": metadata.timestamp,
                "importance": metadata.importance,
                "context_ids": metadata.context_ids,
                "tags": metadata.tags,
                "source": metadata.source,
                "task_id": metadata.task_id
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.patch(
                f"{self.base_url}/memories/{memory_id}",
                headers=self.headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    return MemoryResponse(
                        action="update_memory",
                        success=False,
                        error=f"API error: {error}"
                    )
                    
                data = await response.json()
                return MemoryResponse(
                    action="update_memory",
                    success=True,
                    memory_id=memory_id,
                    metadata=metadata
                )
                
    async def delete_memory(self, memory_id: str) -> MemoryResponse:
        """Delete a memory.
        
        Args:
            memory_id: ID of memory to delete
            
        Returns:
            MemoryResponse with deletion status
            
        Raises:
            aiohttp.ClientError: If API request fails
        """
        request = MemoryRequest(
            action="delete_memory",
            memory_id=memory_id,
            metadata=MemoryMetadata(timestamp=datetime.now().timestamp())
        )
        
        # Validate request
        validate_memory_request(request)
        
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.base_url}/memories/{memory_id}",
                headers=self.headers
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    return MemoryResponse(
                        action="delete_memory",
                        success=False,
                        error=f"API error: {error}"
                    )
                    
                return MemoryResponse(
                    action="delete_memory",
                    success=True,
                    memory_id=memory_id
                )
