# Context Builder Service Design

## Overview

The Context Builder service is responsible for retrieving and aggregating relevant context from multiple databases to provide the LLM orchestrator with the information needed to respond to user queries. It acts as the intelligent data layer between the user's request and the LLM's response generation.

## Architecture

### Core Components

1. **Context Retriever**: Fetches relevant data from multiple databases
2. **Context Ranker**: Ranks and filters retrieved context by relevance
3. **Context Formatter**: Formats context for LLM consumption
4. **Cache Manager**: Manages context caching for performance

### Database Integration

The Context Builder integrates with four primary databases:

#### 1. pgvector (Vector Similarity Search)
- **Purpose**: Semantic search over embeddings
- **Data**: User conversations, documents, knowledge base articles
- **Query Method**: Cosine similarity search
- **Use Cases**: 
  - Finding similar past conversations
  - Retrieving relevant documentation
  - Semantic knowledge base search

#### 2. PostgreSQL (Structured Data)
- **Purpose**: Relational data storage
- **Data**: User preferences, calendar events, tasks, contacts, financial records
- **Query Method**: SQL queries with indexes
- **Use Cases**:
  - User profile and preferences
  - Scheduled events and reminders
  - Task lists and completion status
  - Contact information

#### 3. Redis (Short-term State)
- **Purpose**: Fast key-value storage for ephemeral data
- **Data**: Active sessions, recent interactions, temporary state
- **Query Method**: Key-value lookups with TTL
- **Use Cases**:
  - Current conversation context
  - Recent user actions
  - Temporary computation results
  - Rate limiting and throttling

#### 4. TimescaleDB (Time-series Data)
- **Purpose**: Time-series data storage and analysis
- **Data**: Weather history, financial prices, sensor readings, usage metrics
- **Query Method**: Time-based queries with aggregations
- **Use Cases**:
  - Historical weather patterns
  - Stock price trends
  - Smart home sensor data
  - Usage analytics

## Implementation

### Context Retriever

