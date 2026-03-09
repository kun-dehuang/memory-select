"""FastAPI dependencies for dependency injection."""

import os
import threading
import time
from collections import OrderedDict
from hashlib import sha256
from typing import Annotated, Any, Optional

from fastapi import Depends

from core.mem0_wrapper import Mem0Graph


_CACHE_TTL_SECONDS = 30 * 60
_CACHE_MAX_ENTRIES = 100
_CACHE_KEY_SCOPE = "uid+collection+config"
_CACHE_ENV_KEYS = (
    "MEM0_QDRANT_HOST",
    "MEM0_QDRANT_PORT",
    "QDRANT_API_KEY",
    "MEM0_NEO4J_URI",
    "MEM0_NEO4J_USER",
    "MEM0_NEO4J_PASSWORD",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
)

# 使用带元数据的有序缓存，支持 TTL 和容量淘汰
_memory_instances: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_memory_instances_lock = threading.RLock()
_instance_creation_locks: dict[str, threading.Lock] = {}


def _build_collection_name(uid: str) -> str:
    return f"memory_store_{uid}"


def _build_config_fingerprint() -> str:
    raw = "|".join(f"{key}={os.getenv(key, '')}" for key in _CACHE_ENV_KEYS)
    return sha256(raw.encode("utf-8")).hexdigest()


def _build_cache_key(uid: str, collection_name: str, config_fingerprint: str) -> str:
    return f"{uid}|{collection_name}|{config_fingerprint}"


def _close_memory_instance(instance: Mem0Graph) -> None:
    for attr_name, close_method in (("_async_client", "aclose"), ("_async_client", "close"), ("_sync_client", "close")):
        client = getattr(instance, attr_name, None)
        if client is None:
            continue
        closer = getattr(client, close_method, None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass


def _evict_expired_locked(now: float) -> None:
    expired_keys = [
        cache_key
        for cache_key, entry in _memory_instances.items()
        if now - float(entry.get("last_used_at", now)) > _CACHE_TTL_SECONDS
    ]
    for cache_key in expired_keys:
        entry = _memory_instances.pop(cache_key, None)
        if entry:
            _close_memory_instance(entry["instance"])
        _instance_creation_locks.pop(cache_key, None)


def _evict_if_oversized_locked() -> None:
    while len(_memory_instances) > _CACHE_MAX_ENTRIES:
        cache_key, entry = _memory_instances.popitem(last=False)
        _close_memory_instance(entry["instance"])
        _instance_creation_locks.pop(cache_key, None)


def clear_memory_instance_cache() -> None:
    with _memory_instances_lock:
        while _memory_instances:
            _, entry = _memory_instances.popitem(last=False)
            _close_memory_instance(entry["instance"])
        _instance_creation_locks.clear()


def _build_cache_info(
    *,
    cache_hit: bool,
    cache_age_ms: float,
    cache_lookup_start: float,
    lock_wait_ms: float,
    cache_state: str,
) -> dict[str, Any]:
    return {
        "cache_hit": cache_hit,
        "cache_age_ms": cache_age_ms,
        "cache_lookup": (time.time() - cache_lookup_start) * 1000,
        "lock_wait_ms": lock_wait_ms,
        "cache_state": cache_state,
        "cache_key_scope": _CACHE_KEY_SCOPE,
    }


def get_memory_instance(uid: str) -> Mem0Graph:
    """Get or create a Mem0Graph instance for a user.

    Args:
        uid: User ID for memory isolation

    Returns:
        Mem0Graph instance
    """
    now = time.time()
    collection_name = _build_collection_name(uid)
    config_fingerprint = _build_config_fingerprint()
    cache_key = _build_cache_key(uid, collection_name, config_fingerprint)
    cache_lookup_start = time.time()

    with _memory_instances_lock:
        _evict_expired_locked(now)

        entry = _memory_instances.get(cache_key)
        if entry is not None:
            entry["last_used_at"] = now
            _memory_instances.move_to_end(cache_key)
            instance = entry["instance"]
            instance._cache_info = _build_cache_info(
                cache_hit=True,
                cache_age_ms=max(0.0, (now - float(entry["created_at"])) * 1000),
                cache_lookup_start=cache_lookup_start,
                lock_wait_ms=0.0,
                cache_state="hit",
            )
            return instance

        creation_lock = _instance_creation_locks.get(cache_key)
        if creation_lock is None:
            creation_lock = threading.Lock()
            _instance_creation_locks[cache_key] = creation_lock

    wait_start = time.time()
    with creation_lock:
        lock_wait_ms = (time.time() - wait_start) * 1000

        with _memory_instances_lock:
            now = time.time()
            _evict_expired_locked(now)
            entry = _memory_instances.get(cache_key)
            if entry is not None:
                entry["last_used_at"] = now
                _memory_instances.move_to_end(cache_key)
                instance = entry["instance"]
                instance._cache_info = _build_cache_info(
                    cache_hit=True,
                    cache_age_ms=max(0.0, (now - float(entry["created_at"])) * 1000),
                    cache_lookup_start=cache_lookup_start,
                    lock_wait_ms=lock_wait_ms,
                    cache_state="miss_reused_after_wait" if lock_wait_ms > 0 else "hit",
                )
                return instance

        instance = Mem0Graph(user_id=uid, collection_name=collection_name)
        created_at = time.time()

        with _memory_instances_lock:
            _memory_instances[cache_key] = {
                "instance": instance,
                "created_at": created_at,
                "last_used_at": created_at,
                "config_fingerprint": config_fingerprint,
                "collection_name": collection_name,
            }
            _memory_instances.move_to_end(cache_key)
            _evict_if_oversized_locked()

    instance._cache_info = _build_cache_info(
        cache_hit=False,
        cache_age_ms=0.0,
        cache_lookup_start=cache_lookup_start,
        lock_wait_ms=lock_wait_ms,
        cache_state="miss_created",
    )
    return instance


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
