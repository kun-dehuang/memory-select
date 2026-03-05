"""Mem0 integration wrapper using official mem0ai library.

This wrapper uses the official mem0ai library with:
- Vector Store: Qdrant (local)
- Graph Store: Neo4j (local)
- LLM: Gemini
- Embedder: Gemini

Key design:
- All data is written using graph-enabled mem0 (vector + graph together)
- Write operations are async with parallel processing support
- Search operations are synchronous
"""

import asyncio
import os
import sys
import uuid
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from mem0 import Memory, AsyncMemory
from mem0.configs.base import MemoryConfig, VectorStoreConfig, GraphStoreConfig, LlmConfig
from mem0.embeddings.configs import EmbedderConfig

from config import config
from models import SearchResult, GraphEntity, GraphRelation, GraphVisualization, GraphSearchRelation

debug_logger = None


def _get_debug_logger():
    """Lazy import and get debug logger.

    In production (Railway), returns a simple logger that uses standard logging.
    In local development, uses the custom utils.logger if available.
    """
    global debug_logger
    if debug_logger is None:
        import importlib.util
        import sys
        import logging
        from pathlib import Path

        logger_path = Path(__file__).parent.parent / "utils" / "logger.py"

        # Try to load custom logger (local development)
        if logger_path.exists():
            try:
                spec = importlib.util.spec_from_file_location("utils.logger", logger_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules["utils.logger"] = module
                spec.loader.exec_module(module)
                debug_logger = module.get_debug_logger()
                return debug_logger
            except Exception:
                pass  # Fall through to standard logger

        # Fallback: create a simple logger for production
        class SimpleLogger:
            def __init__(self):
                self.logger = logging.getLogger(__name__)
                if not self.logger.handlers:
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                    )
                    handler.setFormatter(formatter)
                    self.logger.addHandler(handler)
                    self.logger.setLevel(logging.INFO)

            def log_input(self, title, data):
                self.logger.info(f"{title}: {data}")

            def log_output(self, title, data):
                self.logger.info(f"{title}: {data}")

            def log_api_call(self, api_name, endpoint, request_data, response_data, duration_ms):
                self.logger.info(f"{api_name} {endpoint} - {duration_ms:.2f}ms")

            def log_error(self, operation, error, extra=""):
                self.logger.error(f"{operation} failed: {error}. {extra}")

        debug_logger = SimpleLogger()
    return debug_logger

fact_extraction_prompt = """从文本中提取事实信息，必须返回JSON格式：{{"facts": ["事实1", "事实2", ...]}}

要求：
1. 每个事实必须是完整的陈述句
2. 将复杂信息拆分成多个独立事实
3. 即使信息简单也必须提取至少一条事实
4. 使用与输入相同的语言（中文输入用中文输出）

提取所有可识别的信息：时间、人物、地点、动作、物品、感受、细节。

输入文本："""

import mem0.memory.graph_memory

_original_remove_spaces = mem0.memory.graph_memory.MemoryGraph._remove_spaces_from_entities


def _patched_remove_spaces_from_entities(self, entity_list):
    """Filter out entities with empty source/destination/relationship before processing."""
    filtered_entities = []
    for item in entity_list:
        source = item.get("source", "").strip()
        destination = item.get("destination", "").strip()
        relationship = item.get("relationship", "").strip()

        if source and destination and relationship:
            item["source"] = source
            item["destination"] = destination
            item["relationship"] = relationship
            filtered_entities.append(item)
        else:
            import logging
            logging.getLogger(__name__).warning(
                f"Filtered out entity with empty field: source='{source}', "
                f"destination='{destination}', relationship='{relationship}'"
            )

    return _original_remove_spaces(self, filtered_entities)


mem0.memory.graph_memory.MemoryGraph._remove_spaces_from_entities = _patched_remove_spaces_from_entities


# ============== LLM DEBUG LOGGING PATCH ==============
_original_llm_generate = None