```python
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta
import psycopg2
from pgvector.psycopg2 import register_vector
import redis
import numpy as np

class ContextRetriever:
    """Retrieves relevant context from multiple databases"""
    
    def __init__(
        self,
        postgres_conn: psycopg2.connection,
        redis_client: redis.Redis,
        timescale_conn: psycopg2.connection,
        llm_client: Any  # QwenLLMClient for embeddings
    ):
        self.postgres = postgres_conn
        self.redis = redis_client
        self.timescale = timescale_conn
        self.llm = llm_client
        
        # Register pgvector extension
        register_vector(self.postgres)
    
    async def retrieve_context(
        self,
        query: str,
        user_id: str,
        context_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context from all databases
        
        Args:
            query: User's query text
            user_id: User identifier
            context_types: Types of context to retrieve (default: all)
        
        Returns:
            Dictionary containing retrieved context from all sources
        """
        if context_types is None:
            context_types = [
                "semantic", "user_profile", "calendar", "tasks",
                "recent_interactions", "weather", "financial", "smart_home"
            ]
        
        # Generate query embedding for semantic search
        query_embedding = self.llm.get_embedding(query)
        
        # Retrieve context from all sources in parallel
        tasks = []
        
        if "semantic" in context_types:
            tasks.append(self._retrieve_semantic_context(query_embedding, user_id))
        
        if "user_profile" in context_types:
            tasks.append(self._retrieve_user_profile(user_id))
        
        if "calendar" in context_types:
            tasks.append(self._retrieve_calendar_events(user_id))
        
        if "tasks" in context_types:
            tasks.append(self._retrieve_tasks(user_id))
        
        if "recent_interactions" in context_types:
            tasks.append(self._retrieve_recent_interactions(user_id))
        
        if "weather" in context_types:
            tasks.append(self._retrieve_weather_context(user_id))
        
        if "financial" in context_types:
            tasks.append(self._retrieve_financial_context(user_id))
        
        if "smart_home" in context_types:
            tasks.append(self._retrieve_smart_home_context(user_id))
        
        # Execute all retrievals in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        context = {}
        for i, context_type in enumerate(context_types):
            if i < len(results) and not isinstance(results[i], Exception):
                context[context_type] = results[i]
            else:
                context[context_type] = None
        
        return context
    
    async def _retrieve_semantic_context(
        self,
        query_embedding: List[float],
        user_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve semantically similar content from pgvector"""
        cursor = self.postgres.cursor()
        
        # Convert embedding to numpy array for pgvector
        embedding_array = np.array(query_embedding)
        
        # Query pgvector for similar embeddings
        cursor.execute("""
            SELECT 
                id,
                content,
                metadata,
                1 - (embedding <=> %s::vector) AS similarity
            FROM knowledge_base
            WHERE user_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (embedding_array, user_id, embedding_array, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "content": row[1],
                "metadata": row[2],
                "similarity": row[3]
            })
        
        cursor.close()
        return results
    
    async def _retrieve_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Retrieve user profile and preferences from PostgreSQL"""
        cursor = self.postgres.cursor()
        
        cursor.execute("""
            SELECT 
                name,
                email,
                preferences,
                timezone,
                location
            FROM users
            WHERE id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                "name": row[0],
                "email": row[1],
                "preferences": row[2],
                "timezone": row[3],
                "location": row[4]
            }
        return None
    
    async def _retrieve_calendar_events(
        self,
        user_id: str,
        days_ahead: int = 7
    ) -> List[Dict[str, Any]]:
        """Retrieve upcoming calendar events from PostgreSQL"""
        cursor = self.postgres.cursor()
        
        end_date = datetime.now() + timedelta(days=days_ahead)
        
        cursor.execute("""
            SELECT 
                id,
                title,
                description,
                start_time,
                end_time,
                location
            FROM calendar_events
            WHERE user_id = %s
              AND start_time >= NOW()
              AND start_time <= %s
            ORDER BY start_time ASC
            LIMIT 20
        """, (user_id, end_date))
        
        events = []
        for row in cursor.fetchall():
            events.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "start_time": row[3].isoformat(),
                "end_time": row[4].isoformat(),
                "location": row[5]
            })
        
        cursor.close()
        return events
    
    async def _retrieve_tasks(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieve active tasks from PostgreSQL"""
        cursor = self.postgres.cursor()
        
        cursor.execute("""
            SELECT 
                id,
                title,
                description,
                priority,
                due_date,
                status
            FROM tasks
            WHERE user_id = %s
              AND status != 'completed'
            ORDER BY priority DESC, due_date ASC
            LIMIT 20
        """, (user_id,))
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "priority": row[3],
                "due_date": row[4].isoformat() if row[4] else None,
                "status": row[5]
            })
        
        cursor.close()
        return tasks
    
    async def _retrieve_recent_interactions(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve recent interactions from Redis"""
        # Get recent conversation turns from Redis
        key = f"user:{user_id}:recent_interactions"
        interactions = self.redis.lrange(key, 0, limit - 1)
        
        return [
            eval(interaction.decode('utf-8'))
            for interaction in interactions
        ]
    
    async def _retrieve_weather_context(self, user_id: str) -> Dict[str, Any]:
        """Retrieve weather data from TimescaleDB"""
        cursor = self.timescale.cursor()
        
        # Get user location
        user_profile = await self._retrieve_user_profile(user_id)
        if not user_profile or not user_profile.get("location"):
            return None
        
        location = user_profile["location"]
        
        # Get current weather and forecast
        cursor.execute("""
            SELECT 
                time,
                temperature,
                humidity,
                conditions,
                forecast
            FROM weather_data
            WHERE location = %s
              AND time >= NOW() - INTERVAL '1 hour'
            ORDER BY time DESC
            LIMIT 1
        """, (location,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                "time": row[0].isoformat(),
                "temperature": row[1],
                "humidity": row[2],
                "conditions": row[3],
                "forecast": row[4]
            }
        return None
    
    async def _retrieve_financial_context(self, user_id: str) -> Dict[str, Any]:
        """Retrieve financial data from TimescaleDB"""
        cursor = self.timescale.cursor()
        
        # Get user's tracked stocks/crypto
        cursor.execute("""
            SELECT DISTINCT symbol
            FROM user_watchlist
            WHERE user_id = %s
        """, (user_id,))
        
        symbols = [row[0] for row in cursor.fetchall()]
        
        if not symbols:
            cursor.close()
            return None
        
        # Get latest prices for tracked symbols
        cursor.execute("""
            SELECT 
                symbol,
                time,
                price,
                change_percent
            FROM financial_data
            WHERE symbol = ANY(%s)
              AND time >= NOW() - INTERVAL '1 hour'
            ORDER BY time DESC
        """, (symbols,))
        
        prices = []
        for row in cursor.fetchall():
            prices.append({
                "symbol": row[0],
                "time": row[1].isoformat(),
                "price": float(row[2]),
                "change_percent": float(row[3])
            })
        
        cursor.close()
        return {"watchlist": prices}
    
    async def _retrieve_smart_home_context(self, user_id: str) -> Dict[str, Any]:
        """Retrieve smart home device states from TimescaleDB"""
        cursor = self.timescale.cursor()
        
        # Get latest device states
        cursor.execute("""
            SELECT 
                device_id,
                device_name,
                device_type,
                state,
                time
            FROM smart_home_states
            WHERE user_id = %s
              AND time >= NOW() - INTERVAL '5 minutes'
            ORDER BY time DESC
        """, (user_id,))
        
        devices = []
        for row in cursor.fetchall():
            devices.append({
                "device_id": row[0],
                "device_name": row[1],
                "device_type": row[2],
                "state": row[3],
                "time": row[4].isoformat()
            })
        
        cursor.close()
        return {"devices": devices}
```

