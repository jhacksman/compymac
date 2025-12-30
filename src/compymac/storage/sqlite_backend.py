"""
SQLite Storage Backend.

Provides SQLite-based storage for local development and single-machine deployments.
Does not support vector search or full-text search (uses basic LIKE queries).
"""

import sqlite3
import threading
from pathlib import Path
from typing import Any


class SQLiteBackend:
    """
    SQLite storage backend implementation.
    
    Thread-safe via connection-per-thread pattern.
    Does not support vector search or full-text search natively.
    """

    def __init__(self, db_path: Path | str):
        """
        Initialize SQLite backend.
        
        Args:
            db_path: Path to SQLite database file (created if doesn't exist)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Create initial connection to verify path is valid
        self._get_connection()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get thread-local database connection.
        
        Returns:
            SQLite connection for current thread
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.connection = conn
        return self._local.connection

    def execute(self, query: str, params: tuple = ()) -> None:
        """
        Execute a write query.
        
        Args:
            query: SQL query string with ? placeholders
            params: Tuple of parameter values
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

    def execute_many(self, query: str, params_list: list[tuple]) -> None:
        """
        Execute a write query multiple times with different parameters.
        
        Args:
            query: SQL query string with ? placeholders
            params_list: List of parameter tuples
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        conn.commit()

    def fetch_one(self, query: str, params: tuple = ()) -> dict[str, Any] | None:
        """
        Fetch a single row as a dictionary.
        
        Args:
            query: SQL query string with ? placeholders
            params: Tuple of parameter values
            
        Returns:
            Dictionary with column names as keys, or None if no row found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetch_all(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """
        Fetch all matching rows as a list of dictionaries.
        
        Args:
            query: SQL query string with ? placeholders
            params: Tuple of parameter values
            
        Returns:
            List of dictionaries with column names as keys
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def supports_vector_search(self) -> bool:
        """
        SQLite does not support vector search natively.
        
        Returns:
            False
        """
        return False

    def supports_full_text_search(self) -> bool:
        """
        SQLite has FTS5 but we don't use it by default.
        Could be extended to use FTS5 in the future.
        
        Returns:
            False (for now - basic LIKE queries used instead)
        """
        return False

    def close(self) -> None:
        """Close the database connection for current thread."""
        if hasattr(self._local, 'connection') and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None

    def __enter__(self) -> "SQLiteBackend":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close connection."""
        self.close()
