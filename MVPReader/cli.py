"""
Command Line Interface for MVPReader
Provides interactive commands for the feed aggregator
"""

import sys
import argparse
from datetime import datetime

from .config.settings import Settings
from .core.aggregator import FeedAggregator
from .core.feedback_manager import FeedbackManager


class CLI:
    """Command line interface for MVPReader"""
    
    def __init__(self):
        """Initialize CLI"""
        self.settings = Settings()
        self.aggregator = FeedAggregator(self.settings)
        self.feedback_manager = FeedbackManager()
        self.last_summary = None
    
    def run(self):
        """Run the CLI"""
        parser = argparse.ArgumentParser(
            description='MVPReader - Unified Feed Aggregator',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Commands:
  update    - Fetch new events and generate summary
  summary   - Show last generated summary
  stats     - Show statistics
  feedback  - Provide feedback on suggestions
  config    - Show current configuration
  
Examples:
  mvpreader update
  mvpreader summary
  mvpreader feedback sug_0 upvote
            """
        )
        
        parser.add_argument(
            'command',
            choices=['update', 'summary', 'stats', 'feedback', 'config', 'interactive'],
            help='Command to execute'
        )
        
        parser.add_argument(
            'args',
            nargs='*',
            help='Additional arguments for the command'
        )
        
        args = parser.parse_args()
        
        if args.command == 'update':
            self.cmd_update()
        elif args.command == 'summary':
            self.cmd_summary()
        elif args.command == 'stats':
            self.cmd_stats()
        elif args.command == 'feedback':
            self.cmd_feedback(args.args)
        elif args.command == 'config':
            self.cmd_config()
        elif args.command == 'interactive':
            self.cmd_interactive()
    
    def cmd_update(self):
        """Run update cycle and show summary"""
        print("\n🔄 Fetching and analyzing feeds...\n")
        
        summary = self.aggregator.run_update_cycle()
        self.last_summary = summary
        
        self._display_summary(summary)
    
    def cmd_summary(self):
        """Display last summary"""
        if not self.last_summary:
            print("No summary available. Run 'update' first.")
            return
        
        self._display_summary(self.last_summary)
    
    def cmd_stats(self):
        """Display statistics"""
        stats = self.aggregator.get_stats()
        feedback_stats = self.feedback_manager.get_feedback_stats()
        
        print("\n📊 Statistics")
        print("="*60)
        print(f"Total events in store: {stats['total_events']}")
        print(f"Active fetchers: {stats['active_fetchers']}")
        print(f"Fetcher types: {', '.join(stats['fetcher_types'])}")
        print(f"\nFeedback received: {feedback_stats['total']}")
        print(f"Upvotes: {feedback_stats['upvotes']}")
        print(f"Downvotes: {feedback_stats['downvotes']}")
        print(f"Positive ratio: {feedback_stats['ratio']:.1%}")
        print()
    
    def cmd_feedback(self, args):
        """Record feedback on a suggestion"""
        if len(args) < 2:
            print("Usage: mvpreader feedback <suggestion_id> <upvote|downvote> [comment]")
            return
        
        suggestion_id = args[0]
        vote_str = args[1].lower()
        comment = ' '.join(args[2:]) if len(args) > 2 else None
        
        if vote_str not in ['upvote', 'downvote', 'up', 'down', '1', '-1']:
            print("Vote must be 'upvote' or 'downvote'")
            return
        
        vote = 1 if vote_str in ['upvote', 'up', '1'] else -1
        
        feedback = self.feedback_manager.record_feedback(
            suggestion_id, vote, comment
        )
        
        vote_emoji = "👍" if vote > 0 else "👎"
        print(f"\n{vote_emoji} Feedback recorded for {suggestion_id}")
        if comment:
            print(f"Comment: {comment}")
        print()
    
    def cmd_config(self):
        """Display current configuration"""
        print("\n⚙️  Configuration")
        print("="*60)
        
        print("\nAPI Credentials:")
        print(f"  Slack: {'✓ Configured' if self.settings.slack_token else '✗ Not configured'}")
        print(f"  Mastodon: {'✓ Configured' if self.settings.mastodon_token else '✗ Not configured'}")
        print(f"  Bluesky: {'✓ Configured' if self.settings.bluesky_username else '✗ Not configured'}")
        print(f"  OpenAI: {'✓ Configured' if self.settings.openai_api_key else '✗ Not configured'}")
        
        print("\nUser Interests:")
        print(f"  Keywords: {', '.join(self.settings.user_keywords)}")
        print(f"  Topics: {', '.join(self.settings.user_topics)}")
        print(f"  Ignore: {', '.join(self.settings.ignore_keywords)}")
        
        print("\nFeed Settings:")
        print(f"  Retention: {self.settings.retention_hours} hours")
        print(f"  Max events per source: {self.settings.max_events_per_source}")
        print(f"  AI Model: {self.settings.ai_model}")
        print()
    
    def cmd_interactive(self):
        """Run interactive mode"""
        print("\n🤖 MVPReader Interactive Mode")
        print("Type 'help' for commands, 'quit' to exit\n")
        
        while True:
            try:
                command = input("mvpreader> ").strip().lower()
                
                if not command:
                    continue
                
                if command in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if command == 'help':
                    print("\nAvailable commands:")
                    print("  update   - Fetch and analyze feeds")
                    print("  summary  - Show last summary")
                    print("  stats    - Show statistics")
                    print("  config   - Show configuration")
                    print("  help     - Show this help")
                    print("  quit     - Exit interactive mode")
                    print()
                elif command == 'update':
                    self.cmd_update()
                elif command == 'summary':
                    self.cmd_summary()
                elif command == 'stats':
                    self.cmd_stats()
                elif command == 'config':
                    self.cmd_config()
                else:
                    print(f"Unknown command: {command}")
                    print("Type 'help' for available commands")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def _display_summary(self, summary):
        """Display a summary in formatted output"""
        print("\n" + "="*60)
        print(f"📰 Feed Summary - {summary.timestamp.strftime('%Y-%m-%d %I:%M %p')}")
        print("="*60)
        
        print(f"\n📊 Analyzed {summary.event_count} events from {len(summary.sources_analyzed)} sources")
        if summary.sources_analyzed:
            print(f"   Sources: {', '.join(summary.sources_analyzed)}")
        
        if summary.highlights:
            print("\n✨ Highlights:")
            for i, highlight in enumerate(summary.highlights, 1):
                print(f"   {i}. {highlight}")
        else:
            print("\n✨ No highlights to report")
        
        if summary.suggestions:
            print("\n💡 Suggestions:")
            for i, suggestion in enumerate(summary.suggestions, 1):
                sug_id = suggestion.get('id', f'sug_{i}')
                sug_text = suggestion.get('text', str(suggestion))
                print(f"   [{sug_id}] {sug_text}")
            print("\n   💬 Provide feedback: mvpreader feedback <id> upvote/downvote")
        else:
            print("\n💡 No suggestions at this time")
        
        print("\n" + "="*60 + "\n")


def main():
    """Main entry point"""
    cli = CLI()
    cli.run()


if __name__ == '__main__':
    main()
