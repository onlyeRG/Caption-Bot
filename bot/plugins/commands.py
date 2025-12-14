from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot.config import Config
from bot.utils.messages import Messages


async def start_command(client, message):
    await message.reply_text(
        Messages.START_TEXT.format(message.from_user.first_name, Config.ADMIN_USERNAME),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Status", callback_data="cstatus")],
            [
                InlineKeyboardButton("🤩 Help", callback_data="help"),
                InlineKeyboardButton("🛡 About", callback_data="about")
            ],
            [InlineKeyboardButton("🔐 Close", callback_data="close")]
        ]),
        parse_mode="markdown",
        disable_web_page_preview=True
    )

async def help_command(client, message):
    await message.reply_text(
        Messages.HELP_TEXT,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏪ Back", callback_data="back"),
                InlineKeyboardButton("🔐 Close", callback_data="close")
            ]
        ]),
        parse_mode="html",
        disable_web_page_preview=True
    )

async def about_command(client, message):
    await message.reply_text(
        Messages.ABOUT_TEXT,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬇️ Back", callback_data="back"),
                InlineKeyboardButton("🔐 Close", callback_data="close")
            ],
            [InlineKeyboardButton("🤩 Help", callback_data="help")]
        ]),
        parse_mode="html",
        disable_web_page_preview=True
    )

async def callback_handler(client, callback_query: CallbackQuery):
    data = callback_query.data
    
    if data == "cstatus":
        await callback_query.message.edit_text(
            "📊 Use /status command to see collection status",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⬇️ Back", callback_data="back"),
                    InlineKeyboardButton("🔐 Close", callback_data="close")
                ]
            ]),
            parse_mode="html"
        )
    
    elif data == "help":
        await callback_query.message.edit_text(
            Messages.HELP_TEXT,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⬇️ Back", callback_data="back"),
                    InlineKeyboardButton("🔐 Close", callback_data="close")
                ]
            ]),
            parse_mode="html"
        )
    
    elif data == "about":
        await callback_query.message.edit_text(
            Messages.ABOUT_TEXT,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⬇️ Back", callback_data="back"),
                    InlineKeyboardButton("🔐 Close", callback_data="close")
                ],
                [InlineKeyboardButton("🤩 Help", callback_data="help")]
            ]),
            parse_mode="html"
        )
    
    elif data == "back":
        await callback_query.message.edit_text(
            Messages.START_TEXT.format(callback_query.from_user.first_name, Config.ADMIN_USERNAME),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Status", callback_data="cstatus")],
                [
                    InlineKeyboardButton("🤩 Help", callback_data="help"),
                    InlineKeyboardButton("🛡 About", callback_data="about")
                ],
                [InlineKeyboardButton("🔐 Close", callback_data="close")]
            ]),
            parse_mode="markdown"
        )
    
    elif data == "close":
        await callback_query.message.delete()
        if callback_query.message.reply_to_message:
            await callback_query.message.reply_to_message.delete()

def register_handlers(app):
    app.on_message(filters.command("start") & filters.private)(start_command)
    app.on_message(filters.command("help") & filters.private)(help_command)
    app.on_message(filters.command("about") & filters.private)(about_command)
    app.on_callback_query()(callback_handler)
