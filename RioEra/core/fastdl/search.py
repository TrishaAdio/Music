"""
YouTube search and metadata.

Search is treated as a separate concern from streaming because the two have very
different failure modes: YouTube's search endpoint answers normally from a
datacenter IP, while its *player* endpoint returns a bot check on the same IP in
the same second. So search stays on YouTube (it supplies the video ids,
thumbnails and, importantly, durations the rest of the bot is built around) while
audio comes from elsewhere.

The duration this module returns is what makes the match gate accurate: knowing
the requested track is 3:37 long is what rejects a 30-second preview or a
12-minute loop.

Two backends, in order:
  1. keyless InnerTube /youtubei/v1/search - no third-party dependency
  2. youtubesearchpython - kept as a fallback

Backend 1 exists mainly to remove a hard dependency on youtubesearchpython,
which breaks with httpx >= 0.28 (it passes a `proxies` kwarg that was removed).
That is the kind of transitive breakage that takes a bot offline for no reason.
"""

import re
from typing import Any, Dict, List, Optional

from .config import fastdl_config
from .net import get_json, post_json

_SEARCH_ENDPOINT = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
_WEB_CONTEXT = {
    "clientName": "WEB",
    "clientVersion": "2.20250312.04.00",
    "hl": "en",
    "gl": "US",
}
# Restricts results to videos, so playlists/channels do not pollute hits.
_VIDEO_ONLY_PARAMS = "EgIQAQ%3D%3D"

_DURATION_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")


def duration_to_seconds(text: Optional[str]) -> int:
    """'3:37' -> 217, '1:02:03' -> 3723. Returns 0 for live/unknown."""
    if not text:
        return 0
    match = _DURATION_RE.match(str(text).strip())
    if not match:
        return 0
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)


