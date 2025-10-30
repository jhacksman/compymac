"""
Feed Aggregator
Main orchestrator that coordinates all components
"""

from typing import List, Optional
from datetime import datetime, timedelta

from ..config.settings import Settings
from ..fetchers import SlackFetcher, MastodonFetcher, BlueskyFetcher
from .feed_store import FeedStore
from .interest_filter import InterestFilter
from .ai_analyzer import AIAnalyzer
from .models import FeedEvent, AISummary


class FeedAggregator:
    """
    Main orchestrator for the feed aggregation system
    Coordinates fetching, filtering, storage, and analysis
    """
    
    def __init__(self, settings: Settings = None):
        """
        Initialize feed aggregator
        
        Args:
            settings: Settings object (creates default if None)
        """
        self.settings = settings or Settings()
        
        self.feed_store = FeedStore()
        self.interest_filter = InterestFilter(self.settings)
        self.ai_analyzer = AIAnalyzer(self.settings)
        
        self.fetchers = []
        self._init_fetchers()
    
    def _init_fetchers(self):
        """Initialize feed fetchers based on configuration"""
        if self.settings.slack_token:
            try:
                slack_fetcher = SlackFetcher({
                    'token': self.settings.slack_token,
                    'workspace': self.settings.config['api_credentials']['slack'].get('workspace', 'Unknown')
                })
                if slack_fetcher.test_connection():
                    self.fetchers.append(slack_fetcher)
                    print("✓ Slack fetcher initialized")
                else:
                    print("✗ Slack connection failed")
            except Exception as e:
                print(f"✗ Error initializing Slack fetcher: {e}")
        
        if self.settings.mastodon_token:
            try:
                mastodon_fetcher = MastodonFetcher({
                    'access_token': self.settings.mastodon_token,
                    'instance_url': self.settings.mastodon_instance
                })
                if mastodon_fetcher.test_connection():
                    self.fetchers.append(mastodon_fetcher)
                    print("✓ Mastodon fetcher initialized")
                else:
                    print("✗ Mastodon connection failed")
            except Exception as e:
                print(f"✗ Error initializing Mastodon fetcher: {e}")
        
        if self.settings.bluesky_username and self.settings.bluesky_password:
            try:
                bluesky_fetcher = BlueskyFetcher({
                    'username': self.settings.bluesky_username,
                    'password': self.settings.bluesky_password
                })
                if bluesky_fetcher.test_connection():
                    self.fetchers.append(bluesky_fetcher)
                    print("✓ Bluesky fetcher initialized")
                else:
                    print("✗ Bluesky connection failed")
            except Exception as e:
                print(f"✗ Error initializing Bluesky fetcher: {e}")
        
        if not self.fetchers:
            print("⚠ Warning: No fetchers initialized. Please configure API credentials.")
    
    def fetch_new_events(self, since: Optional[datetime] = None) -> List[FeedEvent]:
        """
        Fetch new events from all sources
        
        Args:
            since: Only fetch events after this timestamp
            
        Returns:
            List of new FeedEvents
        """
        all_events = []
        
        for fetcher in self.fetchers:
            try:
                events = fetcher.fetch_events(since)
                all_events.extend(events)
                print(f"Fetched {len(events)} events from {fetcher.__class__.__name__}")
            except Exception as e:
                print(f"Error fetching from {fetcher.__class__.__name__}: {e}")
        
        return all_events
    
    def process_events(self, events: List[FeedEvent]) -> List[FeedEvent]:
        """
        Process events through filtering and storage
        
        Args:
            events: List of FeedEvents to process
            
        Returns:
            List of filtered, relevant events
        """
        filtered_events = self.interest_filter.filter_events(events)
        
        added_count = self.feed_store.add_events(filtered_events)
        print(f"Added {added_count} new events to store")
        
        return filtered_events
    
    def generate_summary(
        self, 
        hours: int = None,
        use_unprocessed_only: bool = True
    ) -> AISummary:
        """
        Generate AI summary of recent events
        
        Args:
            hours: Number of hours to look back (uses settings default if None)
            use_unprocessed_only: Only analyze unprocessed events
            
        Returns:
            AISummary object
        """
        if hours is None:
            hours = self.settings.retention_hours
        
        events = self.feed_store.get_recent_events(
            hours=hours,
            processed=False if use_unprocessed_only else None
        )
        
        if not events:
            print("No events to analyze")
            return AISummary(
                timestamp=datetime.now(),
                highlights=["No new events to report"],
                suggestions=[],
                event_count=0,
                sources_analyzed=[]
            )
        
        print(f"Analyzing {len(events)} events...")
        
        summary = self.ai_analyzer.analyze_events(events)
        
        event_ids = [e.id for e in events]
        self.feed_store.mark_processed(event_ids)
        
        return summary
    
    def run_update_cycle(self) -> AISummary:
        """
        Run a complete update cycle: fetch, process, and analyze
        
        Returns:
            AISummary object
        """
        print("\n" + "="*60)
        print("Running feed update cycle...")
        print("="*60)
        
        since = datetime.now() - timedelta(hours=self.settings.retention_hours)
        new_events = self.fetch_new_events(since)
        
        if new_events:
            filtered_events = self.process_events(new_events)
            print(f"Filtered to {len(filtered_events)} relevant events")
        else:
            print("No new events fetched")
        
        summary = self.generate_summary()
        
        self.feed_store.cleanup_old_events(self.settings.retention_hours)
        
        return summary
    
    def get_stats(self) -> dict:
        """Get statistics about the feed store"""
        return {
            'total_events': self.feed_store.get_event_count(),
            'active_fetchers': len(self.fetchers),
            'fetcher_types': [f.__class__.__name__ for f in self.fetchers]
        }
