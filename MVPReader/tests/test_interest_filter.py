"""
Tests for interest filtering
"""

import unittest
from datetime import datetime

from ..core.models import FeedEvent, Source, EventType
from ..core.interest_filter import InterestFilter
from ..config.settings import Settings


class TestInterestFilter(unittest.TestCase):
    """Test InterestFilter"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.settings = Settings()
        self.settings.config['user_interests']['keywords'] = ['AI', 'python']
        self.settings.config['user_interests']['ignore_keywords'] = ['sports']
        self.filter = InterestFilter(self.settings)
    
    def test_filter_relevant_event(self):
        """Test filtering keeps relevant events"""
        event = FeedEvent(
            id="test_1",
            source=Source.SLACK,
            event_type=EventType.MESSAGE,
            content="Check out this AI research paper",
            author="testuser",
            timestamp=datetime.now()
        )
        
        filtered = self.filter.filter_events([event])
        
        self.assertEqual(len(filtered), 1)
        self.assertGreater(filtered[0].relevance_score, 0)
        self.assertIn('ai', filtered[0].tags)
    
    def test_filter_ignores_irrelevant(self):
        """Test filtering removes irrelevant events"""
        event = FeedEvent(
            id="test_1",
            source=Source.SLACK,
            event_type=EventType.MESSAGE,
            content="Did you watch the sports game?",
            author="testuser",
            timestamp=datetime.now()
        )
        
        filtered = self.filter.filter_events([event])
        
        self.assertEqual(len(filtered), 0)
    
    def test_mentions_always_included(self):
        """Test that mentions are always included"""
        event = FeedEvent(
            id="test_1",
            source=Source.SLACK,
            event_type=EventType.MENTION,
            content="Random message",
            author="testuser",
            timestamp=datetime.now(),
            mentions_user=True
        )
        
        filtered = self.filter.filter_events([event])
        
        self.assertEqual(len(filtered), 1)
        self.assertGreater(filtered[0].relevance_score, 0)
    
    def test_relevance_scoring(self):
        """Test relevance score calculation"""
        event = FeedEvent(
            id="test_1",
            source=Source.SLACK,
            event_type=EventType.MENTION,
            content="Let's discuss AI and python",
            author="testuser",
            timestamp=datetime.now(),
            mentions_user=True
        )
        
        score = self.filter._calculate_relevance_score(event)
        
        self.assertGreater(score, 15)


if __name__ == '__main__':
    unittest.main()
