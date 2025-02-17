"""Exceptions for the memory system."""

class MemoryError(Exception):
    """Base class for memory-related exceptions."""
    pass

class VeniceAPIError(MemoryError):
    """Raised when Venice.ai API operations fail."""
    pass

class ContextWindowExceededError(MemoryError):
    """Raised when context window size exceeds 30k tokens."""
    pass

class InvalidMemoryFormatError(MemoryError):
    """Raised when memory record format is invalid."""
    pass
