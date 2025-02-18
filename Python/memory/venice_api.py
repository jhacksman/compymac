"""Venice.ai API client for memory operations."""

import requests
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
    
    def store_memory(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
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
            payload = {
                "content": content,
                "metadata": metadata,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            response = requests.post(
                f"{self.base_url}/memories",
                headers=self.headers,
                json=payload
            )
            if response.status_code != 201:
                raise VeniceAPIError(f"Failed to store memory: {response.text}")
            
            return response.json()

        except requests.RequestException as e:
            raise VeniceAPIError(f"API request failed: {str(e)}")
    
    def retrieve_context(
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
            params = {
                "query": query,
                **(filters or {})
            }
            
            response = requests.get(
                f"{self.base_url}/memories/search",
                headers=self.headers,
                params=params
            )
            if response.status_code != 200:
                raise VeniceAPIError(f"Failed to retrieve context: {response.text}")
            
            return response.json()

        except requests.RequestException as e:
            raise VeniceAPIError(f"API request failed: {str(e)}")
    
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
            VeniceAPIError: If the API request fails
        """
        try:
            response = requests.patch(
                f"{self.base_url}/memories/{memory_id}",
                headers=self.headers,
                json=updates
            )
            if response.status_code != 200:
                raise VeniceAPIError(f"Failed to update memory: {response.text}")
            
            return response.json()

        except requests.RequestException as e:
            raise VeniceAPIError(f"API request failed: {str(e)}")
    
    def delete_memory(self, memory_id: str) -> None:
        """Delete a memory record.
        
        Args:
            memory_id: ID of the memory to delete
            
        Raises:
            VeniceAPIError: If the API request fails
        """
        try:
            response = requests.delete(
                f"{self.base_url}/memories/{memory_id}",
                headers=self.headers
            )
            if response.status_code != 204:
                raise VeniceAPIError(f"Failed to delete memory: {response.text}")
            
        except requests.RequestException as e:
            raise VeniceAPIError(f"API request failed: {str(e)}")
