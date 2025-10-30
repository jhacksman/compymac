"""
Mastodon Feed Fetcher
Retrieves notifications and timeline from Mastodon instances
"""

import requests
from typing import List, Optional
from datetime import datetime

from .base import BaseFetcher
from ..core.models import FeedEvent, Source, EventType


class MastodonFetcher(BaseFetcher):
    """
    Fetches notifications and posts from Mastodon
    Uses Mastodon REST API
    """
    
    def __init__(self, credentials: dict):
        """
        Initialize Mastodon fetcher
        
        Args:
            credentials: Dict with 'access_token' and 'instance_url'
        """
        super().__init__(credentials)
        self.access_token = credentials.get('access_token')
        self.instance_url = credentials.get('instance_url', 'https://mastodon.social')
        self.headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
    
    def test_connection(self) -> bool:
        """Test Mastodon API connection"""
        try:
            response = requests.get(
                f"{self.instance_url}/api/v1/accounts/verify_credentials",
                headers=self.headers
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Mastodon connection test failed: {e}")
            return False
    
    def fetch_events(self, since: Optional[datetime] = None) -> List[FeedEvent]:
        """
        Fetch notifications from Mastodon
        
        Args:
            since: Only fetch notifications after this timestamp
            
        Returns:
            List of FeedEvent objects
        """
        events = []
        
        try:
            notifications = self._get_notifications(since)
            
            for notif in notifications:
                event = self._notification_to_event(notif)
                if event:
                    events.append(event)
            
            self.update_last_fetch_time()
            
        except Exception as e:
            print(f"Error fetching Mastodon events: {e}")
        
        return events
    
    def _get_notifications(self, since: Optional[datetime] = None) -> List[dict]:
        """Get notifications from Mastodon"""
        try:
            params = {"limit": 40}
            
            if since:
                params["since_id"] = self._timestamp_to_id(since)
            
            response = requests.get(
                f"{self.instance_url}/api/v1/notifications",
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting notifications: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error getting notifications: {e}")
            return []
    
    def _timestamp_to_id(self, timestamp: datetime) -> str:
        """Convert timestamp to Mastodon ID (approximate)"""
        return str(int(timestamp.timestamp() * 1000))
    
    def _notification_to_event(self, notification: dict) -> Optional[FeedEvent]:
        """Convert Mastodon notification to FeedEvent"""
        try:
            notif_type = notification.get('type')
            notif_id = f"mastodon_{notification.get('id')}"
            
            type_mapping = {
                'mention': EventType.MENTION,
                'reblog': EventType.REPOST,
                'favourite': EventType.FAVORITE,
                'follow': EventType.FOLLOW,
                'poll': EventType.NOTIFICATION,
                'status': EventType.MESSAGE
            }
            
            event_type = type_mapping.get(notif_type, EventType.NOTIFICATION)
            
            account = notification.get('account', {})
            author = account.get('username', 'Unknown')
            
            status = notification.get('status', {})
            content = status.get('content', '') if status else f"{notif_type} notification"
            
            created_at = notification.get('created_at', '')
            timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            url = status.get('url') if status else None
            
            return FeedEvent(
                id=notif_id,
                source=Source.MASTODON,
                event_type=event_type,
                content=content,
                author=author,
                timestamp=timestamp,
                url=url,
                mentions_user=(notif_type == 'mention'),
                raw_data=notification
            )
        except Exception as e:
            print(f"Error converting notification to event: {e}")
            return None
