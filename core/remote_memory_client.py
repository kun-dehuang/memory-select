"""Remote HTTP client for Memory API.

This module provides a client wrapper for calling the remote Memory API
over HTTP instead of using local services.
"""

import time
from typing import Any, Optional
import httpx


class RemoteMemoryClient:
    """HTTP client for remote Memory API.

    Provides methods to interact with the remote Memory API deployed on Railway.
    All methods use HTTP requests to communicate with the remote service.
    """

    def __init__(self, base_url: str, timeout: float = 120.0):
        """Initialize the remote memory client.

        Args:
            base_url: Base URL of the remote API (e.g., https://memory-select-production.up.railway.app)
            timeout: Request timeout in seconds (default: 120)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def add(self, uid: str, text: str, metadata: Optional[dict[str, Any]] = None) -> str:
        """Add a new memory.

        Args:
            uid: User ID for memory isolation
            text: Memory text content
            metadata: Additional metadata (optional)

        Returns:
            Memory ID of the added memory

        Raises:
            httpx.HTTPError: If the request fails
        """
        response = self.client.post(
            f"{self.base_url}/api/v1/memory/add",
            json={
                "uid": uid,
                "text": text,
                "metadata": metadata or {}
            }
        )
        response.raise_for_status()
        data = response.json()
        return data.get("memory_id", "")

    def add_batch(self, records: list[dict[str, Any]]) -> list[str]:
        """Add multiple memories in batch.

        Args:
            records: List of records, each with 'uid', 'text', and optional 'meta' keys

        Returns:
            List of memory IDs
        """
        memory_ids = []
        for record in records:
            uid = record.get("uid", "default")
            text = record.get("text", "")
            metadata = record.get("meta", {})
            memory_id = self.add(uid, text, metadata)
            memory_ids.append(memory_id)
        return memory_ids

    def search(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None
    ) -> list["SearchResult"]:
        """Search memories using vector similarity and graph relationships.

        Args:
            query: Search query text
            limit: Maximum number of results
            uid: User ID filter (optional)

        Returns:
            List of SearchResult objects

        Raises:
            httpx.HTTPError: If the request fails
        """
        from models import SearchResult, GraphSearchRelation

        response = self.client.post(
            f"{self.base_url}/api/v1/memory/search",
            json={
                "query": query,
                "limit": limit,
                "uid": uid
            }
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", []):
            graph_relations = [
                GraphSearchRelation(**r) for r in item.get("graph_relations", [])
            ]
            results.append(SearchResult(
                memory_id=item.get("memory_id", ""),
                content=item.get("content", ""),
                score=item.get("score", 0.0),
                metadata=item.get("metadata", {}),
                graph_relations=graph_relations
            ))
        return results

    def search_with_answer(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None
    ) -> dict[str, Any]:
        """Search memories and generate an AI-powered answer.

        Args:
            query: Search query text
            limit: Maximum number of results
            uid: User ID filter (optional)

        Returns:
            Dictionary with 'answer', 'memories', 'relations', and 'raw_results' keys

        Raises:
            httpx.HTTPError: If the request fails
        """
        from models import SearchResult, GraphSearchRelation

        response = self.client.post(
            f"{self.base_url}/api/v1/memory/search-with-answer",
            json={
                "query": query,
                "limit": limit,
                "uid": uid
            }
        )
        response.raise_for_status()
        data = response.json()

        # Convert raw_results to SearchResult objects
        raw_results = []
        for item in data.get("raw_results", []):
            graph_relations = [
                GraphSearchRelation(**r) for r in item.get("graph_relations", [])
            ]
            raw_results.append(SearchResult(
                memory_id=item.get("memory_id", ""),
                content=item.get("content", ""),
                score=item.get("score", 0.0),
                metadata=item.get("metadata", {}),
                graph_relations=graph_relations
            ))

        return {
            "answer": data.get("answer", ""),
            "memories": data.get("memories", []),
            "relations": data.get("relations", []),
            "raw_results": raw_results
        }

    def search_graph_only(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None
    ) -> list["GraphSearchRelation"]:
        """Search only the knowledge graph for entity relationships.

        Args:
            query: Search query text
            limit: Maximum number of results
            uid: User ID filter (optional)

        Returns:
            List of GraphSearchRelation objects

        Raises:
            httpx.HTTPError: If the request fails
        """
        from models import GraphSearchRelation

        response = self.client.post(
            f"{self.base_url}/api/v1/memory/search-graph",
            json={
                "query": query,
                "limit": limit,
                "uid": uid
            }
        )
        response.raise_for_status()
        data = response.json()

        return [
            GraphSearchRelation(**r) for r in data.get("relations", [])
        ]

    def clear(self, uid: str) -> bool:
        """Clear all memories for a user.

        Args:
            uid: User ID to clear memories for

        Returns:
            True if successful

        Raises:
            httpx.HTTPError: If the request fails
        """
        response = self.client.delete(
            f"{self.base_url}/api/v1/memory/clear",
            params={"uid": uid}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("success", False)

    def count(self, uid: str) -> int:
        """Get the total count of memories for a user.

        Args:
            uid: User ID to count memories for

        Returns:
            Number of memories

        Raises:
            httpx.HTTPError: If the request fails
        """
        response = self.client.get(
            f"{self.base_url}/api/v1/memory/count",
            params={"uid": uid}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("count", 0)

    def get_graph_data(self, uid: Optional[str] = None) -> "GraphVisualization":
        """Get complete graph visualization data.

        Args:
            uid: User ID filter (optional)

        Returns:
            GraphVisualization object with nodes and edges

        Raises:
            httpx.HTTPError: If the request fails
        """
        from models import GraphVisualization, GraphEntity, GraphRelation

        params = {"uid": uid} if uid else {}
        response = self.client.get(
            f"{self.base_url}/api/v1/memory/graph",
            params=params
        )
        response.raise_for_status()
        data = response.json()

        nodes = [GraphEntity(**n) for n in data.get("nodes", [])]
        edges = [GraphRelation(**e) for e in data.get("edges", [])]

        return GraphVisualization(nodes=nodes, edges=edges)


class RemoteMemoryFactory:
    """Factory for creating remote memory clients."""

    @staticmethod
    def create(base_url: Optional[str] = None, user_id: str = "default") -> RemoteMemoryClient:
        """Create a remote memory client.

        Args:
            base_url: Base URL of the remote API (uses config if not provided)
            user_id: User ID (for session tracking, not used for API calls)

        Returns:
            RemoteMemoryClient instance
        """
        if base_url is None:
            from config import config
            base_url = config.remote_api_url

        return RemoteMemoryClient(base_url=base_url)
