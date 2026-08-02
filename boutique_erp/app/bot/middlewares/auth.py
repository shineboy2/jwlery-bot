"""
Authentication decorators for admin-only handlers.
"""
from functools import wraps
from app.database.session import async_session
from app.database.repositories import user_repo
from app.core.constants import AdminRole


def admin_required(func):
    """Decorator: Only allows active admins to use the handler."""
    @wraps(func)
    async def wrapper(update, *args, **kwargs):
        # Support both Message and CallbackQuery
        if hasattr(update, 'from_user'):
            chat_id = update.from_user.chat_id if hasattr(update.from_user, 'chat_id') else update.from_user.id
        elif hasattr(update, 'chat'):
            chat_id = update.chat.id
        else:
            return

        async with async_session() as session:
            admin = await user_repo.get_admin_by_chat_id(session, chat_id)
        if not admin or not admin.is_active:
            return  # Silently ignore non-admins

        return await func(update, *args, admin=admin, **kwargs)
    return wrapper


def super_admin_required(func):
    """Decorator: Only allows SUPER_ADMIN role to use the handler."""
    @wraps(func)
    async def wrapper(update, *args, **kwargs):
        if hasattr(update, 'from_user'):
            chat_id = update.from_user.chat_id if hasattr(update.from_user, 'chat_id') else update.from_user.id
        elif hasattr(update, 'chat'):
            chat_id = update.chat.id
        else:
            return

        async with async_session() as session:
            admin = await user_repo.get_admin_by_chat_id(session, chat_id)
        if not admin or admin.role != AdminRole.SUPER_ADMIN:
            return

        return await func(update, *args, admin=admin, **kwargs)
    return wrapper
