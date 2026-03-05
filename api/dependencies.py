"""FastAPI dependencies for dependency injection."""

from typing import Annotated, Optional

from fastapi import Depends

from core.mem0_wrapper import Mem0Graph


# 使用简单的字典缓存，不使用 lru_cache 以避免配置更新后的问题
_memory_instances: dict[str, Mem0Graph] = {}


def get_memory_instance(uid: str) -> Mem0Graph:
    """Get or create a Mem0Graph instance for a user.

    Args:
        uid: User ID for memory isolation

    Returns:
        Mem0Graph instance
    """
    # 每次创建新实例以确保使用最新配置
    # Mem0Graph 内部已处理 user_id 隔离，缓存不是必需的
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