### Context Ranker

```python
from typing import List, Dict, Any
import numpy as np

class ContextRanker:
    """Ranks and filters retrieved context by relevance"""
    
    def __init__(self, llm_client: Any):
        self.llm = llm_client
    
    def rank_context(
        self,
        query: str,
        context: Dict[str, Any],
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Rank and filter context to fit within token budget
        
        Args:
            query: User's query text
            context: Retrieved context from all sources
            max_tokens: Maximum tokens to include in context
        
        Returns:
            Ranked and filtered context
        """
        ranked_context = {}
        
        # Priority order for context types
        priority_order = [
            "recent_interactions",  # Always include recent conversation
            "user_profile",         # User preferences and settings
            "semantic",             # Semantically similar content
            "calendar",             # Upcoming events
            "tasks",                # Active tasks
            "weather",              # Current weather
            "financial",            # Financial data
            "smart_home"            # Smart home states
        ]
        
        current_tokens = 0
        
        for context_type in priority_order:
            if context_type not in context or context[context_type] is None:
                continue
            
            # Estimate tokens for this context type
            context_str = str(context[context_type])
            estimated_tokens = len(context_str) // 4  # Rough estimate
            
            if current_tokens + estimated_tokens <= max_tokens:
                ranked_context[context_type] = context[context_type]
                current_tokens += estimated_tokens
            else:
                # Try to include partial context
                remaining_tokens = max_tokens - current_tokens
                if remaining_tokens > 100:  # Only include if meaningful
                    ranked_context[context_type] = self._truncate_context(
                        context[context_type],
                        remaining_tokens
                    )
                break
        
        return ranked_context
    
    def _truncate_context(
        self,
        context: Any,
        max_tokens: int
    ) -> Any:
        """Truncate context to fit within token budget"""
        if isinstance(context, list):
            # For lists, take first N items
            truncated = []
            current_tokens = 0
            for item in context:
                item_tokens = len(str(item)) // 4
                if current_tokens + item_tokens <= max_tokens:
                    truncated.append(item)
                    current_tokens += item_tokens
                else:
                    break
            return truncated
        elif isinstance(context, dict):
            # For dicts, include all keys but truncate values
            truncated = {}
            for key, value in context.items():
                value_str = str(value)
                if len(value_str) > max_tokens * 4:
                    truncated[key] = value_str[:max_tokens * 4] + "..."
                else:
                    truncated[key] = value
            return truncated
        else:
            # For strings, truncate directly
            context_str = str(context)
            if len(context_str) > max_tokens * 4:
                return context_str[:max_tokens * 4] + "..."
            return context
```

### Context Formatter

