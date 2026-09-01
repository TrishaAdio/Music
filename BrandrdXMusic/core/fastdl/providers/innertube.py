"""
YouTube InnerTube provider - exact-video fallback, still cookieless.

Two things about this file are deliberate and worth not "fixing" later:

1. No API key is sent. The `AIzaSy...` keys that every tutorial hardcodes are
   now rejected outright with HTTP 400 "Precondition check failed". A keyless
   POST to /youtubei/v1/player succeeds and returns in ~0.1s.

2. Only mobile/embedded client contexts are used. These return `adaptiveFormats`
   with plain `url` fields. The desktop WEB client instead returns
   `signatureCipher`, which requires scraping and executing YouTube's JS player
   to descramble - the exact fragile machinery that keeps breaking.

This provider is a fallback rather than the primary path because a flagged
datacenter IP frequently gets `LOGIN_REQUIRED / "Sign in to confirm you're not
a bot"`, which no amount of local cleverness can fix. That failure is detected
and reported clearly so the engine moves on instead of hanging.
"""

from typing import Any, Dict, List, Optional, Tuple

from ..config import fastdl_config
from ..models import NotFound, ProviderError, Resolved, TrackRequest
from ..net import get_json, post_json, probe

NAME = "innertube"

_PLAYER_ENDPOINT = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"

# Ordered by how reliably they return unciphered URLs without a PO token.
_CLIENTS: List[Dict[str, Any]] = [
    {
        "label": "android_vr",
        "context": {
            "clientName": "ANDROID_VR",
            "clientVersion": "1.62.27",
            "deviceMake": "Oculus",
            "deviceModel": "Quest 3",
            "osName": "Android",
            "osVersion": "12",
            "androidSdkVersion": 32,
            "hl": "en",
            "gl": "US",
        },
        "ua": "com.google.android.apps.youtube.vr.oculus/1.62.27 "
              "(Linux; U; Android 12; GB) gzip",
        "client_name_header": "28",
    },
    {
        "label": "ios",
        "context": {
            "clientName": "IOS",
            "clientVersion": "20.10.4",
            "deviceMake": "Apple",
            "deviceModel": "iPhone16,2",
            "osName": "iPhone",
            "osVersion": "18.3.2.22D82",
            "hl": "en",
            "gl": "US",
        },
        "ua": "com.google.ios.youtube/20.10.4 "
              "(iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)",
        "client_name_header": "5",
    },
    {
        "label": "android",
        "context": {
            "clientName": "ANDROID",
            "clientVersion": "20.10.38",
            "androidSdkVersion": 35,
            "osName": "Android",
            "osVersion": "15",
            "hl": "en",
            "gl": "US",
        },
        "ua": "com.google.android.youtube/20.10.38 (Linux; U; Android 15) gzip",
        "client_name_header": "3",
    },
]

_BOT_WALL_REASONS = ("sign in to confirm", "not a bot", "login_required")


async def _call_player(video_id: str, client: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "videoId": video_id,
        "context": {"client": dict(client["context"])},
        "contentCheckOk": True,
        "racyCheckOk": True,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": client["ua"],
        "X-YouTube-Client-Name": client["client_name_header"],
        "X-YouTube-Client-Version": client["context"]["clientVersion"],
        "Origin": "https://www.youtube.com",
    }
    return await post_json(
        _PLAYER_ENDPOINT,
        payload,
        headers=headers,
        timeout=fastdl_config.resolve_timeout,
        retries=0,
    )


def _pick_audio(streaming_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    formats = streaming_data.get("adaptiveFormats") or []
    audio = [
        fmt for fmt in formats
        if str(fmt.get("mimeType", "")).startswith("audio") and fmt.get("url")
    ]
    if not audio:
        return None
    # Prefer m4a/AAC over opus/webm: it muxes into Telegram audio cleanly and
    # needs no re-encode for playback.
    def rank(fmt: Dict[str, Any]) -> Tuple[int, int]:
        mime = str(fmt.get("mimeType", ""))
        prefers = 1 if "mp4a" in mime or "audio/mp4" in mime else 0
        return (prefers, int(fmt.get("bitrate") or 0))

    return sorted(audio, key=rank)[-1]


def _pick_video(streaming_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Progressive formats carry audio+video in one URL, which avoids muxing.
    progressive = [
        fmt for fmt in (streaming_data.get("formats") or [])
        if fmt.get("url") and str(fmt.get("mimeType", "")).startswith("video")
    ]
    if progressive:
        return sorted(progressive, key=lambda f: int(f.get("bitrate") or 0))[-1]
    return None


async def _oembed(video_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Cookieless metadata. This endpoint has no bot gate and answers in ~30ms,
    which is what lets the engine translate a YouTube link into a catalogue
    search when the video itself is not directly fetchable.
    """
    import urllib.parse

    target = urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}", safe="")
    url = f"https://www.youtube.com/oembed?url={target}&format=json"
    try:
        data = await get_json(url, timeout=6.0, retries=1)
    except Exception:
        return None, None
    if not isinstance(data, dict):
        return None, None
    return data.get("title"), data.get("author_name")


async def metadata(video_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Public helper used by the engine for the link -> catalogue bridge."""
    return await _oembed(video_id)


async def resolve(request: TrackRequest) -> Resolved:
    video_id = request.video_id
    if not video_id:
        raise NotFound("innertube requires a video id")

    blocked = False
    errors: List[str] = []

    for client in _CLIENTS:
        try:
            data = await _call_player(video_id, client)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{client['label']}: {type(exc).__name__}")
            continue

        status_block = data.get("playabilityStatus") or {}
        status = str(status_block.get("status") or "")
        if status != "OK":
            reason = str(status_block.get("reason") or status)
            if any(marker in reason.lower() or marker in status.lower()
                   for marker in _BOT_WALL_REASONS):
                blocked = True
            errors.append(f"{client['label']}: {reason}")
            continue

        streaming_data = data.get("streamingData") or {}
        details = data.get("videoDetails") or {}
        chosen = (
            _pick_video(streaming_data) if request.want_video
            else _pick_audio(streaming_data)
        )
        if not chosen:
            errors.append(f"{client['label']}: no unciphered format")
            continue

        try:
            duration = int(details.get("lengthSeconds") or 0) or None
        except (TypeError, ValueError):
            duration = None
        try:
            size = int(chosen.get("contentLength") or 0) or None
        except (TypeError, ValueError):
            size = None

        headers = {"User-Agent": client["ua"]}
        url = chosen["url"]

        ok, probed_size, ranges = await probe(url, headers=headers)
        if not ok:
            errors.append(f"{client['label']}: stream url rejected")
            continue

        mime = str(chosen.get("mimeType", ""))
        if request.want_video:
            ext = "mp4"
        else:
            ext = "m4a" if ("mp4a" in mime or "audio/mp4" in mime) else "opus"

        return Resolved(
            url=url,
            provider=f"{NAME}:{client['label']}",
            ext=ext,
            size=size or probed_size,
            supports_ranges=ranges,
            title=details.get("title"),
            artists=details.get("author"),
            duration=duration,
            thumbnail=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            bitrate=str(chosen.get("bitrate") or ""),
            score=100.0,  # exact video id, no ambiguity
            headers=headers,
        )

    if blocked:
        raise ProviderError(
            "youtube returned its bot check for every client "
            "(server IP is rate limited): " + "; ".join(errors[:3])
        )
    raise NotFound("innertube could not resolve: " + "; ".join(errors[:3]))
