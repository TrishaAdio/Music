"""
Speed benchmark for the audio engine.

Measures the three numbers that actually matter, separately, because they are
very different in practice:

  1. PLAY   - time until audio can start in a voice chat. No download happens;
              this is resolve + ffmpeg opening the stream.
  2. FILE   - time to a complete file on disk (what /song upload needs).
  3. CACHED - time on a repeat request for the same track.

    python3 tools/speed_bench.py
    python3 tools/speed_bench.py --song "kesariya" --song "believer"
"""

import argparse
import asyncio
import logging
import os
import shutil
import statistics
import subprocess
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

for _name, _path in (
    ("BrandrdXMusic", os.path.join(ROOT, "BrandrdXMusic")),
    ("BrandrdXMusic.core", os.path.join(ROOT, "BrandrdXMusic", "core")),
):
    if _name not in sys.modules:
        _stub = types.ModuleType(_name)
        _stub.__path__ = [_path]  # type: ignore[attr-defined]
        sys.modules[_name] = _stub
sys.modules["BrandrdXMusic"].LOGGER = lambda n: logging.getLogger(n)  # type: ignore

from BrandrdXMusic.core.fastdl import (  # noqa: E402
    TrackRequest,
    close_session,
    fastdl_config,
    materialise,
    resolve,
)
from BrandrdXMusic.core.fastdl.cache import url_cache  # noqa: E402

SONGS = [
    "kesariya",
    "tum hi ho",
    "channa mereya",
    "apna bana le",
    "raatan lambiyan",
    "shape of you",
    "blinding lights",
    "believer imagine dragons",
]

FFMPEG = shutil.which("ffmpeg") or "/usr/local/bin/ffmpeg"


def probe_stream(url: str) -> float:
    """
    Time for ffmpeg to open the stream and read the header.

    This is the work py-tgcalls does before the first audio frame reaches
    Telegram, so resolve + this is a realistic 'time until playback starts'.
    """
    if not os.path.exists(FFMPEG):
        return -1.0
    started = time.monotonic()
    try:
        subprocess.run(
            [FFMPEG, "-hide_banner", "-loglevel", "error",
             "-i", url, "-t", "1", "-f", "null", "-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )
    except Exception:
        return -1.0
    return time.monotonic() - started


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--song", action="append", default=[])
    args = parser.parse_args()
    songs = args.song or SONGS

    print(f"provider order : {', '.join(fastdl_config.provider_order)}")
    print(f"direct stream  : {fastdl_config.prefer_direct_stream}")
    print(f"ffmpeg         : {FFMPEG if os.path.exists(FFMPEG) else 'NOT FOUND (skipping open test)'}")
    print()

    play_rows, file_rows, cached_rows = [], [], []

    header = (f"{'song':26} {'resolve':>8} {'ffopen':>8} {'PLAY':>8} "
              f"{'download':>9} {'FILE':>8}  source / matched")
    print("=" * 118)
    print(header)
    print("-" * 118)

    for song in songs:
        request = TrackRequest(query=song)
        try:
            t0 = time.monotonic()
            resolved = await resolve(request, use_cache=False)
            t_resolve = time.monotonic() - t0

            t_open = probe_stream(resolved.url) if resolved.is_remote else 0.0
            play_total = t_resolve + max(t_open, 0.0)

            t1 = time.monotonic()
            local = await materialise(TrackRequest(query=song), resolved)
            t_download = time.monotonic() - t1
            file_total = t_resolve + t_download

            size = os.path.getsize(local.url) if os.path.exists(local.url) else 0

            play_rows.append(play_total)
            file_rows.append(file_total)

            print(f"{song:26} {t_resolve:7.2f}s {t_open:7.2f}s {play_total:7.2f}s "
                  f"{t_download:8.2f}s {file_total:7.2f}s  "
                  f"{resolved.provider} / {str(resolved.title)[:22]!r} "
                  f"{resolved.bitrate or '?'}k {size/1048576:.1f}MiB")
        except Exception as exc:  # noqa: BLE001
            print(f"{song:26} FAILED  {type(exc).__name__}: {str(exc)[:60]}")

    # Repeat requests, the way the bot actually calls it: caching enabled, so
    # the first call populates and the second is the one worth timing.
    print("-" * 118)
    print("repeat request (url cache + disk cache warm, as the bot calls it):")
    url_cache.clear()
    for song in songs:
        try:
            # Warm-up call with caching on, exactly like a real first play.
            warm = await resolve(TrackRequest(query=song))
            await materialise(TrackRequest(query=song), warm)

            t0 = time.monotonic()
            again = await resolve(TrackRequest(query=song))
            await materialise(TrackRequest(query=song), again)
            cached_rows.append(time.monotonic() - t0)
        except Exception:
            pass
    if cached_rows:
        print(f"  {len(cached_rows)} repeats: median "
              f"{statistics.median(cached_rows) * 1000:.1f}ms  "
              f"min {min(cached_rows) * 1000:.1f}ms  "
              f"max {max(cached_rows) * 1000:.1f}ms")

    print("=" * 118)

    def summarise(label: str, rows) -> None:
        if not rows:
            return
        print(f"  {label:34} median {statistics.median(rows):5.2f}s   "
              f"min {min(rows):5.2f}s   max {max(rows):5.2f}s")

    print("SUMMARY")
    summarise("PLAY (voice chat, no download)", play_rows)
    summarise("FILE (full download to disk)", file_rows)
    if cached_rows:
        summarise("CACHED (repeat request)", cached_rows)
    print()
    print(f"  {len(play_rows)}/{len(songs)} songs succeeded")

    await close_session()
    return 0 if len(play_rows) == len(songs) else 1


if __name__ == "__main__":
    async def _run() -> int:
        try:
            return await main()
        finally:
            await close_session()

    raise SystemExit(asyncio.run(_run()))
