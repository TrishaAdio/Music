import os
import re

from pyrogram import filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaVideo,
    Message,
)

from config import (
    BANNED_USERS,
    SONG_DOWNLOAD_DURATION,
    SONG_DOWNLOAD_DURATION_LIMIT,
)
from BrandrdXMusic import YouTube, app
from BrandrdXMusic.core.fastdl import AllProvidersFailed
from BrandrdXMusic.utils.decorators.language import language, languageCB
from BrandrdXMusic.utils.inline.song import song_markup

# Song Module
#
# The old flow was: pick audio/video -> ask yt-dlp to enumerate YouTube's
# formats -> render a keyboard of itags -> download the chosen itag. That middle
# step is gone, because enumerating YouTube formats is a cookie-gated request
# and was the most common failure point in this module. Audio now comes from
# whichever provider answers first, so the only real choice is audio or video
# and the download starts immediately on the first tap.


@app.on_message(filters.command(["song"]))
@language
async def song_commad_private(client, message: Message, _):
    await message.delete()
    url = await YouTube.url(message)

    if url:
        if not await YouTube.exists(url):
            return await message.reply_text(_["song_5"])
        mystic = await message.reply_text(_["play_1"])
        query = url
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["song_2"])
        mystic = await message.reply_text(_["play_1"])
        query = message.text.split(None, 1)[1]

    try:
        (
            title,
            duration_min,
            duration_sec,
            thumbnail,
            vidid,
        ) = await YouTube.details(query)
    except Exception:
        return await mystic.edit_text(_["play_3"])

    if str(duration_min) == "None":
        return await mystic.edit_text(_["song_3"])
    if int(duration_sec) > SONG_DOWNLOAD_DURATION_LIMIT:
        return await mystic.edit_text(
            _["play_4"].format(SONG_DOWNLOAD_DURATION, duration_min)
        )

    buttons = song_markup(_, vidid)
    await mystic.delete()
    await message.reply_photo(
        thumbnail,
        caption=_["song_4"].format(title),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@app.on_callback_query(filters.regex(pattern=r"song_back") & ~BANNED_USERS)
@languageCB
async def songs_back_helper(client, callback_query: CallbackQuery, _):
    callback_request = callback_query.data.strip().split(None, 1)[1]
    _stype, vidid = callback_request.split("|")
    buttons = song_markup(_, vidid)
    await callback_query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# Both the current buttons (song_helper) and any older cached buttons
# (song_download) land here, so stale keyboards keep working.
@app.on_callback_query(
    filters.regex(pattern=r"song_helper|song_download") & ~BANNED_USERS
)
@languageCB
async def song_download_cb(client, callback_query: CallbackQuery, _):
    callback_request = callback_query.data.strip().split(None, 1)[1]
    parts = callback_request.split("|")
    stype = parts[0]
    vidid = parts[-1]  # older callbacks were "stype|format_id|vidid"

    try:
        await callback_query.answer(_["song_8"])
    except Exception:
        pass

    mystic = await callback_query.edit_message_text(_["song_8"])
    yturl = f"https://www.youtube.com/watch?v={vidid}"

    try:
        (
            raw_title,
            _duration_min,
            duration_sec,
            _thumbnail,
            _vidid,
        ) = await YouTube.details(yturl)
    except Exception:
        return await mystic.edit_text(_["song_7"])

    title = re.sub(r"\W+", " ", (raw_title or "Audio")).strip().title()
    performer = await YouTube.title(yturl) or title

    # The message currently shows the thumbnail, so reuse it for the upload.
    try:
        thumb_image_path = await callback_query.message.download()
    except Exception:
        thumb_image_path = None

    file_path = None
    try:
        if stype == "video":
            file_path = await YouTube.download(
                yturl, mystic, songvideo=True, title=title
            )
            media = InputMediaVideo(
                media=file_path,
                duration=int(duration_sec or 0),
                thumb=thumb_image_path,
                caption=title,
                supports_streaming=True,
            )
            action = "upload_video"
        else:
            file_path = await YouTube.download(
                yturl, mystic, songaudio=True, title=title
            )
            media = InputMediaAudio(
                media=file_path,
                caption=title,
                thumb=thumb_image_path,
                title=title,
                performer=performer,
                duration=int(duration_sec or 0),
            )
            action = "upload_audio"
    except AllProvidersFailed as exc:
        return await mystic.edit_text(_["song_9"].format(exc.user_message()))
    except Exception as exc:  # noqa: BLE001
        return await mystic.edit_text(_["song_9"].format(exc))

    if not file_path or not os.path.exists(file_path):
        return await mystic.edit_text(_["song_9"].format("file was not saved"))

    await mystic.edit_text(_["song_11"])
    await app.send_chat_action(
        chat_id=callback_query.message.chat.id, action=action
    )
    try:
        await callback_query.edit_message_media(media=media)
    except Exception:
        return await mystic.edit_text(_["song_10"])
    finally:
        # The engine keeps its own bounded cache, so the upload copy is
        # disposable. Only the thumbnail is ours to clean up unconditionally.
        if thumb_image_path and os.path.exists(thumb_image_path):
            try:
                os.remove(thumb_image_path)
            except OSError:
                pass
