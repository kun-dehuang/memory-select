"""Configuration for the API-only memory service."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class GeminiConfig:
    """Gemini configuration."""
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash"))


@dataclass
class Mem0Config:
    """Mem0 backing store configuration."""
    qdrant_host: str = field(default_factory=lambda: os.getenv("MEM0_QDRANT_HOST", "localhost"))
    qdrant_port: str = field(default_factory=lambda: os.getenv("MEM0_QDRANT_PORT", "6333"))
    qdrant_api_key: str = field(default_factory=lambda: os.getenv("QDRANT_API_KEY", ""))
    qdrant_https: bool = field(default_factory=lambda: os.getenv("QDRANT_HTTPS", "false").lower() == "true")
    neo4j_uri: str = field(default_factory=lambda: os.getenv("MEM0_NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("MEM0_NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("MEM0_NEO4J_PASSWORD", "password123"))
    collection_name: str = "memory_store"

@dataclass
class AppConfig:
    """Application configuration."""
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    mem0: Mem0Config = field(default_factory=Mem0Config)


# Global config instance
config = AppConfig()
