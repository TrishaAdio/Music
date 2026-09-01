"""
Caching and request de-duplication.

Three separate concerns:
  * single-flight  - N users asking for the same song trigger ONE fetch
  * url cache      - short lived, avoids re-resolving within a session
  * disk LRU       - bounded on-disk audio cache so /downloads cannot fill a disk
"""

import asyncio
import os
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, TypeVar

from .config import fastdl_config

T = TypeVar("T")


# --------------------------------------------------------------------------
# single-flight
# --------------------------------------------------------------------------
class SingleFlight:
    """
    Collapse concurrent identical requests into one in-flight coroutine.

    Without this, a busy group where five people spam the same /play triggers
    five downloads of the same file, which is how these bots get IP-throttled.
    """

    def __init__(self) -> None:
        self._inflight: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def run(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            existing = self._inflight.get(key)
            if existing is None:
                waiter: asyncio.Future = asyncio.get_event_loop().create_future()
                self._inflight[key] = waiter

        if existing is not None:
            # A follower: wait on the leader's result. shield() keeps one
            # follower's cancellation from tearing down the shared fetch.
            return await asyncio.shield(existing)

        try:
            result = await factory()
        except BaseException as exc:  # noqa: BLE001
            async with self._lock:
                self._inflight.pop(key, None)
            if not waiter.done():
                waiter.set_exception(exc)
            raise
        else:
            async with self._lock:
                self._inflight.pop(key, None)
            if not waiter.done():
                waiter.set_result(result)
            return result


single_flight = SingleFlight()


# --------------------------------------------------------------------------
# resolved-URL cache
# --------------------------------------------------------------------------
class TTLCache:
    def __init__(self, ttl: float, max_items: int = 2048) -> None:
        self.ttl = ttl
        self.max_items = max_items
        self._data: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._data.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.monotonic() > expires:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._data) >= self.max_items:
            # Drop the soonest-to-expire entries rather than scanning everything.
            for stale in sorted(self._data, key=lambda k: self._data[k][0])[: self.max_items // 4]:
                self._data.pop(stale, None)
        self._data[key] = (time.monotonic() + self.ttl, value)

    def invalidate(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


url_cache = TTLCache(fastdl_config.url_cache_ttl)


# --------------------------------------------------------------------------
# bounded on-disk cache
# --------------------------------------------------------------------------
def cache_path(key: str, ext: str) -> str:
    os.makedirs(fastdl_config.cache_dir, exist_ok=True)
    safe = "".join(ch for ch in key if ch.isalnum() or ch in "-_") or "track"
    return os.path.join(fastdl_config.cache_dir, f"{safe}.{ext.lstrip('.')}")


def cached_file(key: str, ext: str) -> Optional[str]:
    """Return a cached path only if it is a complete, non-empty file."""
    path = cache_path(key, ext)
    try:
        if os.path.isfile(path) and os.path.getsize(path) > 1024:
            os.utime(path, None)  # refresh LRU recency
            return path
    except OSError:
        return None
    return None


def prune_cache() -> Tuple[int, int]:
    """
    Enforce the size/count ceiling, deleting least-recently-used files first.
    Returns (files_removed, bytes_reclaimed).
    """
    directory = fastdl_config.cache_dir
    if not os.path.isdir(directory):
        return 0, 0

    entries = []
    total = 0
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        try:
            if not os.path.isfile(path):
                continue
            stat = os.stat(path)
        except OSError:
            continue
        # Clean up abandoned partial downloads older than an hour.
        if name.endswith(".part"):
            if time.time() - stat.st_mtime > 3600:
                try:
                    os.remove(path)
                except OSError:
                    pass
            continue
        entries.append((stat.st_atime, stat.st_size, path))
        total += stat.st_size

    entries.sort()  # oldest access first
    removed = 0
    reclaimed = 0
    while entries and (
        total > fastdl_config.cache_max_bytes or len(entries) > fastdl_config.cache_max_files
    ):
        _, size, path = entries.pop(0)
        try:
            os.remove(path)
        except OSError:
            continue
        total -= size
        removed += 1
        reclaimed += size
    return removed, reclaimed


def cache_stats() -> Dict[str, Any]:
    directory = fastdl_config.cache_dir
    files = 0
    total = 0
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            path = os.path.join(directory, name)
            try:
                if os.path.isfile(path) and not name.endswith(".part"):
                    files += 1
                    total += os.path.getsize(path)
            except OSError:
                continue
    return {
        "files": files,
        "bytes": total,
        "limit_bytes": fastdl_config.cache_max_bytes,
        "url_entries": len(url_cache),
    }
