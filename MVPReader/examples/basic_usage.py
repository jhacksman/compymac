"""
Basic usage example for MVPReader
Demonstrates how to use the feed aggregator programmatically
"""

import os
from MVPReader.config.settings import Settings
from MVPReader.core.aggregator import FeedAggregator
from MVPReader.core.feedback_manager import FeedbackManager


def main():
    """Run basic example"""
    
    print("MVPReader - Basic Usage Example")
    print("=" * 60)
    
    settings = Settings()
    
    if not settings.openai_api_key:
        print("\n⚠️  Warning: OpenAI API key not configured")
        print("Set OPENAI_API_KEY environment variable or edit config.json")
        return
    
    print("\n1. Initializing feed aggregator...")
    aggregator = FeedAggregator(settings)
    
    stats = aggregator.get_stats()
    print(f"\n   Active fetchers: {stats['active_fetchers']}")
    print(f"   Fetcher types: {', '.join(stats['fetcher_types'])}")
    
    if stats['active_fetchers'] == 0:
        print("\n⚠️  No fetchers initialized. Please configure API credentials.")
        print("   See README.md for setup instructions.")
        return
    
    print("\n2. Running update cycle (fetch, filter, analyze)...")
    summary = aggregator.run_update_cycle()
    
    print("\n3. Results:")
    print(f"\n   📊 Analyzed {summary.event_count} events")
    print(f"   📡 Sources: {', '.join(summary.sources_analyzed)}")
    
    if summary.highlights:
        print("\n   ✨ Highlights:")
        for i, highlight in enumerate(summary.highlights, 1):
            print(f"      {i}. {highlight}")
    
    if summary.suggestions:
        print("\n   💡 Suggestions:")
        for suggestion in summary.suggestions:
            sug_id = suggestion.get('id', 'unknown')
            sug_text = suggestion.get('text', str(suggestion))
            print(f"      [{sug_id}] {sug_text}")
    
    if summary.suggestions:
        print("\n4. Recording feedback example...")
        feedback_manager = FeedbackManager()
        
        first_suggestion = summary.suggestions[0]
        sug_id = first_suggestion.get('id', 'sug_0')
        
        feedback = feedback_manager.record_feedback(
            suggestion_id=sug_id,
            vote=1,  # Upvote
            comment="This is a helpful example"
        )
        
        print(f"   ✓ Recorded upvote for {sug_id}")
        
        stats = feedback_manager.get_feedback_stats()
        print(f"\n   Feedback stats:")
        print(f"   - Total: {stats['total']}")
        print(f"   - Upvotes: {stats['upvotes']}")
        print(f"   - Downvotes: {stats['downvotes']}")
    
    print("\n" + "=" * 60)
    print("Example complete!")
    print("\nNext steps:")
    print("- Run 'python -m MVPReader update' to fetch new events")
    print("- Run 'python -m MVPReader interactive' for interactive mode")
    print("- See README.md for more usage examples")


if __name__ == '__main__':
    main()
