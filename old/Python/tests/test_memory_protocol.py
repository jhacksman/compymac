"""Tests for memory protocol."""

import pytest
from datetime import datetime, timezone

from ..memory.protocol import MemoryMessage

def test_create_message_success():
    """Test successful message creation."""
    message = MemoryMessage.create(
        role="assistant",
        content="test message",
        agent_id="agent_123",
        conversation_id="conv_456",
        tags=["test", "memory"],
        importance="high"
    )
    
    assert message["role"] == "assistant"
    assert message["content"] == "test message"
    assert isinstance(message["timestamp"], str)
    assert message["metadata"]["agent_id"] == "agent_123"
    assert message["metadata"]["conversation_id"] == "conv_456"
    assert message["metadata"]["tags"] == ["test", "memory"]
    assert message["metadata"]["importance"] == "high"

def test_create_message_minimal():
    """Test message creation with minimal fields."""
    message = MemoryMessage.create(
        role="system",
        content="test message"
    )
    
    assert message["role"] == "system"
    assert message["content"] == "test message"
    assert isinstance(message["timestamp"], str)
    assert message["metadata"]["agent_id"] is None
    assert message["metadata"]["conversation_id"] is None
    assert message["metadata"]["tags"] == []
    assert message["metadata"]["importance"] is None

def test_parse_message_success():
    """Test successful message parsing."""
    raw_message = {
        "role": "user",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": "test message",
        "metadata": {
            "agent_id": "agent_123",
            "conversation_id": "conv_456",
            "tags": ["test"],
            "importance": "high"
        }
    }
    
    message = MemoryMessage.parse(raw_message)
    
    assert message["role"] == "user"
    assert message["content"] == "test message"
    assert message["metadata"]["agent_id"] == "agent_123"
    assert message["metadata"]["tags"] == ["test"]

def test_parse_message_missing_fields():
    """Test message parsing with missing fields."""
    raw_message = {
        "role": "user",
        "content": "test message"
    }
    
    with pytest.raises(ValueError) as exc:
        MemoryMessage.parse(raw_message)
    assert "missing required fields" in str(exc.value).lower()

def test_parse_message_invalid_metadata():
    """Test message parsing with invalid metadata."""
    raw_message = {
        "role": "user",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": "test message",
        "metadata": "invalid"  # Should be dict
    }
    
    with pytest.raises(ValueError) as exc:
        MemoryMessage.parse(raw_message)
    assert "metadata must be a dictionary" in str(exc.value).lower()
