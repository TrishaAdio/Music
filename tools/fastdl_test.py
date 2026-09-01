"""
Standalone harness for the fastdl engine.

Runs without Telegram credentials, MongoDB or any bot config, so it can be used
on a fresh server to confirm the download path works before starting the bot:

    python3 tools/fastdl_test.py
    python3 tools/fastdl_test.py --download
    python3 tools/fastdl_test.py --query "kesariya" --query "believer"
"""

import argparse
import asyncio
import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Importing RioEra normally boots the whole bot (pyrogram client, Mongo,
# assistants). fastdl deliberately has no bot dependencies, so stub the parent
# packages to load it in isolation. This is what lets the harness run on a bare
# server with nothing configured.
for name, path in (
    ("RioEra", os.path.join(ROOT, "RioEra")),
    ("RioEra.core", os.path.join(ROOT, "RioEra", "core")),
):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [path]  # type: ignore[attr-defined]
        sys.modules[name] = stub

from RioEra.core.fastdl import (  # noqa: E402
    TrackRequest,
    close_session,
    fastdl_config,
    health_report,
    materialise,
    resolve,
)

DEFAULT_QUERIES = [
    "kesariya",
    "tum hi ho",
    "shape of you",
    "channa mereya",
    "blinding lights",
    "raatan lambiyan",
    "apna bana le",
    "believer imagine dragons",
]

# Real YouTube ids, exercising the oEmbed -> catalogue bridge.
DEFAULT_VIDEO_IDS = [
    "BddP6PYo2gs",  # Kesariya
    "JGwWNGJdvx8",  # Shape of You
    "hT_nvWreIhg",  # Counting Stars
    "kJQP7kiw5Fk",  # Despacito
    "l_MyUGq7pgs",  # Malhari
]


async def run_query(label: str, request: TrackRequest, download: bool) -> dict:
    started = time.monotonic()
    row = {"label": label, "ok": False, "detail": "", "resolve": 0.0, "download": 0.0}
    try:
        resolved = await resolve(request, use_cache=False)
        row["resolve"] = time.monotonic() - started
        row["ok"] = True
        row["detail"] = (
            f"{resolved.provider} | {resolved.title!r} "
            f"| {resolved.bitrate or '?'}kbps | score {resolved.score:.0f} "
            f"| {(resolved.size or 0) / 1048576:.1f}MiB"
        )
        if download:
            dl_started = time.monotonic()
            local = await materialise(request, resolved)
            row["download"] = time.monotonic() - dl_started
            size = os.path.getsize(local.url) if os.path.exists(local.url) else 0
            row["detail"] += f" | saved {size / 1048576:.2f}MiB"
            if size < 1024:
                row["ok"] = False
                row["detail"] += " (TOO SMALL)"
    except Exception as exc:  # noqa: BLE001
        row["resolve"] = time.monotonic() - started
        row["detail"] = f"{type(exc).__name__}: {exc}"[:200]
    return row


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--video-id", action="append", default=[])
    parser.add_argument("--download", action="store_true",
                        help="also download to disk and verify size")
    parser.add_argument("--concurrent", type=int, default=0,
                        help="fire N identical requests to test single-flight")
    args = parser.parse_args()

    queries = args.query or DEFAULT_QUERIES
    video_ids = args.video_id or ([] if args.query else DEFAULT_VIDEO_IDS)

    print(f"provider order : {', '.join(fastdl_config.provider_order)}")
    print(f"direct stream  : {fastdl_config.prefer_direct_stream}")
    print(f"match floor    : {fastdl_config.min_match_score}")
    print(f"cache dir      : {fastdl_config.cache_dir}")
    print()

    rows = []

    if queries:
        print("=" * 100)
        print("TEXT SEARCH")
        print("=" * 100)
        for query in queries:
            row = await run_query(query, TrackRequest(query=query), args.download)
            rows.append(row)
            flag = "ok  " if row["ok"] else "FAIL"
            timing = f"{row['resolve']:5.2f}s"
            if args.download:
                timing += f" +{row['download']:5.2f}s"
            print(f"  [{flag}] {query:26} {timing}  {row['detail']}")

    if video_ids:
        print()
        print("=" * 100)
        print("YOUTUBE ID  (oEmbed title bridge -> catalogue)")
        print("=" * 100)
        for vid in video_ids:
            row = await run_query(vid, TrackRequest(video_id=vid), args.download)
            rows.append(row)
            flag = "ok  " if row["ok"] else "FAIL"
            timing = f"{row['resolve']:5.2f}s"
            if args.download:
                timing += f" +{row['download']:5.2f}s"
            print(f"  [{flag}] {vid:26} {timing}  {row['detail']}")

    if args.concurrent:
        print()
        print("=" * 100)
        print(f"SINGLE-FLIGHT  ({args.concurrent} simultaneous identical requests)")
        print("=" * 100)
        started = time.monotonic()
        results = await asyncio.gather(*[
            resolve(TrackRequest(query="kesariya"), use_cache=False)
            for _ in range(args.concurrent)
        ], return_exceptions=True)
        elapsed = time.monotonic() - started
        good = [r for r in results if not isinstance(r, Exception)]
        urls = {r.url for r in good}
        print(f"  {len(good)}/{args.concurrent} resolved in {elapsed:.2f}s total")
        print(f"  distinct urls returned: {len(urls)} (1 means de-duplication worked)")

    print()
    print("=" * 100)
    print(await health_report())
    print("=" * 100)

    ok = sum(1 for r in rows if r["ok"])
    total = len(rows)
    resolve_times = [r["resolve"] for r in rows if r["ok"]]
    print()
    print(f"RESULT: {ok}/{total} succeeded")
    if resolve_times:
        ordered = sorted(resolve_times)
        median = ordered[len(ordered) // 2]
        print(f"resolve: median {median:.2f}s | min {ordered[0]:.2f}s | max {ordered[-1]:.2f}s")
    if args.download:
        dl = [r["download"] for r in rows if r["ok"] and r["download"]]
        if dl:
            ordered = sorted(dl)
            print(f"download: median {ordered[len(ordered)//2]:.2f}s | "
                  f"min {ordered[0]:.2f}s | max {ordered[-1]:.2f}s")
            end2end = [r["resolve"] + r["download"] for r in rows if r["ok"]]
            ordered = sorted(end2end)
            print(f"end-to-end: median {ordered[len(ordered)//2]:.2f}s | "
                  f"min {ordered[0]:.2f}s | max {ordered[-1]:.2f}s")

    await close_session()
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
