# fastdl — the audio engine

Replaces the old download path. No cookies, no API keys, no accounts, nothing
that expires. Playback normally starts in well under a second because the source
URL is streamed straight into the voice chat instead of being downloaded first.

## What was wrong before

| problem | consequence |
|---|---|
| download host was fetched from `pastebin.com/raw/...` at import time | whoever controlled that paste controlled where every deployment sent its traffic; deleting it bricked the bot |
| one hardcoded fallback host | that host goes down, the bot goes down |
| `/song` called `yt_dlp.extract_info` directly | "Sign in to confirm you're not a bot" as soon as the server IP is flagged |
| a `cookies.txt` was committed to the repo | live Google account credentials leaked, and they expire anyway |
| whole file downloaded before audio started | multi-second waits before anything played |
| no de-duplication | five people spamming `/play` triggered five downloads of the same file |

## Measured behaviour

All figures from a flagged datacenter IP — the worst case, where YouTube refuses
to serve audio at all and yt-dlp fails on every player client. Reproduce with
`python3 tools/speed_bench.py`.

Three numbers matter, and they are very different:

| | median | notes |
|---|---|---|
| **PLAY** (voice chat) | **0.32s** | resolve + ffmpeg opening the stream. Nothing is downloaded. |
| **FILE** (`/song` upload) | **0.33s** | complete file on disk |
| **CACHED** (repeat request) | **<1ms** | in-memory hit, no network |

Cold CDN paths are slower — median **1.05s**, with 7/9 inside 2s and occasional
3–5s outliers. Those outliers are network variance, not engine cost: they occur
on serial and parallel downloads alike, move to different songs on every run, and
a direct `curl` of an edge-warm file returns in 0.04–0.09s at 120–268 MB/s.

Concurrency: 8 simultaneous identical requests collapse to **1** actual fetch.

Integrity: 18/18 sampled downloads decoded cleanly end-to-end under ffmpeg with
durations matching the catalogue metadata, so the speed is not coming from
truncated files.

## How a request flows

```
TrackRequest
  -> resolved-url cache            (instant on repeat)
  -> single-flight gate            (N callers, 1 fetch)
  -> metadata enrichment           (oEmbed / search, ~30-400ms, cookieless)
  -> providers in health order
  -> Resolved: a CDN url, or a local file
```

Search and streaming are deliberately separated. YouTube's *search* endpoint
answers normally from a server IP while its *player* endpoint returns a bot
check, so YouTube still supplies titles, thumbnails, ids and durations, while the
audio bytes come from a source that does not gate them.

## Sources

Order is configurable via `FASTDL_PROVIDERS`. Default:

1. **saavn** — JioSaavn. Direct unsigned 320kbps CDN links. ~0.3s. Best coverage
   for Indian music. No auth of any kind.
2. **soundcloud** — covers Western tracks the JioSaavn catalogue lacks. Uses the
   public web-player `client_id`, auto-refreshed. 30-second previews (`SNIP`) and
   HLS-only items are filtered out.
3. **innertube** — YouTube directly, keyless. Fast when it works; returns a bot
   check from flagged IPs, which is detected and skipped rather than retried.
4. **custom** — your own endpoints, off unless `FASTDL_CUSTOM_API` is set.
5. **ytdlp** — last resort, with `cookiefile` pinned to `None`.

A source that fails repeatedly is benched for a cooldown, then gets one
probationary request. One success clears its record, so an outage anywhere
degrades throughput instead of causing failures.

### Note on hardcoded InnerTube API keys

Every tutorial hardcodes an `AIzaSy...` key. Those are now **rejected** with
`400 Precondition check failed`. Keyless requests succeed. Do not "fix" this file
by adding a key back.

### Note on Piped and Invidious

Both were evaluated and every public instance tested was dead (403/401/502/DNS
failures). They are intentionally not used. Bots that depend on them break.

## Accuracy

Serving audio from a catalogue rather than the exact YouTube video means
correctness stops being free — the first search hit is frequently a karaoke
version, a cover, or a sped-up edit. Every candidate is therefore scored, and
anything below `FASTDL_MIN_MATCH_SCORE` (default 62) is **rejected** so the next
source is tried instead of playing the wrong thing.

Signals: how much of the request the candidate explains (title *and* artist), how
much of the candidate's title the request accounts for, string similarity,
duration agreement, and explicit penalties for karaoke / cover / remix / slowed /
sped-up / nightcore / instrumental / looped / extended uploads. Those penalties
are skipped when the user actually asks for that flavour, so `kesariya lofi` still
returns the lofi version.

Duration is a strong bonus but only a mild penalty in the middle band, because a
music video is often a different length from the release it corresponds to (the
"Kesariya" video runs 2:53, the track is 4:28). Only ratios indicating a genuinely
different item — a clipped preview or a 12-minute loop — are punished hard.

Regression tests: `python3 tools/match_test.py`

## Configuration

All optional; defaults work with nothing set.

| variable | default | meaning |
|---|---|---|
| `FASTDL_PROVIDERS` | `saavn,soundcloud,innertube,custom,ytdlp` | source order |
| `FASTDL_DIRECT_STREAM` | `true` | stream the URL instead of downloading first |
| `FASTDL_MIN_MATCH_SCORE` | `62` | confidence floor; raise if a wrong version ever plays |
| `FASTDL_CUSTOM_API` | *(empty)* | your endpoints, supports `{id}` / `{query}` |
| `FASTDL_CACHE_MAX_MB` | `3072` | on-disk cache ceiling (LRU eviction) |
| `FASTDL_CACHE_MAX_FILES` | `400` | file-count ceiling |
| `FASTDL_SAAVN_BITRATES` | `320,160,96` | quality ladder |
| `FASTDL_ALLOW_YTDLP` | `true` | set false to remove yt-dlp entirely |
| `FASTDL_PARALLEL_PARTS` | `4` | chunks for large ranged downloads |
| `FASTDL_BREAKER_FAILS` | `4` | failures before a source is benched |
| `FASTDL_BREAKER_COOLDOWN` | `120` | bench duration in seconds |

## Operating it

In Telegram (sudo only):

```
/fastdl              provider health, cache stats, settings
/fastdl test         resolve three known tracks, report timings
/fastdl test <song>  resolve one query, report which source served it
/fastdl clear        drop caches
```

On the server, with no bot credentials required:

```
python3 tools/speed_bench.py                 # PLAY / FILE / CACHED timings
python3 tools/fastdl_test.py --download --concurrent 8
python3 tools/youtube_api_test.py            # adapter interface contract
python3 tools/match_test.py                  # accuracy regressions (offline)
```

## Known limitations

* **Video playback still depends on YouTube.** JioSaavn and SoundCloud are
  audio-only, so if the server IP is flagged, video requests fail with a clear
  message while audio keeps working. Audio is the reliable path.
* **Catalogue coverage is not identical to YouTube.** Obscure uploads, podcasts
  and random non-music videos may not resolve from the catalogue sources and will
  fall through to the YouTube-backed ones.
* A wrong-version match is possible when the request is a bare one-word query
  with no artist and no duration hint. Adding the artist fixes it, and the
  duration hint is supplied automatically whenever the request came from search
  or a link.
