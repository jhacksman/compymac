"""
PostgreSQL Storage Backend with pgvector support.

Provides PostgreSQL-based storage for production deployments with:
- pgvector for vector similarity search
- tsvector for full-text search (BM25-like)
- Connection pooling for concurrent access
"""

from typing import Any

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class PostgresBackend:
    """
    PostgreSQL storage backend implementation with pgvector support.

    Requires psycopg2 and a PostgreSQL server with pgvector extension.
    Uses connection pooling for thread-safe concurrent access.
    """

    def __init__(
        self,
        connection_string: str,
        min_connections: int = 1,
        max_connections: int = 10,
    ):
        """
        Initialize PostgreSQL backend.

        Args:
            connection_string: PostgreSQL connection URL
            min_connections: Minimum pool size
            max_connections: Maximum pool size

        Raises:
            ImportError: If psycopg2 is not installed
            Exception: If connection fails
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError(
                "psycopg2 is required for PostgresBackend. "
                "Install with: pip install psycopg2-binary"
            )

        self.connection_string = connection_string
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            min_connections,
            max_connections,
            connection_string,
        )

        # Check if pgvector extension is available
        self._has_pgvector = self._check_pgvector()
        self._has_fts = True  # PostgreSQL always has tsvector

    def _check_pgvector(self) -> bool:
        """Check if pgvector extension is installed."""
        try:
            result = self.fetch_one(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            )
            return result is not None
        except Exception:
            return False

    def _get_connection(self) -> Any:
        """Get a connection from the pool."""
        return self._pool.getconn()

    def _put_connection(self, conn: Any) -> None:
        """Return a connection to the pool."""
        self._pool.putconn(conn)

    def execute(self, query: str, params: tuple = ()) -> None:
        """
        Execute a write query.

        Args:
            query: SQL query string with %s placeholders
            params: Tuple of parameter values
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
            conn.commit()
        finally:
            self._put_connection(conn)

    def execute_many(self, query: str, params_list: list[tuple]) -> None:
        """
        Execute a write query multiple times with different parameters.

        Args:
            query: SQL query string with %s placeholders
            params_list: List of parameter tuples
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(query, params_list)
            conn.commit()
        finally:
            self._put_connection(conn)

    def fetch_one(self, query: str, params: tuple = ()) -> dict[str, Any] | None:
        """
        Fetch a single row as a dictionary.

        Args:
            query: SQL query string with %s placeholders
            params: Tuple of parameter values

        Returns:
            Dictionary with column names as keys, or None if no row found
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
                if row is None:
                    return None
                return dict(row)
        finally:
            self._put_connection(conn)

    def fetch_all(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        """
        Fetch all matching rows as a list of dictionaries.

        Args:
            query: SQL query string with %s placeholders
            params: Tuple of parameter values

        Returns:
            List of dictionaries with column names as keys
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        finally:
            self._put_connection(conn)

    def supports_vector_search(self) -> bool:
        """
        Check if pgvector extension is available.

        Returns:
            True if pgvector is installed
        """
        return self._has_pgvector

    def supports_full_text_search(self) -> bool:
        """
        PostgreSQL always supports full-text search via tsvector.

        Returns:
            True
        """
        return self._has_fts

    def vector_search(
        self,
        table: str,
        embedding_column: str,
        query_embedding: list[float],
        limit: int = 10,
        where_clause: str = "",
        where_params: tuple = (),
    ) -> list[dict[str, Any]]:
        """
        Perform vector similarity search using pgvector.

        Args:
            table: Table name
            embedding_column: Column containing embeddings
            query_embedding: Query vector
            limit: Maximum results
            where_clause: Optional WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause

        Returns:
            List of rows ordered by similarity (closest first)

        Raises:
            RuntimeError: If pgvector is not available
        """
        if not self._has_pgvector:
            raise RuntimeError("pgvector extension is not installed")

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        where = f"WHERE {where_clause}" if where_clause else ""
        query = f"""
            SELECT *, {embedding_column} <-> %s::vector AS distance
            FROM {table}
            {where}
            ORDER BY {embedding_column} <-> %s::vector
            LIMIT %s
        """

        params = (embedding_str, embedding_str, limit) + where_params
        return self.fetch_all(query, params)

    def full_text_search(
        self,
        table: str,
        tsvector_column: str,
        query: str,
        limit: int = 10,
        where_clause: str = "",
        where_params: tuple = (),
    ) -> list[dict[str, Any]]:
        """
        Perform full-text search using tsvector.

        Args:
            table: Table name
            tsvector_column: Column containing tsvector
            query: Search query (will be converted to tsquery)
            limit: Maximum results
            where_clause: Optional WHERE clause (without WHERE keyword)
            where_params: Parameters for WHERE clause

        Returns:
            List of rows ordered by relevance
        """
        where = f"WHERE {where_clause} AND" if where_clause else "WHERE"
        sql = f"""
            SELECT *, ts_rank({tsvector_column}, plainto_tsquery(%s)) AS rank
            FROM {table}
            {where} {tsvector_column} @@ plainto_tsquery(%s)
            ORDER BY rank DESC
            LIMIT %s
        """

        params = (query, query, limit) + where_params
        return self.fetch_all(sql, params)

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()

    def __enter__(self) -> "PostgresBackend":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close all connections."""
        self.close()
