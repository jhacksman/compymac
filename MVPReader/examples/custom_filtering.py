"""
Custom filtering example
Demonstrates how to customize interest filtering
"""

from datetime import datetime, timedelta
from MVPReader.config.settings import Settings
from MVPReader.core.aggregator import FeedAggregator
from MVPReader.core.models import FeedEvent, Source, EventType


def main():
    """Run custom filtering example"""
    
    print("MVPReader - Custom Filtering Example")
    print("=" * 60)
    
    settings = Settings()
    
    settings.config['user_interests']['keywords'] = [
        'machine learning',
        'neural networks',
        'deep learning',
        'transformers'
    ]
    settings.config['user_interests']['topics'] = [
        'AI research',
        'model training',
        'LLM development'
    ]
    settings.config['user_interests']['ignore_keywords'] = [
        'spam',
        'advertisement',
        'promotion'
    ]
    
    print("\n1. Custom interest configuration:")
    print(f"   Keywords: {', '.join(settings.user_keywords)}")
    print(f"   Topics: {', '.join(settings.user_topics)}")
    print(f"   Ignore: {', '.join(settings.ignore_keywords)}")
    
    sample_events = [
        FeedEvent(
            id="test_1",
            source=Source.SLACK,
            event_type=EventType.MESSAGE,
            content="New paper on transformers and attention mechanisms",
            author="researcher",
            timestamp=datetime.now(),
        ),
        FeedEvent(
            id="test_2",
            source=Source.MASTODON,
            event_type=EventType.MESSAGE,
            content="Check out this spam advertisement",
            author="spammer",
            timestamp=datetime.now(),
        ),
        FeedEvent(
            id="test_3",
            source=Source.BLUESKY,
            event_type=EventType.MENTION,
            content="@user what do you think about neural networks?",
            author="friend",
            timestamp=datetime.now(),
            mentions_user=True
        ),
        FeedEvent(
            id="test_4",
            source=Source.SLACK,
            event_type=EventType.MESSAGE,
            content="Lunch meeting at noon",
            author="colleague",
            timestamp=datetime.now(),
        )
    ]
    
    print(f"\n2. Testing with {len(sample_events)} sample events...")
    
    aggregator = FeedAggregator(settings)
    
    filtered_events = aggregator.interest_filter.filter_events(sample_events)
    
    print(f"\n3. Filtering results:")
    print(f"   Input events: {len(sample_events)}")
    print(f"   Filtered events: {len(filtered_events)}")
    
    print("\n4. Relevant events:")
    for event in filtered_events:
        print(f"\n   [{event.source.value}] {event.author}")
        print(f"   Content: {event.content}")
        print(f"   Relevance score: {event.relevance_score:.1f}")
        print(f"   Tags: {', '.join(event.tags)}")
    
    print("\n" + "=" * 60)
    print("Custom filtering example complete!")


if __name__ == '__main__':
    main()
