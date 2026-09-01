from RioEra import app 
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from pyrogram.types import ChatPermissions

spam_chats = []

EMOJI = [ "🦋🦋🦋🦋🦋",
          "🧚🌸🧋🍬🫖",
          "🥀🌷🌹🌺💐",
          "🌸🌿💮🌱🌵",
          "❤️💚💙💜🖤",
          "💓💕💞💗💖",
          "🌸💐🌺🌹🦋",
          "🍔🦪🍛🍲🥗",
          "🍎🍓🍒🍑🌶️",
          "🧋🥤🧋🥛🍷",
          "🍬🍭🧁🎂🍡",
          "🍨🧉🍺☕🍻",
          "🥪🥧🍦🍥🍚",
          "🫖☕🍹🍷🥛",
          "☕🧃🍩🍦🍙",
          "🍁🌾💮🍂🌿",
          "🌨️🌥️⛈️🌩️🌧️",
          "🌷🏵️🌸🌺💐",
          "💮🌼🌻🍀🍁",
          "🧟🦸🦹🧙👸",
          "🧅🍠🥕🌽🥦",
          "🐷🐹🐭🐨🐻‍❄️",
          "🦋🐇🐀🐈🐈‍⬛",
          "🌼🌳🌲🌴🌵",
          "🥩🍋🍐🍈🍇",
          "🍴🍽️🔪🍶🥃",
          "🕌🏰🏩⛩️🏩",
          "🎉🎊🎈🎂🎀",
          "🪴🌵🌴🌳🌲",
          "🎄🎋🎍🎑🎎",
          "🦅🦜🕊️🦤🦢",
          "🦤🦩🦚🦃🦆",
          "🐬🦭🦈🐋🐳",
          "🐔🐟🐠🐡🦐",
          "🦩🦀🦑🐙🦪",
          "🐦🦂🕷️🕸️🐚",
          "🥪🍰🥧🍨🍨",
          " 🥬🍉🧁🧇",
        ]

