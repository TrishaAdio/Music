import asyncio
import importlib
from sys import argv
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from RioEra import LOGGER, app, userbot
from RioEra.core.call import RioCall
from RioEra.misc import sudo
from RioEra.plugins import ALL_MODULES
from RioEra.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("RioEra.plugins" + all_module)
    LOGGER("RioEra.plugins").info("Successfully Imported Modules...")
    await userbot.start()
    await RioCall.start()
    try:
        await RioCall.stream_call("https://graph.org/file/e999c40cb700e7c684b75.mp4")
    except NoActiveGroupCall:
        LOGGER("RioEra").error(
            "Please turn on the videochat of your log group\channel.\n\nStopping Bot..."
        )
        exit()
    except:
        pass
    await RioCall.decorators()
    LOGGER("RioEra").info(
        "ᴅʀᴏᴘ ʏᴏᴜʀ ɢɪʀʟꜰʀɪᴇɴᴅ'ꜱ ɴᴜᴍʙᴇʀ ᴀᴛ @BRANDED_PAID_CC ᴊᴏɪɴ @BRANDRD_BOT , @BRANDED_WORLD ꜰᴏʀ ᴀɴʏ ɪꜱꜱᴜᴇꜱ"
    )
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("RioEra").info("Stopping RioEra Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
