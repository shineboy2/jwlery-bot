from dataclasses import dataclass
from typing import TYPE_CHECKING
from bale import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import Settings

if TYPE_CHECKING:
    from app.bot.router import CallbackRouter

@dataclass
class ApplicationContext:
    bot: Bot
    session_factory: async_sessionmaker[AsyncSession]
    config: Settings
    scheduler: AsyncIOScheduler
    router: 'CallbackRouter'
