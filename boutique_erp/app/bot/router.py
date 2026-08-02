import re
import logging
from typing import Callable, Awaitable, Tuple, List, Dict
from bale import CallbackQuery, Message
from app.core.context import ApplicationContext

logger = logging.getLogger(__name__)

class CallbackRouter:
    def __init__(self):
        self._exact_routes: Dict[str, Callable[[CallbackQuery, ApplicationContext], Awaitable[None]]] = {}
        self._pattern_routes: List[Tuple[re.Pattern, Callable[[CallbackQuery, ApplicationContext, re.Match], Awaitable[None]]]] = []

    def register_exact(self, data: str, handler: Callable[[CallbackQuery, ApplicationContext], Awaitable[None]]) -> None:
        self._exact_routes[data] = handler

    def register_pattern(self, pattern: str, handler: Callable[[CallbackQuery, ApplicationContext, re.Match], Awaitable[None]]) -> None:
        self._pattern_routes.append((re.compile(pattern), handler))

    async def dispatch(self, callback: CallbackQuery, ctx: ApplicationContext) -> None:
        data = callback.data
        if data in self._exact_routes:
            await self._exact_routes[data](callback, ctx)
            return

        for regex, handler in self._pattern_routes:
            match = regex.match(data)
            if match:
                await handler(callback, ctx, match)
                return

        logger.warning(f"Unhandled callback data: {data}")
        await callback.message.reply("دستور نامشخص.")

class MessageRouter:
    def __init__(self, conversations, handlers):
        self.conversations = conversations
        self.handlers = handlers
        self._commands: Dict[str, Callable[[Message, ApplicationContext], Awaitable[None]]] = {}

    def register_command(self, command: str, handler: Callable[[Message, ApplicationContext], Awaitable[None]]) -> None:
        self._commands[command] = handler

    async def dispatch(self, message: Message, ctx: ApplicationContext) -> None:
        text = message.content or ""
        if text.startswith("/"):
            command = text.split()[0]
            if command in self._commands:
                await self._commands[command](message, ctx)
                return

        # FSM dispatch
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if state:
            for handler in self.handlers:
                if handler.HANDLER_NAME == state.handler_name:
                    if await handler.handle_message(message):
                        return

        # Fallback to general handlers
        for handler in self.handlers:
            if hasattr(handler, 'handle_message'):
                if await handler.handle_message(message):
                    return
