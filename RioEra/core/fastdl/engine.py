"""
Resolution and download orchestration.

Request flow:

    TrackRequest
        -> url cache hit?                      (instant)
        -> single-flight gate                  (one fetch per key, N waiters)
        -> metadata enrichment                 (oEmbed, ~30ms, cookieless)
        -> providers in health order           (saavn -> innertube -> custom -> ytdlp)
        -> Resolved (a CDN url, or a local file)

For voice chat the CDN url is handed straight to pytgcalls, so nothing is
written to disk and playback starts as soon as ffmpeg opens the stream. Only
flows that genuinely need bytes on disk (uploading a file to Telegram) download.
"""

import asyncio
import time
from typing import List, Optional, Tuple

from .breaker import breaker
from .cache import (
    cache_path,
    cached_file,
    prune_cache,
    single_flight,
    url_cache,
)
from .config import fastdl_config
from .match import clean_query
from .models import NotFound, ProviderError, Resolved, TrackRequest
from .providers import REGISTRY, innertube


class AllProvidersFailed(Exception):
    """No provider could satisfy the request."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__(self._summary())

    def _summary(self) -> str:
        if not self.errors:
            return "no providers available"
        return " | ".join(self.errors)

    def user_message(self) -> str:
        """A short, non-technical explanation for chat."""
        joined = " ".join(self.errors).lower()
        if "bot check" in joined or "not a bot" in joined:
            return (
                "Couldn't fetch this track right now — YouTube is rate limiting "
                "this server and no mirror had the song. Try again shortly."
            )
        if "scored" in joined:
            return (
                "Couldn't find a confident match for that. Try adding the "
                "artist name to your search."
            )
        return "Couldn't fetch this track from any source. Try again shortly."


async def _enrich(request: TrackRequest) -> None:
    """
    Fill in a searchable query for catalogue providers.

    A YouTube video id alone is useless to a music catalogue, so the title is
    fetched via oEmbed. That endpoint has no bot gate and no cookie requirement
    and answers in roughly 30ms, which is why the bridge is cheap enough to sit
    on the hot path.
    """
    if request.query or not request.video_id:
        return

    title, author = await innertube.metadata(request.video_id)
    if title:
        request.expected_title = request.expected_title or title
        request.expected_artist = request.expected_artist or (author or "")
        request.query = clean_query(title) or title


def _needs_query(provider_name: str) -> bool:
    """Catalogue providers search by text and cannot use a bare video id."""
    return provider_name in ("saavn", "soundcloud")


async def resolve(request: TrackRequest, *, use_cache: bool = True) -> Resolved:
    """Resolve a request to a playable URL or local file."""
    key = request.cache_key()

    if use_cache:
        cached = url_cache.get(key)
        if cached is not None:
            return cached

    async def _work() -> Resolved:
        # Re-check inside the gate: a leader may have just populated the cache.
        if use_cache:
            cached_inner = url_cache.get(key)
            if cached_inner is not None:
                return cached_inner

        errors: List[str] = []
        order = breaker.order(list(fastdl_config.provider_order))

        for name in order:
            provider = REGISTRY.get(name)
            if provider is None:
                continue

            if _needs_query(name) and not request.query:
                try:
                    await _enrich(request)
                except Exception:
                    pass
                if not request.query:
                    errors.append(f"{name}: no query available")
                    continue

            started = time.monotonic()
            try:
                resolved = await asyncio.wait_for(
                    provider.resolve(request),
                    timeout=fastdl_config.resolve_timeout * 2,
                )
            except NotFound as exc:
                # A clean "no match" is not a provider malfunction, so it must
                # not trip the breaker; the provider is healthy, just unhelpful.
                errors.append(f"{name}: {exc}")
                continue
            except asyncio.TimeoutError:
                breaker.record_failure(name, "timeout")
                errors.append(f"{name}: timed out")
                continue
            except ProviderError as exc:
                breaker.record_failure(name, str(exc))
                errors.append(f"{name}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                breaker.record_failure(name, f"{type(exc).__name__}: {exc}")
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                continue

            breaker.record_success(name, time.monotonic() - started)
            if use_cache:
                url_cache.set(key, resolved)
            return resolved

        raise AllProvidersFailed(errors)

    return await single_flight.run(f"resolve:{key}", _work)


async def get_stream(request: TrackRequest) -> Resolved:
    """
    Return something pytgcalls can play immediately.

    When direct streaming is enabled and the provider gave a remote URL, this
    performs no download at all.
    """
    resolved = await resolve(request)
    if fastdl_config.prefer_direct_stream and resolved.is_remote:
        return resolved
    return await materialise(request, resolved)


async def materialise(
    request: TrackRequest,
    resolved: Optional[Resolved] = None,
) -> Resolved:
    """Ensure the track exists as a local file, downloading if necessary."""
    if resolved is None:
        resolved = await resolve(request)
    if resolved.is_local:
        return resolved

    key = request.video_id or request.cache_key().replace(":", "_")
    ext = resolved.ext or "m4a"

    existing = cached_file(key, ext)
    if existing:
        return _localised(resolved, existing)

    async def _work() -> Resolved:
        again = cached_file(key, ext)
        if again:
            return _localised(resolved, again)

        from .net import download_to_file

        destination = cache_path(key, ext)
        try:
            path, elapsed, written = await download_to_file(
                resolved.url,
                destination,
                headers=resolved.headers,
                size=resolved.size,
                supports_ranges=resolved.supports_ranges,
            )
        except Exception:
            # A stale resolved URL is the usual cause; drop it so the retry
            # path re-resolves instead of failing again on the same dead link.
            url_cache.invalidate(request.cache_key())
            raise

        try:
            prune_cache()
        except Exception:
            pass

        result = _localised(resolved, path)
        result.size = written
        return result

    return await single_flight.run(f"download:{key}:{ext}", _work)


def _localised(resolved: Resolved, path: str) -> Resolved:
    return Resolved(
        url=path,
        provider=resolved.provider,
        ext=resolved.ext,
        is_local=True,
        size=resolved.size,
        supports_ranges=False,
        title=resolved.title,
        artists=resolved.artists,
        duration=resolved.duration,
        thumbnail=resolved.thumbnail,
        bitrate=resolved.bitrate,
        score=resolved.score,
    )


async def health_report() -> str:
    from .cache import cache_stats

    stats = cache_stats()
    lines = [
        "fastdl providers:",
        breaker.report(),
        "",
        f"provider order: {', '.join(fastdl_config.provider_order)}",
        f"direct stream: {'on' if fastdl_config.prefer_direct_stream else 'off'}",
        f"match floor: {fastdl_config.min_match_score:.0f}",
        f"disk cache: {stats['files']} files, "
        f"{stats['bytes'] / 1048576:.1f} MiB / {stats['limit_bytes'] / 1048576:.0f} MiB",
        f"resolved-url cache: {stats['url_entries']} entries",
    ]
    return "\n".join(lines)


async def selftest(queries: Optional[List[str]] = None) -> List[Tuple[str, bool, str]]:
    """Resolve a few known tracks and report per-query outcome. Used by /fastdl."""
    queries = queries or ["kesariya", "shape of you", "tum hi ho"]
    results: List[Tuple[str, bool, str]] = []
    for query in queries:
        started = time.monotonic()
        try:
            resolved = await resolve(TrackRequest(query=query), use_cache=False)
            elapsed = time.monotonic() - started
            results.append((
                query, True,
                f"{resolved.provider} {resolved.bitrate or '?'}kbps "
                f"score={resolved.score:.0f} in {elapsed:.2f}s",
            ))
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - started
            results.append((query, False, f"{type(exc).__name__}: {exc}"[:160]))
    return results
