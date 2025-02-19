"""Mock memory database for testing."""
import asyncio
from typing import List, Dict, Any, Optional

class MockMemoryDB:
    """Mock memory database for testing."""
    
    def __init__(self):
        """Initialize mock database."""
        self.memories = {}
        self.next_id = 1
        self._lock = asyncio.Lock()
        
    async def cleanup(self):
        """Clean up database."""
        async with self._lock:
            self.memories.clear()
            self.next_id = 1
            
    def store_memory(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        memory_type: str = 'ltm',
        surprise_score: Optional[float] = None,
        context_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> int:
        """Store a memory in the mock database."""
        memory_id = self.next_id
        self.next_id += 1
        
        self.memories[memory_id] = {
            'id': memory_id,
            'content': content,
            'embedding': embedding,
            'metadata': metadata,
            'memory_type': memory_type,
            'surprise_score': surprise_score,
            'context_ids': context_ids or [],
            'tags': tags or []
        }
        
        return memory_id
        
    def retrieve_similar(
        self,
        embedding: List[float],
        limit: int = 5,
        memory_type: Optional[str] = None,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Retrieve similar memories from mock database."""
        # For testing, just return all memories up to limit
        memories = list(self.memories.values())
        if memory_type:
            memories = [m for m in memories if m['memory_type'] == memory_type]
            
        # Add mock similarity scores
        for memory in memories:
            memory['similarity'] = 0.8  # Mock similarity score
            
        return memories[:limit]
