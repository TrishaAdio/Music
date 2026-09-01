"""
Unit checks for the match gate.

These are the cases that actually went wrong during development, kept as
regressions: covers, karaoke uploads, remixes and sped-up edits must lose to the
real recording, and must be rejected outright when the real one is absent.

    python3 tools/match_test.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "RioEra", "core"))

from fastdl import match  # noqa: E402

FLOOR = 62.0

CASES = [
    # (label, query, expected_artist, expected_duration, candidates, expected_title_or_None)
    (
        "clean query strips youtube promo junk",
        None, None, None, None, None,
    ),
    (
        "real track beats karaoke",
        "Believer Imagine Dragons", "Imagine Dragons", 204,
        [
            {"title": "Believer", "artists": "Imagine Dragons", "duration": 204},
            {"title": "Believer (Originally Perfomed By Imagine Dragons)",
             "artists": "ZZang KARAOKE", "duration": 203},
        ],
        "Believer",
    ),
    (
        "real track beats sped-up edit",
        "OneRepublic Counting Stars", "OneRepublic", 258,
        [
            {"title": "OneRepublic - Counting Stars (SpeedUp Version)",
             "artists": "edits", "duration": 190},
            {"title": "Counting Stars", "artists": "OneRepublic", "duration": 257},
        ],
        "Counting Stars",
    ),
    (
        "real track beats remix",
        "Luis Fonsi Despacito Daddy Yankee", "LuisFonsiVEVO", 229,
        [
            {"title": "Despacito (Bestacito remix)", "artists": "CheesyFox52", "duration": 151},
            {"title": "Despacito", "artists": "Luis Fonsi, Daddy Yankee", "duration": 229},
        ],
        "Despacito",
    ),
    (
        "only covers available -> reject",
        "OneRepublic Counting Stars", "OneRepublic", 258,
        [
            {"title": "Counting Stars (Originally Perfomed By OneRepublic)",
             "artists": "ZZang KARAOKE", "duration": 263},
            {"title": "Counting Stars Cover (2014)", "artists": "Alex Madore", "duration": 253},
        ],
        None,
    ),
    (
        "30s preview rejected against a full track",
        "Kesariya Brahmastra", "Sony Music India", 268,
        [
            {"title": "Kesariya", "artists": "Pritam, Arijit Singh", "duration": 30},
        ],
        None,
    ),
    (
        "youtube video edit still matches the album track "
        "(2:53 video vs 4:28 release)",
        "Kesariya Brahmastra", "Sony Music India", 173,
        [
            {"title": "Kesariya", "artists": "Pritam, Arijit Singh", "duration": 268},
        ],
        "Kesariya",
    ),
    (
        "looped/extended upload rejected",
        "OneRepublic Counting Stars", "OneRepublic", 258,
        [
            {"title": "Counting Stars", "artists": "OneRepublic", "duration": 720},
        ],
        None,
    ),
    (
        "correct duration -> accept",
        "Kesariya Brahmastra", "Sony Music India", 268,
        [
            {"title": "Kesariya", "artists": "Pritam, Arijit Singh", "duration": 268},
        ],
        "Kesariya",
    ),
    (
        "explicit remix request allows a remix",
        "Despacito remix", None, None,
        [
            {"title": "Despacito (Remix)", "artists": "Luis Fonsi", "duration": 230},
        ],
        "Despacito (Remix)",
    ),
    (
        "lofi request allows lofi",
        "kesariya lofi", None, None,
        [
            {"title": "Kesariya (Lofi Flip)", "artists": "Various", "duration": 240},
        ],
        "Kesariya (Lofi Flip)",
    ),
]

CLEAN_CASES = [
    ("Kesariya - Brahmastra | Ranbir Kapoor, Alia Bhatt | Pritam", "Kesariya Brahmastra"),
    ("Ed Sheeran - Shape of You (Official Music Video)", "Ed Sheeran Shape of You"),
    ("Malhari - Full Video Song | Bajirao Mastani", "Malhari"),
    ("Believer - Imagine Dragons [Official Audio] HD", "Believer Imagine Dragons"),
]


def main() -> int:
    failures = 0
    print("clean_query:")
    for raw, expected in CLEAN_CASES:
        got = match.clean_query(raw)
        ok = got.lower() == expected.lower()
        failures += 0 if ok else 1
        print(f"  [{'ok  ' if ok else 'FAIL'}] {raw[:46]!r}\n         -> {got!r}"
              + ("" if ok else f"  (expected {expected!r})"))

    print("\npick_best:")
    for case in CASES:
        label, query, artist, duration, candidates, expected = case
        if candidates is None:
            continue
        best, score = match.pick_best(
            candidates, query,
            expected_artist=artist or "",
            expected_duration=duration,
            minimum=FLOOR,
        )
        got_title = best["title"] if best else None
        ok = (got_title == expected)
        failures += 0 if ok else 1
        shown = f"{got_title!r} (score {score:.0f})" if best else f"REJECTED (best {score:.0f})"
        print(f"  [{'ok  ' if ok else 'FAIL'}] {label}\n         -> {shown}"
              + ("" if ok else f"  (expected {expected!r})"))

    print(f"\n{'PASS' if failures == 0 else f'{failures} FAILURE(S)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
