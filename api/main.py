"""FastAPI application entry point for Memory API.

This module provides the main FastAPI application with:
- CORS middleware configuration
- Route registration
- Health check endpoints
- OpenAI function schema endpoint
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import memory_router
from api.schemas.openai_functions import OPENAI_FUNCTIONS_SCHEMA
from api.schemas.responses import HealthResponse, OpenAIFunctionsResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Memory API",
    description="OpenAI Function Calling compatible API for memory operations with vector and graph search",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS - allow all origins for local/internal network usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(memory_router)

# Also register the router at the root for compatibility
app.include_router(memory_router, prefix="")


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0"
    )


@app.get("/api/v1/functions/schema", response_model=OpenAIFunctionsResponse, tags=["schema"])
async def get_openai_functions_schema() -> OpenAIFunctionsResponse:
    """Get OpenAI Function Calling compatible schema.

    Returns the function definitions that can be used with OpenAI's
    function calling feature or compatible implementations.
    """
    return OpenAIFunctionsResponse(functions=OPENAI_FUNCTIONS_SCHEMA["functions"])


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Memory API",
        "version": "0.1.0",
        "description": "OpenAI Function Calling compatible API for memory operations",
        "endpoints": {
            "health": "/health",
            "functions_schema": "/api/v1/functions/schema",
            "memory": "/api/v1/memory/*",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