```python
from typing import Dict, Any

class ContextFormatter:
    """Formats context for LLM consumption"""
    
    def format_context(self, context: Dict[str, Any]) -> str:
        """
        Format context into a structured string for LLM
        
        Args:
            context: Ranked and filtered context
        
        Returns:
            Formatted context string
        """
        sections = []
        
        # Recent interactions
        if "recent_interactions" in context and context["recent_interactions"]:
            sections.append(self._format_recent_interactions(
                context["recent_interactions"]
            ))
        
        # User profile
        if "user_profile" in context and context["user_profile"]:
            sections.append(self._format_user_profile(
                context["user_profile"]
            ))
        
        # Semantic context
        if "semantic" in context and context["semantic"]:
            sections.append(self._format_semantic_context(
                context["semantic"]
            ))
        
        # Calendar events
        if "calendar" in context and context["calendar"]:
            sections.append(self._format_calendar_events(
                context["calendar"]
            ))
        
        # Tasks
        if "tasks" in context and context["tasks"]:
            sections.append(self._format_tasks(context["tasks"]))
        
        # Weather
        if "weather" in context and context["weather"]:
            sections.append(self._format_weather(context["weather"]))
        
        # Financial
        if "financial" in context and context["financial"]:
            sections.append(self._format_financial(context["financial"]))
        
        # Smart home
        if "smart_home" in context and context["smart_home"]:
            sections.append(self._format_smart_home(context["smart_home"]))
        
        return "\n\n".join(sections)
    
    def _format_recent_interactions(
        self,
        interactions: List[Dict[str, Any]]
    ) -> str:
        """Format recent interactions"""
        lines = ["## Recent Conversation"]
        for interaction in interactions:
            role = interaction.get("role", "user")
            content = interaction.get("content", "")
            lines.append(f"{role.capitalize()}: {content}")
        return "\n".join(lines)
    
    def _format_user_profile(self, profile: Dict[str, Any]) -> str:
        """Format user profile"""
        lines = ["## User Profile"]
        if profile.get("name"):
            lines.append(f"Name: {profile['name']}")
        if profile.get("timezone"):
            lines.append(f"Timezone: {profile['timezone']}")
        if profile.get("location"):
            lines.append(f"Location: {profile['location']}")
        if profile.get("preferences"):
            lines.append(f"Preferences: {profile['preferences']}")
        return "\n".join(lines)
    
    def _format_semantic_context(
        self,
        semantic: List[Dict[str, Any]]
    ) -> str:
        """Format semantic context"""
        lines = ["## Relevant Knowledge"]
        for i, item in enumerate(semantic, 1):
            similarity = item.get("similarity", 0)
            content = item.get("content", "")
            lines.append(f"{i}. (Similarity: {similarity:.2f}) {content}")
        return "\n".join(lines)
    
    def _format_calendar_events(
        self,
        events: List[Dict[str, Any]]
    ) -> str:
        """Format calendar events"""
        lines = ["## Upcoming Events"]
        for event in events:
            title = event.get("title", "")
            start = event.get("start_time", "")
            lines.append(f"- {title} at {start}")
        return "\n".join(lines)
    
    def _format_tasks(self, tasks: List[Dict[str, Any]]) -> str:
        """Format tasks"""
        lines = ["## Active Tasks"]
        for task in tasks:
            title = task.get("title", "")
            priority = task.get("priority", "")
            due = task.get("due_date", "")
            lines.append(f"- [{priority}] {title}" + (f" (Due: {due})" if due else ""))
        return "\n".join(lines)
    
    def _format_weather(self, weather: Dict[str, Any]) -> str:
        """Format weather"""
        lines = ["## Current Weather"]
        if weather.get("temperature"):
            lines.append(f"Temperature: {weather['temperature']}°F")
        if weather.get("conditions"):
            lines.append(f"Conditions: {weather['conditions']}")
        if weather.get("forecast"):
            lines.append(f"Forecast: {weather['forecast']}")
        return "\n".join(lines)
    
    def _format_financial(self, financial: Dict[str, Any]) -> str:
        """Format financial data"""
        lines = ["## Financial Watchlist"]
        watchlist = financial.get("watchlist", [])
        for item in watchlist:
            symbol = item.get("symbol", "")
            price = item.get("price", 0)
            change = item.get("change_percent", 0)
            lines.append(f"- {symbol}: ${price:.2f} ({change:+.2f}%)")
        return "\n".join(lines)
    
    def _format_smart_home(self, smart_home: Dict[str, Any]) -> str:
        """Format smart home states"""
        lines = ["## Smart Home Devices"]
        devices = smart_home.get("devices", [])
        for device in devices:
            name = device.get("device_name", "")
            state = device.get("state", "")
            lines.append(f"- {name}: {state}")
        return "\n".join(lines)
```

### Cache Manager

