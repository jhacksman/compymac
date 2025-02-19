-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create memory table with vector support
CREATE TABLE IF NOT EXISTS memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536),  -- Using 1536 dimensions for Venice.ai embeddings
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    surprise_score FLOAT,
    memory_type VARCHAR(10) CHECK (memory_type IN ('stm', 'mtm', 'ltm')),
    context_ids TEXT[] DEFAULT ARRAY[]::TEXT[],
    tags TEXT[] DEFAULT ARRAY[]::TEXT[]
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_memory_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_metadata ON memories USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Create time-series logging table for LLM interactions
CREATE TABLE IF NOT EXISTS llm_interactions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    agent_id TEXT,
    role VARCHAR(20) CHECK (role IN ('user_query', 'assistant_reply')),
    content TEXT NOT NULL,
    model_name TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

-- Create indexes for time-series table
CREATE INDEX IF NOT EXISTS idx_llm_interactions_timestamp ON llm_interactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_llm_interactions_session ON llm_interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_llm_interactions_agent ON llm_interactions(agent_id);
