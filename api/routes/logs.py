"""Logs API routes for querying detailed operation logs.

Provides endpoints to retrieve recent API logs for debugging and monitoring.
"""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from utils.logger import DebugLogger


router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


class LogEntry(BaseModel):
    """Single log entry model."""
    timestamp: str = Field(..., description="ISO format timestamp")
    type: str = Field(..., description="Log type (api_request, api_response, fact_split, search_results)")
    level: str = Field(..., description="Log level (INFO, DEBUG, ERROR)")
    endpoint: Optional[str] = Field(None, description="API endpoint for request/response logs")
    status: Optional[str] = Field(None, description="Status for response logs (success/error)")
    duration_ms: Optional[float] = Field(None, description="Request duration in milliseconds")
    query: Optional[str] = Field(None, description="Search query for search_results logs")
    results_count: Optional[int] = Field(None, description="Number of results for search_results logs")
    # Additional dynamic fields stored in log entry
    extra: dict = Field(default_factory=dict, description="Additional log-specific data")


class LogsResponse(BaseModel):
    """Response model for logs query."""
    count: int = Field(..., description="Number of log entries returned")
    logs: List[dict] = Field(..., description="List of log entries")


@router.get("", response_model=LogsResponse)
async def get_logs(
    level: Optional[str] = Query(None, description="Filter by log level (INFO, DEBUG, ERROR)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    search: Optional[str] = Query(None, description="Search keyword to filter logs"),
    log_type: Optional[str] = Query(None, description="Filter by log type (api_request, api_response, fact_split, search_results)")
) -> LogsResponse:
    """Get recent API and operation logs.

    Returns detailed logs from memory including:
    - API requests and responses
    - Fact extraction and splits from /add endpoint
    - Search results from /search-with-answer endpoint
    - Graph entity/relation extraction

    Query parameters:
    - level: Filter by log level (INFO, DEBUG, ERROR)
    - limit: Maximum number of logs to return (default: 100, max: 1000)
    - search: Keyword search across all log fields
    - log_type: Filter by log type

    Returns:
        LogsResponse with count and list of log entries
    """
    try:
        logs = DebugLogger.get_recent_logs(
            level=level,
            limit=limit,
            search=search,
            log_type=log_type
        )

        return LogsResponse(
            count=len(logs),
            logs=logs
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve logs: {str(e)}")


@router.delete("/clear")
async def clear_logs() -> dict:
    """Clear all stored logs from memory.

    This endpoint removes all logs from the in-memory storage.
    Use with caution - logs cannot be recovered after clearing.

    Returns:
        Success message
    """
    try:
        DebugLogger.clear_logs()
        return {"success": True, "message": "All logs cleared from memory"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear logs: {str(e)}")


@router.get("/stats")
async def get_log_stats() -> dict:
    """Get statistics about stored logs.

    Returns counts of logs by type, level, and total count.

    Returns:
        Dictionary with log statistics
    """
    try:
        all_logs = DebugLogger.get_recent_logs(limit=10000)

        # Count by type
        type_counts = {}
        level_counts = {}
        endpoint_counts = {}

        for log in all_logs:
            log_type = log.get("type", "unknown")
            level = log.get("level", "UNKNOWN")
            endpoint = log.get("endpoint", "unknown")

            type_counts[log_type] = type_counts.get(log_type, 0) + 1
            level_counts[level] = level_counts.get(level, 0) + 1
            endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

        return {
            "total_logs": len(all_logs),
            "by_type": type_counts,
            "by_level": level_counts,
            "by_endpoint": endpoint_counts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve log stats: {str(e)}")
