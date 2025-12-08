import asyncio
import logging
from pyrogram import idle
from bot.client import CaptionBot
from bot.plugins import commands, collection, caption

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    app = CaptionBot()
    
    commands.register_handlers(app)
    collection.register_handlers(app)
    caption.register_handlers(app)
    
    await app.start()
    print("Bot started successfully!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
