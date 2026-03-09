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
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query, Request

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

# Create a thread pool executor for running synchronous operations
# This helps prevent thread exhaustion in containerized environments
_thread_pool: Optional[ThreadPoolExecutor] = None


def get_thread_pool() -> ThreadPoolExecutor:
    """Get or create the shared thread pool executor."""
    global _thread_pool
    if _thread_pool is None:
        # Limit to 4 workers to avoid thread exhaustion in Railway
        _thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mem_sync_")
    return _thread_pool


async def run_in_thread_pool(func, *args, **kwargs):
    """Run a synchronous function in the thread pool."""
    loop = asyncio.get_running_loop()
    # Wrap the function with args and kwargs for run_in_executor
    import functools
    submitted_at = time.time()
    execution_info: dict[str, float] = {}

    def wrapped_with_timing():
        execution_info["started_at"] = time.time()
        return func(*args, **kwargs)

    wrapped_func = functools.partial(wrapped_with_timing)
    result = await loop.run_in_executor(get_thread_pool(), wrapped_func)
    thread_wait_ms = max(0.0, (execution_info.get("started_at", submitted_at) - submitted_at) * 1000)
    return result, thread_wait_ms


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
        add_start = time.time()
        result = await memory._async_client.add(
            messages=[{"role": "user", "content": request.text}],
            user_id=request.uid,
            metadata=request.metadata or {}
        )
        add_duration_ms = (time.time() - add_start) * 1000
        duration_ms = (time.time() - start_time) * 1000

        # Extract and log fact splits and entities/relations
        facts = []
        entities = []
        relations = []
        memory_id = ""

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
            message="Memory added successfully",
            timings={"add": add_duration_ms}
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
        start_time = time.time()
        memory = get_memory_instance(request.uid) if request.uid else get_memory_instance("default_user")
        # Run the synchronous search in a thread pool
        results, _thread_wait_ms = await run_in_thread_pool(
            memory.search,
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
            count=len(result_responses),
            timings={"search": (time.time() - start_time) * 1000}
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
        start_time = time.time()
        memory = get_memory_instance(request.uid) if request.uid else get_memory_instance("default_user")
        # Run the synchronous search_graph_only in a thread pool
        relations, _thread_wait_ms = await run_in_thread_pool(
            memory.search_graph_only,
            query=request.query,
            limit=request.limit,
            uid=request.uid
        )

        return SearchGraphOnlyResponse(
            query=request.query,
            relations=relations,
            count=len(relations),
            timings={"search_graph": (time.time() - start_time) * 1000}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph search failed: {str(e)}")


@router.post("/search-with-answer", response_model=SearchWithAnswerResponse)
async def search_with_answer(
    request: SearchWithAnswerRequest,
    raw_request: Request
) -> SearchWithAnswerResponse:
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

        instance_init_start = time.time()
        memory = get_memory_instance(uid)
        instance_init_ms = (time.time() - instance_init_start) * 1000

        # Run the synchronous search_with_answer in a thread pool to avoid thread issues
        result, thread_wait_ms = await run_in_thread_pool(
            memory.search_with_answer,
            query=request.query,
            limit=request.limit,
            uid=uid
        )

        postprocess_start = time.time()
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
        postprocess_ms = (time.time() - postprocess_start) * 1000

        route_total_ms = (time.time() - start_time) * 1000
        request_start_time = getattr(raw_request.state, "request_start_time", start_time)
        request_total_ms = (time.time() - request_start_time) * 1000

        core_timings = dict(result.get("timings", {}))
        server_timings = {
            "instance_init": instance_init_ms,
            "thread_wait": thread_wait_ms,
            "search": float(core_timings.get("search", 0.0)),
            "llm": float(core_timings.get("llm", 0.0)),
            "core_total": float(core_timings.get("core_total", 0.0)),
            "postprocess": postprocess_ms,
            "route_total": route_total_ms,
            "request_total": request_total_ms,
        }
        timings = {
            "server": server_timings,
            "client": {},
        }

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
            raw_results=result_responses,
            timings=timings
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
        # Run the synchronous get_graph_data in a thread pool
        graph_data = await run_in_thread_pool(
            memory.get_graph_data,
            uid=uid
        )

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
        # Run the synchronous clear in a thread pool
        await run_in_thread_pool(memory.clear)
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
        # Run the synchronous count in a thread pool
        count = await run_in_thread_pool(memory.count)
        return CountMemoryResponse(
            count=count,
            uid=uid
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to count memories: {str(e)}")
