"""
fastdl - cookieless, multi-source audio resolution for RioEra.

Design goals, in priority order:
  1. never depend on a credential that expires (no cookies, no API keys)
  2. never depend on a single host (any provider can die without an outage)
  3. start playback in about a second (stream the CDN url, skip the download)
  4. never play the wrong recording just because it was faster to find

Typical use:

    from RioEra.core.fastdl import TrackRequest, get_stream

    resolved = await get_stream(TrackRequest(video_id="dQw4w9WgXcQ"))
    await call.join_call(chat_id, origin, resolved.url)
"""

from .breaker import breaker
from .cache import cache_stats, prune_cache, url_cache
from .config import fastdl_config
from .engine import (
    AllProvidersFailed,
    get_stream,
    health_report,
    materialise,
    resolve,
    selftest,
)
from .models import NotFound, ProviderError, Resolved, TrackRequest
from .net import close_session, get_session

__all__ = [
    "AllProvidersFailed",
    "NotFound",
    "ProviderError",
    "Resolved",
    "TrackRequest",
    "breaker",
    "cache_stats",
    "close_session",
    "fastdl_config",
    "get_session",
    "get_stream",
    "health_report",
    "materialise",
    "prune_cache",
    "resolve",
    "selftest",
    "url_cache",
]
