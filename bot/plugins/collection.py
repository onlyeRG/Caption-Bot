import re
import logging
import asyncio
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from collections import defaultdict

logger = logging.getLogger(__name__)

# =========================
# COLLECTION STATE
# =========================

collection_state = {
    "active": False,
    "files": []
}

# =========================
# STRONG DETECTION PATTERNS
# =========================

SEASON_EPISODE_PATTERNS = [
    re.compile(r'\[S(\d+)\]\s*\[(?:E|EP|Episode)\s*(\d+)\]', re.IGNORECASE),
    re.compile(r'\[S(\d+)\s*(?:E|EP|Episode)\s*(\d+)\]', re.IGNORECASE),
    re.compile(r'S(\d+)\s*(?:E|EP|Episode)\s*(\d+)', re.IGNORECASE),
    re.compile(r'S(\d+)[-_](?:E|EP|Episode)\s*(\d+)', re.IGNORECASE),
    re.compile(r'Season\s*(\d+)\s*Episode\s*(\d+)', re.IGNORECASE),
]

EPISODE_ONLY_PATTERN = re.compile(
    r'(?:E|EP|Episode)\s*(\d+)', re.IGNORECASE
)

QUALITY_PATTERN = re.compile(
    r'(4k|2160p|1440p|1080p|720p|480p)', re.IGNORECASE
)

QUALITY_PRIORITY = {
    "480p": 1,
    "720p": 2,
    "1080p": 3,
    "1440p": 4,
    "2160p": 5,
    "4k": 5
}

# =========================
# EXTRACTION LOGIC
# =========================

def extract_info_from_caption(text: str):
    if not text:
        return None

    info = {
        "series": None,
        "season": None,
        "episode": None,
        "quality": None
    }

    for pattern in SEASON_EPISODE_PATTERNS:
        m = pattern.search(text)
        if m:
            info["season"] = m.group(1).zfill(2)
            info["episode"] = m.group(2).zfill(2)
            break

    if not info["episode"]:
        m = EPISODE_ONLY_PATTERN.search(text)
        if m:
            info["episode"] = m.group(1).zfill(2)

    q = QUALITY_PATTERN.search(text)
    if q:
        info["quality"] = q.group(1).lower()

    clean = re.sub(r'\[.*?\]', '', text)
    clean = re.sub(
        r'(Season\s*\d+|S\d+|Episode\s*\d+|E\d+|EP\s*\d+|'
        r'4k|2160p|1440p|1080p|720p|480p|Hindi|English|Dub|Sub)',
        '',
        clean,
        flags=re.IGNORECASE
    )
    clean = re.sub(r'[•|#]', ' ', clean)
    clean = re.sub(r'\s{2,}', ' ', clean).strip()

    if clean:
        info["series"] = clean

    return info if info["episode"] else None

# =========================
# CAPTION FORMAT
# =========================

def format_caption(caption: str) -> str:
    if not caption:
        return caption
    caption = re.sub(r'\.(mp4|mkv)$', '', caption, flags=re.IGNORECASE)
    return f"**{caption}**"

# =========================
# COMMANDS
# =========================

async def collect_command(client, message: Message):
    collection_state["active"] = True
    collection_state["files"] = []
    await message.reply_text(
        "🔄 **Collection Mode Activated**\n\n"
        "Send files now.\n"
        "Use /upload when done.\n"
        "Use /status to check progress.\n"
        "Use /clear to cancel."
    )

async def clear_command(client, message: Message):
    count = len(collection_state["files"])
    collection_state["active"] = False
    collection_state["files"] = []
    await message.reply_text(f"🗑️ Cleared {count} files. Collection stopped.")