def _patched_llm_generate(self, messages, tools=None, tool_choice="auto", **kwargs):
    """Patched LLM generate_response with detailed debug logging."""
    global _original_llm_generate

    logger = _get_debug_logger().logger

    # Log input
    logger.info("=" * 80)
    logger.info("[LLM REQUEST] Provider: " + self.__class__.__name__)
    logger.info("[LLM REQUEST] Messages:")
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # No truncation - log full content
        logger.info(f"  [{role}]: {content}")

    if tools:
        logger.info(f"[LLM REQUEST] Tools: {len(tools)} tools")
        for tool in tools:  # Show all tools
            logger.info(f"  - {tool.get('name', 'unknown')}: {tool.get('description', '')}")  # No truncation

    # Call original
    start_time = time.time()
    response = _original_llm_generate(self, messages=messages, tools=tools, tool_choice=tool_choice, **kwargs)
    duration = (time.time() - start_time) * 1000

    # Log response
    logger.info(f"[LLM RESPONSE] Duration: {duration:.2f}ms")
    logger.info(f"[LLM RESPONSE] Type: {type(response)}")
    logger.info(f"[LLM RESPONSE] Content: {str(response)}")  # No truncation

    # Check for tool_calls
    if isinstance(response, dict):
        if response.get("tool_calls"):
            logger.info(f"[LLM RESPONSE] Tool calls: {len(response['tool_calls'])}")
            for i, tc in enumerate(response["tool_calls"]):  # Show all tool calls
                args = tc.get("arguments", {})
                logger.info(f"  Tool {i+1}: args={str(args)}")  # No truncation
        else:
            logger.info(f"[LLM RESPONSE] No tool_calls, keys: {list(response.keys())}")

    logger.info("=" * 80)
    return response


# Apply the patch
if _original_llm_generate is None:
    from mem0.llms.base import LLMBase
    _original_llm_generate = LLMBase.generate_response
    LLMBase.generate_response = _patched_llm_generate

# ============== END FACT EXTRACTION DEBUG PATCH ==============


