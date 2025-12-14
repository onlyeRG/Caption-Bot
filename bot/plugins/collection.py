import re
import logging
import asyncio
import os
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
    "thumbnail_path": None  # Store custom thumbnail path
}

THUMB_DIR = "thumbnails"
if not os.path.exists(THUMB_DIR):
    os.makedirs(THUMB_DIR)

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

async def handle_photo_thumbnail(client, message: Message):
    """Handle photo uploads and save as custom thumbnail"""
    try:
        # Don't process if in collection mode and it's a file being collected
        if collection_state["active"]:
            # Check if this photo has caption with episode info
            info = extract_info_from_caption(message.caption) if message.caption else None
            if info and info["episode"]:
                # This is a file to collect, not a thumbnail
                await handle_file_collection(client, message)
                return
        
        # Download and save the photo as thumbnail
        thumb_path = os.path.join(THUMB_DIR, f"custom_thumb_{message.chat.id}.jpg")
        
        # Download the photo in highest quality
        downloaded_path = await message.download(file_name=thumb_path)
        
        collection_state["thumbnail_path"] = downloaded_path
        
        await message.reply_text(
            "✅ **Custom thumbnail saved!**\n\n"
            "This thumbnail will be used for all future uploads.\n\n"
            "Use `/viewthumb` to see it or `/delthumb` to remove it."
        )
    
    except Exception as e:
        logger.error(f"Error saving thumbnail: {e}")
        await message.reply_text(f"❌ Error saving thumbnail: {str(e)}")

async def view_thumb_command(client, message: Message):
    """Show the currently saved thumbnail"""
    try:
        if not collection_state["thumbnail_path"] or not os.path.exists(collection_state["thumbnail_path"]):
            await message.reply_text("❌ No custom thumbnail set. Upload a photo to set one.")
            return
        
        await message.reply_photo(
            collection_state["thumbnail_path"],
            caption="📸 **Current Custom Thumbnail**"
        )
    
    except Exception as e:
        logger.error(f"Error viewing thumbnail: {e}")
        await message.reply_text(f"❌ Error viewing thumbnail: {str(e)}")

async def del_thumb_command(client, message: Message):
    """Remove the saved thumbnail"""
    try:
        if not collection_state["thumbnail_path"]:
            await message.reply_text("❌ No custom thumbnail set.")
            return
        
        # Delete the file if it exists
        if os.path.exists(collection_state["thumbnail_path"]):
            os.remove(collection_state["thumbnail_path"])
        
        collection_state["thumbnail_path"] = None
        
        await message.reply_text(
            "🗑️ **Custom thumbnail removed!**\n\n"
            "Default thumbnails will be used for uploads."
        )
    
    except Exception as e:
        logger.error(f"Error deleting thumbnail: {e}")
        await message.reply_text(f"❌ Error deleting thumbnail: {str(e)}")

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
    """Sort and upload all collected files"""
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
            f"📤 **Starting upload of {len(files)} files in {len(sorted_episodes)} episodes...**"
        )
        
        uploaded = 0
        failed = 0
        
        sticker_file_id = "CAACAgUAAyEFAASDb2pxAAEBkQNpN7z9HbBGRreIDUJWfjtVBb8b4AACDAADQ3PJEmHxRHgThp-SNgQ"
        
        custom_thumb = None
        if collection_state["thumbnail_path"] and os.path.exists(collection_state["thumbnail_path"]):
            custom_thumb = collection_state["thumbnail_path"]
            logger.info(f"Using custom thumbnail: {custom_thumb}")
        
        for episode_num in sorted_episodes:
            episode_files = episodes[episode_num]
            
            try:
                await client.send_message(
                    message.chat.id,
                    f"Episode: {int(episode_num)}"
                )
            except Exception as e:
                logger.error(f"Error sending episode announcement for {episode_num}: {e}")
            
            # Upload all files for this episode
            for file_data in episode_files:
                try:
                    caption_to_use = format_caption(file_data["original_caption"])
                    
                    # Send with custom thumbnail based on file type
                    if custom_thumb:
                        # Get the original message
                        original_msg = await client.get_messages(
                            file_data["chat_id"],
                            file_data["message_id"]
                        )
                        
                        if file_data["file_type"] == "document" and original_msg.document:
                            await client.send_document(
                                message.chat.id,
                                original_msg.document.file_id,
                                caption=caption_to_use,
                                thumb=custom_thumb
                            )
                        elif file_data["file_type"] == "video" and original_msg.video:
                            await client.send_video(
                                message.chat.id,
                                original_msg.video.file_id,
                                caption=caption_to_use,
                                thumb=custom_thumb,
                                supports_streaming=True
                            )
                        elif file_data["file_type"] == "audio" and original_msg.audio:
                            await client.send_audio(
                                message.chat.id,
                                original_msg.audio.file_id,
                                caption=caption_to_use,
                                thumb=custom_thumb
                            )
                        elif file_data["file_type"] == "photo" and original_msg.photo:
                            await client.send_photo(
                                message.chat.id,
                                original_msg.photo.file_id,
                                caption=caption_to_use
                            )
                    else:
                        await client.copy_message(
                            message.chat.id,
                            file_data["chat_id"],
                            file_data["message_id"],
                            caption=caption_to_use
                        )
                    
                    uploaded += 1
                    
                except Exception as e:
                    logger.error(f"Error uploading file E{file_data['episode']} {file_data['quality']}: {e}")
                    failed += 1
            
            try:
                await client.send_sticker(
                    message.chat.id,
                    sticker_file_id
                )
            except Exception as e:
                logger.error(f"Error sending sticker for episode {episode_num}: {e}")
            
            # Update status after each episode
            await status_msg.edit_text(
                f"📤 **Upload Progress**\n\n"
                f"Episodes completed: {sorted_episodes.index(episode_num) + 1}/{len(sorted_episodes)}\n"
                f"Files uploaded: {uploaded}/{len(files)}\n"
                f"Failed: {failed}"
            )
        
        # Clear collection after upload
        collection_state["active"] = False
        collection_state["files"] = []
        
        await message.reply_text(
            f"✅ **Upload complete!**\n\n"
            f"**Episodes processed:** {len(sorted_episodes)}\n"
            f"**Files uploaded:** {uploaded}\n"
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
            f"**Files Collected:** {len(collection_state['files'])}\n\n"
        )
        
        if collection_state["files"]:
            # Group by episode
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


def register_handlers(app):
    app.on_message(filters.command("collect") & filters.private)(collect_command)
    app.on_message(filters.command("upload") & filters.private)(upload_command)
    app.on_message(filters.command("clear") & filters.private)(clear_command)
    app.on_message(filters.command("status") & filters.private)(status_command)
    app.on_message(filters.command("viewthumb") & filters.private)(view_thumb_command)
    app.on_message(filters.command("delthumb") & filters.private)(del_thumb_command)
    app.on_message(filters.private & filters.photo)(handle_photo_thumbnail)
    app.on_message(
        filters.private & 
        (filters.document | filters.video | filters.audio) &
        ~filters.command(["collect", "upload", "clear", "status", "start", "help", "about", "viewthumb", "delthumb"])
    )(handle_file_collection)
