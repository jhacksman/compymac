"""
Slack Feed Fetcher
Retrieves messages from Slack channels using the Web API
"""

import requests
from typing import List, Optional
from datetime import datetime

from .base import BaseFetcher
from ..core.models import FeedEvent, Source, EventType


class SlackFetcher(BaseFetcher):
    """
    Fetches messages from Slack workspace
    Uses Slack Web API with Bot Token
    """
    
    def __init__(self, credentials: dict):
        """
        Initialize Slack fetcher
        
        Args:
            credentials: Dict with 'token' and optional 'workspace'
        """
        super().__init__(credentials)
        self.token = credentials.get('token')
        self.workspace = credentials.get('workspace', 'Unknown')
        self.base_url = "https://slack.com/api"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_connection(self) -> bool:
        """Test Slack API connection"""
        try:
            response = requests.get(
                f"{self.base_url}/auth.test",
                headers=self.headers
            )
            data = response.json()
            return data.get('ok', False)
        except Exception as e:
            print(f"Slack connection test failed: {e}")
            return False
    
    def fetch_events(self, since: Optional[datetime] = None) -> List[FeedEvent]:
        """
        Fetch messages from Slack channels
        
        Args:
            since: Only fetch messages after this timestamp
            
        Returns:
            List of FeedEvent objects
        """
        events = []
        
        try:
            channels = self._get_channels()
            
            for channel in channels:
                channel_id = channel['id']
                channel_name = channel['name']
                
                messages = self._get_channel_messages(channel_id, since)
                
                for msg in messages:
                    event = self._message_to_event(msg, channel_name)
                    if event:
                        events.append(event)
            
            self.update_last_fetch_time()
            
        except Exception as e:
            print(f"Error fetching Slack events: {e}")
        
        return events
    
    def _get_channels(self) -> List[dict]:
        """Get list of channels the bot has access to"""
        try:
            response = requests.get(
                f"{self.base_url}/conversations.list",
                headers=self.headers,
                params={"types": "public_channel,private_channel"}
            )
            data = response.json()
            
            if data.get('ok'):
                return data.get('channels', [])
            else:
                print(f"Error getting channels: {data.get('error')}")
                return []
        except Exception as e:
            print(f"Error getting channels: {e}")
            return []
    
    def _get_channel_messages(
        self, 
        channel_id: str, 
        since: Optional[datetime] = None
    ) -> List[dict]:
        """Get messages from a specific channel"""
        try:
            params = {
                "channel": channel_id,
                "limit": 100
            }
            
            if since:
                params["oldest"] = str(since.timestamp())
            
            response = requests.get(
                f"{self.base_url}/conversations.history",
                headers=self.headers,
                params=params
            )
            data = response.json()
            
            if data.get('ok'):
                return data.get('messages', [])
            else:
                print(f"Error getting messages: {data.get('error')}")
                return []
        except Exception as e:
            print(f"Error getting channel messages: {e}")
            return []
    
    def _message_to_event(self, message: dict, channel_name: str) -> Optional[FeedEvent]:
        """Convert Slack message to FeedEvent"""
        try:
            if message.get('subtype') in ['bot_message', 'channel_join', 'channel_leave']:
                return None
            
            msg_id = f"slack_{message.get('ts', '')}"
            content = message.get('text', '')
            author = message.get('user', 'Unknown')
            timestamp = datetime.fromtimestamp(float(message.get('ts', 0)))
            
            mentions_user = '@' in content
            
            event_type = EventType.MENTION if mentions_user else EventType.MESSAGE
            
            return FeedEvent(
                id=msg_id,
                source=Source.SLACK,
                event_type=event_type,
                content=content,
                author=author,
                timestamp=timestamp,
                channel=channel_name,
                mentions_user=mentions_user,
                raw_data=message
            )
        except Exception as e:
            print(f"Error converting message to event: {e}")
            return None
