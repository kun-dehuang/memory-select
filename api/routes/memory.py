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
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.dependencies import get_memory_instance
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


@router.post("/add", response_model=AddMemoryResponse)
async def add_memory(request: AddMemoryRequest) -> AddMemoryResponse:
    """Add a new memory with automatic entity and relationship extraction.

    The memory is stored in both vector store (for semantic search)
    and graph store (for entity relationships).
    """
    try:
        memory = get_memory_instance(request.uid)
        memory_id = await memory.add(
            uid=request.uid,
            text=request.text,
            metadata=request.metadata
        )
        return AddMemoryResponse(
            success=True,
            memory_id=memory_id,
            message="Memory added successfully"
        )
    except Exception as e:
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
    try:
        memory = get_memory_instance(request.uid) if request.uid else get_memory_instance("default_user")
        result = memory.search_with_answer(
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
            for r in result.get("raw_results", [])
        ]

        return SearchWithAnswerResponse(
            query=request.query,
            answer=result.get("answer", ""),
            memories=result.get("memories", []),
            relations=result.get("relations", []),
            raw_results=result_responses
        )
    except Exception as e:
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
