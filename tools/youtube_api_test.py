"""
Integration check for the YouTubeAPI adapter.

Exercises the exact methods and return shapes the bot's call sites rely on, so a
regression in the adapter is caught here rather than in a live voice chat.
Requires no Telegram/Mongo credentials.

    python3 tools/youtube_api_test.py
"""

import asyncio
import inspect
import logging
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "x")
os.environ.setdefault("BOT_TOKEN", "x")
os.environ.setdefault("MONGO_DB_URI", "x")
os.environ.setdefault("LOGGER_ID", "-100")
os.environ.setdefault("OWNER_ID", "1")

# Stub the bot package: the platform adapters only need `app` and `LOGGER`,
# and booting the real thing would require Telegram and MongoDB.
for _name, _path in (
    ("BrandrdXMusic", os.path.join(ROOT, "BrandrdXMusic")),
    ("BrandrdXMusic.core", os.path.join(ROOT, "BrandrdXMusic", "core")),
    ("BrandrdXMusic.utils", os.path.join(ROOT, "BrandrdXMusic", "utils")),
):
    if _name not in sys.modules:
        _stub = types.ModuleType(_name)
        _stub.__path__ = [_path]  # type: ignore[attr-defined]
        sys.modules[_name] = _stub

sys.modules["BrandrdXMusic"].app = types.SimpleNamespace(username="test")  # type: ignore
sys.modules["BrandrdXMusic"].LOGGER = lambda name: logging.getLogger(name)  # type: ignore

from BrandrdXMusic.core.fastdl import close_session  # noqa: E402
from BrandrdXMusic.platforms.Youtube import YouTubeAPI  # noqa: E402

VIDEO_ID = "BddP6PYo2gs"      # Kesariya
QUERY = "tum hi ho"
FAILURES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global FAILURES
    if not condition:
        FAILURES += 1
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}" + (f" -> {detail}" if detail else ""))


async def main() -> int:
    api = YouTubeAPI()

    print("exists / link parsing")
    check("exists(url)", await api.exists("https://www.youtube.com/watch?v=" + VIDEO_ID))
    check("exists(videoid=True)", await api.exists(VIDEO_ID, True))
    check("exists(non-youtube) is False", not await api.exists("https://example.com/x"))

    print("\ndetails() -> 5-tuple (title, duration_min, duration_sec, thumb, vidid)")
    result = await api.details(VIDEO_ID, True)
    check("returns 5 items", isinstance(result, tuple) and len(result) == 5, str(len(result)))
    title, duration_min, duration_sec, thumb, vidid = result
    check("title non-empty", bool(title), repr(title)[:44])
    check("duration_min formatted", bool(duration_min), repr(duration_min))
    check("duration_sec is positive int", isinstance(duration_sec, int) and duration_sec > 0,
          str(duration_sec))
    check("thumbnail is a url", bool(thumb) and thumb.startswith("http"), str(thumb)[:52])
    check("vidid matches request", vidid == VIDEO_ID, str(vidid))

    print("\ntitle / duration / thumbnail scalars")
    check("title()", bool(await api.title(VIDEO_ID, True)))
    check("duration()", bool(await api.duration(VIDEO_ID, True)))
    check("thumbnail()", bool(await api.thumbnail(VIDEO_ID, True)))

    print("\ntrack() -> (dict, vidid)")
    details, track_id = await api.track(VIDEO_ID, True)
    check("dict returned", isinstance(details, dict))
    check("has required keys",
          all(k in (details or {}) for k in ("title", "link", "vidid", "duration_min", "thumb")),
          str(sorted((details or {}).keys())))
    check("track_id matches", track_id == VIDEO_ID)

    print("\nslider() -> (title, duration_min, thumb, vidid)")
    slider = await api.slider(QUERY, 0)
    check("returns 4 items", isinstance(slider, tuple) and len(slider) == 4, str(len(slider)))
    check("slider title non-empty", bool(slider[0]), repr(slider[0])[:44])

    print("\nformats() -> (list, link)")
    formats, link = await api.formats(VIDEO_ID, True)
    check("list returned", isinstance(formats, list) and len(formats) > 0, f"{len(formats)} entries")
    check("entries have expected keys",
          all(all(k in f for k in ("format", "filesize", "format_id", "ext", "format_note", "yturl"))
              for f in formats))
    check("link returned", bool(link))

    print("\ndownload() for playback -> (playable, direct)")
    try:
        got = await api.download(VIDEO_ID, None, videoid=True)
        check("returns a 2-tuple", isinstance(got, tuple) and len(got) == 2, str(type(got)))
        playable, direct = got
        check("direct is True", direct is True)
        check("playable is url or existing file",
              bool(playable)
              and (str(playable).startswith("http") or os.path.exists(str(playable))),
              str(playable)[:66])
    except Exception as exc:  # noqa: BLE001
        check("download() for playback", False, f"{type(exc).__name__}: {exc}"[:200])

    print("\ndownload(songaudio=True) -> bare local path (needed for upload)")
    try:
        path = await api.download(VIDEO_ID, None, videoid=True, songaudio=True)
        check("returns a string, not a tuple", isinstance(path, str), str(type(path)))
        exists = isinstance(path, str) and os.path.exists(path)
        check("file exists on disk", exists, str(path))
        if exists:
            size = os.path.getsize(path)
            check("file is a plausible audio size (>200KB)", size > 200_000,
                  f"{size / 1048576:.2f} MiB")
    except Exception as exc:  # noqa: BLE001
        check("download(songaudio=True)", False, f"{type(exc).__name__}: {exc}"[:200])

    print("\nvideo() -> (1, playable) or (0, message)")
    try:
        code, value = await api.video(VIDEO_ID, True)
        check("code is 0 or 1", code in (0, 1), str(code))
        check("value is a non-empty string", bool(value), str(value)[:70])
        if code == 0:
            print("         note: video unavailable from this IP; "
                  "error path returned cleanly instead of raising")
    except Exception as exc:  # noqa: BLE001
        check("video() never raises", False, f"{type(exc).__name__}: {exc}"[:160])

    print("\nplaylist() -> list")
    try:
        playlist = await api.playlist(
            "https://www.youtube.com/playlist?list=PLFgquLnL59alCl_2TQvOiD5Vgm1hCaGSI", 5, 1
        )
        check("returns a list (may be empty)", isinstance(playlist, list),
              f"{len(playlist)} ids")
    except Exception as exc:  # noqa: BLE001
        check("playlist() never raises", False, f"{type(exc).__name__}: {exc}"[:160])

    print("\nsignature compatibility with bot call sites")
    sig = inspect.signature(api.download)
    for param in ("link", "mystic", "video", "videoid", "songaudio", "songvideo",
                  "format_id", "title"):
        check(f"download() accepts {param}", param in sig.parameters)

    print()
    print(f"{'ALL CHECKS PASSED' if FAILURES == 0 else f'{FAILURES} CHECK(S) FAILED'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    async def _run() -> int:
        try:
            return await main()
        finally:
            await close_session()

    raise SystemExit(asyncio.run(_run()))
