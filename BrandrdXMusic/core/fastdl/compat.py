"""
Drop-in replacement for youtubesearchpython's VideosSearch.

Motivation: youtubesearchpython raises `TypeError: __init__() got an unexpected
keyword argument 'proxies'` against httpx >= 0.28, because httpx removed that
argument. The repo works only because it pins httpx==0.25.2, which means a
routine dependency bump silently takes every search offline - including the
thumbnail lookup that runs on every single play.

This class speaks the same small slice of that API the bot actually uses:

    results = VideosSearch(query, limit=1)
    for result in (await results.next())["result"]:
        result["title"], result["duration"], result["id"], result["link"]
        result["thumbnails"][0]["url"]
        result["viewCount"]["short"], result["viewCount"]["text"]
        result["channel"]["name"], result["channel"]["link"]
        result["publishedTime"]

It is backed by the keyless InnerTube search used elsewhere in fastdl, so it
carries no third-party HTTP dependency at all. If that call fails it falls back
to the real youtubesearchpython when installed, so behaviour only ever improves.
"""

from typing import Any, Dict, List, Optional

from . import search as ytsearch


def _channel_link(name: str) -> str:
    if not name:
        return "https://www.youtube.com"
    return f"https://www.youtube.com/results?search_query={name.replace(' ', '+')}"


def _to_ysp_shape(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a fastdl search result into youtubesearchpython's dict layout."""
    video_id = entry.get("id")
    thumbnail = entry.get("thumbnail") or (
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    )
    channel_name = entry.get("channel") or ""
    views_text = entry.get("views") or ""

    return {
        "type": "video",
        "id": video_id,
        "title": entry.get("title") or "",
        "publishedTime": entry.get("published") or "",
        "duration": entry.get("duration"),
        "viewCount": {"text": views_text, "short": views_text},
        "thumbnails": [
            {"url": thumbnail, "width": 480, "height": 360},
            {"url": thumbnail, "width": 480, "height": 360},
        ],
        "richThumbnail": None,
        "descriptionSnippet": None,
        "channel": {
            "name": channel_name,
            "id": None,
            "thumbnails": [],
            "link": _channel_link(channel_name),
        },
        "accessibility": {"title": entry.get("title") or "", "duration": entry.get("duration")},
        "link": entry.get("link") or f"https://www.youtube.com/watch?v={video_id}",
        "shelfTitle": None,
    }


class VideosSearch:
    """API-compatible subset of youtubesearchpython.__future__.VideosSearch."""

    def __init__(self, query: str, limit: int = 20, language: str = "en",
                 region: str = "US", timeout: Optional[int] = None) -> None:
        self.query = query
        self.limit = int(limit or 1)
        self.language = language
        self.region = region
        self._results: Optional[List[Dict[str, Any]]] = None

    async def next(self) -> Dict[str, Any]:
        entries: List[Dict[str, Any]] = []
        try:
            entries = await ytsearch.search(self.query, limit=self.limit)
        except Exception:
            entries = []

        if not entries:
            # Defer to the original library when present, so this shim can only
            # add coverage, never remove it.
            try:
                from youtubesearchpython.__future__ import (  # type: ignore
                    VideosSearch as _Upstream,
                )

                return await _Upstream(self.query, limit=self.limit).next()
            except Exception:
                return {"result": []}

        self._results = [_to_ysp_shape(entry) for entry in entries]
        return {"result": self._results}

    def result(self) -> Dict[str, Any]:
        return {"result": self._results or []}


__all__ = ["VideosSearch"]