TAGMES = [ " **※ ɪ ʟᴏᴠᴇ ʏᴏᴜ...ᰔᩚ**",
           " **※ ғᴏʀɢᴇᴛ ᴍᴇ..ᰔᩚ",
           " **※ ɪ ᴅᴏɴ'ᴛ ʟᴏᴠᴇ ʏᴏᴜ...ᰔᩚ**",
           " **※ ᴍᴀᴋᴇ ɪᴛ ʏᴏᴜʀs ᴘɪʏᴀ, ᴍᴀᴋᴇ ɪᴛ ʏᴏᴜʀs...ᰔᩚ**",
           " **※ ᴊᴏɪɴ ᴍʏ ɢʀᴏᴜᴘ ᴀʟsᴏ...ᰔᩚ**",
           " **※ ɪ ᴋᴇᴘᴛ ʏᴏᴜʀ ɴᴀᴍᴇ ɪɴ ᴍʏ ʜᴇᴀʀᴛ...ᰔᩚ**",
           " **※ ᴡʜᴇʀᴇ ᴀʀᴇ ᴀʟʟ ʏᴏᴜʀ ғʀɪᴇɴᴅs...ᰔᩚ**",
           " **※ ɪɴ ᴡʜᴏsᴇ ᴍᴇᴍᴏʀʏ ᴀʀᴇ ʏᴏᴜ ʟᴏsᴛ ᴍʏ ʟᴏᴠᴇ...ᰔᩚ**",
           " **※ ᴡʜᴀᴛs ʏᴏᴜʀ ᴘʀᴏғᴇssɪᴏɴ...ᰔᩚ**",
           " **※ ᴡʜᴇʀᴇ ᴅɪᴅ ʏᴏᴜ ʟɪᴠᴇ...ᰔᩚ**",
           " **※ ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ, ʙᴀʙʏ...ᰔᩚ**",
           " **※ ɢᴏᴏᴅ ɴɪɢʜᴛ, ɪᴛ's ᴠᴇʀʏ ʟᴀᴛᴇ...ᰔᩚ**",
           " **※ ɪ ғᴇᴇʟ ᴠᴇʀʏ sᴀᴅ ᴛᴏᴅᴀʏ...ᰔᩚ**",
           " **※ ᴛᴀʟᴋ ᴛᴏ ᴍᴇ ᴛᴏᴏ...ᰔᩚ**",
           " **※ ᴡʜᴀᴛ's ғᴏʀ ᴅɪɴɴᴇʀ ᴛᴏᴅᴀʏ...ᰔᩚ**",
           " **※ ᴡʜᴀᴛ's ɢᴏɪɴɢ ᴏɴ...ᰔᩚ**",
           " **※ ᴡʜʏ ᴅᴏɴ'ᴛ ʏᴏᴜ ᴍᴇssᴀɢᴇ...ᰔᩚ**",
           " **※ ɪ ᴀᴍ ɪɴɴᴏᴄᴇɴᴛ...ᰔᩚ**",
           " **※ ɪᴛ ᴡᴀs ғᴜɴ ʏᴇsᴛᴇʀᴅᴀʏ, ᴡᴀsɴ'ᴛ ɪᴛ...ᰔᩚ**",
           " **※ ᴡʜᴇʀᴇ ᴡᴇʀᴇ ʏᴏᴜ ʙᴜsʏ ʏᴇsᴛᴇʀᴅᴀʏ...ᰔᩚ**",
           " **※ ʏᴏᴜ ʀᴇᴍᴀɪɴ sᴏ ᴄᴀʟᴍ ғʀɪᴇɴᴅ...ᰔᩚ**",
           " **※ ᴅᴏ ʏᴏᴜ ᴋɴᴏᴡ ʜᴏᴡ ᴛᴏ sɪɴɢ, sɪɴɢ...ᰔᩚ**",
           " **※ ᴡɪʟʟ ʏᴏᴜ ᴄᴏᴍᴇ ғᴏʀ ᴀ ᴡᴀʟᴋ ᴡɪᴛʜ ᴍᴇ...ᰔᩚ**",
           " **※ ᴀʟᴡᴀʏs ʙᴇ ʜᴀᴘᴘʏ ғʀɪᴇɴᴅ...ᰔᩚ**",
           " **※ ᴄᴀɴ ᴡᴇ ʙᴇ ғʀɪᴇɴᴅs...ᰔᩚ**",
           " **※ ᴀʀᴇ ʏᴏᴜ ᴍᴀʀʀɪᴇᴅ...ᰔᩚ**",
           " **※ ᴡʜᴇʀᴇ ʜᴀᴠᴇ ʏᴏᴜ ʙᴇᴇɴ ʙᴜsʏ ғᴏʀ sᴏ ᴍᴀɴʏ ᴅᴀʏs...ᰔᩚ**",
           " **※ ʟɪɴᴋ ɪs ɪɴ ʙɪᴏ, ᴛᴏ ᴊᴏɪɴ ɴᴏᴡ...ᰔᩚ**",
           " **※ ʜᴀᴅ ғᴜɴ...ᰔᩚ**",
           " **※ ᴅᴏ ʏᴏᴜ ᴋɴᴏᴡ ᴛʜᴇ ᴏᴡɴᴇʀ ᴏғ ᴛʜɪs ɢʀᴏᴜᴘ...ᰔᩚ**",
           " **※ ᴅᴏ ʏᴏᴜ ᴇᴠᴇʀ ʀᴇᴍᴇᴍʙᴇʀ ᴍᴇ...ᰔᩚ**",
           " **※ ʟᴇᴛ's ᴘᴀʀᴛʏ...ᰔᩚ**",
           " **※ ʜᴏᴡ ᴄᴏᴍᴇ ᴛᴏᴅᴀʏ...ᰔᩚ**",
           " **※ ʟɪsᴛᴇɴ ᴍᴇ...ᰔᩚ**",
           " **※ ʜᴏᴡ ᴡᴀs ʏᴏᴜʀ ᴅᴀʏ...ᰔᩚ**",
           " **※ ᴅɪᴅ ʏᴏᴜ sᴇᴇ...ᰔᩚ**",
           " **※ ᴀʀᴇ ʏᴏᴜ ᴛʜᴇ ᴀᴅᴍɪɴ ʜᴇʀᴇ...ᰔᩚ**",
           " **※ ᴀʀᴇ ʏᴏᴜ ɪɴ ʀᴇʟᴀᴛɪᴏɴsʜɪᴘ...ᰔᩚ**",
           " **※ ᴀɴᴅ ʜᴏᴡ ɪs ᴛʜᴇ ᴘʀɪsᴏɴᴇʀ...ᰔᩚ**",
           " **※ sᴀᴡ ʏᴏᴜ ʏᴇsᴛᴇʀᴅᴀʏ...ᰔᩚ**",
           " **※ ᴡʜᴇʀᴇ ᴀʀᴇ ʏᴏᴜ ғʀᴏᴍ...ᰔᩚ**",
           " **※ ᴀʀᴇ ʏᴏᴜ ᴏɴʟɪɴᴇ...ᰔᩚ**",
           " **※ ᴡʜᴀᴛ ᴅᴏ ʏᴏᴜ ʟɪᴋᴇ ᴛᴏ ᴇᴀᴛ...ᰔᩚ**",
           " **※ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ, ɪ ᴡɪʟʟ ᴘʟᴀʏ ᴍᴜsɪᴄ ᴀɴᴅ ᴛᴀɢ ᴇᴠᴇʀʏᴏɴᴇ...ᰔᩚ**",
           " **※ ᴡɪʟʟ ʏᴏᴜ ᴘʟᴀʏ ᴛʀᴜᴛʜ ᴀɴᴅ ᴅᴀʀᴇ...ᰔᩚ**",
           " **※ ᴡʜᴀᴛs ʜᴀᴘᴘᴇɴᴇᴅ ᴛᴏ ʏᴏᴜ...ᰔᩚ**",
           " **※ ᴅᴏ ʏᴏᴜ ᴡᴀɴɴᴀ ᴇᴀᴛ ᴄʜᴏᴄᴏʟᴀᴛᴇ...ᰔᩚ**",
           " **※ ʜᴇʟʟᴏ ʙᴀʙʏ...ᰔᩚ**",
           " **※ ᴅᴏ ᴄʜᴀᴛᴛɪɴɢ ᴡɪᴛʜ ᴍᴇ...ᰔᩚ**",
           " **※ ᴡʜᴀᴛ ᴅᴏ ʏᴏᴜ sᴀʏ...ᰔᩚ**",
           " **※ ɢɪᴠᴇ ᴍᴇ ʏᴏᴜʀ ᴡʜᴀᴛsᴀᴘᴘ ɴᴜᴍʙᴇʀ ᴘʟᴇᴀsᴇ...ᰔᩚ**"
           ]

