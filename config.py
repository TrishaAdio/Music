import re
import os
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

# Get this value from my.telegram.org/apps
API_ID = int(getenv("API_ID", None))
API_HASH = getenv("API_HASH", None)

# Get your token from @BotFather on Telegram.
BOT_TOKEN = getenv("BOT_TOKEN", None)

# Get your mongo url from cloud.mongodb.com
MONGO_DB_URI = getenv("MONGO_DB_URI", None)
MUSIC_BOT_NAME = getenv("MUSIC_BOT_NAME", None)
PRIVATE_BOT_MODE = getenv("PRIVATE_BOT_MODE", None)

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 900))

# Chat id of a group for logging bot's activities
LOGGER_ID = int(getenv("LOGGER_ID", None))

# Get this value from @BRANDRD_ROBOT on Telegram by /id
OWNER_ID = int(getenv("OWNER_ID", "7250012103"))

## Fill these variables if you're deploying on heroku.
# Your heroku app name
HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
# Get it from http://dashboard.heroku.com/account
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

UPSTREAM_REPO = getenv(
    "UPSTREAM_REPO",
    "https://github.com/surojbera1000/KANI",
)
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = getenv("GIT_TOKEN", None)  # Fill this if your upstream repository is private

SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/Bots_Networks")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/+_moTVrOXK4I5NzVl")

# Set this to True if you want the assistant to automatically leave chats after an interval
AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", False))

# Auto Gcast/Broadcast Handler (True = broadcast on , False = broadcast off During Hosting, Dont Do anything here.)
AUTO_GCAST = os.getenv("AUTO_GCAST")

# Auto Broadcast Message That You Want Use In Auto Broadcast In All Groups.
AUTO_GCAST_MSG = getenv("AUTO_GCAST_MSG", "")

# Get this credentials from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "bcfe26b0ebc3428882a0b5fb3e872473")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "907c6a054c214005aeae1fd752273cc4")


# Maximum limit for fetching playlist's track from youtube, spotify, apple links.
SERVER_PLAYLIST_LIMIT = int(getenv("SERVER_PLAYLIST_LIMIT", "50"))
PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", "25"))

SONG_DOWNLOAD_DURATION = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "180"))
SONG_DOWNLOAD_DURATION_LIMIT = int(getenv("SONG_DOWNLOAD_DURATION_LIMIT", "2000"))

# Telegram audio and video file size limit (in bytes)
TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 1073741824))
# Checkout https://www.gbmb.org/mb-to-bytes for converting mb to bytes


# Get your pyrogram v2 session from @BRANDEDSTRINGSESSION_BOT on Telegram
STRING1 = getenv("STRING_SESSION",  None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)


BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}


START_IMG_URL = getenv(
    "START_IMG_URL", "https://te.legra.ph/file/62c76ac2095332a0ede75.jpg"
)
PING_IMG_URL = getenv(
    "PING_IMG_URL", "https://files.catbox.moe/uk3el3.jpg"
)
PLAYLIST_IMG_URL = "https://te.legra.ph/file/14eb59ea7d31229d8d751.jpg"
STATS_IMG_URL = "https://files.catbox.moe/4a47mn.jpg"
TELEGRAM_AUDIO_URL = "https://te.legra.ph/file/923c1faac33d8c70335dc.jpg"
TELEGRAM_VIDEO_URL = "https://te.legra.ph/file/6c66f8b192532fe758e82.jpg"
STREAM_IMG_URL = "https://te.legra.ph/file/ebc4dc6357be06e08a3ed.jpg"
SOUNCLOUD_IMG_URL = "https://te.legra.ph/file/d339f390ec168c19879c6.jpg"
YOUTUBE_IMG_URL = "https://te.legra.ph/file/ee0cd53ab73f08f4a3627.jpg"
SPOTIFY_ARTIST_IMG_URL = "https://te.legra.ph/file/5f9fb5bba66021c782d96.jpg"
SPOTIFY_ALBUM_IMG_URL = "https://te.legra.ph/file/affe0afec5c7ad63676a4.jpg"
SPOTIFY_PLAYLIST_IMG_URL = "https://te.legra.ph/file/3c446e8dee78ed0ca62ff.jpg"


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60**i for i, x in enumerate(reversed(stringt.split(":"))))


DURATION_LIMIT = int(time_to_seconds(f"{DURATION_LIMIT_MIN}:00"))


if SUPPORT_CHANNEL:
    if not re.match("(?:http|https)://", SUPPORT_CHANNEL):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHANNEL url is wrong. Please ensure that it starts with https://"
        )

if SUPPORT_CHAT:
    if not re.match("(?:http|https)://", SUPPORT_CHAT):
        raise SystemExit(
            "[ERROR] - Your SUPPORT_CHAT url is wrong. Please ensure that it starts with https://"
        )



# ---------------------------------------------------------------------------
# fastdl - audio download engine
# ---------------------------------------------------------------------------
# Every setting below is optional. The defaults need no cookies, no API keys and
# no manual setup, so leaving this whole block untouched is the expected case.
# The engine reads these from the environment directly (see
# RioEra/core/fastdl/config.py); they are mirrored here for discoverability.

# Order in which audio sources are tried. Unknown names are ignored.
#   saavn      - JioSaavn, direct 320kbps CDN, no auth. Best for Indian music.
#   soundcloud - covers Western tracks the JioSaavn catalogue lacks.
#   innertube  - YouTube itself, keyless. Works only if the server IP is clean.
#   custom     - your own resolver endpoints (FASTDL_CUSTOM_API).
#   ytdlp      - last resort; this is the one that asks for cookies when blocked.
FASTDL_PROVIDERS = getenv("FASTDL_PROVIDERS", "saavn,soundcloud,innertube,custom,ytdlp")

# Stream the source URL straight into the voice chat instead of downloading
# first. This is what makes playback start in about a second. Set to "false"
# to force a download before playing.
FASTDL_DIRECT_STREAM = getenv("FASTDL_DIRECT_STREAM", "true")

# Minimum match confidence (0-140) before a track is accepted. Raise it if the
# bot ever plays the wrong version; lower it if searches come back empty.
FASTDL_MIN_MATCH_SCORE = getenv("FASTDL_MIN_MATCH_SCORE", "62")

# Optional: your own resolver endpoints, space or comma separated.
# Supports {id} and {query} placeholders, e.g.
#   FASTDL_CUSTOM_API="https://my-api.example/dl?id={id}"
FASTDL_CUSTOM_API = getenv("FASTDL_CUSTOM_API", "")

# On-disk cache ceiling. The engine evicts least-recently-used files past this.
FASTDL_CACHE_MAX_MB = getenv("FASTDL_CACHE_MAX_MB", "3072")
