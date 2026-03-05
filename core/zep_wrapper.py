"""Zep integration wrapper with unified interface.

Supports Memory (Vector) and Graph modes using Zep Cloud API.
Updated for zep-cloud 3.0+.

Zep Cloud Hierarchy:
- User: Represents a user (e.g., "linmu_001")
- Thread: Belongs to a user, stores messages (e.g., "thread_linmu_001")
"""

import uuid
import re
from typing import Optional
from datetime import datetime

from zep_cloud import Zep

from config import config
from models import SearchResult, GraphEntity, GraphRelation, GraphVisualization, GraphSearchRelation

from core.mem0_wrapper import MemoryInterface
import os


def _convert_to_iso8601(timestamp: str) -> Optional[str]:
    """Convert various timestamp formats to ISO 8601 format required by Zep.

    Zep requires ISO 8601 format like: 2025-10-06T00:00:00Z

    Args:
        timestamp: Timestamp string in various formats

    Returns:
        ISO 8601 formatted string or None if conversion fails
    """
    if not timestamp:
        return None

    # Already in ISO format (contains T and ends with Z or +)
    if 'T' in timestamp and (timestamp.endswith('Z') or '+' in timestamp or timestamp.find('+') > 0):
        return timestamp

    # Handle date range format like "2025-10-06 ~ 2025-10-11"
    # Extract the first date
    if '~' in timestamp or '～' in timestamp:
        # Split on the range indicator and take the first date
        parts = re.split(r'[~～]', timestamp)
        timestamp = parts[0].strip()

    # Remove any time in parentheses like "2025-11-02（15:39~16:42）"
    timestamp = re.sub(r'\([^)]*\)', '', timestamp).strip()

    # Try parsing common formats - handle each separately to avoid regex conflicts
    formats_to_try = [
        '%Y-%m-%d',           # 2025-10-06
        '%Y/%m/%d',           # 2025/10/06
        '%Y-%m-%d %H:%M:%S',  # 2025-10-06 12:30:45
        '%Y%m%d',             # 20251006
    ]

    for fmt in formats_to_try:
        try:
            parsed = datetime.strptime(timestamp, fmt)
            return parsed.isoformat() + 'Z'
        except ValueError:
            continue

    # If all parsing fails, return None (don't set created_at)
    return None


