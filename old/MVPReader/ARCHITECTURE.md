# MVPReader Architecture

## Overview

MVPReader is designed as a modular feed aggregation system that follows a pipeline architecture: Fetch → Transform → Filter → Store → Analyze → Present.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Interface                            │
│                    (cli.py, __main__.py)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Feed Aggregator                             │
│                 (core/aggregator.py)                         │
│  - Orchestrates all components                               │
│  - Manages update cycles                                     │
│  - Coordinates data flow                                     │
└──┬────────┬────────┬────────┬────────┬──────────────────────┘
   │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────────┐
│Slack │ │Masto-│ │Blue- │ │Feed  │ │Interest      │
│Fetch │ │don   │ │sky   │ │Store │ │Filter        │
│      │ │Fetch │ │Fetch │ │      │ │              │
└──────┘ └──────┘ └──────┘ └──────┘ └──────────────┘
   │        │        │        │        │
   └────────┴────────┴────────┴────────┘
                     │
                     ▼
            ┌─────────────────┐
            │   AI Analyzer   │
            │  (Venice.ai)    │
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │Feedback Manager │
            └─────────────────┘
```

## Data Flow

### 1. Fetch Phase
```
[Platform APIs] → [Fetchers] → [Raw Events]
```

Each fetcher:
- Authenticates with platform API
- Retrieves new events since last fetch
- Handles rate limiting and errors
- Returns list of raw platform-specific data

### 2. Transform Phase
```
[Raw Events] → [Normalization] → [FeedEvent Objects]
```

Transformation process:
- Converts platform-specific formats to unified FeedEvent model
- Extracts common fields (id, content, author, timestamp)
- Identifies event types (message, mention, reply, etc.)
- Detects user mentions

### 3. Filter Phase
```
[FeedEvent Objects] → [Interest Filter] → [Relevant Events]
```

Filtering logic:
- Checks against ignore keywords (immediate rejection)
- Calculates relevance scores based on:
  - User mentions (+10 points)
  - Keyword matches (+2 per keyword)
  - Topic matches (+1 per topic)
  - Direct interactions (+3 points)
- Adds tags for categorization
- Filters out events with score ≤ 0 (unless mentions user)

### 4. Store Phase
```
[Relevant Events] → [SQLite Database] → [Persistent Storage]
```

Storage features:
- Deduplication by event ID
- Indexing on timestamp, source, processed status
- Automatic cleanup of old events
- Retention policy enforcement

### 5. Analyze Phase
```
[Stored Events] → [AI Analyzer] → [Summary + Suggestions]
```

AI analysis process:
- Retrieves unprocessed events from store
- Groups events by source
- Constructs prompt with:
  - System context (user interests)
  - Formatted event list
  - Analysis instructions
- Calls Venice.ai API (qwen3-next-80b model)
- Parses response into highlights and suggestions
- Marks events as processed

### 6. Present Phase
```
[Summary] → [CLI/Output] → [User Display]
```

Presentation features:
- Formatted console output
- Grouped by highlights and suggestions
- Includes metadata (event count, sources)
- Provides feedback mechanism

## Key Design Decisions

### 1. Unified Event Model
All events from different platforms are normalized into a common `FeedEvent` structure. This allows:
- Platform-agnostic filtering and analysis
- Easy addition of new platforms
- Consistent storage schema

### 2. SQLite for Storage
Chosen for MVP because:
- No external database server needed
- Built into Python
- Sufficient for single-user workload
- Easy to backup and migrate

Future: Could migrate to PostgreSQL with pgvector for semantic search.

### 3. Interest-Based Filtering
Two-stage filtering approach:
1. **Pre-filter**: Remove obviously irrelevant content (ignore keywords)
2. **Scoring**: Calculate relevance based on user interests

This reduces LLM token usage and improves response quality.

### 4. LLM Context Window Strategy
MVP relies on LLM context window rather than vector database because:
- Simpler implementation
- Sufficient for 48-hour retention window
- Avoids embedding generation overhead

Trade-off: Cannot reference older context beyond retention period.

### 5. Feedback Loop
Simple logging approach for MVP:
- Records upvotes/downvotes to JSONL file
- Provides data for future improvements
- Does not automatically adjust behavior (manual tuning)

Future: Could train ranking model or adjust filters based on feedback.

## Module Responsibilities

### config/
- **settings.py**: Configuration management, credential handling, user preferences

### core/
- **models.py**: Data structures (FeedEvent, AISummary, Feedback)
- **feed_store.py**: SQLite database interface
- **interest_filter.py**: Relevance scoring and filtering
- **ai_analyzer.py**: LLM integration and prompt engineering
- **feedback_manager.py**: Feedback logging and statistics
- **aggregator.py**: Main orchestrator, coordinates all components

### fetchers/
- **base.py**: Abstract base class defining fetcher interface
- **slack_fetcher.py**: Slack Web API integration
- **mastodon_fetcher.py**: Mastodon REST API integration
- **bluesky_fetcher.py**: AT Protocol integration

### CLI
- **cli.py**: Command-line interface implementation
- **__main__.py**: Entry point for `python -m MVPReader`

## Extension Points

### Adding New Platforms
1. Create new fetcher class inheriting from `BaseFetcher`
2. Implement `fetch_events()` and `test_connection()` methods
3. Add credentials to settings
4. Register in aggregator's `_init_fetchers()`

### Custom Filtering Logic
1. Extend `InterestFilter` class
2. Override `_calculate_relevance_score()` method
3. Add new configuration options to settings

### Alternative AI Models
1. Modify `AIAnalyzer` class or create new LLMClient implementation
2. Replace Venice.ai client with alternative (DGX Spark, Anthropic, local model, etc.)
3. Adjust prompt format as needed

### Additional Storage Backends
1. Create new class implementing FeedStore interface
2. Maintain same method signatures
3. Update aggregator to use new backend

## Performance Considerations

### Rate Limiting
- Slack: 1 req/min for conversations.history (tier 3)
- Mastodon: Varies by instance (typically 300 req/5min)
- Bluesky: 3000 req/5min for authenticated requests

Strategy: Periodic polling (5-minute intervals) stays well within limits.

### Token Usage
- Average event: ~50 tokens
- 100 events: ~5000 tokens
- LLM prompt: ~6000 tokens total
- Response: ~1000 tokens
- Cost per analysis: Varies by Venice.ai pricing

### Database Size
- Average event: ~1KB
- 1000 events: ~1MB
- 48-hour retention with 100 events/day: ~200KB
- Negligible storage requirements

## Security Considerations

### Credential Storage
- Config file should be in .gitignore
- Environment variables preferred for production
- No credentials in code or logs

### API Token Permissions
- Slack: Read-only scopes (channels:read, channels:history)
- Mastodon: read:notifications only
- Bluesky: App password (not main password)
- Venice.ai: Standard API key

### Data Privacy
- All data stored locally
- No external sharing except Venice.ai API
- User controls retention period
- Can delete database at any time

## Testing Strategy

### Unit Tests
- Model serialization/deserialization
- Interest filtering logic
- Relevance scoring calculations

### Integration Tests
- Mock API responses
- End-to-end data flow
- Database operations

### Manual Testing
- Real API connections
- Live data processing
- UI/UX validation

## Future Architecture Enhancements

### 1. Vector Database Integration
```
[Events] → [Embeddings] → [Vector DB] → [Semantic Search]
```
Enables long-term memory and semantic retrieval.

### 2. Real-time Streaming
```
[Webhooks/SSE] → [Event Queue] → [Real-time Processing]
```
Replace polling with push-based updates.

### 3. Multi-user Support
```
[User Context] → [Isolated Storage] → [Per-user Analysis]
```
Add user authentication and isolated data stores.

### 4. Web Dashboard
```
[FastAPI Backend] → [REST API] → [React Frontend]
```
Modern web interface with real-time updates.

### 5. Bidirectional Integration
```
[User Action] → [API Write] → [Platform Post/Reply]
```
Enable posting and replying through MVPReader.
