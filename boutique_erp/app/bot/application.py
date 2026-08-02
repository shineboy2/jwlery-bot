import logging
from bale import Bot
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import Settings
from app.core.context import ApplicationContext
from app.bot.router import CallbackRouter, MessageRouter
from app.bot.conversation import ConversationManager

logger = logging.getLogger(__name__)

class BotApplication:
    def __init__(self, config: Settings) -> None:
        self.config = config
        self.bot = Bot(token=config.bale_bot_token)
        self.engine = create_async_engine(config.database_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.scheduler = AsyncIOScheduler()
        self.callback_router = CallbackRouter()
        self.conversations = ConversationManager()
        self.handlers = []
        self.message_router = MessageRouter(self.conversations, self.handlers)
        self.ctx = ApplicationContext(
            bot=self.bot,
            session_factory=self.session_factory,
            config=self.config,
            scheduler=self.scheduler,
            router=self.callback_router
        )

    def initialize(self) -> None:
        self._discover_handlers()
        self._bind_events()

    def _discover_handlers(self) -> None:
        from app.bot.handlers.admin.handler import AdminHandler
        from app.bot.handlers.category.handler import CategoryHandler
        from app.bot.handlers.product.handler import ProductHandler
        from app.bot.handlers.product.channel_handler import ProductChannelHandler
        from app.bot.handlers.order.handler import OrderHandler
        from app.bot.handlers.customer.handler import CustomerHandler
        from app.bot.handlers.report.handler import ReportHandler
        from app.bot.handlers.cms.handler import CmsHandler
        from app.bot.handlers.cms_queue.handler import CmsQueueHandler
        from app.bot.handlers.cms_category.handler import CmsCategoryHandler
        from app.bot.handlers.finance.handler import FinanceHandler

        handler_classes = [
            AdminHandler, CategoryHandler, ProductHandler, ProductChannelHandler, OrderHandler,
            CustomerHandler, ReportHandler, CmsHandler, CmsQueueHandler,
            CmsCategoryHandler, FinanceHandler
        ]

        for cls in handler_classes:
            handler_instance = cls(self.ctx, self.conversations)
            handler_instance.register(self.callback_router, self.message_router)
            self.handlers.append(handler_instance)
            
        logger.info(f"Discovered and registered {len(self.handlers)} handlers.")

    def _bind_events(self) -> None:
        from app.core.errors import global_error_handler

        @self.bot.event
        async def on_message(message):
            if not message:
                return
            try:
                await self.message_router.dispatch(message, self.ctx)
            except Exception as e:
                await global_error_handler(e, message.chat.id, self.bot)

        @self.bot.event
        async def on_callback(callback):
            try:
                await self.callback_router.dispatch(callback, self.ctx)
            except Exception as e:
                await global_error_handler(e, callback.message.chat.id, self.bot)

        @self.bot.event
        async def on_ready():
            logger.info(f"Bot connected as {self.bot.user.username}")
            from app.core.scheduler import register_jobs
            register_jobs(self.ctx)
            self.scheduler.start()
            logger.info("Scheduler started.")

    async def shutdown(self) -> None:
        logger.info("Shutting down Application...")
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
        await self.engine.dispose()
        logger.info("Application shutdown complete.")

    def run(self) -> None:
        logger.info("Starting Bot Application...")
        try:
            self.bot.run()
        finally:
            import asyncio
            # In case the event loop is already closed or we need a new one to clean up
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.shutdown())
            loop.close()
