"""Shared API models."""

from typing import Any
from pydantic import BaseModel, Field


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
