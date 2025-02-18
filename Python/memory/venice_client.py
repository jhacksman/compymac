"""Venice.ai API client for memory operations."""

import json
import re
import os
import time
import aiohttp
from typing import Dict, List, Optional, Generator

from .message_types import MemoryMetadata, MemoryResponse
from .exceptions import VeniceAPIError
from .config import VENICE_API_KEY, VENICE_BASE_URL, VENICE_MODEL


class VeniceClient:
    """Client for Venice.ai API."""
    
    async def delete_memory(self, memory_id: str) -> MemoryResponse:
        """Delete a memory by ID.
        
        Args:
            memory_id: ID of memory to delete
            
        Returns:
            MemoryResponse with success status
            
        Raises:
            VeniceAPIError: If deletion fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self.base_url}/api/v1/memories/{memory_id}",
                    headers=self.headers
                ) as response:
                    await response.read()
                    if response.status != 200:
                        raise VeniceAPIError(f"Failed to delete memory: {response.status}")
                    return MemoryResponse(
                        action="delete_memory",
                        success=True
                    )
        except Exception as e:
            raise VeniceAPIError(f"Failed to delete memory: {str(e)}")
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Venice client."""
        from .config import VENICE_API_KEY, VENICE_BASE_URL, VENICE_MODEL
        self.api_key = api_key or VENICE_API_KEY
        
        # Ensure base URL has /api/v1
        base_url = VENICE_BASE_URL.rstrip("/")
        if not base_url.endswith("/api/v1"):
            if base_url.endswith("/v1"):
                base_url = base_url[:-3] + "/api/v1"  # Replace /v1 with /api/v1
            elif base_url.endswith("/api"):
                base_url = base_url + "/v1"  # Add /v1 to /api
            else:
                base_url = base_url + "/api/v1"  # Add full /api/v1
        print(f"Initialized base URL: {base_url}")  # Debug log
        self._base_url = base_url
        self._model = VENICE_MODEL  # Use configured model name
        
        # Rate limiting settings
        self.max_retries = 3
        self.retry_delay = 1.0  # Initial delay in seconds
        self.max_delay = 8.0  # Maximum delay in seconds
        
        # Set up headers with proper authentication
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    @property
    def base_url(self) -> str:
        """Get the base URL."""
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        """Set the base URL."""
        base_url = value.rstrip("/")
        if not base_url.endswith("/api/v1"):
            if base_url.endswith("/v1"):
                base_url = base_url[:-3] + "/api/v1"  # Replace /v1 with /api/v1
            elif base_url.endswith("/api"):
                base_url = base_url + "/v1"  # Add /v1 to /api
            else:
                base_url = base_url + "/api/v1"  # Add full /api/v1
        print(f"Setting base URL: {base_url}")  # Debug log
        self._base_url = base_url

    @property
    def model(self) -> str:
        """Get the model name."""
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        """Set the model name."""
        self._model = value
        # Set up headers with proper authentication
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CompyMac/1.0",
            "Origin": "https://api.venice.ai",
            "Referer": "https://api.venice.ai/",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, authorization"
        }
        
    def _handle_rate_limit(self, retry_count: int) -> None:
        """Handle rate limiting with exponential backoff."""
        if retry_count >= self.max_retries:
            raise VeniceAPIError("Max retries exceeded due to rate limiting")
            
        delay = min(self.retry_delay * (2 ** retry_count), self.max_delay)
        print(f"Rate limited. Retrying in {delay} seconds...")  # Debug log
        time.sleep(delay)

    async def _stream_chunks(self, response: aiohttp.ClientResponse, retry_count: int = 0) -> Generator[str, None, None]:
        """Stream chunks from response."""
        if response.status_code == 429:  # Rate limit exceeded
            self._handle_rate_limit(retry_count)
            return
            
        buffer = ""
        content_buffer = ""
        for chunk in response.iter_content(chunk_size=512):
            if chunk:
                try:
                    text = chunk.decode("utf-8")
                    print(f"Raw chunk: {text}")  # Debug log
                    buffer += text
                    
                    # Process complete messages
                    while "\n" in buffer:
                        line, remaining = buffer.split("\n", 1)
                        line = line.strip()
                        buffer = remaining
                        
                        if not line:
                            continue
                            
                        if line.startswith("data: "):
                            data = line[6:].strip()  # Skip "data: " prefix
                            if data == "[DONE]":
                                if content_buffer:
                                    yield content_buffer
                                return
                                
                            try:
                                json_data = json.loads(data)
                                print(f"Parsed JSON: {json_data}")  # Debug log
                                
                                if "choices" in json_data and json_data["choices"]:
                                    choice = json_data["choices"][0]
                                    if "delta" in choice and "content" in choice["delta"]:
                                        content = choice["delta"]["content"]
                                        if content:
                                            print(f"Adding content: {content}")  # Debug log
                                            content_buffer += content
                                            yield content_buffer
                                            content_buffer = ""  # Reset after yielding
                                            
                                    # Check for finish_reason to handle end of stream
                                    if choice.get("finish_reason") == "stop":
                                        print("Received stop signal")  # Debug log
                                        return
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e}, data: {data}")  # Debug log
                                continue
                except Exception as e:
                    print(f"Chunk processing error: {e}")  # Debug log
                    raise VeniceAPIError(f"Failed to decode chunk: {str(e)}")
            time.sleep(0.01)  # Small delay to prevent CPU spinning
            
    def stream_memory(
        self,
        content: str,
        metadata: MemoryMetadata,
        timeout: float = 10.0,
        retry_count: int = 0
    ) -> Generator[str, None, None]:
        """Stream memory storage response."""
        try:
            # Convert metadata to dict format
            metadata_dict = {
                "timestamp": metadata.timestamp,
                "importance": metadata.importance or 0.0,
                "context_ids": metadata.context_ids or [],
                "tags": metadata.tags or [],
                "source": metadata.source,
                "task_id": metadata.task_id
            }
            
            print("Starting memory storage...")  # Debug log
            print(f"Base URL: {self.base_url}")  # Debug log
            print(f"Request headers: {self.headers}")  # Debug log
            
            request_data = {
                "model": self.model,  # Use configured model name
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a memory storage system. You MUST ONLY output a memory ID in EXACTLY this format: 'MEMORY_ID: MEM_' followed by EXACTLY 10 digits (0-9). For example: 'MEMORY_ID: MEM_1234567890'. Do not output ANY other text or characters. The ID must contain ONLY digits 0-9 after MEM_, no letters allowed."
                    },
                    {
                        "role": "user",
                        "content": f"Store this memory with metadata:\n{json.dumps(metadata_dict, indent=2)}\n\nContent: {content}"
                    }
                ],
                "stream": True,
                "temperature": 0.0,
                "max_tokens": 100,
                "top_p": 1.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "venice_parameters": {
                    "include_venice_system_prompt": False  # Don't use default system prompt
                }
            }
            print(f"Request data: {json.dumps(request_data, indent=2)}")  # Debug log
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=request_data,
                    headers=self.headers,
                    timeout=timeout
                ) as response:
                print(f"Response status: {response.status_code}")  # Debug log
                print(f"Response headers: {response.headers}")  # Debug log
                
                if response.status_code == 429 and retry_count < self.max_retries:
                    self._handle_rate_limit(retry_count)
                    # Retry with incremented count
                    for chunk in self.stream_memory(content, metadata, timeout, retry_count + 1):
                        yield chunk
                    return
                    
                if response.status_code != 200:
                    error_text = response.text
                    print(f"Error response body: {error_text}")  # Debug log
                    raise VeniceAPIError(
                        f"Failed to store memory: {response.status_code} - {error_text}"
                    )
                    
                for chunk in self._stream_chunks(response, retry_count):
                    yield chunk
                        
        except Exception as e:
            raise VeniceAPIError(f"Failed to stream memory: {str(e)}")
            
    async def store_memory(
        self,
        content: str,
        metadata: MemoryMetadata,
        timeout: float = 10.0
    ) -> MemoryResponse:
        """Store memory in Venice.ai."""
        try:
            # Initialize variables
            full_response = ""
            memory_id = None
            
            # Process streaming response
            for chunk in self.stream_memory(content, metadata, timeout):
                if chunk:
                    # Accumulate the content
                    full_response += chunk
                    clean_response = full_response.replace("\n", "").strip()
                    print(f"Accumulated response: {clean_response}")  # Debug log
                    
                    # Try to find memory ID in various formats
                    patterns = [
                        r'MEMORY[_\s]*ID:\s*MEM[_\s]*(\d{10})',  # Exact format with 10 digits
                        r'MEM[_\s]*(\d{10})',  # Just MEM_ prefix with 10 digits
                    ]
                    
                    # Try pattern matching
                    for pattern in patterns:
                        match = re.search(pattern, clean_response)
                        if match:
                            digits = match.group(1)
                            if digits.isdigit() and len(digits) == 10:
                                memory_id = f"MEM_{digits}"
                                print(f"Found complete memory ID: {memory_id}")
                                return MemoryResponse(
                                    action="store_memory",
                                    success=True,
                                    memory_id=memory_id
                                )
                    
                    # If no complete ID found yet, try to extract digits
                    all_digits = ''.join(re.findall(r'\d+', clean_response))
                    if len(all_digits) >= 10:
                        # Extract just the last 10 digits since they come at the end
                        digits = all_digits[-10:]
                        memory_id = f"MEM_{digits}"
                        print(f"Found complete memory ID from digits: {memory_id}")
                        return MemoryResponse(
                            action="store_memory",
                            success=True,
                            memory_id=memory_id
                        )
            
            # If we get here without finding a memory ID, raise an error
            raise VeniceAPIError("No memory ID found in response")
            
        except Exception as e:
            raise VeniceAPIError(f"Failed to store memory: {str(e)}")
            
    async def retrieve_context(
        self,
        query: str,
        context_id: Optional[str] = None,
        time_range: Optional[float] = None,
        limit: Optional[int] = None,
        timeout: float = 10.0,
        retry_count: int = 0
    ) -> MemoryResponse:
        """Retrieve memories from Venice.ai."""
        try:
            params = {
                "model": self.model,
                "query": query,
                "stream": True
            }
            if context_id:
                params["context_id"] = context_id
            if time_range:
                params["time_range"] = time_range
            if limit:
                params["limit"] = limit
                
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/memories/search",
                    json=params,
                    headers=self.headers,
                    timeout=timeout
                ) as response:
                if response.status_code == 429 and retry_count < self.max_retries:
                    self._handle_rate_limit(retry_count)
                    # Retry with incremented count
                    return self.retrieve_context(
                        query,
                        context_id,
                        time_range,
                        limit,
                        timeout,
                        retry_count + 1
                    )
                if response.status_code != 200:
                    error_text = response.text
                    print(f"Error response body: {error_text}")  # Debug log
                    raise VeniceAPIError(
                        f"Failed to retrieve memories: {response.status_code} - {error_text}"
                    )
                    
                memories = []
                for chunk in self._stream_chunks(response):
                    try:
                        data = json.loads(chunk)
                        if "memories" in data:
                            for memory in data["memories"]:
                                if isinstance(memory.get("metadata"), dict):
                                    memory["metadata"] = MemoryMetadata(**memory["metadata"])
                                memories.append(memory)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue
                        
                return MemoryResponse(
                    action="retrieve_context",
                    success=True,
                    memories=memories
                )
                    
        except Exception as e:
            raise VeniceAPIError(f"Failed to retrieve memories: {str(e)}")
            
    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[MemoryMetadata] = None,
        timeout: float = 10.0,
        retry_count: int = 0
    ) -> MemoryResponse:
        """Update memory in Venice.ai."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    f"{self.base_url}/memories/{memory_id}",
                    json={
                        "model": self.model,
                        "content": content,
                        "metadata": metadata.__dict__ if metadata else None,
                        "stream": True
                    },
                    headers=self.headers,
                    timeout=timeout
                ) as response:
                if response.status_code == 429 and retry_count < self.max_retries:
                    self._handle_rate_limit(retry_count)
                    # Retry with incremented count
                    return self.update_memory(
                        memory_id,
                        content,
                        metadata,
                        timeout,
                        retry_count + 1
                    )
                if response.status_code != 200:
                    error_text = response.text
                    print(f"Error response body: {error_text}")  # Debug log
                    raise VeniceAPIError(
                        f"Failed to update memory: {response.status_code} - {error_text}"
                    )
                    
                success = False
                for chunk in self._stream_chunks(response):
                    try:
                        data = json.loads(chunk)
                        if data.get("success"):
                            success = True
                            break
                    except json.JSONDecodeError:
                        continue
                        
                if not success:
                    raise VeniceAPIError("Failed to update memory")
                    
                return MemoryResponse(
                    action="update_memory",
                    success=True,
                    memory_id=memory_id
                )
                    
        except Exception as e:
            raise VeniceAPIError(f"Failed to update memory: {str(e)}")
