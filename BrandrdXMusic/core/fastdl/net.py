"""
Shared HTTP layer for the fastdl engine.

One pooled aiohttp session for the whole process (creating a session per request
is what made the old downloader slow), plus a range-aware downloader that adapts
between a single streaming read and parallel chunk fetches.
"""

import asyncio
import os
import random
import ssl
import time
from typing import Any, Dict, Optional, Tuple

import aiohttp

from .config import fastdl_config

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

_session: Optional[aiohttp.ClientSession] = None
_session_loop: Optional[asyncio.AbstractEventLoop] = None
_session_lock = asyncio.Lock()


def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    # Some music CDN edges terminate TLS with intermediate chains that trip
    # strict hostname checks on older images. Keep verification on; only relax
    # if the operator explicitly opts in.
    if fastdl_config.insecure_tls:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def get_session() -> aiohttp.ClientSession:
    """Return the shared session, rebuilding it if the loop changed or it closed."""
    global _session, _session_loop

    loop = asyncio.get_event_loop()
    if _session is not None and not _session.closed and _session_loop is loop:
        return _session

    async with _session_lock:
        if _session is not None and not _session.closed and _session_loop is loop:
            return _session

        if _session is not None and not _session.closed:
            try:
                await _session.close()
            except Exception:
                pass

        connector = aiohttp.TCPConnector(
            limit=fastdl_config.pool_limit,
            limit_per_host=fastdl_config.pool_limit_per_host,
            ttl_dns_cache=300,
            use_dns_cache=True,
            enable_cleanup_closed=True,
            force_close=False,
            ssl=_build_ssl_context(),
        )
        _session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(
                total=None,
                connect=fastdl_config.connect_timeout,
                sock_read=fastdl_config.read_timeout,
            ),
            headers={
                "User-Agent": DESKTOP_UA,
                "Accept-Language": "en-US,en;q=0.9",
            },
            auto_decompress=True,
            trust_env=True,
        )
        _session_loop = loop
        return _session


async def close_session() -> None:
    global _session, _session_loop
    if _session is not None and not _session.closed:
        try:
            await _session.close()
        except Exception:
            pass
    _session = None
    _session_loop = None


async def _sleep_backoff(attempt: int) -> None:
    delay = min(0.25 * (2 ** attempt), 2.0) * (0.7 + random.random() * 0.6)
    await asyncio.sleep(delay)


async def get_json(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 8.0,
    retries: int = 1,
) -> Any:
    session = await get_session()
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                resp.raise_for_status()
                # JioSaavn replies with text/html content types on some edges,
                # so never trust the declared content type here.
                return await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries:
                await _sleep_backoff(attempt)
    raise last_err  # type: ignore[misc]


async def post_json(
    url: str,
    payload: Any,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 8.0,
    retries: int = 1,
) -> Any:
    session = await get_session()
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries:
                await _sleep_backoff(attempt)
    raise last_err  # type: ignore[misc]


async def probe(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 6.0,
) -> Tuple[bool, Optional[int], bool]:
    """
    Cheaply check a media URL with a 2-byte range request.

    Returns (usable, total_size_or_None, supports_ranges). A 1-byte range probe
    is used instead of HEAD because several CDNs (including saavncdn) answer
    HEAD with 403 while serving GET fine.
    """
    session = await get_session()
    req_headers = dict(headers or {})
    req_headers["Range"] = "bytes=0-1"
    try:
        async with session.get(
            url, headers=req_headers, timeout=aiohttp.ClientTimeout(total=timeout),
            allow_redirects=True,
        ) as resp:
            if resp.status == 206:
                total = None
                content_range = resp.headers.get("Content-Range", "")
                tail = content_range.rsplit("/", 1)[-1] if "/" in content_range else ""
                if tail.isdigit():
                    total = int(tail)
                return True, total, True
            if resp.status == 200:
                length = resp.headers.get("Content-Length")
                return True, int(length) if length and length.isdigit() else None, False
            return False, None, False
    except Exception:
        return False, None, False


async def _fetch_range(
    session: aiohttp.ClientSession,
    url: str,
    start: int,
    end: int,
    headers: Dict[str, str],
    retries: int = 2,
) -> bytes:
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            hdrs = dict(headers)
            hdrs["Range"] = f"bytes={start}-{end}"
            async with session.get(
                url, headers=hdrs,
                timeout=aiohttp.ClientTimeout(total=fastdl_config.chunk_timeout),
            ) as resp:
                if resp.status not in (200, 206):
                    raise IOError(f"range {start}-{end} returned HTTP {resp.status}")
                return await resp.read()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries:
                await _sleep_backoff(attempt)
    raise last_err  # type: ignore[misc]


async def download_to_file(
    url: str,
    dest: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    size: Optional[int] = None,
    supports_ranges: bool = False,
) -> Tuple[str, float, int]:
    """
    Download `url` to `dest`, returning (path, elapsed_seconds, bytes_written).

    Writes to a `.part` file and atomically renames on success so a killed
    process can never leave a truncated file that later looks like a cache hit.
    """
    started = time.monotonic()
    req_headers = dict(headers or {})
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    part = f"{dest}.part"

    session = await get_session()
    use_parallel = (
        supports_ranges
        and size is not None
        and size >= fastdl_config.parallel_threshold_bytes
        and fastdl_config.parallel_parts > 1
    )

    try:
        if use_parallel:
            parts = fastdl_config.parallel_parts
            chunk = (size + parts - 1) // parts  # type: ignore[operator]
            ranges = []
            for i in range(parts):
                start = i * chunk
                end = min(start + chunk - 1, size - 1)  # type: ignore[operator]
                if start <= end:
                    ranges.append((start, end))

            results = await asyncio.gather(
                *(_fetch_range(session, url, s, e, req_headers) for s, e in ranges)
            )
            written = 0
            with open(part, "wb") as fh:
                for blob in results:
                    fh.write(blob)
                    written += len(blob)

            # A short parallel result means the CDN ignored a range header.
            # Fall back to a plain streaming read rather than shipping a
            # corrupt file into the voice chat.
            if size is not None and written != size:
                use_parallel = False
                os.remove(part)
            else:
                os.replace(part, dest)
                return dest, time.monotonic() - started, written

        written = 0
        async with session.get(
            url, headers=req_headers,
            timeout=aiohttp.ClientTimeout(
                total=fastdl_config.download_timeout,
                connect=fastdl_config.connect_timeout,
                sock_read=fastdl_config.read_timeout,
            ),
        ) as resp:
            if resp.status not in (200, 206):
                raise IOError(f"download failed with HTTP {resp.status}")
            with open(part, "wb") as fh:
                async for blob in resp.content.iter_chunked(fastdl_config.stream_chunk_bytes):
                    fh.write(blob)
                    written += len(blob)

        if written == 0:
            raise IOError("download produced an empty file")
        os.replace(part, dest)
        return dest, time.monotonic() - started, written
    except Exception:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass
        raise
