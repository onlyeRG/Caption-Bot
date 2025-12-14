import re
import logging
import asyncio
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from collections import defaultdict

logger = logging.getLogger(__name__)


# Storage for collection state
collection_state = {
    "active": False,
    "target_channel": None,
    "files": [],  # List of dicts with file metadata
    "custom_thumbnail": None  # Will store the file_id of user's custom thumbnail
}

def extract_info_from_caption(caption: str):
    """
    Extract series name, season, episode, and quality from caption.
    Returns: dict with series, season, episode, quality
    """
    if not caption:
        return None
    
    info = {
        "series": None,
        "season": None,
        "episode": None,
        "quality": None
    }
    
    # Extract season (S01, S02, Season 1, etc.)
    season_match = re.search(r'[Ss](?:eason)?[\s\.]?(\d+)', caption)
    if season_match:
        info["season"] = season_match.group(1).zfill(2)
    
    # Extract episode (E01, E02, Episode 1, etc.)
    episode_match = re.search(r'[Ee](?:pisode)?[\s\.]?(\d+)', caption)
    if episode_match:
        info["episode"] = episode_match.group(1).zfill(2)
    
    # Extract quality (480p, 720p, 1080p, 2160p, etc.)
    quality_match = re.search(r'(\d{3,4})[pP]', caption)
    if quality_match:
        info["quality"] = f"{quality_match.group(1)}p"
    
    # Extract series name (everything before season marker)
    if season_match:
        series_text = caption[:season_match.start()].strip()
        # Clean up series name
        series_text = re.sub(r'[\[\]$$$$]', '', series_text).strip()
        info["series"] = series_text
    else:
        # Try to get first meaningful part
        series_text = re.split(r'[Ss]\d+|[Ee]\d+|\d{3,4}p', caption)[0].strip()
        series_text = re.sub(r'[\[\]$$$$]', '', series_text).strip()
        if series_text:
            info["series"] = series_text
    
    return info if info["episode"] else None

def format_caption(caption: str) -> str:
    """
    Remove .mp4 or .mkv extensions from caption and make it bold
    """
    if not caption:
        return caption
    
    # Remove .mp4 or .mkv from the end of caption (case insensitive)
    caption = re.sub(r'\.(?:mp4|mkv)$', '', caption, flags=re.IGNORECASE)
    
    # Make the caption bold using Markdown
    caption = f"**{caption}**"
    
    return caption

async def set_channel_command(client, message: Message):
    """Set the target channel for uploads"""
    try:
        if len(message.command) < 2:
            await message.reply_text(
                "❌ **Usage:** `/setchannel <channel_id>`\n\n"
                "Example: `/setchannel -1001234567890`\n\n"
                "**How to get channel ID:**\n"
                "1. Forward a message from your channel to @userinfobot\n"
                "2. It will show you the channel ID"
            )
            return
        
        channel_id = message.command[1]
        
        # Try to validate channel access
        try:
            if channel_id.lstrip('-').isdigit():
                channel_id = int(channel_id)
            
            # Test if bot has access
            chat = await client.get_chat(channel_id)
            collection_state["target_channel"] = channel_id
            
            await message.reply_text(
                f"✅ **Target channel set successfully!**\n\n"
                f"**Channel:** {chat.title or chat.first_name}\n"
                f"**ID:** `{channel_id}`\n\n"
                f"Now use `/collect` to start collecting files."
            )
        except Exception as e:
            await message.reply_text(
                f"❌ **Error accessing channel:**\n`{str(e)}`\n\n"
                "Make sure:\n"
                "• The channel ID is correct\n"
                "• Bot is added as admin in the channel\n"
                "• Bot has permission to send messages"
            )
    
    except Exception as e:
        logger.error(f"Error in setchannel command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")


async def collect_command(client, message: Message):
    """Start collection mode"""
    try:
        collection_state["active"] = True
        collection_state["files"] = []
        
        await message.reply_text(
            "🔄 **Collection mode activated!**\n\n"
            "Send me your files one by one. I'll analyze their captions and store them.\n\n"
            "**What I'll extract:**\n"
            "• Series name\n"
            "• Season number\n"
            "• Episode number\n"
            "• Quality\n\n"
            "When done, use `/upload` to organize and send them back to you.\n"
            "Use `/clear` to cancel and clear all files."
        )
    
    except Exception as e:
        logger.error(f"Error in collect command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")


