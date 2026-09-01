from pyrogram import Client, filters, enums
from pyrogram.types import ChatPrivileges, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ChatAdminRequired
from functools import wraps
from BrandrdXMusic import app
import asyncio

def mention(user_id, name):
    return f"[{name}](tg://user?id={user_id})"

def admin_required(*privileges):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message):
            if not message.from_user:
                await message.reply_text("ʏᴏᴜ ᴀʀᴇ ᴀɴ ᴀɴᴏɴʏᴍᴏᴜs ᴀᴅᴍɪɴ. ᴜɴʜɪᴅᴇ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")
                return

            member = await message.chat.get_member(message.from_user.id)
            if member.status == enums.ChatMemberStatus.OWNER:
                return await func(client, message)
            elif member.status == enums.ChatMemberStatus.ADMINISTRATOR:
                if not member.privileges:
                    await message.reply_text("ᴄᴀɴɴᴏᴛ ʀᴇᴛʀɪᴇᴠᴇ ʏᴏᴜʀ ᴀᴅᴍɪɴ ᴘʀɪᴠɪʟᴇɢᴇs.")
                    return
                missing_privileges = [priv for priv in privileges if not getattr(member.privileges, priv, False)]
                if missing_privileges:
                    await message.reply_text(f"ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴘᴇʀᴍɪssɪᴏɴs: {', '.join(missing_privileges)}")
                    return
                return await func(client, message)
            else:
                await message.reply_text("ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ.")
                return
        return wrapper
    return decorator

async def animate_message(message, text_sequence):
    for text in text_sequence:
        await message.edit(text)
        await asyncio.sleep(0.5)

@app.on_callback_query(filters.regex("^close_promote$"))
async def close_promote_callback(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception as e:
        await callback_query.answer(f"ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴇʟᴇᴛᴇ: {str(e)}", show_alert=True)

@app.on_message(filters.command("promote"))
@admin_required("can_promote_members")
async def promote_command_handler(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴛᴏ ᴘʀᴏᴍᴏᴛᴇ.")
        return

    user = message.reply_to_message.from_user
    chat = message.chat

    try:
        m = await message.reply_text("ᴘʀᴏᴍᴏᴛɪɴɢ.")
        await animate_message(m, ["**ᴘʀᴏᴍᴏᴛɪɴɢ..**", "**ᴘʀᴏᴍᴏᴛɪɴɢ...**", "**ᴘʀᴏᴍᴏᴛɪɴɢ....**", "**ᴘʀᴏᴍᴏᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!**"])

        await client.promote_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            privileges=ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_manage_video_chats=True,
                is_anonymous=False,
            )
        )

        close_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close_promote")]]
        )

        await m.edit(
            f"""**✦ ᴘʀᴏᴍᴏᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ ✦**

**➥ ᴜsᴇʀ:** {mention(user.id, user.first_name)}
**➥ ʀᴀɴᴋ:** ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀ
**➥ ʙʏ:** {mention(message.from_user.id, message.from_user.first_name)}

**» ᴡᴇ ᴀᴘᴘᴏɪɴᴛᴇᴅ ʏᴏᴜ ᴀs ᴀᴅᴍɪɴ! ɴᴏᴡ ᴅᴏ ʏᴏᴜʀ ʙᴇsᴛ!**""",
            reply_markup=close_button
        )

    except Exception as e:
        await message.reply_text(f"ᴇʀʀᴏʀ: {e}")

@app.on_message(filters.command("demote"))
@admin_required("can_promote_members")
async def demote_command_handler(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴛᴏ ᴅᴇᴍᴏᴛᴇ.")
        return

    user = message.reply_to_message.from_user
    chat = message.chat

    try:
        m = await message.reply_text("ᴅᴇᴍᴏᴛɪɴɢ.")
        await animate_message(m, ["**ᴅᴇᴍᴏᴛɪɴɢ..**", "**ᴅᴇᴍᴏᴛɪɴɢ...**", "**ᴅᴇᴍᴏᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!**"])

        await client.promote_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            privileges=ChatPrivileges(
                can_change_info=False,
                can_invite_users=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_pin_messages=False,
                can_promote_members=False,
                can_manage_chat=False,
                can_manage_video_chats=False,
                is_anonymous=False,
            )
        )

        close_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close_promote")]]
        )

        await m.edit(
            f"""**✦ ᴅᴇᴍᴏᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ ✦**

**➥ ᴜsᴇʀ:** {mention(user.id, user.first_name)}
**➥ ʀᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ:** ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀ
**➥ ʙʏ:** {mention(message.from_user.id, message.from_user.first_name)}

**» ʏᴏᴜʀ ᴀᴅᴍɪɴ ᴘᴏᴡᴇʀs ʜᴀᴠᴇ ʙᴇᴇɴ ʀᴇᴠᴏᴋᴇᴅ.**""",
            reply_markup=close_button
        )

    except Exception as e:
        await message.reply_text(f"» ᴇʀʀᴏʀ: {e}")
