"""Response schemas for Memory API."""

from typing import Any, Optional
from pydantic import BaseModel

from models import SearchResult, GraphSearchRelation, GraphEntity, GraphRelation


class AddMemoryResponse(BaseModel):
    """Response from add memory operation."""
    success: bool
    memory_id: str
    message: Optional[str] = None
    timings: dict[str, float]


class SearchResultResponse(BaseModel):
    """Single search result."""
    memory_id: str
    content: str
    score: float
    metadata: dict[str, Any]
    graph_relations: list[GraphSearchRelation]


class SearchMemoryResponse(BaseModel):
    """Response from memory search."""
    query: str
    results: list[SearchResultResponse]
    count: int
    timings: dict[str, float]


class SearchWithAnswerResponse(BaseModel):
    """Response from search with AI-generated answer."""
    query: str
    answer: str
    memories: list[str]
    relations: list[dict[str, str]]
    raw_results: list[SearchResultResponse]
    timings: dict[str, float]


class SearchGraphOnlyResponse(BaseModel):
    """Response from graph-only search."""
    query: str
    relations: list[GraphSearchRelation]
    count: int
    timings: dict[str, float]


class GetGraphDataResponse(BaseModel):
    """Response with graph visualization data."""
    nodes: list[GraphEntity]
    edges: list[GraphRelation]
    node_count: int
    edge_count: int


class ClearMemoryResponse(BaseModel):
    """Response from clear memory operation."""
    success: bool
    message: str


class CountMemoryResponse(BaseModel):
    """Response from count memory operation."""
    count: int
    uid: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class OpenAIFunctionsResponse(BaseModel):
    """OpenAI Functions schema response."""
    functions: list[dict[str, Any]]
