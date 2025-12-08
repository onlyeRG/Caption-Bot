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
    "files": []  # List of dicts with file metadata
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
        if not collection_state["target_channel"]:
            await message.reply_text(
                "❌ **Please set a target channel first!**\n\n"
                "Use: `/setchannel <channel_id>`"
            )
            return
        
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
            "When done, use `/upload` to organize and send them to the channel.\n"
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
        
        if not collection_state["target_channel"]:
            await message.reply_text("❌ No target channel set!")
            return
        
        files = collection_state["files"]
        
        # Sort files: first by episode, then by quality
        quality_order = {"480p": 1, "720p": 2, "1080p": 3, "2160p": 4, "Unknown": 0}
        
        sorted_files = sorted(
            files,
            key=lambda x: (
                int(x["episode"]),
                quality_order.get(x["quality"], 0)
            )
        )
        
        status_msg = await message.reply_text(
            f"📤 **Starting upload of {len(sorted_files)} files...**\n\n"
            "This may take a while. I'll add delays to avoid flood limits."
        )
        
        uploaded = 0
        failed = 0
        
        for idx, file_data in enumerate(sorted_files, 1):
            try:
                if idx > 1:
                    await asyncio.sleep(3)  # 3 second delay between uploads
                
                # Get the original message
                original_msg = await client.get_messages(
                    file_data["chat_id"],
                    file_data["message_id"]
                )
                
                # Format clean caption
                series_name = file_data["series"]
                season = file_data["season"]
                episode = file_data["episode"]
                quality = file_data["quality"]
                
                clean_caption = (
                    f"{series_name} [S{season}]\n"
                    f"[ E{episode} ]\n"
                    f"• Quality: {quality}"
                )
                
                while True:
                    try:
                        # Copy file to target channel with new caption
                        if file_data["file_type"] == "document":
                            await client.send_document(
                                collection_state["target_channel"],
                                original_msg.document.file_id,
                                caption=clean_caption
                            )
                        elif file_data["file_type"] == "video":
                            await client.send_video(
                                collection_state["target_channel"],
                                original_msg.video.file_id,
                                caption=clean_caption
                            )
                        elif file_data["file_type"] == "audio":
                            await client.send_audio(
                                collection_state["target_channel"],
                                original_msg.audio.file_id,
                                caption=clean_caption
                            )
                        elif file_data["file_type"] == "photo":
                            await client.send_photo(
                                collection_state["target_channel"],
                                original_msg.photo.file_id,
                                caption=clean_caption
                            )
                        
                        uploaded += 1
                        
                        # Update status every 5 files
                        if uploaded % 5 == 0:
                            await status_msg.edit_text(
                                f"📤 **Upload Progress**\n\n"
                                f"Uploaded: {uploaded}/{len(sorted_files)}\n"
                                f"Failed: {failed}"
                            )
                        
                        break  # Success, exit retry loop
                        
                    except FloodWait as e:
                        wait_time = e.value
                        logger.warning(f"FloodWait: Waiting {wait_time} seconds")
                        await status_msg.edit_text(
                            f"⏳ **Flood limit reached!**\n\n"
                            f"Waiting {wait_time} seconds before continuing...\n"
                            f"Uploaded: {uploaded}/{len(sorted_files)}"
                        )
                        await asyncio.sleep(wait_time)
                        # Retry after waiting
                
            except Exception as e:
                logger.error(f"Error uploading file E{file_data['episode']} {file_data['quality']}: {e}")
                failed += 1
        
        # Clear collection after upload
        collection_state["active"] = False
        collection_state["files"] = []
        
        await message.reply_text(
            f"✅ **Upload complete!**\n\n"
            f"**Uploaded:** {uploaded} files\n"
            f"**Failed:** {failed} files\n\n"
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
        channel_info = "Not set"
        if collection_state["target_channel"]:
            try:
                chat = await client.get_chat(collection_state["target_channel"])
                channel_info = f"{chat.title or chat.first_name} (`{collection_state['target_channel']}`)"
            except:
                channel_info = f"`{collection_state['target_channel']}`"
        
        status_text = (
            f"📊 **Collection Status**\n\n"
            f"**Mode:** {'🔄 Active' if collection_state['active'] else '⏸️ Inactive'}\n"
            f"**Target Channel:** {channel_info}\n"
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
    app.on_message(filters.command("setchannel") & filters.private)(set_channel_command)
    app.on_message(filters.command("collect") & filters.private)(collect_command)
    app.on_message(filters.command("upload") & filters.private)(upload_command)
    app.on_message(filters.command("clear") & filters.private)(clear_command)
    app.on_message(filters.command("status") & filters.private)(status_command)
    app.on_message(
        filters.private & 
        (filters.document | filters.video | filters.audio | filters.photo) &
        ~filters.command(["collect", "upload", "clear", "setchannel", "status", "start", "help", "about"])
    )(handle_file_collection)