class ZepMemory(MemoryInterface):
    """Zep Standard Memory API with unified interface."""

    def __init__(self, user_id: Optional[str] = None, session_id: Optional[str] = None):
        """Initialize Zep client and ensure user + thread exist.

        Args:
            user_id: Zep user ID (e.g., "linmu_001")
            session_id: Optional thread ID. Defaults to 'thread_{user_id}'

        Raises:
            ValueError: If ZEP_API_KEY is not configured
        """
        if not config.zep.api_key:
            raise ValueError("ZEP_API_KEY is required. Set it in .env file.")

        self.client = Zep(api_key=config.zep.api_key)
        self.user_id = user_id or "memory_select_user"
        # Map session_id to thread_id for Zep Cloud
        self.thread_id = session_id or f"thread_{self.user_id}"
        self._ensure_user()
        self._ensure_thread()

    def _ensure_user(self) -> None:
        """Ensure user exists in Zep."""
        try:
            self.client.user.get(user_id=self.user_id)
        except Exception:
            # User doesn't exist, create it
            try:
                self.client.user.add(user_id=self.user_id)
            except Exception:
                pass

    def _ensure_thread(self) -> None:
        """Ensure thread exists in Zep."""
        # First check if thread exists
        try:
            self.client.thread.get(thread_id=self.thread_id)
            return  # Thread exists
        except Exception:
            pass  # Thread doesn't exist, create it

        # Create the thread
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.client.thread.create(
                    thread_id=self.thread_id,
                    user_id=self.user_id
                )
                print(f"[Zep] Thread '{self.thread_id}' created")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)
                else:
                    print(f"[Zep] Failed to create thread after {max_retries} attempts: {e}")

    def add(self, uid: str, text: str, metadata: dict) -> str:
        """Add a single memory to Zep.

        Args:
            uid: User ID
            text: Memory text content
            metadata: Additional metadata (timestamp, category, etc.)

        Returns:
            Memory ID
        """
        memory_id = str(uuid.uuid4())

        message = {
            "role": "user",
            "content": text,
            "metadata": {
                "uid": uid,
                "memory_id": memory_id,
                **metadata
            }
        }

        # Add created_at from metadata.timestamp if available (convert to ISO 8601)
        if "timestamp" in metadata:
            iso_timestamp = _convert_to_iso8601(metadata["timestamp"])
            if iso_timestamp:
                message["created_at"] = iso_timestamp

        result = self.client.thread.add_messages(
            thread_id=self.thread_id,
            messages=[message]
        )

        return memory_id

    def add_batch(self, records: list[dict]) -> list[str]:
        """Add multiple memories in batch.

        Note: Zep Cloud free tier has rate limits (5 req/sec).
        We process in smaller batches with delays to avoid 429 errors.

        Args:
            records: List of dicts with 'uid', 'text', 'meta' keys

        Returns:
            List of memory IDs
        """
        import time

        memory_ids = []
        messages = []

        # Prepare all messages
        for record in records:
            memory_id = str(uuid.uuid4())
            memory_ids.append(memory_id)

            meta = record.get("meta", {})
            message = {
                "role": "user",
                "content": record["text"],
                "metadata": {
                    "uid": record.get("uid", ""),
                    "memory_id": memory_id,
                    **meta
                }
            }

            # Add created_at from meta.timestamp if available (convert to ISO 8601)
            if "timestamp" in meta:
                iso_timestamp = _convert_to_iso8601(meta["timestamp"])
                if iso_timestamp:
                    message["created_at"] = iso_timestamp

            messages.append(message)

        # Process in smaller batches to avoid rate limits
        # Free tier: 5 requests per second
        batch_size = 5  # Conservative batch size
        delay_between_batches = 1.2  # Seconds between batches

        success_count = 0
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]

            # Ensure thread still exists before writing
            try:
                self.client.thread.get(thread_id=self.thread_id)
            except Exception:
                print(f"[Zep] Thread not found, recreating...")
                self._ensure_thread()

            try:
                # Try batch API for this chunk
                self.client.thread.add_messages_batch(
                    thread_id=self.thread_id,
                    messages=batch
                )
                success_count += len(batch)
                print(f"[Zep] Progress: {success_count}/{len(messages)} memories added")
            except Exception as e:
                error_str = str(e)
                # Check for rate limit or thread not found errors
                if "429" in error_str or "rate limit" in error_str.lower():
                    print(f"[Zep] Rate limit hit, waiting...")
                    time.sleep(5)  # Wait longer for rate limit reset
                    # Retry this batch
                    try:
                        self.client.thread.add_messages_batch(
                            thread_id=self.thread_id,
                            messages=batch
                        )
                        success_count += len(batch)
                        print(f"[Zep] Retry successful: {success_count}/{len(messages)}")
                    except Exception as e2:
                        print(f"[Zep] Retry failed: {e2}")
                        # Try one by one
                        for msg in batch:
                            try:
                                self.client.thread.add_messages(
                                    thread_id=self.thread_id,
                                    messages=[msg]
                                )
                                success_count += 1
                                time.sleep(0.3)  # Delay between individual messages
                            except Exception as e3:
                                print(f"[Zep] Error adding single message: {e3}")
                elif "404" in error_str or "not found" in error_str.lower():
                    print(f"[Zep] Thread not found, recreating and retrying...")
                    self._ensure_thread()
                    # Retry this batch
                    try:
                        self.client.thread.add_messages_batch(
                            thread_id=self.thread_id,
                            messages=batch
                        )
                        success_count += len(batch)
                    except Exception as e2:
                        print(f"[Zep] Retry after recreation failed: {e2}")
                else:
                    print(f"[Zep] Batch upload error: {e}")
                    # Try one by one
                    for msg in batch:
                        try:
                            self.client.thread.add_messages(
                                thread_id=self.thread_id,
                                messages=[msg]
                            )
                            success_count += 1
                            time.sleep(0.3)
                        except Exception as e2:
                            print(f"[Zep] Error adding single message: {e2}")

            # Delay between batches to avoid rate limits
            if i + batch_size < len(messages):
                time.sleep(delay_between_batches)

        print(f"[Zep] Total added: {success_count}/{len(messages)} memories to thread '{self.thread_id}' for user '{self.user_id}'")
        return memory_ids

    def search(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None
    ) -> list[SearchResult]:
        """Search memories using keyword-based search (non-graph).

        Retrieves all messages from the thread and performs
        keyword matching on the client side.

        Args:
            query: Search query text
            limit: Max number of results
            uid: Optional user ID filter (not used, already isolated by thread)

        Returns:
            List of SearchResult objects
        """
        search_results = []
        query_lower = query.lower()

        # Define keyword weights for better relevance
        keyword_weights = {
            '买': 3.0,
            '购': 3.0,
            '买过': 3.0,
            '购买': 3.0,
            '买了': 3.0,
            '去': 1.0,
            '吃': 2.0,
            '做': 2.0,
            'like': 2.0,
            'love': 2.0,
            'bought': 3.0,
            'went': 1.0,
        }

        try:
            # Get all messages from the thread
            result = self.client.thread.get(thread_id=self.thread_id)

            if hasattr(result, 'messages') and result.messages:
                scored_messages = []

                # Extract query keywords for better matching
                keywords = [query_lower]
                for word in query_lower.split():
                    if len(word) > 1:
                        keywords.append(word)

                # Remove duplicates while preserving order
                seen = set()
                unique_keywords = []
                for kw in keywords:
                    if kw not in seen and len(kw) > 0:
                        seen.add(kw)
                        unique_keywords.append(kw)

                for msg in result.messages:
                    if hasattr(msg, 'content') and msg.content:
                        content = msg.content
                        content_lower = content.lower()

                        # Calculate relevance score based on keyword matching
                        score = 0.0
                        matched_keywords = []

                        for keyword in unique_keywords:
                            if keyword in content_lower:
                                weight = keyword_weights.get(keyword, len(keyword) if len(keyword) > 1 else 0.5)
                                score += weight
                                matched_keywords.append(keyword)

                        # Only include messages with some relevance
                        if score > 0:
                            metadata = {}
                            if hasattr(msg, 'metadata') and msg.metadata:
                                metadata = dict(msg.metadata)

                            scored_messages.append(SearchResult(
                                memory_id=metadata.get("memory_id", str(uuid.uuid4())),
                                content=content,
                                score=score,
                                metadata=metadata
                            ))

                # Sort by score (highest first) and limit results
                scored_messages.sort(key=lambda x: x.score, reverse=True)
                search_results = scored_messages[:limit]

        except Exception as e:
            print(f"[Zep Memory] Search error: {e}")

        return search_results

    def search_with_answer(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None
    ) -> dict:
        """Search memories and generate LLM-enhanced answer.

        Args:
            query: Search query text
            limit: Max number of results
            uid: Optional user ID filter

        Returns:
            Dictionary with:
            - answer: LLM-generated answer
            - memories: List of raw memory texts
            - raw_results: Original SearchResult objects
        """
        from core.llm import get_llm_client

        user_id = uid or self.user_id
        search_results = self.search(query=query, limit=limit, uid=user_id)
        memories = [r.content for r in search_results if r.content]

        llm_client = get_llm_client()
        answer = llm_client.generate_answer(
            question=query,
            memory_context=memories
        )

        return {
            "answer": answer,
            "memories": memories,
            "raw_results": search_results
        }

    def clear(self) -> None:
        """Clear all memories by deleting and recreating thread."""
        try:
            # Delete the thread
            self.client.thread.delete(thread_id=self.thread_id)
        except Exception:
            pass
        self._ensure_thread()

    def count(self) -> int:
        """Get total memory count."""
        try:
            result = self.client.thread.get(thread_id=self.thread_id)
            if hasattr(result, 'messages') and result.messages:
                return len(result.messages)
        except Exception:
            pass
        return 0