def _runs_text(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    if "simpleText" in node:
        return str(node["simpleText"])
    return "".join(str(run.get("text", "")) for run in (node.get("runs") or []))


def _collect_video_renderers(node: Any, out: List[Dict[str, Any]]) -> None:
    if isinstance(node, dict):
        renderer = node.get("videoRenderer")
        if isinstance(renderer, dict) and renderer.get("videoId"):
            out.append(renderer)
        for value in node.values():
            _collect_video_renderers(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_video_renderers(value, out)


def _normalise_renderer(renderer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    video_id = renderer.get("videoId")
    if not video_id:
        return None

    title = _runs_text(renderer.get("title"))
    length_text = _runs_text(renderer.get("lengthText")) or None

    thumbnails = ((renderer.get("thumbnail") or {}).get("thumbnails")) or []
    thumbnail = thumbnails[-1]["url"].split("?")[0] if thumbnails else (
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    )

    channel = ""
    for key in ("ownerText", "longBylineText", "shortBylineText"):
        channel = _runs_text(renderer.get(key))
        if channel:
            break

    views = _runs_text(renderer.get("viewCountText"))
    published = _runs_text(renderer.get("publishedTimeText"))

    return {
        "id": video_id,
        "title": title,
        "duration": length_text,          # None for live streams
        "duration_sec": duration_to_seconds(length_text),
        "thumbnail": thumbnail,
        "channel": channel,
        "views": views,
        "published": published,
        "link": f"https://www.youtube.com/watch?v={video_id}",
    }


async def _innertube_search(query: str, limit: int) -> List[Dict[str, Any]]:
    payload = {
        "query": query,
        "context": {"client": dict(_WEB_CONTEXT)},
        "params": _VIDEO_ONLY_PARAMS,
    }
    data = await post_json(
        _SEARCH_ENDPOINT,
        payload,
        headers={"Content-Type": "application/json", "Origin": "https://www.youtube.com"},
        timeout=fastdl_config.resolve_timeout,
        retries=1,
    )
    renderers: List[Dict[str, Any]] = []
    _collect_video_renderers(data, renderers)

    results: List[Dict[str, Any]] = []
    seen = set()
    for renderer in renderers:
        item = _normalise_renderer(renderer)
        if item and item["id"] not in seen:
            seen.add(item["id"])
            results.append(item)
        if len(results) >= limit:
            break
    return results


async def _ysp_search(query: str, limit: int) -> List[Dict[str, Any]]:
    """Fallback via youtubesearchpython, if it is installed and importable."""
    from youtubesearchpython.__future__ import VideosSearch

    raw = await VideosSearch(query, limit=limit).next()
    results = []
    for entry in (raw or {}).get("result", []):
        thumbnails = entry.get("thumbnails") or []
        results.append({
            "id": entry.get("id"),
            "title": entry.get("title") or "",
            "duration": entry.get("duration"),
            "duration_sec": duration_to_seconds(entry.get("duration")),
            "thumbnail": (
                thumbnails[0]["url"].split("?")[0] if thumbnails
                else f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg"
            ),
            "channel": ((entry.get("channel") or {}).get("name") or ""),
            "views": ((entry.get("viewCount") or {}).get("text") or ""),
            "published": entry.get("publishedTime") or "",
            "link": entry.get("link") or f"https://www.youtube.com/watch?v={entry.get('id')}",
        })
    return [r for r in results if r["id"]]


_VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)


def extract_video_id(text: Optional[str]) -> Optional[str]:
    """Pull an 11-character video id out of any YouTube URL form."""
    if not text:
        return None
    text = str(text).strip()
    found = _VIDEO_ID_RE.search(text)
    if found:
        return found.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    return None


async def search(query: str, limit: int = 1) -> List[Dict[str, Any]]:
    """
    Search YouTube, returning normalised dicts. Never raises; returns [] instead,
    so a search outage degrades to "no results" rather than a traceback in chat.
    """
    query = (query or "").strip()
    if not query:
        return []

    # A bare link/id needs a metadata lookup, not a keyword search.
    video_id = extract_video_id(query)
    if video_id:
        detail = await video_details(video_id)
        return [detail] if detail else []

    for backend in (_innertube_search, _ysp_search):
        try:
            results = await backend(query, limit)
            if results:
                return results
        except Exception:
            continue
    return []


async def video_details(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Metadata for a known video id.

    Tries search first (it returns a duration), then falls back to oEmbed, which
    has no bot gate but also no duration.
    """
    try:
        results = await _innertube_search(video_id, 6)
        for item in results:
            if item["id"] == video_id:
                return item
    except Exception:
        pass

    try:
        results = await _ysp_search(f"https://www.youtube.com/watch?v={video_id}", 1)
        if results:
            return results[0]
    except Exception:
        pass

    # Last resort: title only. Duration stays unknown, which the match gate
    # treats as "no duration signal" rather than as a mismatch.
    try:
        import urllib.parse

        target = urllib.parse.quote(
            f"https://www.youtube.com/watch?v={video_id}", safe=""
        )
        data = await get_json(
            f"https://www.youtube.com/oembed?url={target}&format=json",
            timeout=6.0,
            retries=1,
        )
        if isinstance(data, dict) and data.get("title"):
            return {
                "id": video_id,
                "title": data["title"],
                "duration": None,
                "duration_sec": 0,
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "channel": data.get("author_name") or "",
                "views": "",
                "published": "",
                "link": f"https://www.youtube.com/watch?v={video_id}",
            }
    except Exception:
        pass
    return None


_PLAYLIST_ITEM_KEYS = (
    "playlistVideoRenderer",      # normal saved playlists
    "playlistPanelVideoRenderer",  # radio / autogenerated mixes
    "gridVideoRenderer",           # grid layouts
    "videoRenderer",               # fallback shape
)


def _harvest_video_ids(node: Any, out: List[str], seen: set, limit: int) -> None:
    if len(out) >= limit:
        return
    if isinstance(node, dict):
        for key in _PLAYLIST_ITEM_KEYS:
            renderer = node.get(key)
            if isinstance(renderer, dict):
                vid = renderer.get("videoId")
                if vid and vid not in seen:
                    seen.add(vid)
                    out.append(vid)
                    if len(out) >= limit:
                        return
        for value in node.values():
            _harvest_video_ids(value, out, seen, limit)
    elif isinstance(node, list):
        for value in node:
            _harvest_video_ids(value, out, seen, limit)


def extract_playlist_id(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    text = str(text)
    found = re.search(r"[?&]list=([A-Za-z0-9_-]+)", text)
    if found:
        return found.group(1)
    if re.fullmatch(r"(?:PL|UU|OL|RD|LL|FL)[A-Za-z0-9_-]{8,}", text.strip()):
        return text.strip()
    return None


async def playlist_video_ids(playlist_url: str, limit: int) -> List[str]:
    """
    Video ids from a playlist.

    Playlist shapes vary a lot (saved playlists, channel uploads, auto-generated
    mixes), and no single endpoint covers all of them, so three strategies are
    tried in order and the first that yields anything wins. Returns [] rather
    than raising, so a weird playlist degrades to "nothing queued".
    """
    list_id = extract_playlist_id(playlist_url)
    if not list_id:
        return []

    # 1) InnerTube browse - fastest, no third-party dependency.
    try:
        data = await post_json(
            "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false",
            {"browseId": f"VL{list_id}", "context": {"client": dict(_WEB_CONTEXT)}},
            headers={"Content-Type": "application/json",
                     "Origin": "https://www.youtube.com"},
            timeout=fastdl_config.resolve_timeout,
            retries=0,
        )
        ids: List[str] = []
        _harvest_video_ids(data, ids, set(), limit)
        if ids:
            return ids
    except Exception:
        pass

    # 2) Scrape ytInitialData from the playlist page.
    try:
        from .net import get_session

        session = await get_session()
        async with session.get(
            f"https://www.youtube.com/playlist?list={list_id}&hl=en"
        ) as resp:
            html = await resp.text()
        blob = re.search(r"ytInitialData\s*=\s*(\{.*?\})\s*;\s*</script>", html, re.S)
        if blob:
            import json as _json

            ids = []
            _harvest_video_ids(_json.loads(blob.group(1)), ids, set(), limit)
            if ids:
                return ids
    except Exception:
        pass

    # 3) yt-dlp flat extraction. Metadata-only, so it is not subject to the
    #    player bot check the streaming path hits, and it handles odd playlists.
    try:
        import asyncio

        def _flat() -> List[str]:
            import yt_dlp

            options = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "playlistend": limit,
                "ignoreerrors": True,
                "skip_download": True,
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/playlist?list={list_id}", download=False
                )
            found: List[str] = []
            for entry in ((info or {}).get("entries") or []):
                if entry and entry.get("id"):
                    found.append(entry["id"])
            return found[:limit]

        return await asyncio.get_event_loop().run_in_executor(None, _flat)
    except Exception:
        return []