async def handle_file_collection(client, message: Message):
    """Handle files sent during collection mode"""
    try:
        if not collection_state["active"]:
            return  # Not in collection mode, ignore
        
        # Get caption from message
        caption = message.caption
        
        # Extract info from caption (priority) or filename (fallback)
        info = extract_info_from_caption(caption) if caption else None
        
        if not info:
            # Try filename as fallback
            media = message.document or message.video or message.audio
            if media and hasattr(media, 'file_name'):
                info = extract_info_from_caption(media.file_name)
        
        if not info or not info["episode"]:
            await message.reply_text(
                "⚠️ **Could not extract episode information!**\n\n"
                "Make sure your caption or filename contains:\n"
                "• Season number (S01 or Season 1)\n"
                "• Episode number (E01 or Episode 1)\n"
                "• Quality (480p, 720p, 1080p, etc.)\n\n"
                "This file was not added to collection."
            )
            return
        
        # Store file metadata
        file_data = {
            "message_id": message.id,
            "chat_id": message.chat.id,
            "series": info["series"] or "Unknown Series",
            "season": info["season"] or "01",
            "episode": info["episode"],
            "quality": info["quality"] or "Unknown",
            "original_caption": caption,
            "file_type": "document" if message.document else "video" if message.video else "audio" if message.audio else "photo"
        }
        
        collection_state["files"].append(file_data)
        
        await message.reply_text(
            f"✅ **File added to collection!**\n\n"
            f"**Series:** {file_data['series']}\n"
            f"**Season:** S{file_data['season']}\n"
            f"**Episode:** E{file_data['episode']}\n"
            f"**Quality:** {file_data['quality']}\n\n"
            f"**Total files collected:** {len(collection_state['files'])}"
        )
    
    except Exception as e:
        logger.error(f"Error handling file collection: {e}")
        await message.reply_text(f"❌ Error processing file: {str(e)}")


async def upload_command(client, message: Message):
    """Sort and forward all collected files"""
    try:
        if not collection_state["active"]:
            await message.reply_text("❌ Collection mode is not active!")
            return
        
        if not collection_state["files"]:
            await message.reply_text("❌ No files collected yet!")
            return
        
        files = collection_state["files"]
        
        episodes = defaultdict(list)
        for file_data in files:
            episodes[file_data["episode"]].append(file_data)
        
        sorted_episodes = sorted(episodes.keys(), key=lambda x: int(x))
        
        quality_order = {"480p": 1, "720p": 2, "1080p": 3, "2160p": 4, "Unknown": 0}
        for episode in episodes:
            episodes[episode] = sorted(
                episodes[episode],
                key=lambda x: quality_order.get(x["quality"], 0)
            )
        
        status_msg = await message.reply_text(
            f"📤 **Starting to forward {len(files)} files in {len(sorted_episodes)} episodes...**"
        )
        
        forwarded = 0
        failed = 0
        
        sticker_file_id = "CAACAgUAAyEFAASDb2pxAAEBkQNpN7z9HbBGRreIDUJWfjtVBb8b4AACDAADQ3PJEmHxRHgThp-SNgQ"
        
        custom_thumb = collection_state.get("custom_thumbnail")
        
        for episode_num in sorted_episodes:
            episode_files = episodes[episode_num]
            
            try:
                await client.send_message(
                    message.chat.id,
                    f"📺 **Episode: {int(episode_num)}**"
                )
            except Exception as e:
                logger.error(f"Error sending episode announcement for {episode_num}: {e}")
            
            for file_data in episode_files:
                try:
                    await client.forward_messages(
                        chat_id=message.chat.id,
                        from_chat_id=file_data["chat_id"],
                        message_ids=file_data["message_id"]
                    )
                    
                    forwarded += 1
                    
                except FloodWait as e:
                    logger.warning(f"FloodWait: Sleeping for {e.value} seconds")
                    await asyncio.sleep(e.value)
                    
                    try:
                        await client.forward_messages(
                            chat_id=message.chat.id,
                            from_chat_id=file_data["chat_id"],
                            message_ids=file_data["message_id"]
                        )
                        forwarded += 1
                    except Exception as retry_error:
                        logger.error(f"Error forwarding file E{file_data['episode']} {file_data['quality']} after retry: {retry_error}")
                        failed += 1
                        
                except Exception as e:
                    logger.error(f"Error forwarding file E{file_data['episode']} {file_data['quality']}: {e}")
                    failed += 1
            
            try:
                await client.send_sticker(
                    message.chat.id,
                    sticker_file_id
                )
            except Exception as e:
                logger.error(f"Error sending sticker for episode {episode_num}: {e}")
            
            await status_msg.edit_text(
                f"📤 **Forward Progress**\n\n"
                f"Episodes completed: {sorted_episodes.index(episode_num) + 1}/{len(sorted_episodes)}\n"
                f"Files forwarded: {forwarded}/{len(files)}\n"
                f"Failed: {failed}"
            )
        
        collection_state["active"] = False
        collection_state["files"] = []
        
        await message.reply_text(
            f"✅ **Forwarding complete!**\n\n"
            f"**Episodes processed:** {len(sorted_episodes)}\n"
            f"**Files forwarded:** {forwarded}\n"
            f"**Failed:** {failed}\n\n"
            f"Collection mode has been deactivated."
        )
    
    except Exception as e:
        logger.error(f"Error in upload command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")