class ZepGraph(MemoryInterface):
    """Zep Graph Memory API with unified interface.

    Zep automatically extracts entities and relationships from memories.
    """

    def __init__(self, user_id: Optional[str] = None, session_id: Optional[str] = None):
        """Initialize Zep Graph client.

        Args:
            user_id: Zep user ID (e.g., "linmu_001")
            session_id: Optional thread ID. Defaults to 'thread_{user_id}'

        Raises:
            ValueError: If ZEP_API_KEY is not configured
        """
        if not config.zep.api_key:
            raise ValueError("ZEP_API_KEY is required. Set it in .env file.")

        self.client = Zep(api_key=config.zep.api_key)
        self.user_id = user_id or "memory_select_user"
        self.thread_id = session_id or f"thread_{self.user_id}"
        self._memory_client = ZepMemory(user_id=self.user_id, session_id=self.thread_id)

    def add(self, uid: str, text: str, metadata: dict) -> str:
        """Add a memory. Zep automatically extracts entities.

        Args:
            uid: User ID
            text: Memory text content
            metadata: Additional metadata

        Returns:
            Memory ID
        """
        return self._memory_client.add(uid, text, metadata)

    def add_batch(self, records: list[dict]) -> list[str]:
        """Add multiple memories. Zep extracts entities from each.

        Args:
            records: List of dicts with 'uid', 'text', 'meta' keys

        Returns:
            List of memory IDs
        """
        return self._memory_client.add_batch(records)

    def search(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None
    ) -> list[SearchResult]:
        """Search memories using Zep with graph context.

        Performs parallel searches:
        1. Graph search - finds entities and relationships (returns facts)
        2. Thread search - finds original memory messages

        Args:
            query: Search query text
            limit: Max number of results
            uid: Optional user ID filter

        Returns:
            List of SearchResult objects with graph_relations attached
        """
        search_results = []
        graph_relations = []

        try:
            # 1. Graph search - get facts and relationships
            effective_limit = min(limit, 50) if limit else 50
            graph_result = self.client.graph.search(
                query=query,
                user_id=self.user_id,
                limit=effective_limit
            )

            # Extract edges - Zep returns facts with relationship info
            if hasattr(graph_result, 'edges') and graph_result.edges:
                for edge in graph_result.edges:
                    # Zep edges have: name (relation type), fact (readable description)
                    # Note: Zep uses UUIDs for source/target, not entity names
                    # We use the fact which contains readable information
                    if hasattr(edge, 'fact') and edge.fact:
                        search_results.append(SearchResult(
                            memory_id=str(uuid.uuid4()),
                            content=edge.fact,
                            score=float(edge.score) if hasattr(edge, 'score') else 1.0,
                            metadata={
                                "source": "zep_graph",
                                "relation_type": edge.name if hasattr(edge, 'name') else None,
                                "relation_uuid": getattr(edge, 'uuid_', None)
                            },
                            graph_relations=[]  # Facts are self-contained
                        ))

                    # Also create a graph relation entry
                    # Since Zep doesn't provide entity names, we use relation type + fact
                    if hasattr(edge, 'name'):
                        # Create a simplified relation representation
                        relation_type = str(edge.name)
                        fact_preview = (edge.fact[:30] + "...") if hasattr(edge, 'fact') and len(edge.fact) > 30 else (edge.fact if hasattr(edge, 'fact') else "")
                        graph_relations.append(GraphSearchRelation(
                            source=f"Entity_{getattr(edge, 'source_node_uuid', '')[:8]}",  # UUID prefix
                            relationship=relation_type,
                            destination=f"Entity_{getattr(edge, 'target_node_uuid', '')[:8]}"  # UUID prefix
                        ))

        except Exception as e:
            print(f"[Zep Graph] Graph search error: {e}")

        # 2. If no graph results, fall back to thread messages
        if not search_results:
            try:
                thread_result = self.client.thread.get(thread_id=self.thread_id)
                query_lower = query.lower()

                if hasattr(thread_result, 'messages') and thread_result.messages:
                    for msg in thread_result.messages:
                        if hasattr(msg, 'content') and msg.content:
                            content_lower = msg.content.lower()
                            # Simple keyword matching
                            if any(qw in content_lower for qw in query_lower.split() if len(qw) > 1):
                                metadata = {}
                                if hasattr(msg, 'metadata') and msg.metadata:
                                    metadata = dict(msg.metadata)

                                search_results.append(SearchResult(
                                    memory_id=metadata.get("memory_id", str(uuid.uuid4())),
                                    content=msg.content,
                                    score=1.0,
                                    metadata=metadata,
                                    graph_relations=graph_relations
                                ))
                        if len(search_results) >= limit:
                            break
            except Exception as e:
                print(f"[Zep Graph] Thread search error: {e}")

        # 3. Last resort: get_user_context
        if not search_results:
            try:
                result = self.client.thread.get_user_context(thread_id=self.thread_id)
                if hasattr(result, 'context') and result.context:
                    search_results.append(SearchResult(
                        memory_id=str(uuid.uuid4()),
                        content=result.context,
                        score=1.0,
                        metadata={"source": "zep_user_context"},
                        graph_relations=graph_relations
                    ))
            except Exception as e:
                print(f"[Zep Graph] get_user_context error: {e}")

        return search_results[:limit] if search_results else []

    def get_graph_data(self, uid: Optional[str] = None) -> GraphVisualization:
        """Get graph data with entities and relations from Zep.

        Args:
            uid: Optional user ID filter

        Returns:
            GraphVisualization with nodes and edges
        """
        try:
            # Use graph search to get entities and relationships
            # Use a broad query to get graph data
            result = self.client.graph.search(
                query="summary",  # Non-empty query to avoid 400 INVALID_ARGUMENT
                user_id=self.user_id,
                limit=50
            )

            nodes = []
            edges = []
            seen_entities = set()

            # Process nodes - these are entities
            if hasattr(result, 'nodes') and result.nodes:
                for node in result.nodes:
                    if hasattr(node, 'name') and node.name:
                        entity_name = node.name
                        if entity_name not in seen_entities:
                            nodes.append(GraphEntity(
                                name=entity_name,
                                type=node.type if hasattr(node, 'type') else "ENTITY",
                                properties={}
                            ))
                            seen_entities.add(entity_name)

            # Process edges - these are relationships
            if hasattr(result, 'edges') and result.edges:
                for edge in result.edges:
                    if hasattr(edge, 'name') and edge.name:
                        # Create edge representation
                        source = edge.source if hasattr(edge, 'source') else "unknown"
                        target = edge.target if hasattr(edge, 'target') else "unknown"
                        edges.append(GraphRelation(
                            source=source,
                            target=target,
                            relation_type=edge.name
                        ))

            return GraphVisualization(nodes=nodes, edges=edges)

        except Exception as e:
            print(f"[Zep] Get graph data error: {e}")
            # Return empty graph on error
            return GraphVisualization(nodes=[], edges=[])

    def clear(self) -> None:
        """Clear all graph data."""
        self._memory_client.clear()

    def count(self) -> int:
        """Get total memory count."""
        return self._memory_client.count()


class ZepFactory:
    """Factory for creating Zep instances."""

    @staticmethod
    def create(mode: str = "memory", user_id: Optional[str] = None) -> MemoryInterface:
        """Create a Zep instance.

        Args:
            mode: 'memory' for vector memory, 'graph' for graph memory
            user_id: User ID for isolation

        Returns:
            MemoryInterface instance

        Raises:
            ValueError: If mode is invalid
        """
        mode = mode.lower()
        if mode in ("memory", "standard", "vector"):
            return ZepMemory(user_id=user_id)
        elif mode == "graph":
            return ZepGraph(user_id=user_id)
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'memory' or 'graph'")
