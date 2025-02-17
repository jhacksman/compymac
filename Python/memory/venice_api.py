"""Venice.ai API client for memory operations."""

import aiohttp
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from .exceptions import VeniceAPIError

class VeniceAPI:
    """Client for interacting with Venice.ai API."""
    
    def __init__(self, api_key: str):
        """Initialize Venice.ai API client.
        
        Args:
            api_key: Venice.ai API authentication key
        """
        self.api_key = api_key
        self.base_url = "https://api.venice.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def store_memory(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Store a new memory in Venice.ai.
        
        Args:
            content: Raw memory content
            metadata: Additional memory metadata including tags, importance, etc.
            
        Returns:
            Dict containing the stored memory record
            
        Raises:
            VeniceAPIError: If the API request fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "content": content,
                    "metadata": metadata,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                response = await session.post(
                    f"{self.base_url}/memories",
                    headers=self.headers,
                    json=payload
                )
                if response.status != 201:
                    error_body = await response.text()
                    raise VeniceAPIError(f"Failed to store memory: {error_body}")
                
                return await response.json()

        except aiohttp.ClientError as e:
            raise VeniceAPIError(f"API request failed: {str(e)}")
    
    async def retrieve_context(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve context using hybrid query approach.
        
        Args:
            query: Search query for semantic similarity
            filters: Optional filters for time-based and relational filtering
            
        Returns:
            List of memory records matching the query and filters
            
        Raises:
            VeniceAPIError: If the API request fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "query": query,
                    **(filters or {})
                }
                
                response = await session.get(
                    f"{self.base_url}/memories/search",
                    headers=self.headers,
                    params=params
                )
                if response.status != 200:
                    error_body = await response.text()
                    raise VeniceAPIError(f"Failed to retrieve context: {error_body}")
                
                return await response.json()

        except aiohttp.ClientError as e:
            raise VeniceAPIError(f"API request failed: {str(e)}")
    
    async def update_memory(
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
            VeniceAPIError: If the API request fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.patch(
                    f"{self.base_url}/memories/{memory_id}",
                    headers=self.headers,
                    json=updates
                )
                if response.status != 200:
                    error_body = await response.text()
                    raise VeniceAPIError(f"Failed to update memory: {error_body}")
                
                return await response.json()

        except aiohttp.ClientError as e:
            raise VeniceAPIError(f"API request failed: {str(e)}")
    
    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory record.
        
        Args:
            memory_id: ID of the memory to delete
            
        Raises:
            VeniceAPIError: If the API request fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.delete(
                    f"{self.base_url}/memories/{memory_id}",
                    headers=self.headers
                )
                if response.status != 204:
                    error_body = await response.text()
                    raise VeniceAPIError(f"Failed to delete memory: {error_body}")
                
        except aiohttp.ClientError as e:
            raise VeniceAPIError(f"API request failed: {str(e)}")
