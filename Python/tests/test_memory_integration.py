"""Integration tests for memory operations."""

import pytest
import websockets.sync.client as websockets
import json
from datetime import datetime, timezone

from ..memory.protocol import MemoryMessage
from ..memory.exceptions import VeniceAPIError

@pytest.fixture(scope="module")
def server():
    """Create and start mock WebSocket server."""
    from .mock_websocket_server import MockWebSocketServer
    server = MockWebSocketServer()
    server.start()  # Synchronous start
    # Wait for server to be ready
    import time
    time.sleep(1)
    try:
        yield server
    finally:
        server.stop()  # Synchronous stop

@pytest.fixture
def websocket(server):
    try:
        with websockets.connect('ws://localhost:8765') as websocket:
            yield websocket
    except Exception as e:
        pytest.fail(f"Failed to connect to WebSocket server: {str(e)}")


def test_store_memory_roundtrip(websocket):
    """Test complete WebSocket round-trip for store_memory."""
    store_request = MemoryMessage.create(
        role="assistant",
        content="test memory",
        agent_id="test_agent",
        importance="high"
    )
    store_request["action"] = "store_memory"
    
    websocket.send(json.dumps(store_request))
    response = json.loads(websocket.recv())
    
    assert response["status"] == "success"
    assert response["id"] is not None
    assert response["content"] == "test memory"
    assert response["metadata"]["importance"] == "high"

def test_retrieve_context_roundtrip(websocket):
    """Test complete WebSocket round-trip for retrieve_context."""
    # First store a memory
    store_request = MemoryMessage.create(
        role="assistant",
        content="test memory",
        agent_id="test_agent",
        importance="high"
    )
    store_request["action"] = "store_memory"
    
    websocket.send(json.dumps(store_request))
    store_response = json.loads(websocket.recv())
    assert store_response["status"] == "success"
    
    # Then retrieve it
    retrieve_request = {
        "action": "retrieve_context",
        "query": "test memory",
        "filters": {
            "time_range": "1d"
        }
    }
    
    websocket.send(json.dumps(retrieve_request))
    response = json.loads(websocket.recv())
    
    assert response["status"] == "success"
    assert len(response["memories"]) > 0
    assert response["memories"][0]["content"] == "test memory"

def test_update_memory_roundtrip(websocket):
    """Test complete WebSocket round-trip for update_memory."""
    # First store a memory
    store_request = MemoryMessage.create(
        role="assistant",
        content="test memory",
        agent_id="test_agent",
        importance="high"
    )
    store_request["action"] = "store_memory"
    
    websocket.send(json.dumps(store_request))
    store_response = json.loads(websocket.recv())
    assert store_response["status"] == "success"
    memory_id = store_response["id"]
    
    # Then update it
    update_request = {
        "action": "update_memory",
        "memory_id": memory_id,
        "updates": {
            "content": "updated memory",
            "metadata": {"importance": "medium"}
        }
    }
    
    websocket.send(json.dumps(update_request))
    response = json.loads(websocket.recv())
    
    assert response["status"] == "success"
    assert response["content"] == "updated memory"
    assert response["metadata"]["importance"] == "medium"

def test_delete_memory_roundtrip(websocket):
    """Test complete WebSocket round-trip for delete_memory."""
    # First store a memory
    store_request = MemoryMessage.create(
        role="assistant",
        content="test memory",
        agent_id="test_agent",
        importance="high"
    )
    store_request["action"] = "store_memory"
    
    websocket.send(json.dumps(store_request))
    store_response = json.loads(websocket.recv())
    assert store_response["status"] == "success"
    memory_id = store_response["id"]
    
    # Then delete it
    delete_request = {
        "action": "delete_memory",
        "memory_id": memory_id
    }
    
    websocket.send(json.dumps(delete_request))
    response = json.loads(websocket.recv())
    
    assert response["status"] == "success"
    
    # Verify deletion by trying to retrieve
    retrieve_request = {
        "action": "retrieve_context",
        "query": "test memory"
    }
    
    websocket.send(json.dumps(retrieve_request))
    response = json.loads(websocket.recv())
    
    assert response["status"] == "success"
    assert len(response["memories"]) == 0

def test_error_handling(websocket):
    """Test error handling in WebSocket communication."""
    # Try to update non-existent memory
    update_request = {
        "action": "update_memory",
        "memory_id": "nonexistent_id",
        "updates": {"content": "test"}
    }
    
    websocket.send(json.dumps(update_request))
    response = json.loads(websocket.recv())
    
    assert response["status"] == "error"
    assert "memory not found" in response["message"].lower()
