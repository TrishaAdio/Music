"""
Tunables for the fastdl engine.

Everything is env-overridable so behaviour can be changed on a running deploy
without touching code. Defaults are chosen to work on a fresh VPS with no
cookies, no API keys and no manual setup.
"""

import os
from dataclasses import dataclass, field
from typing import List


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def _env_list(name: str) -> List[str]:
    raw = os.getenv(name, "") or ""
    return [item.strip().rstrip("/") for item in raw.replace(",", " ").split() if item.strip()]


@dataclass
class FastDLConfig:
    # ---- provider order -------------------------------------------------
    # Comma separated. Unknown names are ignored, so it is safe to prune.
    # Order matters: saavn is first because it is the only source measured to be
    # both fast and unconditionally cookieless. soundcloud covers the Western
    # catalogue gap. The YouTube-backed providers are last because they are the
    # ones that break when a server IP gets flagged.
    provider_order: List[str] = field(
        default_factory=lambda: _env_list("FASTDL_PROVIDERS")
        or ["saavn", "soundcloud", "innertube", "custom", "ytdlp"]
    )

    # Operator supplied HTTP resolvers, tried by the "custom" provider.
    # Each entry may contain {id} / {query}; if absent, ?id= is appended.
    custom_endpoints: List[str] = field(default_factory=lambda: _env_list("FASTDL_CUSTOM_API"))

    # ---- behaviour ------------------------------------------------------
    # Hand a CDN URL straight to ffmpeg/pytgcalls instead of downloading first.
    # This is what turns a play command into a sub-second start.
    prefer_direct_stream: bool = _env_bool("FASTDL_DIRECT_STREAM", True)

    # Reject a candidate whose title/duration confidence is below this.
    # Playing a wrong remix is worse than being a little slower.
    min_match_score: float = _env_float("FASTDL_MIN_MATCH_SCORE", 62.0)

    # Saavn audio quality ladder, best first.
    saavn_bitrates: List[str] = field(
        default_factory=lambda: _env_list("FASTDL_SAAVN_BITRATES") or ["320", "160", "96"]
    )

    allow_ytdlp: bool = _env_bool("FASTDL_ALLOW_YTDLP", True)
    ytdlp_player_clients: List[str] = field(
        default_factory=lambda: _env_list("FASTDL_YTDLP_CLIENTS")
        or ["android_vr", "ios", "android", "web_safari"]
    )

    # ---- caching --------------------------------------------------------
    cache_dir: str = os.getenv("FASTDL_CACHE_DIR", "downloads")
    cache_max_bytes: int = _env_int("FASTDL_CACHE_MAX_MB", 3072) * 1024 * 1024
    cache_max_files: int = _env_int("FASTDL_CACHE_MAX_FILES", 400)
    # Resolved URLs expire; googlevideo links die in ~6h, saavn links are stable.
    url_cache_ttl: float = _env_float("FASTDL_URL_TTL", 3600.0)

    # ---- networking -----------------------------------------------------
    pool_limit: int = _env_int("FASTDL_POOL_LIMIT", 100)
    pool_limit_per_host: int = _env_int("FASTDL_POOL_PER_HOST", 24)
    connect_timeout: float = _env_float("FASTDL_CONNECT_TIMEOUT", 6.0)
    read_timeout: float = _env_float("FASTDL_READ_TIMEOUT", 30.0)
    download_timeout: float = _env_float("FASTDL_DOWNLOAD_TIMEOUT", 240.0)
    chunk_timeout: float = _env_float("FASTDL_CHUNK_TIMEOUT", 45.0)
    stream_chunk_bytes: int = _env_int("FASTDL_STREAM_CHUNK_KB", 256) * 1024
    parallel_parts: int = _env_int("FASTDL_PARALLEL_PARTS", 4)
    parallel_threshold_bytes: int = _env_int("FASTDL_PARALLEL_MIN_MB", 6) * 1024 * 1024
    insecure_tls: bool = _env_bool("FASTDL_INSECURE_TLS", False)

    # How long a provider stays benched after repeated failures.
    breaker_threshold: int = _env_int("FASTDL_BREAKER_FAILS", 4)
    breaker_cooldown: float = _env_float("FASTDL_BREAKER_COOLDOWN", 120.0)

    # Per-provider resolve budget. Keeps one sick provider from stalling a play.
    resolve_timeout: float = _env_float("FASTDL_RESOLVE_TIMEOUT", 10.0)


fastdl_config = FastDLConfig()
