"""Retry handler for agent operations."""

import random
import asyncio
from typing import Optional, Callable, Any, TypeVar, Awaitable

T = TypeVar('T')

class RetryHandler:
    """Handles retries with exponential backoff."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 8.0):
        """Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
    def calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds with jitter
        """
        delay = min(
            self.base_delay * (2 ** attempt),
            self.max_delay
        )
        # Add jitter
        jitter = delay * 0.1  # 10% jitter
        return delay + (random.random() * jitter)
        
    async def execute_with_retry(
        self,
        operation: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any
    ) -> T:
        """Execute an async operation with retry logic.
        
        Args:
            operation: Async function to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result from operation
            
        Raises:
            Exception: If all retries fail
        """
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.calculate_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                
        if last_error:
            raise last_error
        raise Exception("Operation failed after all retries")
