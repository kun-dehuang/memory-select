"""Lean mem0 wrapper for the API-only memory service."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Optional

from mem0 import AsyncMemory, Memory
from mem0.configs.base import GraphStoreConfig, LlmConfig, MemoryConfig, VectorStoreConfig
from mem0.embeddings.configs import EmbedderConfig

import mem0.llms.gemini as mem0_gemini
import mem0.memory.graph_memory as mem0_graph_memory

from core.llm import get_llm_client
from models import GraphEntity, GraphRelation, GraphSearchRelation, GraphVisualization, SearchResult


logger = logging.getLogger("memory_select.mem0")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

_RECOVERABLE_GRAPH_ERROR_MARKERS = (
    "broken pipe",
    "failed to write data to connection",
    "service unavailable",
    "session expired",
    "defunct connection",
    "failed to obtain a connection",
    "connection acquisition timeout",
    "cannot resolve address",
)


_current_remove_spaces = mem0_graph_memory.MemoryGraph._remove_spaces_from_entities
_original_remove_spaces = getattr(_current_remove_spaces, "_memory_select_original", _current_remove_spaces)


def _patched_remove_spaces_from_entities(self, entity_list):
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
    return _original_remove_spaces(self, filtered_entities)


_patched_remove_spaces_from_entities._memory_select_original = _original_remove_spaces
_patched_remove_spaces_from_entities._memory_select_patched = True
if not getattr(mem0_graph_memory.MemoryGraph._remove_spaces_from_entities, "_memory_select_patched", False):
    mem0_graph_memory.MemoryGraph._remove_spaces_from_entities = _patched_remove_spaces_from_entities

_current_gemini_parse_response = mem0_gemini.GeminiLLM._parse_response
_original_gemini_parse_response = getattr(
    _current_gemini_parse_response,
    "_memory_select_original",
    _current_gemini_parse_response,
)


def _patched_gemini_parse_response(self, response, tools):
    parsed = _original_gemini_parse_response(self, response, tools)
    if tools and isinstance(parsed, dict) and parsed.get("content") is None:
        parsed["content"] = ""
    return parsed


_patched_gemini_parse_response._memory_select_original = _original_gemini_parse_response
_patched_gemini_parse_response._memory_select_patched = True
if not getattr(mem0_gemini.GeminiLLM._parse_response, "_memory_select_patched", False):
    mem0_gemini.GeminiLLM._parse_response = _patched_gemini_parse_response


def _qdrant_config(collection_name: str) -> dict[str, Any]:
    host = os.getenv("MEM0_QDRANT_HOST", "localhost").strip()
    port = int(os.getenv("MEM0_QDRANT_PORT", "6333"))
    api_key = os.getenv("QDRANT_API_KEY", "").strip()
    https = os.getenv("QDRANT_HTTPS", "false").lower() == "true"

    config: dict[str, Any] = {
        "collection_name": collection_name,
        "embedding_model_dims": 768,
    }

    if host.startswith("http://") or host.startswith("https://"):
        config["url"] = host
    elif api_key:
        scheme = "https" if https else "http"
        config["url"] = f"{scheme}://{host}:{port}"
    else:
        config["host"] = host
        config["port"] = port

    if api_key:
        config["api_key"] = api_key

    return config


def _memory_config(collection_name: str) -> MemoryConfig:
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash")

    return MemoryConfig(
        vector_store=VectorStoreConfig(
            provider="qdrant",
            config=_qdrant_config(collection_name),
        ),
        llm=LlmConfig(
            provider="gemini",
            config={
                "model": gemini_model,
                "api_key": gemini_api_key,
            },
        ),
        embedder=EmbedderConfig(
            provider="gemini",
            config={
                "model": "models/gemini-embedding-001",
                "api_key": gemini_api_key,
            },
        ),
        graph_store=GraphStoreConfig(
            provider="neo4j",
            config={
                "url": os.getenv("MEM0_NEO4J_URI", "bolt://localhost:7687"),
                "username": os.getenv("MEM0_NEO4J_USER", "neo4j"),
                "password": os.getenv("MEM0_NEO4J_PASSWORD", "password123"),
                "database": "neo4j",
            },
            llm=LlmConfig(
                provider="gemini",
                config={
                    "model": gemini_model,
                    "api_key": gemini_api_key,
                },
            ),
            threshold=0.7,
        ),
    )


class Mem0Graph:
    """API-facing mem0 wrapper that keeps vector and graph storage together."""

    def __init__(self, user_id: Optional[str] = None, collection_name: Optional[str] = None):
        self.user_id = user_id or "default_user"
        self.collection_name = collection_name or f"memory_store_{self.user_id}"
        self._config = _memory_config(self.collection_name)
        self._async_client = AsyncMemory(self._config)
        self._sync_client = Memory(self._config)
        self._cache_info: dict[str, Any] = {}

    async def add(self, uid: str, text: str, metadata: dict[str, Any]) -> dict[str, Any]:
        start_time = time.time()
        payload = dict(metadata)
        if "unixtime" in payload:
            payload["timestamp"] = payload["unixtime"]

        result = await self._async_client.add(
            messages=[{"role": "user", "content": text}],
            user_id=uid,
            metadata=payload,
        )

        memory_id = str(uuid.uuid4())
        if result and result.get("results"):
            memory_id = result["results"][0].get("id", memory_id)

        return {
            "memory_id": memory_id,
            "raw_result": result,
            "timings": {"add": (time.time() - start_time) * 1000},
        }

    def search(self, query: str, limit: int = 5, uid: Optional[str] = None) -> list[SearchResult]:
        user_id = uid or self.user_id
        vector_results = self._search_vector_results(query=query, user_id=user_id, limit=limit * 3)
        graph_relations = self._search_graph_relations(query=query, user_id=user_id, limit=limit * 3)
        attached = self._attach_graph_relations(vector_results, graph_relations)
        attached.sort(key=lambda item: (item._timestamp, item.score), reverse=True)
        return attached[:limit]

    def search_with_answer(self, query: str, limit: int = 5, uid: Optional[str] = None) -> dict[str, Any]:
        overall_start = time.time()
        results = self.search(query=query, limit=limit, uid=uid)
        search_time = (time.time() - overall_start) * 1000

        memories = [result.content for result in results if result.content]
        relations = []
        if results and results[0].graph_relations:
            relations = [
                {
                    "source": relation.source,
                    "relationship": relation.relationship,
                    "destination": relation.destination,
                }
                for relation in results[0].graph_relations
            ]

        llm_start = time.time()
        answer = get_llm_client().generate_graph_enhanced_answer(
            question=query,
            memories=memories,
            relations=relations,
        )
        llm_time = (time.time() - llm_start) * 1000

        return {
            "answer": answer,
            "memories": memories,
            "relations": relations,
            "raw_results": results,
            "timings": {
                "search": search_time,
                "llm": llm_time,
                "core_total": (time.time() - overall_start) * 1000,
            },
        }

    def search_graph_only(self, query: str, limit: int = 5, uid: Optional[str] = None) -> list[GraphSearchRelation]:
        user_id = uid or self.user_id
        return self._search_graph_relations(query=query, user_id=user_id, limit=limit)

    def get_graph_data(self, uid: Optional[str] = None) -> GraphVisualization:
        user_id = uid or self.user_id
        nodes: list[GraphEntity] = []
        edges: list[GraphRelation] = []
        seen_nodes: set[str] = set()

        try:
            if self._sync_client.enable_graph and self._sync_client.graph:
                graph_data = self._sync_client.graph.get_all(filters={"user_id": user_id}, limit=100)
                for item in graph_data:
                    source_name = item.get("source", "")
                    target_name = item.get("target", "")
                    relationship = item.get("relationship", "")

                    if source_name and source_name not in seen_nodes:
                        nodes.append(GraphEntity(name=source_name, type="Entity", properties={}))
                        seen_nodes.add(source_name)
                    if target_name and target_name not in seen_nodes:
                        nodes.append(GraphEntity(name=target_name, type="Entity", properties={}))
                        seen_nodes.add(target_name)
                    if source_name and target_name:
                        edges.append(
                            GraphRelation(
                                source=source_name,
                                target=target_name,
                                relation_type=relationship,
                                properties={},
                            )
                        )
        except Exception:
            logger.exception("Failed to fetch graph data for user_id=%s", user_id)

        return GraphVisualization(nodes=nodes, edges=edges)

    def clear(self) -> None:
        self._sync_client.delete_all(user_id=self.user_id)
        if self._sync_client.enable_graph and self._sync_client.graph:
            try:
                self._sync_client.graph.delete_all(filters={"user_id": self.user_id})
            except Exception:
                logger.exception("Failed to clear graph data for user_id=%s", self.user_id)

    def count(self) -> int:
        result = self._sync_client.get_all(user_id=self.user_id)
        return len(result.get("results", [])) if result else 0

    def _search_vector_results(self, query: str, user_id: str, limit: int) -> list[SearchResult]:
        items = self._sync_client._search_vector_store(query, {"user_id": user_id}, limit, threshold=None)
        results: list[SearchResult] = []
        for item in items:
            result = SearchResult(
                memory_id=item.get("id", str(uuid.uuid4())),
                content=item.get("memory", ""),
                score=item.get("score", 1.0),
                metadata=item.get("metadata", {}),
            )
            result._timestamp = self._extract_timestamp(result.metadata)
            results.append(result)
        return results

    def _search_graph_relations(self, query: str, user_id: str, limit: int) -> list[GraphSearchRelation]:
        if not getattr(self._sync_client, "enable_graph", False) or not getattr(self._sync_client, "graph", None):
            return []

        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                relations_raw = self._sync_client.graph.search(query, {"user_id": user_id}, limit)
                return [
                    GraphSearchRelation(
                        source=item.get("source", ""),
                        relationship=item.get("relationship", ""),
                        destination=item.get("destination", ""),
                    )
                    for item in (relations_raw or [])
                ]
            except Exception as error:
                last_error = error
                if attempt == 0 and self._is_recoverable_graph_error(error):
                    self._refresh_sync_client()
                    continue
                break

        if last_error is not None:
            logger.warning("Graph search degraded for user_id=%s: %s", user_id, last_error)
        return []

    def _attach_graph_relations(
        self,
        search_results: list[SearchResult],
        graph_relations: list[GraphSearchRelation],
    ) -> list[SearchResult]:
        attached_results: list[SearchResult] = []
        for result in search_results:
            attached = SearchResult(
                memory_id=result.memory_id,
                content=result.content,
                score=result.score,
                metadata=result.metadata,
                graph_relations=list(graph_relations),
            )
            attached._timestamp = result._timestamp
            attached_results.append(attached)
        return attached_results

    def _refresh_sync_client(self) -> None:
        close_method = getattr(self._sync_client, "close", None)
        if callable(close_method):
            try:
                close_method()
            except Exception:
                logger.exception("Failed to close sync mem0 client before refresh")
        self._sync_client = Memory(self._config)

    @staticmethod
    def _extract_timestamp(metadata: dict[str, Any]) -> int:
        timestamp = metadata.get("timestamp") or metadata.get("unixtime") or 0
        try:
            return int(timestamp) if timestamp is not None else 0
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _is_recoverable_graph_error(error: Exception) -> bool:
        error_type = error.__class__.__name__.lower()
        error_message = str(error).lower()
        if isinstance(error, BrokenPipeError):
            return True
        if error_type in {"serviceunavailable", "sessionexpired"}:
            return True
        return any(marker in error_message for marker in _RECOVERABLE_GRAPH_ERROR_MARKERS)
