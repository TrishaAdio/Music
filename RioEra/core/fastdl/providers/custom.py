"""
Operator-supplied resolver endpoints.

This replaces the old design, where the download host was fetched at import time
from a pastebin URL. That meant whoever controlled that paste controlled where
every deployment sent its traffic, and deleting the paste bricked the bot.

Endpoints now come from the FASTDL_CUSTOM_API environment variable and default
to empty, so nothing external is contacted unless the operator opts in:

    FASTDL_CUSTOM_API="https://my-api.example/download?id={id}"

Templates support {id} and {query}. The response is scanned for a direct media
URL under any of the common key names, so most self-hosted wrappers work as-is.
"""

import urllib.parse
from typing import Any, Dict, List, Optional

from ..config import fastdl_config
from ..models import NotFound, Resolved, TrackRequest
from ..net import get_json, probe

NAME = "custom"

_URL_KEYS = (
    "url", "audio_url", "audioUrl", "stream_url", "streamUrl", "link",
    "download_url", "downloadUrl", "media_url", "mediaUrl", "direct_url", "src",
)
_CONTAINER_KEYS = ("result", "data", "results", "response", "song", "audio", "media")


def _find_media_url(payload: Any, depth: int = 0) -> Optional[str]:
    """Walk the response looking for the first plausible media URL."""
    if depth > 6:
        return None
    if isinstance(payload, str):
        if payload.startswith(("http://", "https://")):
            return payload
        return None
    if isinstance(payload, list):
        for item in payload:
            found = _find_media_url(item, depth + 1)
            if found:
                return found
        return None
    if isinstance(payload, dict):
        for key in _URL_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
            if isinstance(value, (dict, list)):
                found = _find_media_url(value, depth + 1)
                if found:
                    return found
        for key in _CONTAINER_KEYS:
            if key in payload:
                found = _find_media_url(payload[key], depth + 1)
                if found:
                    return found
        for value in payload.values():
            if isinstance(value, (dict, list)):
                found = _find_media_url(value, depth + 1)
                if found:
                    return found
    return None


def _build_url(template: str, request: TrackRequest) -> str:
    identifier = request.video_id or ""
    query = request.query or request.expected_title or ""
    if "{id}" in template or "{query}" in template:
        return (
            template
            .replace("{id}", urllib.parse.quote(identifier, safe=""))
            .replace("{query}", urllib.parse.quote(query, safe=""))
        )
    joiner = "&" if "?" in template else "?"
    key = "id" if identifier else "query"
    value = identifier or query
    return f"{template}{joiner}{key}={urllib.parse.quote(value, safe='')}"


async def resolve(request: TrackRequest) -> Resolved:
    endpoints: List[str] = fastdl_config.custom_endpoints
    if not endpoints:
        raise NotFound("no custom endpoints configured (FASTDL_CUSTOM_API)")

    errors: List[str] = []
    for template in endpoints:
        target = _build_url(template, request)
        try:
            payload = await get_json(
                target, timeout=fastdl_config.resolve_timeout, retries=0
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{_host(template)}: {type(exc).__name__}")
            continue

        media_url = _find_media_url(payload)
        if not media_url:
            errors.append(f"{_host(template)}: no media url in response")
            continue

        ok, size, ranges = await probe(media_url)
        if not ok:
            errors.append(f"{_host(template)}: media url unreachable")
            continue

        meta: Dict[str, Any] = payload if isinstance(payload, dict) else {}
        return Resolved(
            url=media_url,
            provider=f"{NAME}:{_host(template)}",
            ext="mp4" if request.want_video else "m4a",
            size=size,
            supports_ranges=ranges,
            title=meta.get("title") or request.expected_title,
            duration=request.expected_duration,
            score=90.0,
        )

    raise NotFound("custom endpoints exhausted: " + "; ".join(errors[:3]))


def _host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc or url[:40]
    except Exception:
        return url[:40]
