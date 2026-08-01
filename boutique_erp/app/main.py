"""
Entry point for Smart Boutique ERP Bot.
"""
import logging
import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.bot.loader import bot, register_handlers
from app.core.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Start the bot."""
    logger.info("Starting Smart Boutique ERP Bot...")
    
    @bot.event
    async def on_ready():
        logger.info(f"Bot connected as {bot.user.username}")
        start_scheduler()
        logger.info("Scheduler started.")

    register_handlers()
    logger.info("Handlers registered. Bot is now running.")
    bot.run()


if __name__ == "__main__":
    main()