```python
import hashlib
import json
from typing import Any, Optional
import redis

class CacheManager:
    """Manages context caching for performance"""
    
    def __init__(self, redis_client: redis.Redis, ttl: int = 300):
        self.redis = redis_client
        self.ttl = ttl  # Cache TTL in seconds
    
    def get_cached_context(
        self,
        query: str,
        user_id: str,
        context_types: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get cached context if available"""
        cache_key = self._generate_cache_key(query, user_id, context_types)
        cached = self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached.decode('utf-8'))
        return None
    
    def cache_context(
        self,
        query: str,
        user_id: str,
        context_types: List[str],
        context: Dict[str, Any]
    ):
        """Cache context for future use"""
        cache_key = self._generate_cache_key(query, user_id, context_types)
        self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(context)
        )
    
    def _generate_cache_key(
        self,
        query: str,
        user_id: str,
        context_types: List[str]
    ) -> str:
        """Generate cache key from query and parameters"""
        key_data = f"{user_id}:{query}:{','.join(sorted(context_types))}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()
        return f"context_cache:{key_hash}"
```

### Complete Context Builder Service

```python
class ContextBuilderService:
    """Complete Context Builder service"""
    
    def __init__(
        self,
        postgres_conn: psycopg2.connection,
        redis_client: redis.Redis,
        timescale_conn: psycopg2.connection,
        llm_client: Any
    ):
        self.retriever = ContextRetriever(
            postgres_conn,
            redis_client,
            timescale_conn,
            llm_client
        )
        self.ranker = ContextRanker(llm_client)
        self.formatter = ContextFormatter()
        self.cache = CacheManager(redis_client)
    
    async def build_context(
        self,
        query: str,
        user_id: str,
        context_types: List[str] = None,
        max_tokens: int = 4000
    ) -> str:
        """
        Build formatted context for LLM
        
        Args:
            query: User's query text
            user_id: User identifier
            context_types: Types of context to retrieve (default: all)
            max_tokens: Maximum tokens to include in context
        
        Returns:
            Formatted context string ready for LLM
        """
        # Check cache first
        cached_context = self.cache.get_cached_context(
            query,
            user_id,
            context_types or []
        )
        
        if cached_context:
            return self.formatter.format_context(cached_context)
        
        # Retrieve context from all sources
        context = await self.retriever.retrieve_context(
            query,
            user_id,
            context_types
        )
        
        # Rank and filter context
        ranked_context = self.ranker.rank_context(
            query,
            context,
            max_tokens
        )
        
        # Cache for future use
        self.cache.cache_context(
            query,
            user_id,
            context_types or [],
            ranked_context
        )
        
        # Format for LLM
        formatted_context = self.formatter.format_context(ranked_context)
        
        return formatted_context
```

## Database Schema

### PostgreSQL Schema

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    preferences JSONB,
    timezone VARCHAR(50),
    location VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Calendar events table
CREATE TABLE calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    location VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_calendar_events_user_time ON calendar_events(user_id, start_time);

-- Tasks table
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    priority VARCHAR(20) CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    due_date TIMESTAMP,
    status VARCHAR(20) CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);

-- Knowledge base table with pgvector
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1536),  -- Dimension depends on embedding model
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_knowledge_base_embedding ON knowledge_base USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_knowledge_base_user ON knowledge_base(user_id);

-- User watchlist for financial tracking
CREATE TABLE user_watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    asset_type VARCHAR(20) CHECK (asset_type IN ('stock', 'crypto', 'forex')),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);
```

### TimescaleDB Schema

```sql
-- Weather data (hypertable)
CREATE TABLE weather_data (
    time TIMESTAMPTZ NOT NULL,
    location VARCHAR(255) NOT NULL,
    temperature REAL,
    humidity REAL,
    conditions VARCHAR(100),
    forecast JSONB
);

SELECT create_hypertable('weather_data', 'time');
CREATE INDEX idx_weather_location_time ON weather_data(location, time DESC);

-- Financial data (hypertable)
CREATE TABLE financial_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price NUMERIC(20, 8),
    volume BIGINT,
    change_percent REAL
);

SELECT create_hypertable('financial_data', 'time');
CREATE INDEX idx_financial_symbol_time ON financial_data(symbol, time DESC);

-- Smart home states (hypertable)
CREATE TABLE smart_home_states (
    time TIMESTAMPTZ NOT NULL,
    user_id UUID NOT NULL,
    device_id VARCHAR(100) NOT NULL,
    device_name VARCHAR(255),
    device_type VARCHAR(50),
    state JSONB
);

