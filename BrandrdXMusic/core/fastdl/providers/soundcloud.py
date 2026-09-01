"""
SoundCloud provider - fallback coverage for tracks the JioSaavn catalogue lacks.

This exists because of a measured gap: JioSaavn's catalogue is excellent for
Indian music but does not carry many Western originals. Searching it for
"Counting Stars" or "Believer" returns only karaoke and cover uploads, which the
match gate correctly rejects, leaving those requests with nowhere to go.

Authentication is a public `client_id` scraped from SoundCloud's own web player
bundle and cached in memory. No user account, no cookie, nothing that expires
per-user. If the id rotates, it is simply re-scraped on the next failure.

Two SoundCloud-specific hazards are handled explicitly:
  * `policy: SNIP` items are 30-second previews masquerading as full tracks.
    They are filtered out, otherwise the bot plays 30s and stops.
  * Many tracks only expose HLS transcodings. Only `progressive` (plain HTTP)
    transcodings are used, since those stream into ffmpeg without a playlist.
"""

import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional

from .. import match
from ..config import fastdl_config
from ..models import NotFound, ProviderError, Resolved, TrackRequest
from ..net import get_json, get_session, probe

NAME = "soundcloud"

_API = "https://api-v2.soundcloud.com"
_client_id: Optional[str] = None
_client_id_fetched_at: float = 0.0
_CLIENT_ID_TTL = 6 * 3600


async def _scrape_client_id() -> Optional[str]:
    """Pull the public client_id out of the web player's JS bundle."""
    session = await get_session()
    try:
        async with session.get("https://soundcloud.com/discover", timeout=None) as resp:
            page = await resp.text()
    except Exception:
        return None

    scripts = re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', page)
    # The id lives in one of the later bundles, so search from the end.
    for src in reversed(scripts):
        try:
            async with session.get(src, timeout=None) as resp:
                body = await resp.text()
        except Exception:
            continue
        found = re.search(r'client_id[:=]"([A-Za-z0-9]{32})"', body)
        if found:
            return found.group(1)
    return None


async def _get_client_id(force: bool = False) -> str:
    global _client_id, _client_id_fetched_at
    fresh = (time.time() - _client_id_fetched_at) < _CLIENT_ID_TTL
    if _client_id and fresh and not force:
        return _client_id

    scraped = await _scrape_client_id()
    if scraped:
        _client_id = scraped
        _client_id_fetched_at = time.time()
        return scraped
    if _client_id:
        return _client_id  # stale is better than nothing
    raise ProviderError("could not obtain a soundcloud client_id")


async def _search(query: str, client_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    params = urllib.parse.urlencode({
        "q": query, "client_id": client_id, "limit": str(limit),
    })
    data = await get_json(
        f"{_API}/search/tracks?{params}",
        timeout=fastdl_config.resolve_timeout,
        retries=0,
    )
    if isinstance(data, dict):
        return data.get("collection") or []
    return []


def _to_candidate(track: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not track.get("streamable"):
        return None
    # SNIP == 30s preview. Playing one is worse than not playing anything.
    if str(track.get("policy") or "").upper() == "SNIP":
        return None

    duration_ms = track.get("duration") or track.get("full_duration") or 0
    duration = int(duration_ms // 1000) or None
    if duration and duration < 45:
        return None  # too short to be a real track

    transcodings = ((track.get("media") or {}).get("transcodings")) or []
    progressive = [
        t for t in transcodings
        if ((t.get("format") or {}).get("protocol") == "progressive") and t.get("url")
    ]
    if not progressive:
        return None

    user = track.get("user") or {}
    return {
        "title": match.strip_html(track.get("title")),
        "artists": match.strip_html(user.get("username") or user.get("full_name") or ""),
        "duration": duration,
        "transcoding_url": progressive[0]["url"],
        "thumbnail": (track.get("artwork_url") or "").replace("large", "t500x500") or None,
    }


async def resolve(request: TrackRequest) -> Resolved:
    if request.want_video:
        raise NotFound("soundcloud is audio-only")

    query = (request.query or request.expected_title or "").strip()
    if not query:
        raise NotFound("soundcloud needs a text query")

    client_id = await _get_client_id()
    cleaned = match.clean_query(query) or query

    try:
        results = await _search(cleaned, client_id)
    except Exception:
        # A rotated client_id shows up as an auth error; re-scrape once.
        client_id = await _get_client_id(force=True)
        results = await _search(cleaned, client_id)

    if not results:
        raise NotFound(f"no soundcloud results for {cleaned!r}")

    candidates = [c for c in (_to_candidate(t) for t in results) if c]
    if not candidates:
        raise NotFound("soundcloud results had no full-length progressive streams")

    best, score = match.pick_best(
        candidates,
        cleaned,
        expected_artist=request.expected_artist or "",
        expected_duration=request.expected_duration,
        minimum=fastdl_config.min_match_score,
    )
    if best is None:
        raise NotFound(
            f"best soundcloud match scored {score:.0f} < "
            f"{fastdl_config.min_match_score:.0f} for {cleaned!r}"
        )

    # The transcoding endpoint returns a short-lived CDN URL.
    separator = "&" if "?" in best["transcoding_url"] else "?"
    media = await get_json(
        f"{best['transcoding_url']}{separator}client_id={client_id}",
        timeout=fastdl_config.resolve_timeout,
        retries=1,
    )
    media_url = (media or {}).get("url") if isinstance(media, dict) else None
    if not media_url:
        raise ProviderError("soundcloud did not return a media url")

    ok, size, ranges = await probe(media_url)
    if not ok:
        raise ProviderError("soundcloud media url unreachable")

    return Resolved(
        url=media_url,
        provider=NAME,
        ext="mp3",
        size=size,
        supports_ranges=ranges,
        title=best.get("title"),
        artists=best.get("artists"),
        duration=best.get("duration"),
        thumbnail=best.get("thumbnail"),
        bitrate="128",
        score=score,
    )
