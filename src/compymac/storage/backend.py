"""
Storage Backend Abstract Base Class.

Defines the interface for pluggable storage backends (SQLite, PostgreSQL).
All storage operations go through this interface to enable backend switching.
"""

from abc import ABC, abstractmethod
from typing import Any


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.

    Implementations must provide:
    - execute(): Run write queries (INSERT, UPDATE, DELETE, CREATE)
    - fetch_one(): Fetch a single row
    - fetch_all(): Fetch all matching rows
    - supports_vector_search(): Whether backend supports vector similarity
    - supports_full_text_search(): Whether backend supports full-text search
    """

    @abstractmethod
    def execute(self, query: str, params: tuple = ()) -> None:
        """
        Execute a write query (INSERT, UPDATE, DELETE, CREATE TABLE, etc.).

        Args:
            query: SQL query string with placeholders
            params: Tuple of parameter values

        Raises:
            Exception: If query execution fails
        """
        pass

    @abstractmethod
    def execute_many(self, query: str, params_list: list[tuple]) -> None:
        """
        Execute a write query multiple times with different parameters.

        Args:
            query: SQL query string with placeholders
            params_list: List of parameter tuples

        Raises:
            Exception: If query execution fails
        """
        pass

    @abstractmethod
    def fetch_one(self, query: str, params: tuple = ()) -> dict[str, Any] | None:
        """
        Fetch a single row as a dictionary.

        Args:
            query: SQL query string with placeholders
            params: Tuple of parameter values

        Returns:
            Dictionary with column names as keys, or None if no row found
        """
        pass

    @abstractmethod
    def fetch_all(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """
        Fetch all matching rows as a list of dictionaries.

        Args:
            query: SQL query string with placeholders
            params: Tuple of parameter values

        Returns:
            List of dictionaries with column names as keys
        """
        pass

    @abstractmethod
    def supports_vector_search(self) -> bool:
        """
        Check if backend supports vector similarity search.

        Returns:
            True if pgvector or similar is available
        """
        pass

    @abstractmethod
    def supports_full_text_search(self) -> bool:
        """
        Check if backend supports full-text search.

        Returns:
            True if tsvector/BM25 or similar is available
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass

    def __enter__(self) -> "StorageBackend":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close connection."""
        self.close()
