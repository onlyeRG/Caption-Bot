import re
import logging
import asyncio
from html import escape
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.enums import ParseMode
from collections import defaultdict

logger = logging.getLogger(__name__)

# =========================
# COLLECTION STATE
# =========================

collection_state = {
    "active": False,
    "files": [],
    "tag_remove": False
}

# =========================
# REGEX PATTERNS
# =========================

SEASON_EPISODE_PATTERNS = [
    re.compile(r'\[S(\d+)\]\s*\[(?:E|EP|Episode)\s*[-–:]*\s*(\d+)\]', re.I),
    re.compile(r'\[S(\d+)\s*(?:E|EP|Episode)\s*[-–:]*\s*(\d+)\]', re.I),
    re.compile(r'S(\d+)\s*(?:E|EP|Episode)\s*[-–:]*\s*(\d+)', re.I),
    re.compile(r'S(\d+)[-_](?:E|EP|Episode)\s*[-–:]*\s*(\d+)', re.I),
    re.compile(r'Season\s*(\d+)\s*Episode\s*[-–:]*\s*(\d+)', re.I),
]

EPISODE_ONLY_PATTERN = re.compile(
    r'(?:E|EP|Episode)\s*[-–:]*\s*(\d+)',
    re.I
)

QUALITY_PATTERN = re.compile(r'(4k|2160p|1440p|1080p|720p|480p)', re.I)

# =========================
# HELPERS
# =========================

def remove_tags(text: str) -> str:
    if not text:
        return text

    # remove promo lines
    promo_patterns = [
        r'^.*powered\s*by\s*:.*$',
        r'^.*main\s*channel\s*:.*$',
        r'^.*join\s*our\s*channel.*$',
        r'^.*join\s*channel.*$',
        r'^.*official\s*channel.*$'
    ]

    for p in promo_patterns:
        text = re.sub(p, '', text, flags=re.I | re.M)

    # remove arrow lines
    text = re.sub(r'^➳.*$', '', text, flags=re.M)

    # ✅ REMOVE ONLY [@TAGS], NOT [720p]
    text = re.sub(r'\[@[A-Za-z0-9_\.]+\]', '', text)

    return re.sub(r'\s{2,}', ' ', text).strip()

def remove_extension(text: str) -> str:
    if not text:
        return text
    return re.sub(r'\.(mkv|mp4|avi|mov|webm)$', '', text, flags=re.I).strip()

def make_caption_safe(text: str):
    if not text:
        return None
    return f"<b>{escape(text)}</b>"

# =========================
# EXTRACT INFO
# =========================

def extract_info_from_caption(text: str):
    if not text:
        return None

    info = {"episode": None, "quality": None}

    for p in SEASON_EPISODE_PATTERNS:
        m = p.search(text)
        if m:
            info["episode"] = m.group(2).zfill(2)
            break

    if not info["episode"]:
        m = EPISODE_ONLY_PATTERN.search(text)
        if m:
            info["episode"] = m.group(1).zfill(2)

    q = QUALITY_PATTERN.search(text)
    if q:
        info["quality"] = q.group(1).lower()

    return info if info["episode"] else None

# =========================
# COMMANDS
# =========================

async def collect_command(client, message: Message):
    collection_state["active"] = True
    collection_state["files"] = []
    await message.reply_text(
        "🔄 **Collection mode activated**\n\nSend files now.\nUse /upload when done.",
        parse_mode=ParseMode.MARKDOWN
    )

async def clear_command(client, message: Message):
    c = len(collection_state["files"])
    collection_state["active"] = False
    collection_state["files"] = []
    await message.reply_text(
        f"🗑️ **Collection cleared!**\nRemoved {c} files.",
        parse_mode=ParseMode.MARKDOWN
    )

async def status_command(client, message: Message):
    await message.reply_text(
        f"📊 **Files Collected:** {len(collection_state['files'])}",
        parse_mode=ParseMode.MARKDOWN
    )

async def tagremove_command(client, message: Message):
    collection_state["tag_remove"] = not collection_state["tag_remove"]
    await message.reply_text(
        f"🏷️ **Tag Remove:** {'ON ✅' if collection_state['tag_remove'] else 'OFF ❌'}",
        parse_mode=ParseMode.MARKDOWN
    )

# =========================
# FILE COLLECTION
# =========================

async def handle_file_collection(client, message: Message):
    if not collection_state["active"]:
        return

    caption = message.caption or ""

    if collection_state["tag_remove"]:
        caption = remove_tags(caption)

    info = extract_info_from_caption(caption)

    if not info:
        await message.reply_text("⚠️ **Episode detect nahi hua.**", parse_mode=ParseMode.MARKDOWN)
        return

    collection_state["files"].append({
        "chat_id": message.chat.id,
        "message_id": message.id,
        "episode": info["episode"],
        "quality": info["quality"] or "Unknown",
        "file_type": (
            "document" if message.document else
            "video" if message.video else
            "audio" if message.audio else "photo"
        )
    })

    await message.reply_text(
        f"✅ **File added**\nEpisode: E{info['episode']}\nTotal: {len(collection_state['files'])}",
        parse_mode=ParseMode.MARKDOWN
    )

# =========================
# UPLOAD
# =========================

async def upload_command(client, message: Message):
    episodes = defaultdict(list)
    for f in collection_state["files"]:
        episodes[f["episode"]].append(f)

    sticker_id = "CAACAgUAAxkBAAEQA6ppQSnwhAAB6b8IKv2TtiG-jcEgsEQAAv0TAAKjMWBUnDlKQXMRBi82BA"

    for ep in sorted(episodes, key=lambda x: int(x)):
        await client.send_message(
            message.chat.id,
            f"🎬 **Episode {ep}**",
            parse_mode=ParseMode.MARKDOWN
        )

        for f in episodes[ep]:
            try:
                msg = await client.get_messages(f["chat_id"], f["message_id"])
                raw = msg.caption or ""

                if collection_state["tag_remove"]:
                    raw = remove_tags(raw)

                raw = remove_extension(raw)
                raw = make_caption_safe(raw)

                if f["file_type"] == "video":
                    await client.send_video(message.chat.id, msg.video.file_id, caption=raw, parse_mode=ParseMode.HTML)
                elif f["file_type"] == "document":
                    await client.send_document(message.chat.id, msg.document.file_id, caption=raw, parse_mode=ParseMode.HTML)
                elif f["file_type"] == "audio":
                    await client.send_audio(message.chat.id, msg.audio.file_id, caption=raw, parse_mode=ParseMode.HTML)
                elif f["file_type"] == "photo":
                    await client.send_photo(message.chat.id, msg.photo.file_id, caption=raw, parse_mode=ParseMode.HTML)

            except FloodWait as fw:
                await asyncio.sleep(fw.value)

        await client.send_sticker(message.chat.id, sticker_id)

    collection_state["active"] = False
    collection_state["files"] = []
    await message.reply_text("✅ **Upload completed**", parse_mode=ParseMode.MARKDOWN)

# =========================
# REGISTER
# =========================

def register_handlers(app):
    app.on_message(filters.command("collect") & filters.private)(collect_command)
    app.on_message(filters.command("upload") & filters.private)(upload_command)
    app.on_message(filters.command("clear") & filters.private)(clear_command)
    app.on_message(filters.command("status") & filters.private)(status_command)
    app.on_message(filters.command("tagremove") & filters.private)(tagremove_command)
    app.on_message(
        filters.private & (filters.document | filters.video | filters.audio | filters.photo)
    )(handle_file_collection)