async def clear_command(client, message: Message):
    """Clear all collected files and deactivate collection mode"""
    try:
        files_count = len(collection_state["files"])
        
        collection_state["active"] = False
        collection_state["files"] = []
        
        await message.reply_text(
            f"🗑️ **Collection cleared!**\n\n"
            f"Removed {files_count} files from collection.\n"
            f"Collection mode has been deactivated."
        )
    
    except Exception as e:
        logger.error(f"Error in clear command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")


async def status_command(client, message: Message):
    """Show current collection status"""
    try:
        status_text = (
            f"📊 **Collection Status**\n\n"
            f"**Mode:** {'🔄 Active' if collection_state['active'] else '⏸️ Inactive'}\n"
            f"**Files Collected:** {len(collection_state['files'])}\n"
            f"**Custom Thumbnail:** {'✅ Set' if collection_state.get('custom_thumbnail') else '❌ Not Set'}\n\n"
        )
        
        if collection_state["files"]:
            episodes = defaultdict(list)
            for f in collection_state["files"]:
                episodes[f["episode"]].append(f)
            
            status_text += "**Collected Episodes:**\n"
            for ep in sorted(episodes.keys()):
                qualities = [f["quality"] for f in episodes[ep]]
                status_text += f"• E{ep}: {', '.join(qualities)}\n"
        
        await message.reply_text(status_text)
    
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await message.reply_text(f"❌ An error occurred: {str(e)}")


async def set_thumbnail_command(client, message: Message):
    """Inform user that thumbnails are preserved via forwarding"""
    await message.reply_text(
        "ℹ️ **Thumbnail information:**\n\n"
        "This bot now forwards files instead of re-uploading them.\n"
        "Forwarding automatically preserves the original thumbnail exactly as it is.\n\n"
        "You don't need to set a custom thumbnail - the original will be kept!"
    )


async def delete_thumbnail_command(client, message: Message):
    """Inform user that thumbnails are preserved via forwarding"""
    await message.reply_text(
        "ℹ️ **Thumbnail information:**\n\n"
        "This bot now forwards files instead of re-uploading them.\n"
        "Forwarding automatically preserves the original thumbnail exactly as it is.\n\n"
        "You don't need to manage thumbnails - originals are always kept!"
    )


async def show_thumbnail_command(client, message: Message):
    """Inform user that thumbnails are preserved via forwarding"""
    await message.reply_text(
        "ℹ️ **Thumbnail information:**\n\n"
        "This bot now forwards files instead of re-uploading them.\n"
        "Forwarding automatically preserves the original thumbnail exactly as it is.\n\n"
        "Your files will keep their original thumbnails when forwarded!"
    )

def register_handlers(app):
    app.on_message(filters.command("collect") & filters.private)(collect_command)
    app.on_message(filters.command("upload") & filters.private)(upload_command)
    app.on_message(filters.command("clear") & filters.private)(clear_command)
    app.on_message(filters.command("status") & filters.private)(status_command)
    app.on_message(filters.command("setthumbnail") & filters.private)(set_thumbnail_command)
    app.on_message(filters.command("deletethumbnail") & filters.private)(delete_thumbnail_command)
    app.on_message(filters.command("showthumbnail") & filters.private)(show_thumbnail_command)
    app.on_message(
        filters.private & 
        (filters.document | filters.video | filters.audio | filters.photo) &
        ~filters.command(["collect", "upload", "clear", "status", "start", "help", "about", "setthumbnail", "deletethumbnail", "showthumbnail"])
    )(handle_file_collection)
