"""Mock MemoryDB for testing."""

from typing import Optional, List, Dict
import numpy as np

class MockMemoryDB:
    """Mock database for testing memory operations."""
    
    def __init__(self):
        """Initialize mock database."""
        self.memories = {}
        self.next_id = 1
    
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
        embedding: list[float],
        limit: int = 5,
        memory_type: Optional[str] = None,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        """Retrieve similar memories from mock database."""
        # Convert embeddings to numpy arrays for cosine similarity
        query_embedding = np.array(embedding)
        
        similarities = []
        for memory in self.memories.values():
            if memory_type and memory['memory_type'] != memory_type:
                continue
                
            memory_embedding = np.array(memory['embedding'])
            similarity = np.dot(query_embedding, memory_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(memory_embedding)
            )
            
            if similarity >= min_similarity:
                memory_copy = dict(memory)
                memory_copy['similarity'] = float(similarity)
                similarities.append(memory_copy)
        
        # Sort by similarity and apply limit
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:limit]
