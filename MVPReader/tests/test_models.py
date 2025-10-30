"""
Tests for data models
"""

import unittest
from datetime import datetime

from ..core.models import FeedEvent, Source, EventType, AISummary, Feedback


class TestFeedEvent(unittest.TestCase):
    """Test FeedEvent model"""
    
    def test_create_event(self):
        """Test creating a FeedEvent"""
        event = FeedEvent(
            id="test_1",
            source=Source.SLACK,
            event_type=EventType.MESSAGE,
            content="Test message",
            author="testuser",
            timestamp=datetime.now()
        )
        
        self.assertEqual(event.id, "test_1")
        self.assertEqual(event.source, Source.SLACK)
        self.assertEqual(event.event_type, EventType.MESSAGE)
        self.assertFalse(event.mentions_user)
        self.assertEqual(event.relevance_score, 0.0)
    
    def test_to_dict(self):
        """Test converting event to dictionary"""
        event = FeedEvent(
            id="test_1",
            source=Source.MASTODON,
            event_type=EventType.MENTION,
            content="@user hello",
            author="testuser",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            mentions_user=True
        )
        
        data = event.to_dict()
        
        self.assertEqual(data['id'], "test_1")
        self.assertEqual(data['source'], "mastodon")
        self.assertEqual(data['event_type'], "mention")
        self.assertTrue(data['mentions_user'])
    
    def test_from_dict(self):
        """Test creating event from dictionary"""
        data = {
            'id': 'test_1',
            'source': 'bluesky',
            'event_type': 'reply',
            'content': 'Test reply',
            'author': 'testuser',
            'timestamp': '2024-01-01T12:00:00',
            'mentions_user': True,
            'relevance_score': 5.0,
            'tags': ['test'],
            'processed': False
        }
        
        event = FeedEvent.from_dict(data)
        
        self.assertEqual(event.id, 'test_1')
        self.assertEqual(event.source, Source.BLUESKY)
        self.assertEqual(event.event_type, EventType.REPLY)
        self.assertTrue(event.mentions_user)
        self.assertEqual(event.relevance_score, 5.0)


class TestAISummary(unittest.TestCase):
    """Test AISummary model"""
    
    def test_create_summary(self):
        """Test creating an AISummary"""
        summary = AISummary(
            timestamp=datetime.now(),
            highlights=["Highlight 1", "Highlight 2"],
            suggestions=[{"id": "sug_0", "text": "Do something"}],
            event_count=10,
            sources_analyzed=["slack", "mastodon"]
        )
        
        self.assertEqual(len(summary.highlights), 2)
        self.assertEqual(len(summary.suggestions), 1)
        self.assertEqual(summary.event_count, 10)
    
    def test_to_dict(self):
        """Test converting summary to dictionary"""
        summary = AISummary(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            highlights=["Test"],
            suggestions=[],
            event_count=5,
            sources_analyzed=["slack"]
        )
        
        data = summary.to_dict()
        
        self.assertIn('timestamp', data)
        self.assertIn('highlights', data)
        self.assertEqual(data['event_count'], 5)


class TestFeedback(unittest.TestCase):
    """Test Feedback model"""
    
    def test_create_feedback(self):
        """Test creating Feedback"""
        feedback = Feedback(
            suggestion_id="sug_0",
            vote=1,
            timestamp=datetime.now(),
            comment="Good suggestion"
        )
        
        self.assertEqual(feedback.suggestion_id, "sug_0")
        self.assertEqual(feedback.vote, 1)
        self.assertEqual(feedback.comment, "Good suggestion")
    
    def test_to_dict(self):
        """Test converting feedback to dictionary"""
        feedback = Feedback(
            suggestion_id="sug_0",
            vote=-1,
            timestamp=datetime(2024, 1, 1, 12, 0, 0)
        )
        
        data = feedback.to_dict()
        
        self.assertEqual(data['suggestion_id'], "sug_0")
        self.assertEqual(data['vote'], -1)
        self.assertIn('timestamp', data)


if __name__ == '__main__':
    unittest.main()