async def status_command(client, message: Message):
    text = (
        f"📊 **Collection Status**\n\n"
        f"Mode: {'ACTIVE' if collection_state['active'] else 'INACTIVE'}\n"
        f"Files Collected: {len(collection_state['files'])}\n\n"
    )

    episodes = defaultdict(list)
    for f in collection_state["files"]:
        episodes[f["episode"]].append(f)

    for ep in sorted(episodes, key=lambda x: int(x)):
        qualities = [f["quality"] for f in episodes[ep]]
        text += f"• E{ep}: {', '.join(qualities)}\n"

    await message.reply_text(text)

# =========================
# FILE HANDLER
# =========================

async def handle_file_collection(client, message: Message):
    if not collection_state["active"]:
        return

    info = extract_info_from_caption(message.caption) if message.caption else None

    if not info:
        media = message.document or message.video or message.audio
        if media and media.file_name:
            info = extract_info_from_caption(media.file_name)

    if not info:
        await message.reply_text("⚠️ Episode detect nahi hua. File skip.")
        return

    file_data = {
        "chat_id": message.chat.id,
        "message_id": message.id,
        "series": info["series"] or "Unknown",
        "season": info["season"] or "01",
        "episode": info["episode"],
        "quality": info["quality"] or "Unknown",
        "file_type": (
            "document" if message.document else
            "video" if message.video else
            "audio" if message.audio else
            "photo"
        ),
        "caption": message.caption
    }

    collection_state["files"].append(file_data)

    await message.reply_text(
        f"✅ **Added**\n"
        f"{file_data['series']}\n"
        f"S{file_data['season']}E{file_data['episode']} | {file_data['quality']}"
    )

# =========================
# UPLOAD LOGIC
# =========================

async def upload_command(client, message: Message):
    if not collection_state["files"]:
        await message.reply_text("❌ No files to upload.")
        return

    episodes = defaultdict(list)
    for f in collection_state["files"]:
        episodes[f["episode"]].append(f)

    for ep in episodes:
        episodes[ep].sort(
            key=lambda x: QUALITY_PRIORITY.get(x["quality"], 0)
        )

    status_msg = await message.reply_text("📤 **Upload started...**")
    uploaded = failed = 0

    sticker_id = "CAACAgUAAxkBAAEQA6ppQSnwhAAB6b8IKv2TtiG-jcEgsEQAAv0TAAKjMWBUnDlKQXMRBi82BA"

    for ep in sorted(episodes, key=lambda x: int(x)):
        await message.reply_text(f"🎬 **Episode {ep}**")

        for f in episodes[ep]:
            try:
                msg = await client.get_messages(f["chat_id"], f["message_id"])
                cap = format_caption(f["caption"])

                if f["file_type"] == "document":
                    await client.send_document(message.chat.id, msg.document.file_id, caption=cap)
                elif f["file_type"] == "video":
                    await client.send_video(message.chat.id, msg.video.file_id, caption=cap)
                elif f["file_type"] == "audio":
                    await client.send_audio(message.chat.id, msg.audio.file_id, caption=cap)
                elif f["file_type"] == "photo":
                    await client.send_photo(message.chat.id, msg.photo.file_id, caption=cap)

                uploaded += 1

            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                failed += 1
                logger.error(f"Upload error: {e}")

        await client.send_sticker(message.chat.id, sticker_id)

        await status_msg.edit_text(
            f"📤 **Progress**\n"
            f"Uploaded: {uploaded}\n"
            f"Failed: {failed}"
        )

    collection_state["active"] = False
    collection_state["files"] = []

    await message.reply_text(
        f"✅ **Upload Completed**\n\n"
        f"Uploaded: {uploaded}\n"
        f"Failed: {failed}"
    )

# =========================
# REGISTER
# =========================

def register_handlers(app):
    app.on_message(filters.command("collect") & filters.private)(collect_command)
    app.on_message(filters.command("upload") & filters.private)(upload_command)
    app.on_message(filters.command("clear") & filters.private)(clear_command)
    app.on_message(filters.command("status") & filters.private)(status_command)
    app.on_message(
        filters.private &
        (filters.document | filters.video | filters.audio | filters.photo)
    )(handle_file_collection)
