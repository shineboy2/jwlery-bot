import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ConversationState:
    handler_name: str
    step: str
    data: dict
    created_at: datetime

class ConversationManager:
    def __init__(self, timeout_minutes: int = 30):
        self._states: Dict[int, ConversationState] = {}
        self.timeout = timedelta(minutes=timeout_minutes)

    def start(self, chat_id: int, handler_name: str, step: str, data: dict = None) -> None:
        self._states[chat_id] = ConversationState(
            handler_name=handler_name,
            step=step,
            data=data or {},
            created_at=datetime.now()
        )

    def get(self, chat_id: int, handler_name: str) -> Optional[ConversationState]:
        state = self.get_active(chat_id)
        if state and state.handler_name == handler_name:
            return state
        return None

    def get_active(self, chat_id: int) -> Optional[ConversationState]:
        state = self._states.get(chat_id)
        if state:
            if datetime.now() - state.created_at > self.timeout:
                logger.info(f"Conversation {state.handler_name} timed out for chat {chat_id}")
                self.end(chat_id, state.handler_name)
                return None
            return state
        return None

    def advance(self, chat_id: int, handler_name: str, step: str, **extra_data) -> None:
        state = self.get(chat_id, handler_name)
        if state:
            state.step = step
            state.data.update(extra_data)
            state.created_at = datetime.now()  # refresh timeout

    def end(self, chat_id: int, handler_name: str) -> None:
        state = self._states.get(chat_id)
        if state and state.handler_name == handler_name:
            del self._states[chat_id]

    def clear_all(self, chat_id: int) -> None:
        self._states.pop(chat_id, None)

    def is_in_conversation(self, chat_id: int, handler_name: str) -> bool:
        return self.get(chat_id, handler_name) is not None
