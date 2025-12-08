import logging
from pyrogram import filters
from bot.config import Config

logger = logging.getLogger(__name__)

async def auto_caption(client, message):
    try:
        media = message.document or message.video or message.audio or message.photo
        
        if message.caption:
            file_caption = message.caption
        else:
            fname = getattr(media, 'file_name', 'Media')
            filename = fname.replace("_", ".")
            file_caption = f"`{filename}`"
        
        caption_text = Config.CAPTION_TEXT
        position = Config.CAPTION_POSITION
        
        if position == "top":
            final_caption = f"{caption_text}\n{file_caption}" if caption_text else file_caption
        elif position == "bottom":
            final_caption = f"{file_caption}\n{caption_text}" if caption_text else file_caption
        else:
            final_caption = caption_text or file_caption
        
        await message.edit_caption(
            caption=final_caption,
            parse_mode="markdown"
        )
        
    except Exception as e:
        logger.error(f"Error editing caption: {e}")

def register_handlers(app):
    app.on_message(
        filters.channel & 
        (filters.document | filters.video | filters.audio | filters.photo)
    )(auto_caption)
