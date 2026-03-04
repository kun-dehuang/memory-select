"""Configuration management for Memory Comparison Tool."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class GeminiConfig:
    """Gemini LLM configuration compatible with mem0's BaseLlmConfig."""
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash"))
    temperature: float = 0.1
    max_tokens: int = 2000
    top_p: float = 0.9
    top_k: int = 1
    enable_vision: bool = False
    vision_details: Optional[str] = "auto"


@dataclass
class Mem0Config:
    """Mem0 configuration."""
    qdrant_host: str = field(default_factory=lambda: os.getenv("MEM0_QDRANT_HOST", "localhost"))
    qdrant_port: str = field(default_factory=lambda: os.getenv("MEM0_QDRANT_PORT", "6333"))
    qdrant_api_key: str = field(default_factory=lambda: os.getenv("QDRANT_API_KEY", ""))
    qdrant_https: bool = field(default_factory=lambda: os.getenv("QDRANT_HTTPS", "false").lower() == "true")
    neo4j_uri: str = field(default_factory=lambda: os.getenv("MEM0_NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("MEM0_NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("MEM0_NEO4J_PASSWORD", "password123"))
    collection_name: str = "memory_store"


@dataclass
class ZepConfig:
    """Zep configuration."""
    api_key: str = field(default_factory=lambda: os.getenv("ZEP_API_KEY", ""))
    api_url: str = field(default_factory=lambda: os.getenv("ZEP_API_URL", "https://api.getzep.com"))


@dataclass
class AppConfig:
    """Application configuration."""
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    mem0: Mem0Config = field(default_factory=Mem0Config)
    zep: ZepConfig = field(default_factory=ZepConfig)

    @property
    def data_dir(self) -> str:
        return os.path.join(os.path.dirname(__file__), "data")

    @property
    def uploads_dir(self) -> str:
        return os.path.join(self.data_dir, "uploads")


# Global config instance
config = AppConfig()
