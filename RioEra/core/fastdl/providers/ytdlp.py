"""
yt-dlp provider - last resort only, and explicitly cookieless.

yt-dlp is kept in the chain because it handles long-tail cases nothing else
does, but it is deliberately last and deliberately never handed a cookie file.
Cookie-based extraction is the thing that keeps breaking these bots: exported
cookies get invalidated by YouTube, the account gets flagged, and every play
starts failing until someone re-exports them by hand.

Instead only the mobile/embedded player clients are requested, and extraction is
run in a worker thread so the blocking network work never stalls the event loop.
"""

import asyncio
from typing import Any, Dict, List, Optional

from ..config import fastdl_config
from ..models import NotFound, ProviderError, Resolved, TrackRequest

NAME = "ytdlp"


def _extract(target: str, want_video: bool) -> Dict[str, Any]:
    import yt_dlp

    options: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "format": "bestvideo[height<=480]+bestaudio/best" if want_video else "bestaudio/best",
        "socket_timeout": 15,
        "retries": 2,
        "extractor_args": {
            "youtube": {
                # Mobile clients return unciphered URLs and do not need cookies.
                "player_client": list(fastdl_config.ytdlp_player_clients),
                "player_skip": ["configs"],
            }
        },
        # Hard guarantee that no cookie jar is ever consulted.
        "cookiefile": None,
        "cookiesfrombrowser": None,
        "nocheckcertificate": fastdl_config.insecure_tls,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(target, download=False)


def _best_url(info: Dict[str, Any], want_video: bool) -> Optional[Dict[str, Any]]:
    if info.get("url") and not info.get("requested_formats"):
        return {"url": info["url"], "ext": info.get("ext"),
                "filesize": info.get("filesize") or info.get("filesize_approx"),
                "abr": info.get("abr")}

    formats: List[Dict[str, Any]] = info.get("formats") or []
    if want_video:
        usable = [
            f for f in formats
            if f.get("url") and f.get("vcodec") not in (None, "none")
            and f.get("acodec") not in (None, "none")
        ]
        key = lambda f: (f.get("height") or 0, f.get("tbr") or 0)  # noqa: E731
    else:
        usable = [
            f for f in formats
            if f.get("url") and f.get("acodec") not in (None, "none")
            and f.get("vcodec") in (None, "none")
        ]
        key = lambda f: (1 if (f.get("ext") == "m4a") else 0, f.get("abr") or 0)  # noqa: E731

    if not usable:
        usable = [f for f in formats if f.get("url")]
        if not usable:
            return None
    best = sorted(usable, key=key)[-1]
    return {
        "url": best["url"],
        "ext": best.get("ext"),
        "filesize": best.get("filesize") or best.get("filesize_approx"),
        "abr": best.get("abr"),
    }


async def resolve(request: TrackRequest) -> Resolved:
    if not fastdl_config.allow_ytdlp:
        raise NotFound("ytdlp disabled by configuration")

    if request.video_id:
        target = f"https://www.youtube.com/watch?v={request.video_id}"
    elif request.query:
        target = f"ytsearch1:{request.query}"
    else:
        raise NotFound("ytdlp needs a video id or query")

    try:
        info = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, _extract, target, request.want_video
            ),
            timeout=max(fastdl_config.resolve_timeout * 3, 30.0),
        )
    except asyncio.TimeoutError:
        raise ProviderError("ytdlp extraction timed out")
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"ytdlp extraction failed: {type(exc).__name__}: {exc}"[:300])

    if not info:
        raise NotFound("ytdlp returned no info")
    if info.get("entries"):
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise NotFound("ytdlp search returned nothing")
        info = entries[0]

    chosen = _best_url(info, request.want_video)
    if not chosen:
        raise NotFound("ytdlp found no downloadable format")

    ext = chosen.get("ext") or ("mp4" if request.want_video else "m4a")
    return Resolved(
        url=chosen["url"],
        provider=NAME,
        ext=ext,
        size=chosen.get("filesize"),
        supports_ranges=True,
        title=info.get("title"),
        artists=info.get("uploader") or info.get("channel"),
        duration=int(info["duration"]) if info.get("duration") else None,
        thumbnail=info.get("thumbnail"),
        bitrate=str(chosen.get("abr") or ""),
        score=95.0,
        headers={"User-Agent": "Mozilla/5.0"},
    )
