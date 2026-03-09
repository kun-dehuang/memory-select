"""Core modules for memory systems with unified interface."""

from .mem0_wrapper import (
    MemoryInterface,
    Mem0Standard,
    Mem0Graph,
    Mem0Factory,
)
from .zep_wrapper import (
    ZepMemory,
    ZepGraph,
    ZepFactory,
)
from .remote_memory_client import (
    RemoteMemoryClient,
    RemoteMemoryFactory,
)

__all__ = [
    # Interface
    "MemoryInterface",
    # Mem0
    "Mem0Standard",
    "Mem0Graph",
    "Mem0Factory",
    # Zep
    "ZepMemory",
    "ZepGraph",
    "ZepFactory",
    # Remote API
    "RemoteMemoryClient",
    "RemoteMemoryFactory",
]