class MemoryInterface(ABC):
    """Unified interface for memory systems."""

    @abstractmethod
    async def add(self, uid: str, text: str, metadata: dict) -> str:
        """Add a single memory (async). Returns memory ID."""
        pass

    @abstractmethod
    async def add_batch(self, records: list[dict], max_concurrency: int = 5) -> list[str]:
        """Add multiple memories with parallel processing. Returns list of memory IDs."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 5, uid: Optional[str] = None) -> list[SearchResult]:
        """Search memories (sync). Returns list of search results."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all memories."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Get total memory count."""
        pass


class Mem0Base(MemoryInterface):
    """Base class for Mem0 memory systems.

    All instances use graph-enabled mem0 for writing (vector + graph together).
    Write operations are async, search operations are sync.
    """

    _shared_client = None
    _shared_config = None

    def __init__(self, user_id: Optional[str] = None, collection_name: Optional[str] = None):
        """Initialize Mem0 memory with graph support.

        Args:
            user_id: User ID for isolation
            collection_name: Optional custom collection name
        """
        self.user_id = user_id or "default_user"
        self.collection_name = collection_name or f"memory_store_{self.user_id}"

        # Build Qdrant config for local or cloud
        qdrant_config = {
            "collection_name": self.collection_name,
            "embedding_model_dims": 768,
        }

        # For Qdrant Cloud, use url instead of host/port
        if config.mem0.qdrant_api_key or config.mem0.qdrant_host.startswith("http"):
            qdrant_config["url"] = config.mem0.qdrant_host
            if config.mem0.qdrant_api_key:
                qdrant_config["api_key"] = config.mem0.qdrant_api_key
        else:
            # Local Qdrant
            qdrant_config["host"] = config.mem0.qdrant_host
            qdrant_config["port"] = int(config.mem0.qdrant_port)

        self._config = MemoryConfig(
            vector_store=VectorStoreConfig(
                provider="qdrant",
                config=qdrant_config
            ),
            llm=LlmConfig(
                provider="gemini",
                config={
                    "model": config.gemini.model,
                    "api_key": config.gemini.api_key,
                }
            ),
            embedder=EmbedderConfig(
                provider="gemini",
                config={
                    "model": "models/gemini-embedding-001",
                    "api_key": config.gemini.api_key,
                }
            ),
            graph_store=GraphStoreConfig(
                provider="neo4j",
                config={
                    "url": config.mem0.neo4j_uri,
                    "username": config.mem0.neo4j_user,
                    "password": config.mem0.neo4j_password,
                },
                llm=LlmConfig(
                    provider="gemini",
                    config={
                        "model": config.gemini.model,
                        "api_key": config.gemini.api_key,
                    }
                ),
                threshold=0.7,
            ),
            #custom_fact_extraction_prompt=fact_extraction_prompt,
        )

        self._async_client = AsyncMemory(self._config)
        self._sync_client = Memory(self._config)

    async def add(self, uid: str, text: str, metadata: dict) -> str:
        """Add a memory using mem0 with graph extraction (async).

        This writes to BOTH vector store (facts) and graph store (entities/relations).

        Args:
            uid: User ID
            text: Memory text content
            metadata: Additional metadata

        Returns:
            Memory ID
        """
        _get_debug_logger().logger.info(f"[ADD MEMORY] User: {uid}, Text length: {len(text)}")
        _get_debug_logger().log_input("Add memory input", {
            "uid": uid,
            "text": text,  # No truncation
            "metadata": metadata
        })

        messages = [{"role": "user", "content": text}]
        metadata_with_timestamp = dict(metadata)
        if "unixtime" in metadata:
            metadata_with_timestamp["timestamp"] = metadata["unixtime"]

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                start_time = time.time()
                result = await self._async_client.add(
                    messages,
                    user_id=uid,
                    metadata=metadata_with_timestamp
                )
                duration = (time.time() - start_time) * 1000

                _get_debug_logger().log_api_call(
                    api_name="Mem0",
                    endpoint="add",
                    request_data={"messages": messages, "user_id": uid, "metadata": metadata_with_timestamp},
                    response_data=result,
                    duration_ms=duration
                )

                if result and "results" in result:
                    memories = result["results"]
                    if memories:
                        memory_id = memories[0].get("id", str(uuid.uuid4()))
                        memory_text = memories[0].get("memory", "")
                        _get_debug_logger().log_output("Memory add result", {
                            "memory_id": memory_id,
                            "memory": memory_text,
                            "duration_ms": duration
                        })
                        return memory_id
                    else:
                        _get_debug_logger().logger.warning(f"[ADD MEMORY] No memories returned, duration: {duration:.2f}ms")
                else:
                    _get_debug_logger().logger.warning(f"[ADD MEMORY] Unexpected result format, duration: {duration:.2f}ms")
                return str(uuid.uuid4())

            except Exception as e:
                duration = (time.time() - start_time) * 1000
                error_str = str(e)
                _get_debug_logger().log_error(
                    f"Memory add (attempt {attempt + 1}/{max_retries})",
                    e,
                    f"Duration: {duration:.2f}ms"
                )

                if any(code in error_str for code in ["502", "500", "429", "Bad Gateway", "Server Error"]):
                    if attempt < max_retries - 1:
                        _get_debug_logger().logger.warning(
                            f"API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s..."
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                raise

        return str(uuid.uuid4())

    async def add_batch(self, records: list[dict], max_concurrency: int = 5) -> list[str]:
        """Add multiple memories with async parallel processing using Semaphore.

        Args:
            records: List of dicts with 'uid', 'text', 'meta' keys
            max_concurrency: Maximum number of concurrent operations (default: 5)

        Returns:
            List of memory IDs
        """
        _get_debug_logger().logger.info(f"[ADD BATCH] Starting batch add of {len(records)} records with max_concurrency={max_concurrency}")

        semaphore = asyncio.Semaphore(max_concurrency)

        async def _add_with_semaphore(index: int, record: dict) -> tuple[int, str]:
            """Add a single record with semaphore control."""
            async with semaphore:
                try:
                    memory_id = await self.add(
                        uid=record.get("uid", ""),
                        text=record["text"],
                        metadata=record.get("meta", {})
                    )
                    return (index, memory_id)
                except Exception as e:
                    _get_debug_logger().log_error(f"Add batch record {index+1}", e)
                    return (index, str(uuid.uuid4()))

        tasks = [_add_with_semaphore(i, record) for i, record in enumerate(records)]
        results = await asyncio.gather(*tasks)

        results.sort(key=lambda x: x[0])
        memory_ids = [result[1] for result in results]

        success_count = sum(1 for mid in memory_ids if mid != str(uuid.uuid4()) or mid)
        error_count = len(memory_ids) - success_count

        _get_debug_logger().logger.info(f"[ADD BATCH] Complete: {success_count} success, {error_count} errors")
        return memory_ids

    def search(self, query: str, limit: int = 5, uid: Optional[str] = None) -> list[SearchResult]:
        """Search memories (sync). To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement search method")

    def clear(self) -> None:
        """Clear all memories for this user."""
        self._sync_client.delete_all(user_id=self.user_id)
        if self._sync_client.enable_graph and self._sync_client.graph:
            try:
                self._sync_client.graph.delete_all(filters={"user_id": self.user_id})
            except Exception:
                pass

    def count(self) -> int:
        """Get total memory count."""
        result = self._sync_client.get_all(user_id=self.user_id)
        if result and "results" in result:
            return len(result["results"])
        return 0

    def add_batch_sync(self, records: list[dict], max_concurrency: int = 5) -> list[str]:
        """Synchronous wrapper for add_batch.

        Args:
            records: List of dicts with 'uid', 'text', 'meta' keys
            max_concurrency: Maximum number of concurrent operations (default: 5)

        Returns:
            List of memory IDs
        """
        return asyncio.run(self.add_batch(records, max_concurrency))

    def add_batch_pure_sync(self, records: list[dict]) -> list[str]:
        """Pure synchronous batch import using sync client (no asyncio).

        This method uses the synchronous Mem0 client directly, avoiding
        any async/await overhead. Suitable for Streamlit and other
        frameworks that don't work well with asyncio.

        Args:
            records: List of dicts with 'uid', 'text', 'meta' keys

        Returns:
            List of memory IDs
        """
        _get_debug_logger().logger.info(f"[ADD BATCH PURE SYNC] Starting sync batch add of {len(records)} records")

        memory_ids = []
        for i, record in enumerate(records):
            try:
                messages = [{"role": "user", "content": record["text"]}]
                metadata = dict(record.get("meta", {}))
                if "unixtime" in metadata:
                    metadata["timestamp"] = metadata["unixtime"]

                start_time = time.time()
                result = self._sync_client.add(
                    messages,
                    user_id=record.get("uid", ""),
                    metadata=metadata
                )
                duration = (time.time() - start_time) * 1000

                if result and "results" in result and result["results"]:
                    memory_id = result["results"][0].get("id", str(uuid.uuid4()))
                    memory_ids.append(memory_id)
                else:
                    memory_ids.append(str(uuid.uuid4()))

                _get_debug_logger().logger.debug(
                    f"[ADD BATCH PURE SYNC] Record {i+1}/{len(records)} imported in {duration:.2f}ms"
                )

            except Exception as e:
                _get_debug_logger().log_error(f"Add batch sync record {i+1}", e)
                memory_ids.append(str(uuid.uuid4()))

        _get_debug_logger().logger.info(f"[ADD BATCH PURE SYNC] Complete: {len(memory_ids)} records processed")
        return memory_ids


