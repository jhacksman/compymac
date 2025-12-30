"""
Venice.ai Embedder for generating vector embeddings.

Uses Venice.ai API for embedding generation with caching and rate limiting.
"""

import hashlib
import os
import time
from typing import Any

import httpx


class VeniceEmbedder:
    """
    Embedder that uses Venice.ai API for vector embeddings.

    Features:
    - Single and batch embedding
    - In-memory caching to avoid redundant API calls
    - Rate limiting with exponential backoff
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str = "text-embedding-3-small",
        cache_enabled: bool = True,
        max_retries: int = 3,
    ):
        """
        Initialize Venice.ai embedder.

        Args:
            api_key: Venice.ai API key (defaults to VENICE_API_KEY env var)
            api_base: Venice.ai API base URL (defaults to VENICE_API_BASE env var)
            model: Embedding model to use
            cache_enabled: Whether to cache embeddings
            max_retries: Maximum retries on rate limit
        """
        self.api_key = api_key or os.environ.get("VENICE_API_KEY")
        self.api_base = api_base or os.environ.get(
            "VENICE_API_BASE", "https://api.venice.ai/api/v1"
        )
        self.model = model
        self.cache_enabled = cache_enabled
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError(
                "Venice.ai API key required. Set VENICE_API_KEY env var or pass api_key."
            )

        # In-memory cache: hash(text) -> embedding
        self._cache: dict[str, list[float]] = {}

        # HTTP client
        self._client = httpx.Client(
            base_url=self.api_base,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        # Check cache
        if self.cache_enabled:
            cache_key = self._cache_key(text)
            if cache_key in self._cache:
                return self._cache[cache_key]

        # Call API
        embedding = self._call_api([text])[0]

        # Cache result
        if self.cache_enabled:
            self._cache[cache_key] = embedding

        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Check cache for each text
        results: list[list[float] | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []

        if self.cache_enabled:
            for i, text in enumerate(texts):
                cache_key = self._cache_key(text)
                if cache_key in self._cache:
                    results[i] = self._cache[cache_key]
                else:
                    texts_to_embed.append((i, text))
        else:
            texts_to_embed = list(enumerate(texts))

        # Call API for uncached texts
        if texts_to_embed:
            indices, uncached_texts = zip(*texts_to_embed, strict=True)
            embeddings = self._call_api(list(uncached_texts))

            for i, embedding in zip(indices, embeddings, strict=True):
                results[i] = embedding
                if self.cache_enabled:
                    cache_key = self._cache_key(texts[i])
                    self._cache[cache_key] = embedding

        return [r for r in results if r is not None]

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """
        Call Venice.ai embeddings API.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            Exception: If API call fails after retries
        """
        for attempt in range(self.max_retries):
            try:
                response = self._client.post(
                    "/embeddings",
                    json={
                        "model": self.model,
                        "input": texts,
                    },
                )

                if response.status_code == 429:
                    # Rate limited - exponential backoff
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()

                # Extract embeddings from response
                embeddings = []
                for item in sorted(data["data"], key=lambda x: x["index"]):
                    embeddings.append(item["embedding"])

                return embeddings

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                raise

        raise Exception(f"Failed to get embeddings after {self.max_retries} retries")

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    def cache_size(self) -> int:
        """Get number of cached embeddings."""
        return len(self._cache)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "VeniceEmbedder":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
