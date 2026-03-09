"""FastAPI application entry point for Memory API.

This module provides the main FastAPI application with:
- CORS middleware configuration
- API logging middleware
- Route registration
- Health check endpoints
- OpenAI function schema endpoint
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import memory_router, logs_router
from api.dependencies import clear_memory_instance_cache
from api.middleware import APILoggingMiddleware
from api.schemas.openai_functions import OPENAI_FUNCTIONS_SCHEMA
from api.schemas.responses import HealthResponse, OpenAIFunctionsResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown
    clear_memory_instance_cache()


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

# Add API logging middleware
app.add_middleware(APILoggingMiddleware)

# Register routes
app.include_router(memory_router)

# Register logs router
app.include_router(logs_router)

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


@app.get("/api/v1/config/debug", tags=["debug"])
async def config_debug() -> dict:
    """Debug endpoint to check configuration (hides sensitive data)."""
    from config import config
    import os

    return {
        "neo4j": {
            "uri": config.mem0.neo4j_uri,
            "user": config.mem0.neo4j_user,
            "password_set": len(config.mem0.neo4j_password) > 0,
        },
        "qdrant": {
            "host": config.mem0.qdrant_host,
            "api_key_set": len(config.mem0.qdrant_api_key) > 0,
        },
        "gemini": {
            "api_key_set": len(config.gemini.api_key) > 0,
            "model": config.gemini.model,
        },
        "env_raw": {
            "MEM0_NEO4J_URI": os.getenv("MEM0_NEO4J_URI", "not set"),
            "MEM0_NEO4J_USER": os.getenv("MEM0_NEO4J_USER", "not set"),
            "MEM0_NEO4J_PASSWORD": "***" if os.getenv("MEM0_NEO4J_PASSWORD") else "not set",
            "MEM0_QDRANT_HOST": os.getenv("MEM0_QDRANT_HOST", "not set"),
            "QDRANT_API_KEY": "***" if os.getenv("QDRANT_API_KEY") else "not set",
            "GEMINI_API_KEY": "***" if os.getenv("GEMINI_API_KEY") else "not set",
        }
    }


@app.get("/api/v1/config/test-neo4j", tags=["debug"])
async def test_neo4j_connection() -> dict:
    """Test Neo4j connection directly."""
    from config import config
    import traceback

    result = {
        "config": {
            "uri": config.mem0.neo4j_uri,
            "user": config.mem0.neo4j_user,
            "password_set": len(config.mem0.neo4j_password) > 0,
        },
        "connection_test": None,
        "langchain_test": None,
        "error": None
    }

    # Test 1: Direct neo4j driver connection
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            config.mem0.neo4j_uri,
            auth=(config.mem0.neo4j_user, config.mem0.neo4j_password)
        )
        driver.verify_connectivity()
        result["connection_test"] = "SUCCESS - Direct driver connection works"
        driver.close()
    except Exception as e:
        result["connection_test"] = f"FAILED - {str(e)}"
        result["error"] = str(e)

    # Test 2: langchain_neo4j connection
    try:
        from langchain_neo4j import Neo4jGraph
        graph = Neo4jGraph(
            url=config.mem0.neo4j_uri,
            username=config.mem0.neo4j_user,
            password=config.mem0.neo4j_password,
            database="neo4j",
            refresh_schema=False
        )
        # Try a simple query
        graph.query("RETURN 1 AS test")
        result["langchain_test"] = "SUCCESS - langchain_neo4j works"
    except Exception as e:
        result["langchain_test"] = f"FAILED - {str(e)}"
        if result["error"] is None:
            result["error"] = f"langchain: {str(e)}"
        result["traceback"] = traceback.format_exc()

    return result

@app.get("/api/v1/config/test-mem0-internal", tags=["debug"])
async def test_mem0_internal_neo4j() -> dict:
    """Test Neo4j connection exactly like mem0 MemoryGraph does."""
    from langchain_neo4j import Neo4jGraph
    from config import config
    import os

    # Read env vars directly like Mem0Base does
    neo4j_uri = os.getenv("MEM0_NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("MEM0_NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("MEM0_NEO4J_PASSWORD", "password123")

    result = {
        "env_vars": {
            "uri": neo4j_uri,
            "user": neo4j_user,
            "password_length": len(neo4j_password),
        },
        "test1_positional_args": None,
        "test2_keyword_args": None,
        "error": None
    }

    # Test 1: Using positional args (like MemoryGraph does)
    try:
        graph1 = Neo4jGraph(
            neo4j_uri,
            neo4j_user,
            neo4j_password,
            "neo4j",
            refresh_schema=False,
            driver_config={"notifications_min_severity": "OFF"},
        )
        # Try a simple query
        graph1.query("RETURN 1 AS test")
        result["test1_positional_args"] = "SUCCESS"
    except Exception as e:
        result["test1_positional_args"] = f"FAILED - {str(e)}"
        result["error"] = str(e)

    # Test 2: Using keyword args (like test-neo4j does)
    try:
        graph2 = Neo4jGraph(
            url=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password,
            database="neo4j",
            refresh_schema=False
        )
        graph2.query("RETURN 1 AS test")
        result["test2_keyword_args"] = "SUCCESS"
    except Exception as e:
        result["test2_keyword_args"] = f"FAILED - {str(e)}"
        if result["error"] is None:
            result["error"] = str(e)

    return result


@app.get("/api/v1/config/show-mem0-config", tags=["debug"])
async def show_mem0_config() -> dict:
    """Show the actual mem0 configuration (without sensitive data)."""
    from config import config
    from mem0.configs.base import MemoryConfig, VectorStoreConfig, GraphStoreConfig, LlmConfig
    from mem0.embeddings.configs import EmbedderConfig

    # Build the same config that Mem0Base uses
    qdrant_config = {
        "collection_name": "test_collection",
        "embedding_model_dims": 768,
    }

    if config.mem0.qdrant_api_key or config.mem0.qdrant_host.startswith("http"):
        qdrant_config["url"] = config.mem0.qdrant_host
        if config.mem0.qdrant_api_key:
            qdrant_config["api_key"] = "***"
    else:
        qdrant_config["host"] = config.mem0.qdrant_host
        qdrant_config["port"] = int(config.mem0.qdrant_port)

    graph_config = {
        "url": config.mem0.neo4j_uri,
        "username": config.mem0.neo4j_user,
        "password": "***",
        "database": "neo4j",
    }

    return {
        "qdrant_config": qdrant_config,
        "graph_config": graph_config,
        "neo4j_uri_from_config": config.mem0.neo4j_uri,
        "neo4j_user_from_config": config.mem0.neo4j_user,
        "neo4j_password_length": len(config.mem0.neo4j_password),
    }

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
