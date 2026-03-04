"""Data models for the Memory Comparison Tool."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """Generic memory record structure."""
    uid: str
    text: str
    timestamp: str
    category: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphSearchRelation(BaseModel):
    """A single relation result from graph search."""
    source: str
    relationship: str
    destination: str


class SearchResult(BaseModel):
    """Search result from memory systems."""
    memory_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Graph relations (only populated by graph-based systems)
    graph_relations: list[GraphSearchRelation] = Field(default_factory=list)
    # Internal timestamp for time-based sorting (private attribute)
    _timestamp: int = 0


class ComparisonResult(BaseModel):
    """Result of comparing two memory systems."""
    query: str
    results_standard: list[SearchResult]
    results_graph: list[SearchResult]
    query_time_standard: float
    query_time_graph: float


class GraphEntity(BaseModel):
    """Entity extracted from graph memory."""
    name: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphRelation(BaseModel):
    """Relation from graph memory."""
    source: str
    target: str
    relation_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphVisualization(BaseModel):
    """Graph data for visualization."""
    nodes: list[GraphEntity]
    edges: list[GraphRelation]


class SystemMetrics(BaseModel):
    """Metrics for a memory system."""
    system_name: str
    total_memories: int
    indexing_time: float
    avg_query_time: float
    memory_type: str  # "vector" or "graph"
