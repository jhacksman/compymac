"""Venice.ai API client for memory operations."""

from typing import Dict, List, Optional
from datetime import datetime
import aiohttp

from .message_types import MemoryMetadata, MemoryResponse
from .exceptions import VeniceAPIError


class VeniceClient:
    """Client for Venice.ai API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Venice client.
        
        Args:
            api_key: Optional API key for Venice.ai
        """
        self.api_key = api_key
        self.base_url = "https://api.venice.ai/v1"
        
    async def store_memory(
        self,
        content: str,
        metadata: MemoryMetadata
    ) -> MemoryResponse:
        """Store memory in Venice.ai.
        
        Args:
            content: Memory content to store
            metadata: Associated metadata
            
        Returns:
            Response containing memory ID
            
        Raises:
            VeniceAPIError: If API request fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/memories",
                    json={
                        "content": content,
                        "metadata": metadata.__dict__
                    },
                    headers=self._get_headers()
                ) as response:
                    data = await response.json()
                    
                    if response.status != 200:
                        raise VeniceAPIError(
                            f"Failed to store memory: {data.get('error')}"
                        )
                        
                    return MemoryResponse(
                        action="store_memory",
                        success=True,
                        memory_id=data.get("id")
                    )
                    
        except Exception as e:
            raise VeniceAPIError(f"Failed to store memory: {str(e)}")
            
    async def retrieve_context(
        self,
        query: str,
        context_id: Optional[str] = None,
        time_range: Optional[float] = None,
        limit: Optional[int] = None
    ) -> MemoryResponse:
        """Retrieve relevant memories from Venice.ai.
        
        Args:
            query: Search query
            context_id: Optional context ID filter
            time_range: Optional time range in seconds
            limit: Maximum number of memories to return
            
        Returns:
            Response containing matching memories
            
        Raises:
            VeniceAPIError: If API request fails
        """
        try:
            params = {"query": query}
            if context_id:
                params["context_id"] = context_id
            if time_range:
                params["time_range"] = time_range
            if limit:
                params["limit"] = limit
                
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/memories/search",
                    params=params,
                    headers=self._get_headers()
                ) as response:
                    data = await response.json()
                    
                    if response.status != 200:
                        raise VeniceAPIError(
                            f"Failed to retrieve memories: {data.get('error')}"
                        )
                        
                    return MemoryResponse(
                        action="retrieve_context",
                        success=True,
                        memories=data.get("memories", [])
                    )
                    
        except Exception as e:
            raise VeniceAPIError(f"Failed to retrieve memories: {str(e)}")
            
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers.
        
        Returns:
            Dictionary of headers
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        return headers
