"""
Base fetcher class
Defines interface for all feed fetchers
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from ..core.models import FeedEvent


class BaseFetcher(ABC):
    """
    Abstract base class for feed fetchers
    All platform-specific fetchers should inherit from this
    """
    
    def __init__(self, credentials: dict):
        """
        Initialize fetcher with credentials
        
        Args:
            credentials: Dictionary containing API credentials
        """
        self.credentials = credentials
        self.last_fetch_time: Optional[datetime] = None
    
    @abstractmethod
    def fetch_events(self, since: Optional[datetime] = None) -> List[FeedEvent]:
        """
        Fetch new events from the platform
        
        Args:
            since: Only fetch events after this timestamp
            
        Returns:
            List of FeedEvent objects
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the API connection is working
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    def update_last_fetch_time(self):
        """Update the last fetch timestamp"""
        self.last_fetch_time = datetime.now()
