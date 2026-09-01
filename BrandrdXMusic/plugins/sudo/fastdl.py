"""
/fastdl - inspect and test the audio engine from inside Telegram.

Exists so that "the bot can't play anything" becomes a question you can answer
in one command instead of by reading logs: it shows which sources are healthy,
which are benched and why, and can run a live resolve test on demand.

    /fastdl              provider health, cache stats, current settings
    /fastdl test         resolve three known tracks and report timings
    /fastdl test <song>  resolve a specific query and report which source served it
    /fastdl clear        drop the resolved-url cache and prune the disk cache
"""

import time

from pyrogram import filters
from pyrogram.types import Message

from BrandrdXMusic import app
from BrandrdXMusic.core.fastdl import (
    AllProvidersFailed,
    TrackRequest,
    health_report,
    prune_cache,
    resolve,
    selftest,
    url_cache,
)
from BrandrdXMusic.misc import SUDOERS


@app.on_message(filters.command(["fastdl", "dlstatus"]) & SUDOERS)
async def fastdl_command(client, message: Message):
    args = message.text.split(None, 2)
    action = args[1].lower() if len(args) > 1 else "status"

    if action == "clear":
        url_cache.clear()
        removed, reclaimed = prune_cache()
        return await message.reply_text(
            "**fastdl cache cleared**\n"
            f"resolved-url cache emptied\n"
            f"disk: {removed} file(s) removed, {reclaimed / 1048576:.1f} MiB reclaimed"
        )

    if action == "test":
        query = args[2] if len(args) > 2 else None
        mystic = await message.reply_text("Testing sources, hold on...")

        if query:
            started = time.monotonic()
            try:
                resolved = await resolve(TrackRequest(query=query), use_cache=False)
                elapsed = time.monotonic() - started
                size = f"{resolved.size / 1048576:.1f} MiB" if resolved.size else "unknown"
                return await mystic.edit_text(
                    f"**Resolved in {elapsed:.2f}s**\n\n"
                    f"query: `{query}`\n"
                    f"source: `{resolved.provider}`\n"
                    f"matched: `{resolved.title}`\n"
                    f"artist: `{resolved.artists or 'n/a'}`\n"
                    f"duration: `{resolved.duration or '?'}s`\n"
                    f"quality: `{resolved.bitrate or '?'}kbps`\n"
                    f"confidence: `{resolved.score:.0f}`\n"
                    f"size: `{size}`\n"
                    f"mode: `{'direct stream' if resolved.is_remote else 'local file'}`"
                )
            except AllProvidersFailed as exc:
                elapsed = time.monotonic() - started
                return await mystic.edit_text(
                    f"**Failed after {elapsed:.2f}s**\n\n"
                    f"query: `{query}`\n\n"
                    f"{exc.user_message()}\n\n"
                    f"per-source detail:\n`{exc}`"[:3800]
                )
            except Exception as exc:  # noqa: BLE001
                return await mystic.edit_text(f"Unexpected error: `{exc}`"[:3800])

        rows = await selftest()
        lines = ["**fastdl self test**", ""]
        for label, ok, detail in rows:
            lines.append(f"{'PASS' if ok else 'FAIL'} `{label}` - {detail}")
        passed = sum(1 for _, ok, _ in rows if ok)
        lines.append("")
        lines.append(f"{passed}/{len(rows)} sources answered")
        return await mystic.edit_text("\n".join(lines)[:4000])

    report = await health_report()
    return await message.reply_text(
        f"**fastdl status**\n\n```\n{report}\n```\n"
        "`/fastdl test` to run a live check, `/fastdl test <song>` for one query, "
        "`/fastdl clear` to reset caches."[:4000]
    )
