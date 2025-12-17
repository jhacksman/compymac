"""
Interest Filtering System
Tags and filters events based on user preferences
"""

from typing import List, Set
from ..core.models import FeedEvent
from ..config.settings import Settings


class InterestFilter:
    """
    Filters and tags events based on user interests
    Implements keyword matching and relevance scoring
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize interest filter
        
        Args:
            settings: Settings object with user preferences
        """
        self.settings = settings
        self.keywords = set(k.lower() for k in settings.user_keywords)
        self.topics = set(t.lower() for t in settings.user_topics)
        self.ignore_keywords = set(k.lower() for k in settings.ignore_keywords)
    
    def filter_events(self, events: List[FeedEvent]) -> List[FeedEvent]:
        """
        Filter and tag events based on relevance
        
        Args:
            events: List of FeedEvents to filter
            
        Returns:
            Filtered list of relevant events with tags and scores
        """
        filtered_events = []
        
        for event in events:
            if self._should_ignore(event):
                continue
            
            score = self._calculate_relevance_score(event)
            event.relevance_score = score
            
            event.tags = self._extract_tags(event)
            
            if score > 0 or event.mentions_user:
                filtered_events.append(event)
        
        filtered_events.sort(key=lambda e: e.relevance_score, reverse=True)
        
        return filtered_events
    
    def _should_ignore(self, event: FeedEvent) -> bool:
        """Check if event should be ignored based on ignore keywords"""
        content_lower = event.content.lower()
        
        for keyword in self.ignore_keywords:
            if keyword in content_lower:
                return True
        
        return False
    
    def _calculate_relevance_score(self, event: FeedEvent) -> float:
        """
        Calculate relevance score for an event
        
        Scoring:
        - Mentions user: +10.0
        - Keyword match: +2.0 per keyword
        - Topic match: +1.0 per topic
        - Direct message/reply: +3.0
        """
        score = 0.0
        content_lower = event.content.lower()
        
        if event.mentions_user:
            score += 10.0
        
        for keyword in self.keywords:
            if keyword in content_lower:
                score += 2.0
        
        for topic in self.topics:
            if topic in content_lower:
                score += 1.0
        
        if event.event_type.value in ['mention', 'reply']:
            score += 3.0
        
        return score
    
    def _extract_tags(self, event: FeedEvent) -> List[str]:
        """Extract relevant tags from event content"""
        tags = []
        content_lower = event.content.lower()
        
        for keyword in self.keywords:
            if keyword in content_lower:
                tags.append(keyword)
        
        tags.append(event.event_type.value)
        
        tags.append(event.source.value)
        
        if event.mentions_user:
            tags.append('mentions_me')
        
        return list(set(tags))  # Remove duplicates