VC_TAG = [" **⚘ আমাকে ভুলে যাও...💥**",
         " **⚘ আমি তোমাকে ভালোবাসি না...💥**",
         " **⚘ এটাকে তোমার করো পিয়া, তোমার করো...💥**",
         " **⚘ আমার গ্রুপেও যোগ দিন...💥**",
         " **⚘ আমি হৃদয়ে তোমার নাম রেখেছি...💥**",
         " **⚘ তোমার সব বন্ধু কোথায়...💥**",
         " **⚘ কার স্মৃতিতে তুমি হারিয়ে গেছো আমার ভালোবাসা...💥**",
         " **⚘ তোমার পেশা কি...💥**",
         " **⚘ তুমি কোথায় থাকো...💥**",
         " **⚘ শুভ সকাল, বাবু...💥**",
         " **⚘ শুভ রাত্রি, অনেক দেরি হয়ে গেছে...💥**",
         " **⚘ আমার আজ খুব খারাপ লাগছে...💥**",
         " **⚘ আমার সাথেও কথা বল...💥**",
         " **⚘ আজ রাতের খাবারের জন্য কি...💥**",
         " **⚘ কি হচ্ছে...💥**",
         " **⚘ তুমি মেসেজ দাও না কেন...💥**",
         " **⚘ আমি নির্দোষ...💥**",
         " **⚘ এটা গতকাল মজা ছিল, তাই না...💥**",
         " **⚘ তুমি গতকাল কোথায় ব্যস্ত ছিলে...💥**",
         " **⚘ তুমি কি সম্পর্কে আছো...💥**",
         " **⚘ তুমি খুব শান্ত থাকো বন্ধু...💥**",
         " **⚘ তুমি কি গাইতে জানো, গাইতে...💥**",
         " **⚘ তুমি কি আমার সাথে বেড়াতে আসবে...💥**",
         " **⚘ সবসময় হাসিখুশি থেকো বন্ধু...💥**",
         " **⚘ আমরা কি বন্ধু হতে পারি...💥**",
         " **⚘ তুমি কি বিবাহিত...💥**",
         " **⚘ এত দিন কোথায় ব্যস্ত ছিলে...💥**",
         " **⚘ লিঙ্ক বায়োতে আছে, এখন যোগ দিতে...💥**",
         " **⚘ মজা করলাম...💥**",
         " **⚘ আপনি কি এই গ্রুপের মালিককে চেনেন...💥**",
         " **⚘ তোমার কি কখনো মনে পড়ে আমায়...💥**",
         " **⚘ চলো পার্টি করি...💥**",
         " **⚘ আজ কেমন এলো...💥**",
         " **⚘ কেমন কাটলো তোমার দিন...💥**",
         " **⚘ তুমি কি দেখেছো...💥**",
         " **⚘ আপনি কি এখানকার প্রশাসক...💥**",
         " **⚘ আমরা বন্ধু হতে পারি...💥**",
         " **⚘ তুমি কি সম্পর্কে আছো...💥**",
         " **⚘ আর বন্দী কেমন আছে...💥**",
         " **⚘ তোমাকে গতকাল দেখেছি...💥**",
         " **⚘ তুমি কোথা থেকে...💥**",
         " **⚘ আপনি কি অনলাইনে আছেন...💥**",
         " **⚘ তুমি কি আমার বন্ধু....💥**",
         " **⚘ তুমি কি খেতে পছন্দ কর...💥**",
         " **⚘ আমাকে আপনার গ্রুপে অ্যাড করুন, আমি গান বাজিয়ে সবাইকে ট্যাগ করব....💥**",
         " **⚘ আজ আমি দুঃখিত...💥**",
         " **⚘ তুমি কি সত্য খেলবে এবং সাহস করবে...💥**",
         " **⚘ তোমার মত বন্ধু থাকলে চিন্তার কি আছে...💥**",
         " **⚘ কি হয়েছে তোমার...💥**",
         " **⚘ তুমি কি চকলেট খেতে চাও....💥**",
         " **⚘ হ্যালো বাবু...💥**",
         " **⚘ আমার সাথে চ্যাট করো...💥**",
         " **⚘ তুমি কি বলো...💥**"
        ]


