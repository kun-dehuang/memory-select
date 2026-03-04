#!/usr/bin/env python3
"""Delete all data for a specific user from mem0 stores (Qdrant and Neo4j)."""

import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import config
from mem0 import Memory
from mem0.configs.base import MemoryConfig, VectorStoreConfig, GraphStoreConfig, LlmConfig
from mem0.embeddings.configs import EmbedderConfig


def delete_user_data(user_id: str) -> dict:
    """Delete all data for a specific user from both Qdrant and Neo4j.

    Args:
        user_id: The user ID to delete data for (e.g., "bingj")

    Returns:
        Dictionary with deletion results
    """
    collection_name = f"memory_store_{user_id}"

    print(f"\n{'='*60}")
    print(f"Deleting data for user_id: {user_id}")
    print(f"Qdrant collection: {collection_name}")
    print(f"{'='*60}\n")

    # Configure mem0 with the same settings
    mem_config = MemoryConfig(
        vector_store=VectorStoreConfig(
            provider="qdrant",
            config={
                "host": config.mem0.qdrant_host,
                "port": int(config.mem0.qdrant_port),
                "collection_name": collection_name,
                "embedding_model_dims": 768,
            }
        ),
        llm=LlmConfig(
            provider="gemini",
            config={
                "model": config.gemini.model,
                "api_key": config.gemini.api_key,
            }
        ),
        embedder=EmbedderConfig(
            provider="gemini",
            config={
                "model": "models/gemini-embedding-001",
                "api_key": config.gemini.api_key,
            }
        ),
        graph_store=GraphStoreConfig(
            provider="neo4j",
            config={
                "url": config.mem0.neo4j_uri,
                "username": config.mem0.neo4j_user,
                "password": config.mem0.neo4j_password,
            },
            llm=LlmConfig(
                provider="gemini",
                config={
                    "model": config.gemini.model,
                    "api_key": config.gemini.api_key,
                }
            ),
            threshold=0.7,
        ),
    )

    client = Memory(mem_config)

    results = {
        "user_id": user_id,
        "vector_store": {"deleted": False, "count": 0, "error": None},
        "graph_store": {"deleted": False, "count": 0, "error": None},
    }

    # 1. Delete from Vector Store (Qdrant)
    print("[1/3] Checking Vector Store (Qdrant)...")
    try:
        # Get count before deletion
        all_data = client.get_all(user_id=user_id)
        if all_data and "results" in all_data:
            results["vector_store"]["count"] = len(all_data["results"])
            print(f"  Found {results['vector_store']['count']} memories in vector store")
        else:
            print("  No memories found in vector store")

        # Delete all vectors
        print("  Deleting all vectors...")
        client.delete_all(user_id=user_id)
        results["vector_store"]["deleted"] = True
        print("  Vector store deletion complete")
    except Exception as e:
        results["vector_store"]["error"] = str(e)
        print(f"  Error deleting from vector store: {e}")

    # 2. Delete from Graph Store (Neo4j)
    print("\n[2/3] Deleting from Graph Store (Neo4j)...")
    try:
        if client.enable_graph and client.graph:
            # Delete all graph data for this user
            client.graph.delete_all(filters={"user_id": user_id})
            results["graph_store"]["deleted"] = True
            print("  Graph store deletion complete")
        else:
            results["graph_store"]["error"] = "Graph not enabled"
            print("  Graph store not enabled")
    except Exception as e:
        results["graph_store"]["error"] = str(e)
        print(f"  Error deleting from graph store: {e}")

    # 3. Verify deletion
    print("\n[3/3] Verifying deletion...")
    try:
        remaining = client.get_all(user_id=user_id)
        remaining_count = len(remaining.get("results", [])) if remaining else 0
        print(f"  Remaining memories in vector store: {remaining_count}")

        if client.enable_graph and client.graph:
            graph_data = client.graph.get_all(filters={"user_id": user_id}, limit=1000)
            remaining_graph = len(graph_data) if graph_data else 0
            print(f"  Remaining relations in graph store: {remaining_graph}")
        else:
            remaining_graph = "N/A"
            print(f"  Remaining relations in graph store: N/A")

        if remaining_count == 0:
            print("\n✓ Vector store successfully cleaned")
        else:
            print(f"\n⚠ Warning: {remaining_count} items still remain in vector store")

        if remaining_graph == 0:
            print("✓ Graph store successfully cleaned")
        elif remaining_graph == "N/A":
            print("⚠ Graph store status unknown")
        else:
            print(f"⚠ Warning: {remaining_graph} items still remain in graph store")

    except Exception as e:
        print(f"  Error during verification: {e}")

    return results


if __name__ == "__main__":
    user_id = "bingj"

    if len(sys.argv) > 1:
        user_id = sys.argv[1]

    print(f"\nStarting deletion for user: {user_id}")
    print("This will delete ALL data for this user from both Qdrant and Neo4j.")

    confirm = input("\nType 'yes' to confirm: ")
    if confirm.lower() != "yes":
        print("Deletion cancelled.")
        sys.exit(0)

    results = delete_user_data(user_id)

    print(f"\n{'='*60}")
    print("Deletion Summary")
    print(f"{'='*60}")
    print(f"User ID: {results['user_id']}")
    print(f"\nVector Store (Qdrant):")
    print(f"  Deleted: {results['vector_store']['deleted']}")
    print(f"  Items found: {results['vector_store']['count']}")
    if results['vector_store']['error']:
        print(f"  Error: {results['vector_store']['error']}")

    print(f"\nGraph Store (Neo4j):")
    print(f"  Deleted: {results['graph_store']['deleted']}")
    if results['graph_store']['error']:
        print(f"  Error: {results['graph_store']['error']}")
    print()
