"""OpenAI Function Calling compatible schemas.

This module defines the OpenAI function calling schema for memory operations.
External agents can use these schemas to call memory operations as tools.
"""

OPENAI_FUNCTIONS_SCHEMA = {
    "functions": [
        {
            "name": "add_memory",
            "description": "Add a new memory to the knowledge base with automatic entity and relationship extraction",
            "parameters": {
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "User ID for memory isolation"
                    },
                    "text": {
                        "type": "string",
                        "description": "Memory text content to store"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata (optional)"
                    }
                },
                "required": ["uid", "text"]
            }
        },
        {
            "name": "search_memory",
            "description": "Search memories using both vector similarity and graph relationships",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5
                    },
                    "uid": {
                        "type": "string",
                        "description": "User ID to filter memories (optional)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "search_with_answer",
            "description": "Search memories and generate an AI-powered answer using retrieved context",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Question or search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to retrieve",
                        "default": 5
                    },
                    "uid": {
                        "type": "string",
                        "description": "User ID to filter memories (optional)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "search_graph_only",
            "description": "Search only the knowledge graph for entity relationships without vector search",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for graph entities"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 5
                    },
                    "uid": {
                        "type": "string",
                        "description": "User ID to filter memories (optional)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_graph_data",
            "description": "Get complete graph visualization data with nodes and edges",
            "parameters": {
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "User ID to filter graph data (optional)"
                    }
                }
            }
        },
        {
            "name": "clear_memory",
            "description": "Clear all stored memories for a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "User ID to clear memories for"
                    }
                },
                "required": ["uid"]
            }
        },
        {
            "name": "count_memory",
            "description": "Get the total count of stored memories for a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "User ID to count memories for"
                    }
                },
                "required": ["uid"]
            }
        }
    ]
}