SELECT create_hypertable('smart_home_states', 'time');
CREATE INDEX idx_smart_home_user_time ON smart_home_states(user_id, time DESC);
```

### Redis Schema

```
# Recent interactions (list)
user:{user_id}:recent_interactions -> List of JSON-encoded interaction objects

# Context cache (string with TTL)
context_cache:{hash} -> JSON-encoded context (TTL: 5 minutes)

# Session state (hash)
session:{session_id} -> Hash of session data

# Rate limiting (string with TTL)
rate_limit:{user_id}:{endpoint} -> Request count (TTL: 1 minute)
```

## Performance Considerations

### Optimization Strategies

1. **Parallel Retrieval**: Fetch from all databases concurrently using asyncio
2. **Caching**: Cache frequently accessed context in Redis with appropriate TTL
3. **Indexing**: Proper database indexes for fast queries
4. **Connection Pooling**: Reuse database connections
5. **Lazy Loading**: Only retrieve context types that are needed
6. **Token Budget**: Limit context size to fit within LLM's context window

### Monitoring

```python
import time
from typing import Dict, Any

class ContextBuilderMetrics:
    """Metrics collection for Context Builder"""
    
    def __init__(self):
        self.retrieval_times = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def record_retrieval_time(self, context_type: str, duration: float):
        """Record retrieval time for a context type"""
        if context_type not in self.retrieval_times:
            self.retrieval_times[context_type] = []
        self.retrieval_times[context_type].append(duration)
    
    def record_cache_hit(self):
        """Record cache hit"""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        self.cache_misses += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        avg_times = {}
        for context_type, times in self.retrieval_times.items():
            avg_times[context_type] = sum(times) / len(times)
        
        total_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            "average_retrieval_times": avg_times,
            "cache_hit_rate": cache_hit_rate,
            "total_requests": total_requests
        }
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_context_retriever():
    """Test context retrieval from multiple databases"""
    # Mock database connections
    postgres_mock = Mock()
    redis_mock = Mock()
    timescale_mock = Mock()
    llm_mock = Mock()
    
    # Mock LLM embedding
    llm_mock.get_embedding.return_value = [0.1] * 1536
    
    retriever = ContextRetriever(
        postgres_mock,
        redis_mock,
        timescale_mock,
        llm_mock
    )
    
    # Test retrieval
    context = await retriever.retrieve_context(
        "What's the weather today?",
        "user-123",
        ["weather", "user_profile"]
    )
    
    assert "weather" in context
    assert "user_profile" in context

@pytest.mark.asyncio
async def test_context_ranker():
    """Test context ranking and filtering"""
    llm_mock = Mock()
    ranker = ContextRanker(llm_mock)
    
    context = {
        "semantic": [{"content": "test" * 100}],
        "user_profile": {"name": "Test User"},
        "calendar": [{"title": "Meeting"}]
    }
    
    ranked = ranker.rank_context(
        "test query",
        context,
        max_tokens=100
    )
    
    # Should prioritize user_profile and calendar over semantic
    assert "user_profile" in ranked
    assert "calendar" in ranked

def test_context_formatter():
    """Test context formatting"""
    formatter = ContextFormatter()
    
    context = {
        "user_profile": {"name": "Test User", "timezone": "UTC"},
        "calendar": [{"title": "Meeting", "start_time": "2025-10-29T10:00:00"}]
    }
    
    formatted = formatter.format_context(context)
    
    assert "Test User" in formatted
    assert "Meeting" in formatted
    assert "## User Profile" in formatted
    assert "## Upcoming Events" in formatted
```

## Deployment

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: passfel
      POSTGRES_USER: passfel
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
  
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_DB: passfel_timeseries
      POSTGRES_USER: passfel
      POSTGRES_PASSWORD: ${TIMESCALE_PASSWORD}
    volumes:
      - timescale_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"

volumes:
  postgres_data:
  redis_data:
  timescale_data:
```

## Conclusion

The Context Builder service provides a robust, scalable architecture for retrieving and aggregating relevant context from multiple databases. It integrates seamlessly with the LLM orchestrator to provide rich, personalized context for every user interaction.

**Key Features:**
- Multi-database integration (pgvector, PostgreSQL, Redis, TimescaleDB)
- Parallel retrieval for performance
- Intelligent ranking and filtering
- Context caching for efficiency
- Flexible context type selection
- Token budget management
- Comprehensive monitoring and metrics

---

*Last Updated: 2025-10-29*
*Design document for PASSFEL Context Builder Service*