@app.on_message(filters.command(["entag", "englishtag" ], prefixes=["/", "@", "#"]))
async def mentionall(client, message):
    chat_id = message.chat.id
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply("๏ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴏɴʟʏ ғᴏʀ ɢʀᴏᴜᴘs.")

    is_admin = False
    try:
        participant = await client.get_chat_member(chat_id, message.from_user.id)
    except UserNotParticipant:
        is_admin = False
    else:
        if participant.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ):
            is_admin = True
    if not is_admin:
        return await message.reply("๏ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪɴ ʙᴀʙʏ, ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴛᴀɢ ᴍᴇᴍʙᴇʀs. ")

    if message.reply_to_message and message.text:
        return await message.reply("/entag ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ᴛʏᴘᴇ ʟɪᴋᴇ ᴛʜɪs / ʀᴇᴘʟʏ ᴀɴʏ ᴍᴇssᴀɢᴇ ɴᴇxᴛ ᴛɪᴍᴇ ʙᴏᴛ ᴛᴀɢɢɪɴɢ...")
    elif message.text:
        mode = "text_on_cmd"
        msg = message.text
    elif message.reply_to_message:
        mode = "text_on_reply"
        msg = message.reply_to_message
        if not msg:
            return await message.reply("/entag ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ᴛʏᴘᴇ ʟɪᴋᴇ ᴛʜɪs / ʀᴇᴘʟʏ ᴀɴʏ ᴍᴇssᴀɢᴇ ɴᴇxᴛ ᴛɪᴍᴇ ғᴏᴛ ᴛᴀɢɢɪɴɢ...")
    else:
        return await message.reply("/entag ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ᴛʏᴘᴇ ʟɪᴋᴇ ᴛʜɪs / ʀᴇᴘʟʏ ᴀɴʏ ᴍᴇssᴀɢᴇ ɴᴇxᴛ ᴛɪᴍᴇ ʙᴏᴛ ᴛᴀɢɢɪɴɢ...")
    if chat_id in spam_chats:
        return await message.reply("๏ ᴘʟᴇᴀsᴇ ᴀᴛ ғɪʀsᴛ sᴛᴏᴘ ʀᴜɴɴɪɴɢ ᴍᴇɴᴛɪᴏɴ ᴘʀᴏᴄᴇss...")
    spam_chats.append(chat_id)
    usrnum = 0
    usrtxt = ""
    async for usr in client.get_chat_members(chat_id):
        if not chat_id in spam_chats:
            break
        if usr.user.is_bot:
            continue
        usrnum += 1
        usrtxt += "<a href='tg://user?id={}'>{}</a>".format(usr.user.id, usr.user.first_name)

        if usrnum == 1:
            if mode == "text_on_cmd":
                txt = f"{usrtxt} {random.choice(TAGMES)}"
                await client.send_message(chat_id, txt)
            elif mode == "text_on_reply":
                await msg.reply(f"[{random.choice(EMOJI)}](tg://user?id={usr.user.id})")
            await asyncio.sleep(4)
            usrnum = 0
            usrtxt = ""
    try:
        spam_chats.remove(chat_id)
    except:
        pass


