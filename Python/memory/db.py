"""Database connection and utilities for memory system."""

import os
from typing import Optional
import psycopg2
from psycopg2.extras import Json
import numpy as np

class MemoryDB:
    """Database connection manager for memory system."""
    
    def __init__(self, connection_string: Optional[str] = None):
        """Initialize database connection.
        
        Args:
            connection_string: Optional PostgreSQL connection string.
                             If not provided, will use DATABASE_URL env var.
        """
        self.conn_string = connection_string or os.getenv('DATABASE_URL')
        if not self.conn_string:
            raise ValueError("Database connection string not provided")
        
        # Configure connection pool for efficient resource usage
        self.pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=self.conn_string
        )
        
        # Test connection and create tables if needed
        self.test_connection()
    
    def test_connection(self) -> None:
        """Test database connection and initialize if needed."""
        try:
            with psycopg2.connect(self.conn_string) as conn:
                with conn.cursor() as cur:
                    # Check if pgvector extension is enabled
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_extension WHERE extname = 'vector'
                        );
                    """)
                    result = cur.fetchone()
                    has_vector = result[0] if result else False
                    if not has_vector:
                        raise RuntimeError(
                            "pgvector extension not enabled. Please run migrations."
                        )
        except Exception as e:
            raise ConnectionError(f"Database connection failed: {str(e)}")
    
    def get_connection(self):
        """Get a database connection from the pool."""
        return self.pool.getconn()
        
    def put_connection(self, conn):
        """Return a connection to the pool."""
        self.pool.putconn(conn)
        
    def close(self):
        """Close all pool connections."""
        if hasattr(self, 'pool'):
            self.pool.closeall()
    
    def store_memory(
        self,
        content: str,
        embedding: list[float],
        metadata: dict,
        memory_type: str = 'ltm',
        surprise_score: Optional[float] = None,
        context_ids: Optional[list[str]] = None,
        tags: Optional[list[str]] = None
    ) -> int:
        """Store a memory in the database.
        
        Args:
            content: Text content of the memory
            embedding: Vector embedding from Venice.ai
            metadata: Associated metadata
            memory_type: Type of memory ('stm', 'mtm', 'ltm')
            surprise_score: Optional novelty score
            context_ids: Optional list of related context IDs
            tags: Optional list of tags
            
        Returns:
            ID of the stored memory
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO memories (
                        content, embedding, metadata, memory_type,
                        surprise_score, context_ids, tags
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    content,
                    embedding,
                    Json(metadata),
                    memory_type,
                    surprise_score,
                    context_ids or [],
                    tags or []
                ))
                result = cur.fetchone()
                return int(result[0]) if result else 0
    
    def retrieve_similar(
        self,
        embedding: list[float],
        limit: int = 5,
        memory_type: Optional[str] = None,
        min_similarity: float = 0.7
    ) -> list[dict]:
        """Retrieve similar memories using vector similarity.
        
        Args:
            embedding: Query vector from Venice.ai
            limit: Maximum number of results
            memory_type: Optional filter by memory type
            min_similarity: Minimum cosine similarity threshold
            
        Returns:
            List of similar memories with their metadata
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        id, content, metadata, created_at,
                        surprise_score, memory_type, context_ids, tags,
                        1 - (embedding <=> %s) as similarity
                    FROM memories
                    WHERE 1 - (embedding <=> %s) > %s
                """
                params = [embedding, embedding, min_similarity]
                
                if memory_type:
                    query += " AND memory_type = %s"
                    params.append(memory_type)
                
                query += " ORDER BY similarity DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                results = []
                for row in cur.fetchall():
                    results.append({
                        'id': row[0],
                        'content': row[1],
                        'metadata': row[2],
                        'created_at': row[3],
                        'surprise_score': row[4],
                        'memory_type': row[5],
                        'context_ids': row[6],
                        'tags': row[7],
                        'similarity': row[8]
                    })
                return results
