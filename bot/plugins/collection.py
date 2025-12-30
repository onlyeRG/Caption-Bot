import re
import asyncio
from html import escape
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait

from config import CONFIG

# =========================
# PYROGRAM APP
# =========================

app = Client(
    "filter_bot",
    api_id=CONFIG.API_ID,
    api_hash=CONFIG.API_HASH,
    bot_token=CONFIG.BOT_TOKEN
)

# =========================
# COLLECTION STATE
# =========================

collection_state = {
    "active": False,
    "files": [],
    "tag_remove": False,
    "forward": False
}

# =========================
# REGEX
# =========================

EP_PATTERN = re.compile(r'(?:E|EP|Episode)\s*[-:]?\s*(\d+)', re.I)

# =========================
# HELPERS
# =========================

def remove_tags(text: str) -> str:
    if not text:
        return text

    # ONLY remove telegram tags like @SBANIME or [@SBANIME]
    text = re.sub(r'\[@[A-Za-z0-9_\.]+\]', '', text)
    text = re.sub(r'@[A-Za-z0-9_\.]+', '', text)

    return re.sub(r'\s{2,}', ' ', text).strip()


def remove_extension(text: str) -> str:
    return re.sub(r'\.(mkv|mp4|avi|mov|webm)$', '', text, flags=re.I).strip()


def make_caption(text: str) -> str:
    if not text:
        return ""
    return f"<b>{escape(text)}</b>"


def extract_episode(text: str):
    if not text:
        return None
    m = EP_PATTERN.search(text)
    return m.group(1).zfill(2) if m else None

# =========================
# COMMANDS
# =========================

@app.on_message(filters.command("collect") & filters.private)
async def collect_cmd(_, msg: Message):
    collection_state["active"] = True
    collection_state["files"] = []
    await msg.reply_text("🔄 Collection started.\nSend files now.")

@app.on_message(filters.command("clear") & filters.private)
async def clear_cmd(_, msg: Message):
    count = len(collection_state["files"])
    collection_state["active"] = False
    collection_state["files"] = []
    await msg.reply_text(f"🗑️ Cleared {count} files.")

@app.on_message(filters.command("status") & filters.private)
async def status_cmd(_, msg: Message):
    await msg.reply_text(f"📊 Files collected: {len(collection_state['files'])}")

@app.on_message(filters.command("tagremove") & filters.private)
async def tagremove_cmd(_, msg: Message):
    collection_state["tag_remove"] = not collection_state["tag_remove"]
    await msg.reply_text(
        f"🏷️ Tag Remove: {'ON ✅' if collection_state['tag_remove'] else 'OFF ❌'}"
    )

@app.on_message(filters.command("forward") & filters.private)
async def forward_cmd(_, msg: Message):
    collection_state["forward"] = not collection_state["forward"]
    await msg.reply_text(
        f"🔁 Forward Mode: {'ON ✅' if collection_state['forward'] else 'OFF ❌'}"
    )

# =========================
# FILE COLLECT
# =========================

@app.on_message(
    filters.private &
    (filters.video | filters.document | filters.audio | filters.photo)
)
async def collect_files(_, msg: Message):
    if not collection_state["active"]:
        return

    caption = msg.caption or ""
    episode = extract_episode(caption)

    if not episode:
        await msg.reply_text("⚠️ Episode detect nahi hua.")
        return

    collection_state["files"].append({
        "chat_id": msg.chat.id,
        "message_id": msg.id,
        "episode": episode,
        "type": (
            "video" if msg.video else
            "document" if msg.document else
            "audio" if msg.audio else
            "photo"
        )
    })

    await msg.reply_text(f"✅ Added E{episode} | Total: {len(collection_state['files'])}")

# =========================
# UPLOAD
# =========================

@app.on_message(filters.command("upload") & filters.private)
async def upload_cmd(client, msg: Message):
    episodes = defaultdict(list)

    for f in collection_state["files"]:
        episodes[f["episode"]].append(f)

    sticker_id = "CAACAgUAAxkBAAEQA6ppQSnwhAAB6b8IKv2TtiG-jcEgsEQAAv0TAAKjMWBUnDlKQXMRBi82BA"

    for ep in sorted(episodes, key=int):
        await client.send_message(
            msg.chat.id,
            f"🎬 <b>Episode {ep}</b>",
            parse_mode=ParseMode.HTML
        )

        for f in episodes[ep]:
            try:
                original = await client.get_messages(
                    f["chat_id"],
                    f["message_id"]
                )

                if collection_state["forward"]:
                    await client.forward_messages(
                        chat_id=msg.chat.id,
                        from_chat_id=f["chat_id"],
                        message_ids=f["message_id"]
                    )
                else:
                    caption = original.caption or ""

                    if collection_state["tag_remove"]:
                        caption = remove_tags(caption)

                    caption = remove_extension(caption)
                    caption = make_caption(caption)

                    if f["type"] == "video":
                        await client.send_video(
                            msg.chat.id,
                            original.video.file_id,
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )
                    elif f["type"] == "document":
                        await client.send_document(
                            msg.chat.id,
                            original.document.file_id,
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )
                    elif f["type"] == "audio":
                        await client.send_audio(
                            msg.chat.id,
                            original.audio.file_id,
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )
                    elif f["type"] == "photo":
                        await client.send_photo(
                            msg.chat.id,
                            original.photo.file_id,
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )

            except FloodWait as fw:
                await asyncio.sleep(fw.value)

        await client.send_sticker(msg.chat.id, sticker_id)

    collection_state["active"] = False
    collection_state["files"] = []

    await msg.reply_text("✅ Upload completed.")

# =========================
# START
# =========================

print("🤖 Filter Bot Started")
app.run()