class Mem0Standard(Mem0Base):
    """Mem0 Standard Memory - Vector search only.

    Data is written to both vector and graph stores (via Mem0Base).
    Search only returns vector store results (facts), ignoring graph data.
    """

    def search(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None,
        use_time_ranking: bool = False
    ) -> list[SearchResult]:
        """Search memories using vector search only (sync).

        Args:
            query: Search query text
            limit: Max number of results
            uid: Optional user ID filter
            use_time_ranking: If True, sort results by timestamp (newest first)

        Returns:
            List of SearchResult objects (vector search results only)
        """
        user_id = uid or self.user_id
        actual_limit = limit * 3 if use_time_ranking else limit

        _get_debug_logger().logger.info(f"[SEARCH] Mem0Standard - query: '{query}', user_id: {user_id}, limit: {actual_limit}")

        start_time = time.time()
        result = self._sync_client.search(
            query=query,
            user_id=user_id,
            limit=actual_limit
        )
        duration = (time.time() - start_time) * 1000

        _get_debug_logger().log_api_call(
            api_name="Mem0",
            endpoint="search",
            request_data={"query": query, "user_id": user_id, "limit": actual_limit},
            response_data=result,
            duration_ms=duration
        )

        search_results = []
        if result and "results" in result:
            for item in result["results"]:
                search_results.append(SearchResult(
                    memory_id=item.get("id", str(uuid.uuid4())),
                    content=item.get("memory", ""),
                    score=item.get("score", 1.0),
                    metadata=item.get("metadata", {})
                ))

        _get_debug_logger().logger.debug(f"[SEARCH] Found {len(search_results)} results in {duration:.2f}ms")
        for i, sr in enumerate(search_results):  # Show all results
            _get_debug_logger().logger.debug(f"  [{i}] score={sr.score:.3f}: {sr.content}")  # No truncation

        if use_time_ranking and search_results:
            indexed_results = []
            for i, result in enumerate(search_results):
                metadata = result.metadata
                timestamp = metadata.get("timestamp") or metadata.get("unixtime") or "0"
                try:
                    ts_int = int(timestamp) if isinstance(timestamp, (int, float)) else 0
                except (ValueError, TypeError):
                    ts_int = 0

                indexed_results.append({
                    "index": i,
                    "timestamp": ts_int,
                    "score": result.score,
                    "result": result
                })

            indexed_results.sort(key=lambda x: (x["timestamp"], x["score"]), reverse=True)

            sorted_results = [item["result"] for item in indexed_results]
            return sorted_results[:limit]

        return search_results

    def search_with_answer(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None
    ) -> dict:
        """Search memories and generate LLM-enhanced answer (vector search only).

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


class Mem0Graph(Mem0Base):
    """Mem0 Graph Memory - Vector + Graph search.

    Data is written to both vector and graph stores (via Mem0Base).
    Search returns both vector results (facts) and graph results (entities/relations).
    """

    def search(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None,
        use_time_ranking: bool = False
    ) -> list[SearchResult]:
        """Search memories using both vector and graph search (sync).

        Args:
            query: Search query text
            limit: Max number of results
            uid: Optional user ID filter
            use_time_ranking: If True, sort results by timestamp (newest first)

        Returns:
            List of SearchResult objects, each containing:
            - content: The memory text (from vector search)
            - graph_relations: Related entities/relationships (from graph search)
        """
        user_id = uid or self.user_id
        actual_limit = limit * 3

        _get_debug_logger().logger.info(f"[SEARCH] Mem0Graph - query: '{query}', user_id: {user_id}, limit: {actual_limit}")

        result = self._sync_client.search(
            query=query,
            user_id=user_id,
            limit=actual_limit
        )

        search_results = []

        memories = result.get("results", []) if result else []

        relations_raw = result.get("relations", []) if result else []
        graph_relations = [
            GraphSearchRelation(
                source=r.get("source", ""),
                relationship=r.get("relationship", ""),
                destination=r.get("destination", "")
            )
            for r in relations_raw
        ]

        for item in memories:
            metadata = item.get("metadata", {})
            timestamp = metadata.get("timestamp") or metadata.get("unixtime") or 0
            search_results.append(SearchResult(
                memory_id=item.get("id", str(uuid.uuid4())),
                content=item.get("memory", ""),
                score=item.get("score", 1.0),
                metadata=metadata,
                graph_relations=graph_relations,
                _timestamp=int(timestamp) if isinstance(timestamp, (int, float)) else 0
            ))

        if use_time_ranking and search_results:
            search_results.sort(key=lambda x: (x._timestamp, x.score), reverse=True)

        return search_results[:limit]

    def search_with_answer(
        self,
        query: str,
        limit: int = 5,
        uid: Optional[str] = None
    ) -> dict:
        """Search memories and generate LLM-enhanced answer combining vector and graph results.

        Args:
            query: Search query text
            limit: Max number of results
            uid: Optional user ID filter

        Returns:
            Dictionary with:
            - answer: LLM-generated fused answer
            - memories: List of raw memory texts
            - relations: List of graph relations
            - raw_results: Original SearchResult objects
        """
        from core.llm import get_llm_client

        user_id = uid or self.user_id

        search_results = self.search(query=query, limit=limit, uid=user_id)

        memories = [r.content for r in search_results if r.content]

        relations = []
        if search_results and search_results[0].graph_relations:
            relations = [
                {"source": r.source, "relationship": r.relationship, "destination": r.destination}
                for r in search_results[0].graph_relations
            ]

        llm_client = get_llm_client()
        answer = llm_client.generate_graph_enhanced_answer(
            question=query,
            memories=memories,
            relations=relations
        )

        return {
            "answer": answer,
            "memories": memories,
            "relations": relations,
            "raw_results": search_results
        }

    def search_graph_only(self, query: str, limit: int = 5, uid: Optional[str] = None) -> list[GraphSearchRelation]:
        """Pure graph search - returns entities and relationships from the graph.

        This searches ONLY the graph store (Neo4j), not the vector store.

        Args:
            query: Search query text
            limit: Max number of results
            uid: Optional user ID filter

        Returns:
            List of GraphSearchRelation objects
        """
        user_id = uid or self.user_id
        filters = {"user_id": user_id}

        if self._sync_client.enable_graph and self._sync_client.graph:
            relations_raw = self._sync_client.graph.search(query, filters, limit)
            return [
                GraphSearchRelation(
                    source=r.get("source", ""),
                    relationship=r.get("relationship", ""),
                    destination=r.get("destination", "")
                )
                for r in (relations_raw or [])
            ]
        return []

    def get_graph_data(self, uid: Optional[str] = None) -> GraphVisualization:
        """Get graph data for visualization using mem0ai's graph.

        Args:
            uid: Optional user ID filter

        Returns:
            GraphVisualization with nodes and edges
        """
        user_id = uid or self.user_id
        nodes = []
        edges = []

        try:
            if self._sync_client.enable_graph and self._sync_client.graph:
                filters = {"user_id": user_id}
                graph_data = self._sync_client.graph.get_all(filters=filters, limit=100)

                seen_nodes = set()

                for item in graph_data:
                    source_name = item.get("source", "")
                    target_name = item.get("target", "")
                    relationship = item.get("relationship", "")
                    rel_id = f"{source_name}-{relationship}-{target_name}"

                    if source_name and source_name not in seen_nodes:
                        nodes.append(GraphEntity(
                            name=source_name,
                            type="Entity",
                            properties={}
                        ))
                        seen_nodes.add(source_name)

                    if target_name and target_name not in seen_nodes:
                        nodes.append(GraphEntity(
                            name=target_name,
                            type="Entity",
                            properties={}
                        ))
                        seen_nodes.add(target_name)

                    if source_name and target_name:
                        edges.append(GraphRelation(
                            source=source_name,
                            target=target_name,
                            relation_type=relationship,
                            properties={}
                        ))
        except Exception as e:
            pass

        return GraphVisualization(nodes=nodes, edges=edges)


class Mem0Factory:
    """Factory for creating Mem0 instances.

    Both 'standard' and 'graph' modes write to the same storage (vector + graph).
    They differ only in search behavior:
    - standard: Returns only vector search results
    - graph: Returns vector + graph search results
    """

    @staticmethod
    def create(mode: str = "standard", user_id: Optional[str] = None, collection_name: Optional[str] = None) -> MemoryInterface:
        """Create a Mem0 instance.

        Args:
            mode: 'standard' for vector-only search, 'graph' for vector+graph search
            user_id: User ID for isolation
            collection_name: Optional custom collection name

        Returns:
            MemoryInterface instance

        Raises:
            ValueError: If mode is invalid
        """
        mode = mode.lower()
        if mode == "standard":
            return Mem0Standard(user_id=user_id, collection_name=collection_name)
        elif mode == "graph":
            return Mem0Graph(user_id=user_id, collection_name=collection_name)
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'standard' or 'graph'")
