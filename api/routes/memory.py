"""Memory API routes."""

import asyncio
import logging
import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

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
logger = logging.getLogger("memory_select.api")

# Create a thread pool executor for running synchronous operations
# This helps prevent thread exhaustion in containerized environments
_thread_pool: Optional[ThreadPoolExecutor] = None


def get_thread_pool() -> ThreadPoolExecutor:
    """Get or create the shared thread pool executor."""
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mem_sync_")
    return _thread_pool


def shutdown_thread_pool() -> None:
    """Shutdown the shared thread pool during app shutdown."""
    global _thread_pool
    if _thread_pool is None:
        return
    _thread_pool.shutdown(wait=False, cancel_futures=True)
    _thread_pool = None


async def run_in_thread_pool(func, *args, with_wait_time: bool = False, **kwargs):
    """Run a synchronous function in the thread pool.

    By default this preserves the original behavior and returns only the
    function result. Callers can opt in to thread wait timing when needed.
    """
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
    if with_wait_time:
        return result, thread_wait_ms
    return result


@router.post("/add", response_model=AddMemoryResponse)
async def add_memory(request: AddMemoryRequest) -> AddMemoryResponse:
    """Add a new memory."""
    start_time = time.time()
    try:
        memory = get_memory_instance(request.uid)
        result = await memory.add(request.uid, request.text, request.metadata or {})

        return AddMemoryResponse(
            success=True,
            memory_id=result["memory_id"],
            message="Memory added successfully",
            timings={
                **result.get("timings", {}),
                "total": (time.time() - start_time) * 1000,
            },
        )
    except Exception as e:
        logger.exception("Failed to add memory for uid=%s", request.uid)
        raise HTTPException(status_code=500, detail=f"Failed to add memory: {str(e)}")


@router.post("/search", response_model=SearchMemoryResponse)
async def search_memory(request: SearchMemoryRequest) -> SearchMemoryResponse:
    """Search memories using both vector similarity and graph relationships."""
    try:
        start_time = time.time()
        memory = get_memory_instance(request.uid) if request.uid else get_memory_instance("default_user")
        # Run the synchronous search in a thread pool
        results = await run_in_thread_pool(
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
    """Search only the knowledge graph for entity relationships."""
    try:
        start_time = time.time()
        memory = get_memory_instance(request.uid) if request.uid else get_memory_instance("default_user")
        # Run the synchronous search_graph_only in a thread pool
        relations = await run_in_thread_pool(
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
) -> SearchWithAnswerResponse:
    """Search memories and generate an AI-powered answer."""
    start_time = time.time()
    uid = request.uid or "default_user"

    try:
        memory = get_memory_instance(uid)

        result, thread_wait_ms = await run_in_thread_pool(
            memory.search_with_answer,
            with_wait_time=True,
            query=request.query,
            limit=request.limit,
            uid=uid
        )

        raw_results = result.get("raw_results", [])
        relations = result.get("relations", [])

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

        return SearchWithAnswerResponse(
            query=request.query,
            answer=result.get("answer", ""),
            memories=result.get("memories", []),
            relations=relations,
            raw_results=result_responses,
            timings={
                **result.get("timings", {}),
                "thread_wait": thread_wait_ms,
                "total": (time.time() - start_time) * 1000,
            },
        )
    except Exception as e:
        logger.exception("Search with answer failed for uid=%s", uid)
        raise HTTPException(status_code=500, detail=f"Search with answer failed: {str(e)}")


@router.get("/graph", response_model=GetGraphDataResponse)
async def get_graph_data(uid: Optional[str] = Query(None, description="User ID filter")) -> GetGraphDataResponse:
    """Get complete graph visualization data."""
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
    """Clear all stored memories for a user."""
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
