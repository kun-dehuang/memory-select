"""FastAPI dependencies for dependency injection."""

from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends

from core.mem0_wrapper import Mem0Graph


@lru_cache(maxsize=128)
def get_memory_instance(uid: str) -> Mem0Graph:
    """Get or create a Mem0Graph instance for a user.

    Uses LRU cache to reuse instances for the same user ID.

    Args:
        uid: User ID for memory isolation

    Returns:
        Mem0Graph instance
    """
    return Mem0Graph(user_id=uid)


async def get_memory_for_request(uid: Optional[str] = None) -> Optional[Mem0Graph]:
    """Get memory instance for a request.

    Args:
        uid: Optional user ID

    Returns:
        Mem0Graph instance or None if no uid provided
    """
    if uid:
        return get_memory_instance(uid)
    return None


# Type alias for dependency injection
MemoryDep = Annotated[Mem0Graph, Depends(get_memory_instance)]
OptionalMemoryDep = Annotated[Optional[Mem0Graph], Depends(get_memory_for_request)]
