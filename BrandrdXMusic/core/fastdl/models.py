"""Shared data types passed between the engine and its providers."""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class TrackRequest:
    """What the caller wants. Every field beyond one identifier is a hint."""

    # A YouTube video id, when the caller has one.
    video_id: Optional[str] = None
    # Free-text search ("kesariya", or a cleaned-up video title).
    query: Optional[str] = None
    # Hints used for match scoring; populated from YouTube metadata when known.
    expected_title: Optional[str] = None
    expected_artist: Optional[str] = None
    expected_duration: Optional[int] = None
    want_video: bool = False

    def cache_key(self) -> str:
        base = self.video_id or (self.query or "").strip().lower()
        return f"{'v' if self.want_video else 'a'}:{base}"


@dataclass
class Resolved:
    """A playable result."""

    # Either an http(s) URL (streamable straight into ffmpeg) or a local path.
    url: str
    provider: str
    ext: str = "m4a"
    is_local: bool = False
    size: Optional[int] = None
    supports_ranges: bool = False
    title: Optional[str] = None
    artists: Optional[str] = None
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    bitrate: Optional[str] = None
    score: float = 0.0
    # Headers required to fetch `url` (googlevideo needs a matching UA).
    headers: Dict[str, str] = field(default_factory=dict)

    @property
    def is_remote(self) -> bool:
        return not self.is_local and self.url.startswith(("http://", "https://"))


class ProviderError(Exception):
    """A provider could not satisfy the request. Non-fatal: try the next one."""


class NotFound(ProviderError):
    """The provider works but genuinely has no acceptable match."""
