"""Memory API routes.

Provides REST endpoints for memory operations including:
- Add memory
- Search memory (vector + graph)
- Search graph only
- Search with AI answer
- Get graph visualization data
- Clear memories
- Count memories
"""

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.dependencies import get_memory_instance
from utils.logger import get_debug_logger
from api.schemas.requests import (
    AddMemoryRequest,
    SearchMemoryRequest,
    SearchWithAnswerRequest,
    SearchGraphOnlyRequest,
)
from api.schemas.responses import (
    AddMemoryResponse,
    SearchMemoryResponse,
    SearchResultResponse,
    SearchWithAnswerResponse,
    SearchGraphOnlyResponse,
    GetGraphDataResponse,
    ClearMemoryResponse,
    CountMemoryResponse,
)

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])

# Initialize debug logger for detailed logging
debug_logger = get_debug_logger()


@router.post("/add", response_model=AddMemoryResponse)
async def add_memory(request: AddMemoryRequest) -> AddMemoryResponse:
    """Add a new memory with automatic entity and relationship extraction.

    The memory is stored in both vector store (for semantic search)
    and graph store (for entity relationships).
    """
    start_time = time.time()
    try:
        memory = get_memory_instance(request.uid)

        # Log the add request
        debug_logger.log_api_request(
            endpoint="/api/v1/memory/add",
            method="POST",
            uid=request.uid,
            request_data={
                "text": request.text,
                "metadata": request.metadata
            }
        )

        # Get the underlying mem0 client to capture detailed response
        result = await memory._async_client.add(
            messages=[{"role": "user", "content": request.text}],
            user_id=request.uid,
            metadata=request.metadata or {}
        )
        duration_ms = (time.time() - start_time) * 1000

        # Extract and log fact splits and entities/relations
        facts = []
        entities = []
        relations = []

        if result and "results" in result and result["results"]:
            memory_data = result["results"][0]
            memory_id = memory_data.get("id", "")
            facts.append(memory_data.get("memory", ""))

            # Check for graph data in the response
            if "graph" in memory_data:
                graph_data = memory_data["graph"]
                entities = graph_data.get("entities", [])
                relations = graph_data.get("relationships", [])

        # Log detailed fact split information
        debug_logger.log_fact_split(
            text=request.text,
            facts=facts,
            entities=entities,
            relations=relations
        )

        # Log the API response
        debug_logger.log_api_response(
            endpoint="/api/v1/memory/add",
            status="success",
            response_data={
                "memory_id": memory_id,
                "facts_count": len(facts),
                "entities_count": len(entities),
                "relations_count": len(relations)
            },
            duration_ms=duration_ms
        )

        return AddMemoryResponse(
            success=True,
            memory_id=memory_id,
            message="Memory added successfully"
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        debug_logger.log_api_response(
            endpoint="/api/v1/memory/add",
            status="error",
            error=str(e),
            duration_ms=duration_ms
        )
        raise HTTPException(status_code=500, detail=f"Failed to add memory: {str(e)}")


@router.post("/search", response_model=SearchMemoryResponse)
async def search_memory(request: SearchMemoryRequest) -> SearchMemoryResponse:
    """Search memories using both vector similarity and graph relationships."""
    try:
        memory = get_memory_instance(request.uid) if request.uid else get_memory_instance("default_user")
        results = memory.search(
            query=request.query,
            limit=request.limit,
            uid=request.uid
        )

        result_responses = [
            SearchResultResponse(
                memory_id=r.memory_id,
                content=r.content,
                score=r.score,
                metadata=r.metadata,
                graph_relations=r.graph_relations
            )
            for r in results
        ]

        return SearchMemoryResponse(
            query=request.query,
            results=result_responses,
            count=len(result_responses)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/search-graph", response_model=SearchGraphOnlyResponse)
async def search_graph_only(request: SearchGraphOnlyRequest) -> SearchGraphOnlyResponse:
    """Search only the knowledge graph for entity relationships.

    This searches ONLY the graph store (Neo4j), not the vector store.
    Useful for exploring relationships between entities.
    """
    try:
        memory = get_memory_instance(request.uid) if request.uid else get_memory_instance("default_user")
        relations = memory.search_graph_only(
            query=request.query,
            limit=request.limit,
            uid=request.uid
        )

        return SearchGraphOnlyResponse(
            query=request.query,
            relations=relations,
            count=len(relations)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph search failed: {str(e)}")


@router.post("/search-with-answer", response_model=SearchWithAnswerResponse)
async def search_with_answer(request: SearchWithAnswerRequest) -> SearchWithAnswerResponse:
    """Search memories and generate an AI-powered answer.

    Combines vector search, graph relationships, and LLM to generate
    a comprehensive answer to the user's question.
    """
    start_time = time.time()
    uid = request.uid or "default_user"

    try:
        # Log the search request
        debug_logger.log_api_request(
            endpoint="/api/v1/memory/search-with-answer",
            method="POST",
            uid=uid,
            request_data={
                "query": request.query,
                "limit": request.limit
            }
        )

        memory = get_memory_instance(uid)
        result = memory.search_with_answer(
            query=request.query,
            limit=request.limit,
            uid=uid
        )

        # Extract raw results and relations for logging
        raw_results = result.get("raw_results", [])
        relations = result.get("relations", [])

        # Log detailed search results
        debug_logger.log_search_results(
            query=request.query,
            results=[
                {
                    "memory_id": r.memory_id,
                    "content": r.content,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in raw_results
            ],
            relations=relations,
            limit=request.limit
        )

        result_responses = [
            SearchResultResponse(
                memory_id=r.memory_id,
                content=r.content,
                score=r.score,
                metadata=r.metadata,
                graph_relations=r.graph_relations
            )
            for r in raw_results
        ]

        duration_ms = (time.time() - start_time) * 1000

        # Log the API response
        debug_logger.log_api_response(
            endpoint="/api/v1/memory/search-with-answer",
            status="success",
            response_data={
                "results_count": len(result_responses),
                "relations_count": len(relations),
                "answer_length": len(result.get("answer", ""))
            },
            duration_ms=duration_ms
        )

        return SearchWithAnswerResponse(
            query=request.query,
            answer=result.get("answer", ""),
            memories=result.get("memories", []),
            relations=relations,
            raw_results=result_responses
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        debug_logger.log_api_response(
            endpoint="/api/v1/memory/search-with-answer",
            status="error",
            error=str(e),
            duration_ms=duration_ms
        )
        raise HTTPException(status_code=500, detail=f"Search with answer failed: {str(e)}")


@router.get("/graph", response_model=GetGraphDataResponse)
async def get_graph_data(uid: Optional[str] = Query(None, description="User ID filter")) -> GetGraphDataResponse:
    """Get complete graph visualization data.

    Returns nodes (entities) and edges (relationships) for visualization.
    """
    try:
        memory = get_memory_instance(uid) if uid else get_memory_instance("default_user")
        graph_data = memory.get_graph_data(uid=uid)

        return GetGraphDataResponse(
            nodes=graph_data.nodes,
            edges=graph_data.edges,
            node_count=len(graph_data.nodes),
            edge_count=len(graph_data.edges)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get graph data: {str(e)}")


@router.delete("/clear", response_model=ClearMemoryResponse)
async def clear_memory(uid: str = Query(..., description="User ID to clear memories for")) -> ClearMemoryResponse:
    """Clear all stored memories for a user.

    This deletes both vector store and graph store data for the user.
    """
    try:
        memory = get_memory_instance(uid)
        memory.clear()
        return ClearMemoryResponse(
            success=True,
            message=f"All memories cleared for user: {uid}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear memories: {str(e)}")


@router.get("/count", response_model=CountMemoryResponse)
async def count_memory(uid: str = Query(..., description="User ID to count memories for")) -> CountMemoryResponse:
    """Get the total count of stored memories for a user."""
    try:
        memory = get_memory_instance(uid)
        count = memory.count()
        return CountMemoryResponse(
            count=count,
            uid=uid
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to count memories: {str(e)}")
