"""Request schemas for Memory API."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class AddMemoryRequest(BaseModel):
    """Request to add a new memory."""
    uid: str = Field(..., description="User ID for memory isolation")
    text: str = Field(..., description="Memory text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SearchMemoryRequest(BaseModel):
    """Request to search memories."""
    query: str = Field(..., description="Search query text")
    limit: int = Field(default=5, ge=1, le=100, description="Max number of results")
    uid: Optional[str] = Field(None, description="User ID filter (optional)")


class SearchWithAnswerRequest(BaseModel):
    """Request to search memories and generate AI answer."""
    query: str = Field(..., description="Search query text")
    limit: int = Field(default=5, ge=1, le=100, description="Max number of results")
    uid: Optional[str] = Field(None, description="User ID filter (optional)")


class SearchGraphOnlyRequest(BaseModel):
    """Request to search only the graph for relationships."""
    query: str = Field(..., description="Search query text")
    limit: int = Field(default=5, ge=1, le=100, description="Max number of results")
    uid: Optional[str] = Field(None, description="User ID filter (optional)")


class GetGraphDataRequest(BaseModel):
    """Request to get graph visualization data."""
    uid: Optional[str] = Field(None, description="User ID filter (optional)")


class ClearMemoryRequest(BaseModel):
    """Request to clear all memories for a user."""
    uid: str = Field(..., description="User ID to clear memories for")


class CountMemoryRequest(BaseModel):
    """Request to count memories for a user."""
    uid: str = Field(..., description="User ID to count memories for")
