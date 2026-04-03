from telegramautomation.config import load_config
from telethon import TelegramClient

async def main():
    cfg = load_config()
    client = TelegramClient(
        cfg.telegram_session_name,
        cfg.telegram_api_id,
        cfg.telegram_api_hash,
        system_version="4.1.6",
        device_model="Desktop",
        app_version="1.0"
    )
    print("Telegram Agent Login System")
    print("Connecting...")
    await client.start()
    print("Success! You are logged in.")
    print("Session file generated as:", cfg.telegram_session_name + ".session")
    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
