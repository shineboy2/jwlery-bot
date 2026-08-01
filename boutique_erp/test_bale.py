import asyncio
from bale import Bot
from app.core.config import settings

async def main():
    bot = Bot(settings.bale_bot_token)
    try:
        await bot.send_message(chat_id=settings.channel_id, text="test")
        print("Sent to channel_id")
    except Exception as e:
        print(f"Error channel_id: {e}")
        try:
            await bot.send_message(chat_id=settings.channel_username, text="test")
            print("Sent to channel_username")
        except Exception as e2:
            print(f"Error channel_username: {e2}")

asyncio.run(main())