@app.on_message(filters.command(["bntag"], prefixes=["/", "@", "#"]))
async def mention_allvc(client, message):
    chat_id = message.chat.id
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply("๏ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴏɴʟʏ ғᴏʀ ɢʀᴏᴜᴘs.")

    is_admin = False
    try:
        participant = await client.get_chat_member(chat_id, message.from_user.id)
    except UserNotParticipant:
        is_admin = False
    else:
        if participant.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ):
            is_admin = True
    if not is_admin:
        return await message.reply("๏ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪɴ ʙᴀʙʏ, ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴛᴀɢ ᴍᴇᴍʙᴇʀs. ")
    if chat_id in spam_chats:
        return await message.reply("๏ ᴘʟᴇᴀsᴇ ᴀᴛ ғɪʀsᴛ sᴛᴏᴘ ʀᴜɴɴɪɴɢ ᴍᴇɴᴛɪᴏɴ ᴘʀᴏᴄᴇss...")
    spam_chats.append(chat_id)
    usrnum = 0
    usrtxt = ""
    async for usr in client.get_chat_members(chat_id):
        if not chat_id in spam_chats:
            break
        if usr.user.is_bot:
            continue
        usrnum += 1
        usrtxt += "<a href='tg://user?id={}'>{}</a>".format(usr.user.id, usr.user.first_name)

        if usrnum == 1:
            txt = f"{usrtxt} {random.choice(VC_TAG)}"
            await client.send_message(chat_id, txt)
            await asyncio.sleep(4)
            usrnum = 0
            usrtxt = ""
    try:
        spam_chats.remove(chat_id)
    except:
        pass



@app.on_message(filters.command(["cancel", "enstop", "bnstop"]))
async def cancel_spam(client, message):
    if not message.chat.id in spam_chats:
        return await message.reply("๏ ᴄᴜʀʀᴇɴᴛʟʏ ɪ'ᴍ ɴᴏᴛ ᴛᴀɢɢɪɴɢ ʙᴀʙʏ.")
    is_admin = False
    try:
        participant = await client.get_chat_member(message.chat.id, message.from_user.id)
    except UserNotParticipant:
        is_admin = False
    else:
        if participant.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ):
            is_admin = True
    if not is_admin:
        return await message.reply("๏ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴅᴍɪɴ ʙᴀʙʏ, ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ᴛᴀɢ ᴍᴇᴍʙᴇʀs.")
    else:
        try:
            spam_chats.remove(message.chat.id)
        except:
            pass
        return await message.reply("๏ ᴍᴇɴᴛɪᴏɴ ᴘʀᴏᴄᴇss sᴛᴏᴘᴘᴇᴅ ๏")
          
