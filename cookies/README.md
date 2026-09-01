# This bot does not use YouTube cookies

The audio engine (`RioEra/core/fastdl`) never reads a cookie file. Sources
are tried in order and the default ones need no credentials at all:

| source | auth needed | notes |
|---|---|---|
| `saavn` | none | direct 320kbps CDN, best for Indian music |
| `soundcloud` | none | public client_id, auto-refreshed; covers Western tracks |
| `innertube` | none | YouTube, keyless; only works if the server IP is not flagged |
| `custom` | your own | optional, set `FASTDL_CUSTOM_API` |
| `ytdlp` | none (forced) | last resort; `cookiefile` is pinned to `None` |

## Why cookies were removed

Cookie-based YouTube extraction is not a fix, it is a recurring outage:

* exported cookies are invalidated by YouTube after a while, so playback breaks
  on its own schedule with no code change
* the Google account they belong to gets flagged for automated access
* a `cookies.txt` is a **live credential**. Anything holding `SID`, `SSID`,
  `HSID`, `SAPISID` or `LOGIN_INFO` can act as that signed-in account, so
  committing one to a repository leaks the account

A cookie file previously committed here has been deleted for that reason. **If it
was a real account, treat those cookies as compromised**: sign out of all
sessions at <https://myaccount.google.com/device-activity> and change the
password.

## If you still want to force yt-dlp behaviour

Drop `ytdlp` from the chain entirely:

    FASTDL_PROVIDERS=saavn,soundcloud,innertube,custom

Or check what is actually happening with `/fastdl` and `/fastdl test <song>`
in Telegram.
