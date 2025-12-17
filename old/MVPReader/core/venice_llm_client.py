"""
Venice.ai LLM Client
Adapter for Venice.ai API using the existing VeniceClient
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional

from .llm_client import LLMClient


class VeniceLLMClient(LLMClient):
    """LLM client for Venice.ai API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.venice.ai", model: str = "qwen3-next-80b"):
        """
        Initialize Venice LLM client
        
        Args:
            api_key: Venice.ai API key
            base_url: Base URL for Venice API
            model: Model identifier
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> str:
        """
        Send chat completion request to Venice.ai
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier (uses default if None)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Generated text response
        """
        model_to_use = model or self.model
        
        request_data = {
            "model": model_to_use,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        if kwargs:
            request_data.update(kwargs)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v1/chat/completions",
                    json=request_data,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Venice API error: {response.status} - {error_text}")
                    
                    data = await response.json()
                    
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"]
                    else:
                        raise Exception("No response from Venice API")
                        
        except Exception as e:
            raise Exception(f"Failed to get chat completion from Venice: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        Test if connection to Venice.ai is working
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def _test():
                try:
                    result = await self.chat(
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=5
                    )
                    return bool(result)
                except:
                    return False
            
            result = loop.run_until_complete(_test())
            loop.close()
            return result
            
        except Exception as e:
            print(f"Venice connection test failed: {e}")
            return False
