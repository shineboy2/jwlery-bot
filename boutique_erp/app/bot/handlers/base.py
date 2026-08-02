from abc import ABC, abstractmethod
from typing import Optional
from bale import Message, CallbackQuery
from app.core.context import ApplicationContext
from app.bot.router import CallbackRouter, MessageRouter
from app.bot.conversation import ConversationManager
from app.database.models import Admin
from app.core.constants import AdminRole
from app.database.repositories import admin_repo

class BaseHandler(ABC):
    HANDLER_NAME: str = "base"

    def __init__(self, ctx: ApplicationContext, conversations: ConversationManager) -> None:
        self.ctx = ctx
        self.conversations = conversations
        self.bot = ctx.bot
        self.session_factory = ctx.session_factory

    @abstractmethod
    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        pass

    @abstractmethod
    async def handle_message(self, message: Message) -> bool:
        return False

    async def require_admin(self, chat_id: int) -> Optional[Admin]:
        async with self.session_factory() as session:
            admin = await admin_repo.get_admin_by_chat_id(session, chat_id)
            if admin and admin.is_active:
                return admin
        return None

    async def require_super_admin(self, chat_id: int) -> Optional[Admin]:
        async with self.session_factory() as session:
            admin = await admin_repo.get_admin_by_chat_id(session, chat_id)
            if admin and admin.is_active and admin.role == AdminRole.SUPER_ADMIN.value:
                return admin
        return None
