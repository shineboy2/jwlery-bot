"""
Entry point for Smart Boutique ERP Bot.
"""
import logging
import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import Settings
from app.bot.application import BotApplication

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Start the bot using BotApplication."""
    logger.info("Starting Smart Boutique ERP Bot...")
    
    config = Settings()
    
    app = BotApplication(config)
    app.initialize()
    app.run()

if __name__ == "__main__":
    main()
