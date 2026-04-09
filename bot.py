"""
Main Bot Entry Point
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import Config
from database import db
from handlers import router

# Validate configuration
Config.validate()

# Initialize bot
bot = Bot(
    token=Config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
dp.include_router(router)

async def on_startup():
    """Actions on bot startup"""
    logging.info("Bot starting...")
    logging.info(f"Admins: {Config.ADMIN_IDS}")
    
    # Initialize database tables
    db.init_database()
    logging.info("Database initialized")
    
    # Notify admins
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "🤖 <b>Bot Started Successfully!</b>\n\n"
                "Admin panel: /admin\n"
                "Help: /help"
            )
        except Exception as e:
            logging.error(f"Failed to notify admin {admin_id}: {e}")

async def on_shutdown():
    """Actions on bot shutdown"""
    logging.info("Bot shutting down...")
    
    # Notify admins
    for admin_id in Config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "🤖 <b>Bot Stopped</b>"
            )
        except:
            pass

async def main():
    """Main function"""
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Start polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
    )
    
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped by user")