"""
Admin panel handlers: /start, settings, admin management.
"""
import logging

from bale import Bot, Message, CallbackQuery

from app.core.config import settings
from app.core.constants import AdminRole
from app.database.crud import (
    get_admin_by_chat_id, create_admin, get_all_admins, deactivate_admin
)
from app.bot.keyboards.inline import main_menu_keyboard, settings_keyboard, back_to_main_keyboard
from app.bot.loader import bot

logger = logging.getLogger(__name__)

# Simple in-memory state for multi-step flows
_waiting_for = {}  # {chat_id: "awaiting_admin_chat_id" | "awaiting_remove_admin_id"}


async def cmd_start(message: Message):
    """Handle /start command. Auto-register SUPER_ADMIN on first run."""
    chat_id = message.chat.id
    full_name = message.chat.first_name or "ادمین"

    # Auto-register SUPER_ADMIN if this is the super admin and not yet in DB
    if chat_id == settings.super_admin_chat_id:
        admin = await get_admin_by_chat_id(chat_id)
        if not admin:
            await create_admin(
                chat_id=chat_id,
                full_name=full_name,
                role=AdminRole.SUPER_ADMIN.value
            )
            logger.info(f"SUPER_ADMIN {chat_id} auto-registered.")
        admin = await get_admin_by_chat_id(chat_id)
    else:
        admin = await get_admin_by_chat_id(chat_id)

    if not admin or not admin.is_active:
        # Non-admin users silently ignored
        return

    logger.info("Before reply")
    try:
        await message.reply(
            f"👋 سلام {full_name} عزیز!\n\n"
            "🎛 به پنل مدیریت بوتیک خوش آمدید.\n"
            "از منوی زیر انتخاب کنید:",
            components=main_menu_keyboard(admin.role == AdminRole.SUPER_ADMIN.value)
        )
        logger.info("After reply")
    except Exception as e:
        logger.error(f"Error in reply: {e}", exc_info=True)


async def callback_main_menu(callback: CallbackQuery):
    """Show main menu when 'menu:main' is pressed."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    await callback.message.edit(
        "🎛 پنل مدیریت بوتیک\nاز منوی زیر انتخاب کنید:",
        components=main_menu_keyboard(admin.role == AdminRole.SUPER_ADMIN.value)
    )


async def callback_settings(callback: CallbackQuery):
    """Show settings menu."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    is_super = admin.role == AdminRole.SUPER_ADMIN.value
    await callback.message.edit(
        "⚙️ تنظیمات\nمدیریت ادمین‌های ربات:",
        components=settings_keyboard(is_super_admin=is_super)
    )


async def callback_admin_list(callback: CallbackQuery):
    """Show list of all admins."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    admins = await get_all_admins()
    text = "👤 لیست ادمین‌ها:\n\n"
    for a in admins:
        status = "✅" if a.is_active else "❌"
        role_text = "👑 سوپر ادمین" if a.role == AdminRole.SUPER_ADMIN.value else "🔑 ادمین"
        text += f"{status} {role_text}: {a.full_name}\n📌 Chat ID: `{a.chat_id}`\n\n"

    if not admins:
        text = "هیچ ادمینی ثبت نشده است."

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    back_kb = build_kb([[
        InlineKeyboardButton("🔙 بازگشت", callback_data="menu:settings")
    ]])
    await callback.message.edit(text, components=back_kb)


async def callback_admin_add(callback: CallbackQuery):
    """Start add admin flow - only for SUPER_ADMIN."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or admin.role != AdminRole.SUPER_ADMIN.value:
        await callback.message.reply("⛔ فقط سوپر ادمین می‌تواند ادمین اضافه کند.")
        return

    _waiting_for[chat_id] = "awaiting_admin_chat_id"
    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="menu:settings")
    ]])
    await callback.message.edit(
        "➕ افزودن ادمین جدید\n\n"
        "لطفاً Chat ID ادمین جدید را ارسال کنید:\n"
        "(عدد بدون @ مثلاً: 123456789)",
        components=cancel_kb
    )


async def callback_admin_remove(callback: CallbackQuery):
    """Start remove admin flow - only for SUPER_ADMIN."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or admin.role != AdminRole.SUPER_ADMIN.value:
        await callback.message.reply("⛔ فقط سوپر ادمین می‌تواند ادمین حذف کند.")
        return

    _waiting_for[chat_id] = "awaiting_remove_admin_id"
    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="menu:settings")
    ]])
    await callback.message.edit(
        "🗑 حذف ادمین\n\n"
        "Chat ID ادمینی که می‌خواهید حذف کنید را ارسال کنید:",
        components=cancel_kb
    )


async def handle_message(message: Message):
    """Handle text messages for multi-step admin flows."""
    chat_id = message.chat.id

    # Check if we are waiting for input
    state = _waiting_for.get(chat_id)
    if not state:
        return

    if state == "awaiting_admin_chat_id":
        try:
            new_chat_id = int(message.content.strip())
        except ValueError:
            await message.reply("⚠️ Chat ID باید یک عدد باشد. دوباره ارسال کنید:")
            return

        # Check if already admin
        existing = await get_admin_by_chat_id(new_chat_id)
        if existing:
            await message.reply(f"⚠️ این کاربر قبلاً ادمین است ({existing.full_name}).")
            del _waiting_for[chat_id]
            return

        # Cannot add yourself or super admin
        if new_chat_id == settings.super_admin_chat_id:
            await message.reply("⚠️ سوپر ادمین از قبل ثبت است.")
            del _waiting_for[chat_id]
            return

        new_admin = await create_admin(
            chat_id=new_chat_id,
            full_name=f"ادمین {new_chat_id}",
            role=AdminRole.ADMIN.value
        )
        del _waiting_for[chat_id]
        await message.reply(
            f"✅ ادمین جدید با Chat ID `{new_chat_id}` اضافه شد.\n"
            "برای استفاده از ربات باید /start بفرستد.",
            components=back_to_main_keyboard()
        )

    elif state == "awaiting_remove_admin_id":
        try:
            remove_chat_id = int(message.content.strip())
        except ValueError:
            await message.reply("⚠️ Chat ID باید یک عدد باشد. دوباره ارسال کنید:")
            return

        if remove_chat_id == settings.super_admin_chat_id:
            await message.reply("⛔ نمی‌توان سوپر ادمین را حذف کرد.")
            del _waiting_for[chat_id]
            return

        success = await deactivate_admin(remove_chat_id)
        del _waiting_for[chat_id]
        if success:
            await message.reply(
                f"✅ ادمین با Chat ID `{remove_chat_id}` غیرفعال شد.",
                components=back_to_main_keyboard()
            )
        else:
            await message.reply(
                "⚠️ ادمینی با این Chat ID پیدا نشد.",
                components=back_to_main_keyboard()
            )


def get_waiting_state(chat_id: int) -> str | None:
    """Return current waiting state for a chat_id (used by other handlers)."""
    return _waiting_for.get(chat_id)


def clear_waiting_state(chat_id: int):
    """Clear waiting state (used by other handlers)."""
    _waiting_for.pop(chat_id, None)
