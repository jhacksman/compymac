"""
Bluesky Feed Fetcher
Retrieves notifications from Bluesky using AT Protocol
"""

import requests
from typing import List, Optional
from datetime import datetime

from .base import BaseFetcher
from ..core.models import FeedEvent, Source, EventType


class BlueskyFetcher(BaseFetcher):
    """
    Fetches notifications from Bluesky
    Uses AT Protocol API
    """
    
    def __init__(self, credentials: dict):
        """
        Initialize Bluesky fetcher
        
        Args:
            credentials: Dict with 'username' and 'password'
        """
        super().__init__(credentials)
        self.username = credentials.get('username')
        self.password = credentials.get('password')
        self.base_url = "https://bsky.social/xrpc"
        self.access_token = None
        self.did = None
        
        if self.username and self.password:
            self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with Bluesky and get access token"""
        try:
            response = requests.post(
                f"{self.base_url}/com.atproto.server.createSession",
                json={
                    "identifier": self.username,
                    "password": self.password
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('accessJwt')
                self.did = data.get('did')
                return True
            else:
                print(f"Bluesky authentication failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"Bluesky authentication error: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test Bluesky API connection"""
        if not self.access_token:
            return self._authenticate()
        
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(
                f"{self.base_url}/app.bsky.actor.getProfile",
                headers=headers,
                params={"actor": self.did}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Bluesky connection test failed: {e}")
            return False
    
    def fetch_events(self, since: Optional[datetime] = None) -> List[FeedEvent]:
        """
        Fetch notifications from Bluesky
        
        Args:
            since: Only fetch notifications after this timestamp
            
        Returns:
            List of FeedEvent objects
        """
        events = []
        
        if not self.access_token:
            print("Not authenticated with Bluesky")
            return events
        
        try:
            notifications = self._get_notifications(since)
            
            for notif in notifications:
                event = self._notification_to_event(notif)
                if event:
                    events.append(event)
            
            self.update_last_fetch_time()
            
        except Exception as e:
            print(f"Error fetching Bluesky events: {e}")
        
        return events
    
    def _get_notifications(self, since: Optional[datetime] = None) -> List[dict]:
        """Get notifications from Bluesky"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            params = {"limit": 50}
            
            response = requests.get(
                f"{self.base_url}/app.bsky.notification.listNotifications",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                notifications = data.get('notifications', [])
                
                if since:
                    notifications = [
                        n for n in notifications
                        if self._parse_timestamp(n.get('indexedAt')) > since
                    ]
                
                return notifications
            else:
                print(f"Error getting notifications: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error getting notifications: {e}")
            return []
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse Bluesky timestamp string"""
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            return datetime.now()
    
    def _notification_to_event(self, notification: dict) -> Optional[FeedEvent]:
        """Convert Bluesky notification to FeedEvent"""
        try:
            reason = notification.get('reason')
            notif_id = f"bluesky_{notification.get('uri', '').split('/')[-1]}"
            
            type_mapping = {
                'like': EventType.FAVORITE,
                'repost': EventType.REPOST,
                'follow': EventType.FOLLOW,
                'mention': EventType.MENTION,
                'reply': EventType.REPLY,
                'quote': EventType.REPOST
            }
            
            event_type = type_mapping.get(reason, EventType.NOTIFICATION)
            
            author_data = notification.get('author', {})
            author = author_data.get('handle', 'Unknown')
            
            record = notification.get('record', {})
            content = record.get('text', f"{reason} notification")
            
            timestamp = self._parse_timestamp(notification.get('indexedAt', ''))
            
            uri = notification.get('uri', '')
            url = f"https://bsky.app/profile/{author}/post/{uri.split('/')[-1]}" if uri else None
            
            return FeedEvent(
                id=notif_id,
                source=Source.BLUESKY,
                event_type=event_type,
                content=content,
                author=author,
                timestamp=timestamp,
                url=url,
                mentions_user=(reason in ['mention', 'reply']),
                raw_data=notification
            )
        except Exception as e:
            print(f"Error converting notification to event: {e}")
            return None
