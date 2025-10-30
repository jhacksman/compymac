# MVPReader - Unified Feed Aggregator

An AI-powered feed aggregator that consolidates information from multiple communication platforms (Slack, Mastodon, Bluesky) and uses large language models to highlight relevant content and suggest actions.

## Overview

MVPReader serves as a unified feed reader that retrieves notifications and posts from your accounts on supported platforms, filters them according to your interests, and presents AI-generated summaries with actionable insights. Instead of manually checking numerous apps, MVPReader brings everything together in one place.

## Features

- **Multi-Platform Integration**: Connects to Slack, Mastodon, and Bluesky
- **Intelligent Filtering**: Tags and filters events based on your interests and keywords
- **AI-Powered Analysis**: Uses GPT-4 to generate summaries and suggestions
- **Feedback System**: Upvote/downvote suggestions to improve relevance over time
- **Local Storage**: SQLite database for event storage with configurable retention
- **CLI Interface**: Simple command-line interface for interaction

## Architecture

```
MVPReader/
├── config/           # Configuration management
├── core/             # Core components
│   ├── models.py           # Data models
│   ├── feed_store.py       # SQLite storage
│   ├── interest_filter.py  # Interest-based filtering
│   ├── ai_analyzer.py      # LLM analysis
│   ├── feedback_manager.py # Feedback tracking
│   └── aggregator.py       # Main orchestrator
├── fetchers/         # Platform-specific fetchers
│   ├── slack_fetcher.py
│   ├── mastodon_fetcher.py
│   └── bluesky_fetcher.py
└── cli.py            # Command-line interface
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure API credentials:
```bash
cp config/config.example.json config/config.json
# Edit config.json with your API credentials
```

Alternatively, set environment variables:
```bash
export SLACK_BOT_TOKEN="xoxb-your-token"
export MASTODON_ACCESS_TOKEN="your-token"
export MASTODON_INSTANCE_URL="https://mastodon.social"
export BLUESKY_USERNAME="your-username.bsky.social"
export BLUESKY_PASSWORD="your-app-password"
export OPENAI_API_KEY="sk-your-key"
```

## Configuration

### API Credentials

#### Slack
1. Create a Slack App at https://api.slack.com/apps
2. Add Bot Token Scopes: `channels:read`, `channels:history`, `groups:read`, `groups:history`
3. Install app to workspace and copy the Bot User OAuth Token

#### Mastodon
1. Go to your Mastodon instance settings
2. Navigate to Development → New Application
3. Grant `read:notifications` scope
4. Copy the access token

#### Bluesky
1. Use your Bluesky username (e.g., username.bsky.social)
2. Generate an App Password in settings (not your main password)

#### OpenAI
1. Get API key from https://platform.openai.com/api-keys

### User Interests

Edit `config.json` to customize:
- **keywords**: Terms you want to track (e.g., "AI", "python")
- **topics**: Broader topics of interest
- **ignore_keywords**: Terms to filter out
- **priority_channels**: Specific channels to always include

## Usage

### Command Line Interface

Run an update cycle (fetch, filter, analyze):
```bash
python -m MVPReader update
```

Show last summary:
```bash
python -m MVPReader summary
```

View statistics:
```bash
python -m MVPReader stats
```

Provide feedback on suggestions:
```bash
python -m MVPReader feedback sug_0 upvote
python -m MVPReader feedback sug_1 downvote "Not relevant"
```

Show configuration:
```bash
python -m MVPReader config
```

Interactive mode:
```bash
python -m MVPReader interactive
```

### Python API

```python
from MVPReader.config.settings import Settings
from MVPReader.core.aggregator import FeedAggregator

# Initialize
settings = Settings()
aggregator = FeedAggregator(settings)

# Run update cycle
summary = aggregator.run_update_cycle()

# Display results
print(f"Highlights: {summary.highlights}")
print(f"Suggestions: {summary.suggestions}")
```

## How It Works

1. **Fetch**: Retrieves new events from configured platforms via their APIs
2. **Transform**: Normalizes data into a common `FeedEvent` format
3. **Filter**: Applies interest-based filtering and relevance scoring
4. **Store**: Saves events to local SQLite database
5. **Analyze**: Uses GPT-4 to generate summaries and suggestions
6. **Present**: Displays results in formatted output

## Data Flow

```
[Slack API] ──┐
              │
[Mastodon] ───┼──> [Fetchers] ──> [Filter] ──> [Store] ──> [AI Analyzer] ──> [Summary]
              │                                                    │
[Bluesky] ────┘                                                    │
                                                                   ↓
                                                            [Feedback System]
```

## Interest Filtering

Events are scored based on:
- **User mentions**: +10.0 points
- **Keyword matches**: +2.0 per keyword
- **Topic matches**: +1.0 per topic
- **Direct interactions** (mentions, replies): +3.0 points

Events with ignore keywords are filtered out. Only relevant events (score > 0 or mentions user) are stored and analyzed.

## AI Analysis

The system uses GPT-4 to:
1. Identify important events requiring attention
2. Summarize key highlights in concise format
3. Suggest appropriate actions or responses

The LLM is provided with:
- System prompt describing user interests
- Recent events grouped by source
- Instructions to focus on relevance and actionability

## Feedback Loop

Users can upvote/downvote suggestions to indicate relevance. Feedback is logged for future analysis and can be used to:
- Adjust interest filters
- Refine prompt engineering
- Train ranking algorithms (future enhancement)

## Storage

- **Database**: SQLite at `~/.mvpreader/feed_store.db`
- **Feedback Log**: JSONL at `~/.mvpreader/feedback.jsonl`
- **Retention**: Configurable (default 48 hours)

## Future Enhancements

- **Long-term Memory**: Vector database for historical context
- **Additional Integrations**: Discord, Email, GitHub, Twitter/X
- **Bidirectional Interaction**: Post replies and updates
- **Improved Ranking**: ML-based suggestion ranking
- **Web Dashboard**: User-friendly web interface
- **Real-time Notifications**: Push alerts for critical events
- **Webhook Support**: Real-time event streaming

## Limitations

- **Read-only**: MVP does not post or reply (future feature)
- **No long-term memory**: Relies on LLM context window
- **Rate limits**: Respects API rate limits (may delay updates)
- **Token costs**: OpenAI API usage incurs costs

## Troubleshooting

### No events fetched
- Check API credentials in config
- Verify network connectivity
- Check API rate limits

### AI analysis fails
- Verify OpenAI API key
- Check API quota/billing
- Review error messages in output

### Connection errors
- Test individual fetchers with `test_connection()`
- Verify instance URLs (Mastodon)
- Check authentication tokens

## Contributing

This is an MVP implementation. Contributions welcome for:
- Additional platform integrations
- Improved filtering algorithms
- Better prompt engineering
- UI/UX enhancements

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built for integration with CompyMac project
- Inspired by ElizaOS memory architecture
- Uses AT Protocol for Bluesky integration
- Leverages OpenAI GPT-4 for analysis
