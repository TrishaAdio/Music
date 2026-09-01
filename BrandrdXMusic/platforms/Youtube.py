"""
YouTube platform adapter.

The public surface of this module (the YouTubeAPI class) is unchanged, so every
existing caller in the bot keeps working. What changed is everything underneath:

Before
    * the download host was fetched from a pastebin URL at import time, so a
      third party could redirect or disable every deployment at will, and the
      hardcoded fallback was a single host with no redundancy
    * metadata came from youtubesearchpython, which breaks on httpx >= 0.28
    * /song used yt_dlp.extract_info directly, which now demands cookies
    * every play downloaded the whole file before audio started

After
    * audio is resolved through BrandrdXMusic.core.fastdl: several independent
      cookieless sources tried in health order, with a match-confidence gate
    * search/metadata come from keyless InnerTube, with youtubesearchpython only
      as a fallback
    * playback normally streams a CDN url straight into pytgcalls, so nothing is
      downloaded for a voice-chat play at all

Search and streaming are separated on purpose: YouTube's search endpoint answers
fine from a server IP while its player endpoint returns a bot check, so YouTube
still supplies titles/durations/ids while audio comes from elsewhere.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from BrandrdXMusic.core.fastdl import (
    AllProvidersFailed,
    TrackRequest,
    get_stream,
    materialise,
)
from BrandrdXMusic.core.fastdl import search as ytsearch
from BrandrdXMusic.core.fastdl.cache import TTLCache
from BrandrdXMusic.core.fastdl.match import clean_query
from BrandrdXMusic.utils.formatters import time_to_seconds

# Metadata resolved by details()/track() is reused by download() so the match
# gate gets a duration for free instead of paying for a second lookup.
_meta_cache = TTLCache(ttl=1800.0, max_items=1024)


def _remember(entry: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if entry and entry.get("id"):
        _meta_cache.set(entry["id"], entry)
    return entry


def _recall(video_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not video_id:
        return None
    return _meta_cache.get(video_id)


async def _lookup(query: str) -> Optional[Dict[str, Any]]:
    """Resolve a query or link to a single normalised metadata dict."""
    video_id = ytsearch.extract_video_id(query)
    if video_id:
        cached = _recall(video_id)
        if cached:
            return cached
        return _remember(await ytsearch.video_details(video_id))
    results = await ytsearch.search(query, limit=1)
    return _remember(results[0]) if results else None


def _request_for(
    video_id: Optional[str],
    *,
    want_video: bool = False,
    query: Optional[str] = None,
) -> TrackRequest:
    """Build a TrackRequest, attaching any metadata already known."""
    meta = _recall(video_id)
    request = TrackRequest(video_id=video_id, want_video=want_video, query=query)
    if meta:
        request.expected_title = meta.get("title")
        request.expected_artist = meta.get("channel")
        request.expected_duration = meta.get("duration_sec") or None
        if not request.query and meta.get("title"):
            request.query = clean_query(meta["title"]) or meta["title"]
    return request


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="

    # ------------------------------------------------------------------
    # link helpers
    # ------------------------------------------------------------------
    async def exists(self, link: str, videoid: Union[bool, str] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link or ""))

    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    # ------------------------------------------------------------------
    # metadata
    # ------------------------------------------------------------------
    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        entry = await _lookup(link)
        if not entry:
            raise ValueError(f"no results for {link!r}")

        duration_min = entry.get("duration")
        duration_sec = entry.get("duration_sec") or 0
        if duration_min and not duration_sec:
            try:
                duration_sec = int(time_to_seconds(duration_min))
            except Exception:
                duration_sec = 0
        return (
            entry.get("title"),
            duration_min,
            duration_sec,
            entry.get("thumbnail"),
            entry.get("id"),
        )

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        entry = await _lookup(link.split("&")[0])
        return entry.get("title") if entry else None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        entry = await _lookup(link.split("&")[0])
        return entry.get("duration") if entry else None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        entry = await _lookup(link.split("&")[0])
        if entry:
            return entry.get("thumbnail")
        vid = ytsearch.extract_video_id(link)
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else None

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        entry = await _lookup(link)
        if not entry:
            return None, None
        return (
            {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "vidid": entry.get("id"),
                "duration_min": entry.get("duration"),
                "thumb": entry.get("thumbnail"),
            },
            entry.get("id"),
        )

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        return await ytsearch.playlist_video_ids(link, int(limit))

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        results = await ytsearch.search(link, limit=10)
        if not results:
            raise ValueError(f"no results for {link!r}")
        entry = results[min(int(query_type), len(results) - 1)]
        _remember(entry)
        return (
            entry.get("title"),
            entry.get("duration"),
            entry.get("thumbnail"),
            entry.get("id"),
        )

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        """
        Available download options.

        The old implementation asked yt-dlp to enumerate YouTube's own formats,
        which is now a cookie-gated request. Since audio is served from whichever
        provider answers, the real choice is simply audio or video, so a small
        synthetic list is returned in the shape callers expect.
        """
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        entry = await _lookup(link)
        duration_sec = (entry or {}).get("duration_sec") or 0

        # Rough size estimate so the UI can show something sensible.
        audio_bytes = int(duration_sec * 320 * 1000 / 8) if duration_sec else None
        video_bytes = int(duration_sec * 900 * 1000 / 8) if duration_sec else None

        formats_available = [
            {
                "format": "audio only (best available)",
                "filesize": audio_bytes,
                "format_id": "fastdl-audio",
                "ext": "m4a",
                "format_note": "Best",
                "yturl": link,
            },
            {
                "format": "video - best available",
                "filesize": video_bytes,
                "format_id": "fastdl-video",
                "ext": "mp4",
                "format_note": "Best",
                "yturl": link,
            },
        ]
        return formats_available, link

    # ------------------------------------------------------------------
    # media
    # ------------------------------------------------------------------
    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Return (1, playable) or (0, error_message)."""
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        video_id = ytsearch.extract_video_id(link)
        if not video_id and link:
            entry = await _lookup(link)
            video_id = (entry or {}).get("id")
        if not video_id:
            return 0, "Could not identify that video."

        try:
            resolved = await get_stream(
                _request_for(video_id, want_video=True)
            )
            return 1, resolved.url
        except AllProvidersFailed as exc:
            return 0, exc.user_message()
        except Exception as exc:  # noqa: BLE001
            return 0, f"Video resolution failed: {exc}"

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Union[str, Tuple[str, bool]]:
        """
        Resolve a track for playback or upload.

        Return shape is kept exactly as callers expect:
          * songaudio / songvideo -> a local file path (a file must exist to
            upload it to Telegram)
          * otherwise -> (playable, direct) where `playable` is usually a CDN
            url and `direct` is True, meaning "hand this to the player as-is"
        """
        if videoid:
            link = self.base + link

        video_id = ytsearch.extract_video_id(link)
        query = None
        if not video_id:
            # A raw search string rather than a link.
            query = link
            entry = await _lookup(link)
            if entry:
                video_id = entry.get("id")

        want_video = bool(video or songvideo)
        request = _request_for(video_id, want_video=want_video, query=query)

        # Uploading to Telegram needs real bytes on disk.
        if songaudio or songvideo:
            resolved = await materialise(request)
            return resolved.url

        resolved = await get_stream(request)
        # `direct` tells the queue to reuse this exact target on replay. Remote
        # urls are marked direct too: pytgcalls streams them, and the resolved-url
        # cache keeps them valid for the length of a normal queue.
        return resolved.url, True


# ----------------------------------------------------------------------
# Backwards-compatible module-level helpers.
# ----------------------------------------------------------------------
async def download_song(link: str):
    """Kept for compatibility. Returns (path, None) or (None, error)."""
    video_id = ytsearch.extract_video_id(link) or link
    try:
        resolved = await materialise(_request_for(video_id))
        return resolved.url, None
    except AllProvidersFailed as exc:
        return None, exc.user_message()
    except Exception as exc:  # noqa: BLE001
        return None, f"Error: {exc}"


async def download_video(link: str):
    """Kept for compatibility. Returns (path, None) or (None, error)."""
    video_id = ytsearch.extract_video_id(link) or link
    try:
        resolved = await materialise(_request_for(video_id, want_video=True))
        return resolved.url, None
    except AllProvidersFailed as exc:
        return None, exc.user_message()
    except Exception as exc:  # noqa: BLE001
        return None, f"Error: {exc}"


async def get_playlist_videos(playlist_url: str, limit: int) -> List[str]:
    return await ytsearch.playlist_video_ids(playlist_url, limit)
