# RioEra

A Telegram music bot that streams audio into group voice chats.

The point of this fork is the download path. Most bots in this family resolve
audio through YouTube via yt-dlp, which means they stop working the moment the
server IP gets flagged and they stay broken until somebody re-exports a cookies
file by hand. RioEra doesn't use cookies at all — audio comes from several
independent sources tried in order, so no single one going down takes the bot
offline.

## How fast

Measured on a datacenter IP that YouTube refuses to serve audio to at all
(`yt-dlp` fails there on every player client):

| | median |
|---|---|
| Start playing in a voice chat | **0.32s** |
| Full file on disk (`/song`) | **0.33s** |
| Repeat request | **under 1ms** |

Voice-chat playback doesn't download anything — the CDN URL goes straight into
ffmpeg. Cold paths (a track never fetched before) run about **1s**.

Reproduce it yourself, no credentials needed:

```bash
python3 tools/speed_bench.py
```

## How much music

Tested across 43 tracks in 22 categories: **81% resolved** on a fully blocked IP.

Solid: Hindi, Punjabi, Tamil, Telugu, Bengali, Marathi, Western pop and rock,
K-pop, Latin, Arabic, Turkish, French, classical, anime and game soundtracks.

Weak: non-music content. Podcasts, hour-long loops, radio streams and random
uploads mostly don't resolve, because the catalogue sources don't carry them and
YouTube is the only place they exist.

**This is a music catalogue, not a video platform.** If you need to play
arbitrary YouTube videos, you need a clean IP — no code change fixes an
IP-level block. What you get instead is a bot that keeps working without
maintenance.

## Audio sources

Tried in health order. A source that keeps failing is benched for a cooldown,
then gets one probationary request, so an outage degrades throughput instead of
breaking playback.

| source | credentials | notes |
|---|---|---|
| JioSaavn | none | direct 320kbps CDN, ~0.3s, best coverage for Indian music |
| SoundCloud | none | public client_id, auto-refreshed; covers Western gaps |
| InnerTube | none | YouTube directly, keyless; only works on unflagged IPs |
| custom | yours | optional, set `FASTDL_CUSTOM_API` |
| yt-dlp | none, enforced | last resort; `cookiefile` is pinned to `None` |

Because audio may come from a catalogue rather than the exact video you searched
for, every candidate is scored on title, artist and duration, with penalties for
karaoke, covers, remixes, sped-up and looped uploads. Anything below the
confidence threshold is **rejected** and the next source is tried, rather than
playing the wrong recording. Ask for a remix or lofi version explicitly and those
penalties lift.

Full detail: [`docs/FASTDL.md`](docs/FASTDL.md)

## Setup

Requires Python 3.9+, ffmpeg, and a MongoDB URI.

```bash
git clone https://github.com/TrishaAdio/Music.git
cd Music
pip install -U -r requirements.txt
cp sample.env .env      # fill it in
python3 -m RioEra
```

Minimum config — everything else is optional:

| variable | where to get it |
|---|---|
| `API_ID`, `API_HASH` | [my.telegram.org/apps](https://my.telegram.org/apps) |
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) |
| `MONGO_DB_URI` | [cloud.mongodb.com](https://cloud.mongodb.com) |
| `LOGGER_ID` | numeric id of a log group |
| `OWNER_ID` | your Telegram user id |
| `STRING_SESSION` | assistant account session string |

The audio engine needs **no configuration at all**. Tuning knobs are documented
in `sample.env` if you want them.

## Commands

Music: `/play`, `/vplay`, `/pause`, `/resume`, `/skip`, `/stop`, `/seek`,
`/loop`, `/shuffle`, `/queue`, `/speed`
Downloads: `/song <name or link>`
Engine (sudo): `/fastdl`, `/fastdl test <song>`, `/fastdl clear`

`/fastdl` is worth knowing about — it reports which sources are healthy, which
are benched and why, so "it won't play anything" is one command to diagnose
instead of a log dive.

## Testing

All harnesses run without Telegram or MongoDB configured:

```bash
python3 tools/speed_bench.py        # timings
python3 tools/fastdl_test.py --download --concurrent 8
python3 tools/youtube_api_test.py   # adapter contract
python3 tools/match_test.py         # match accuracy, offline
```

## A note on cookies

There is no cookies file and nothing reads one. If you're tempted to add one
back: exported YouTube cookies expire on their own schedule, get the account
flagged, and a `cookies.txt` is a live credential — anything holding `SID`,
`SSID`, `SAPISID` or `LOGIN_INFO` can act as that signed-in account. Committing
one to a repository leaks the account.

The upstream source this was forked from had exactly that, plus a GitHub token
in `config.py`. Both were removed before the first commit here. See
[`cookies/README.md`](cookies/README.md).

## Credits

Forked from the BrandrdXMusic / KANI lineage of Telegram music bots. Built on
[Pyrogram](https://github.com/pyrogram/pyrogram) and
[py-tgcalls](https://github.com/pytgcalls/pytgcalls). Licensed under the terms in
[LICENSE](LICENSE).
