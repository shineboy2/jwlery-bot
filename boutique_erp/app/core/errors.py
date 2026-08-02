import logging
from bale import Bot

logger = logging.getLogger(__name__)

class BotError(Exception):
    def __init__(self, user_message: str, log_message: str = ""):
        super().__init__(log_message or user_message)
        self.user_message = user_message
        self.log_message = log_message

class NotFoundError(BotError):
    pass

class ValidationError(BotError):
    pass

class InsufficientStockError(BotError):
    pass

class PermissionError(BotError):
    pass

class ExternalServiceError(BotError):
    pass

async def global_error_handler(error: Exception, chat_id: int, bot: Bot) -> None:
    if isinstance(error, BotError):
        logger.warning(f"BotError ({type(error).__name__}): {error.log_message or error.user_message}")
        try:
            await bot.send_message(chat_id, f"⚠️ {error.user_message}")
        except Exception as e:
            logger.error(f"Failed to send error message to {chat_id}: {e}")
    else:
        logger.error(f"Unhandled Exception: {error}", exc_info=error)
        try:
            await bot.send_message(chat_id, "❌ خطای غیرمنتظره‌ای رخ داد. لطفا دوباره تلاش کنید.")
        except Exception as e:
            logger.error(f"Failed to send fallback error message to {chat_id}: {e}")
