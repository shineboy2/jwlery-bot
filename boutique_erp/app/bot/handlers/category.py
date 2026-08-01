"""
Category management handlers: list, add, edit, toggle.
"""
import logging

from bale import Message, CallbackQuery

from app.database.crud import (
    get_all_categories, get_category_by_id, create_category,
    update_category, toggle_category, get_category_by_prefix
)
from app.bot.keyboards.inline import (
    categories_menu_keyboard, category_detail_keyboard,
    back_to_main_keyboard, main_menu_keyboard
)
from app.database.crud import get_admin_by_chat_id
from app.core.constants import AdminRole

logger = logging.getLogger(__name__)

# In-memory state for category flows
_cat_states = {}  # {chat_id: {"step": "...", "data": {...}}}


async def callback_categories_menu(callback: CallbackQuery):
    """Show categories list."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    categories = await get_all_categories(active_only=False)
    is_super = admin.role == AdminRole.SUPER_ADMIN.value

    if not categories:
        text = "🗂 دسته‌بندی‌ها\n\nهنوز دسته‌بندی ایجاد نشده است."
    else:
        text = f"🗂 دسته‌بندی‌ها ({len(categories)} مورد):\n\nروی هر دسته‌بندی کلیک کنید:"

    await callback.message.edit(
        text,
        components=categories_menu_keyboard(categories, is_super_admin=is_super)
    )


async def callback_category_view(callback: CallbackQuery, category_id: int):
    """Show category details."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    category = await get_category_by_id(category_id)
    if not category:
        await callback.message.reply("دسته‌بندی یافت نشد.")
        return

    status = "✅ فعال" if category.is_active else "❌ غیرفعال"
    text = (
        f"🗂 دسته‌بندی: {category.name}\n"
        f"🔤 پیشوند SKU: {category.prefix}\n"
        f"📊 وضعیت: {status}"
    )
    await callback.message.edit(
        text,
        components=category_detail_keyboard(category.id, category.is_active)
    )


async def callback_category_add(callback: CallbackQuery):
    """Start add category flow."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _cat_states[chat_id] = {"step": "awaiting_name", "data": {}}

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data="menu:categories")
    ]])
    await callback.message.edit(
        "➕ افزودن دسته‌بندی جدید\n\n"
        "مرحله ۱/۲: نام دسته‌بندی را وارد کنید:\n"
        "مثال: گردنبند، دستبند، انگشتر",
        components=cancel_kb
    )


async def callback_category_toggle(callback: CallbackQuery, category_id: int):
    """Toggle category active status."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    category = await toggle_category(category_id)
    if not category:
        await callback.message.reply("دسته‌بندی یافت نشد.")
        return

    status_text = "✅ فعال شد" if category.is_active else "❌ غیرفعال شد"
    # f"دسته‌بندی {category.name} {status_text}" (silent callback answer)
    await callback_category_view(callback, category_id)


async def callback_category_edit(callback: CallbackQuery, category_id: int):
    """Start edit category flow."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _cat_states[chat_id] = {"step": "edit_name", "data": {"category_id": category_id}}

    from bale import InlineKeyboardButton
    from app.bot.keyboards.inline import build_kb
    cancel_kb = build_kb([[
        InlineKeyboardButton("❌ لغو", callback_data=f"cat:view:{category_id}")
    ]])
    
    category = await get_category_by_id(category_id)
    await callback.message.edit(
        f"✏️ ویرایش دسته‌بندی ({category.name})\n\n"
        "نام جدید دسته‌بندی را وارد کنید:\n"
        "(برای تغییر ندادن نام، علامت - را بفرستید)",
        components=cancel_kb
    )


async def handle_category_message(message: Message) -> bool:
    """
    Handle text messages for category flow.
    Returns True if message was handled (consumed), False if not for this handler.
    """
    chat_id = message.chat.id
    state = _cat_states.get(chat_id)
    if not state:
        return False

    step = state["step"]
    text = message.content.strip() if message.content else ""

    if step == "awaiting_name":
        if len(text) < 2:
            await message.reply("⚠️ نام باید حداقل ۲ کاراکتر باشد.")
            return True

        state["data"]["name"] = text
        state["step"] = "awaiting_prefix"
        _cat_states[chat_id] = state

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[
            InlineKeyboardButton("❌ لغو", callback_data="menu:categories")
        ]])
        await message.reply(
            f"✅ نام: {text}\n\n"
            "مرحله ۲/۲: پیشوند (prefix) برای کد محصول را وارد کنید:\n"
            "مثال: NK (گردنبند)، BR (دستبند)، RN (انگشتر)\n"
            "⚠️ فقط ۲-۴ حرف انگلیسی بزرگ",
            components=cancel_kb
        )
        return True

    elif step == "awaiting_prefix":
        prefix = text.upper().strip()
        if not prefix.isalpha() or not (2 <= len(prefix) <= 4):
            await message.reply("⚠️ پیشوند باید ۲ تا ۴ حرف انگلیسی باشد. مثال: NK")
            return True

        # Check uniqueness
        existing = await get_category_by_prefix(prefix)
        if existing:
            await message.reply(f"⚠️ پیشوند '{prefix}' قبلاً استفاده شده است. پیشوند دیگری وارد کنید:")
            return True

        state["data"]["prefix"] = prefix
        state["step"] = "awaiting_attributes"
        _cat_states[chat_id] = state

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[
            InlineKeyboardButton("❌ لغو", callback_data="menu:categories")
        ]])
        await message.reply(
            f"✅ پیشوند: {prefix}\n\n"
            "مرحله ۳/۳: ویژگی‌های این دسته‌بندی را با کاما (,) جدا کرده و وارد کنید:\n"
            "مثال: وزن، عیار، سایز\n"
            "(اگر ویژگی خاصی ندارد، کلمه 'ندارد' را ارسال کنید)",
            components=cancel_kb
        )
        return True

    elif step == "awaiting_attributes":
        attributes = []
        if text.strip() and text.strip() != "ندارد":
            attributes = [attr.strip() for attr in text.split(",") if attr.strip()]
        
        name = state["data"]["name"]
        prefix = state["data"]["prefix"]
        try:
            category = await create_category(name=name, prefix=prefix, attributes=attributes)
        except Exception as e:
            logger.error(f"Error creating category: {e}")
            await message.reply(f"❌ خطا در ایجاد دسته‌بندی: {str(e)}")
            del _cat_states[chat_id]
            return True

        del _cat_states[chat_id]
        
        attr_str = "، ".join(attributes) if attributes else "ندارد"
        await message.reply(
            f"✅ دسته‌بندی ایجاد شد!\n\n"
            f"📌 نام: {category.name}\n"
            f"🔤 پیشوند: {category.prefix}\n"
            f"🏷 ویژگی‌ها: {attr_str}\n"
            f"کد اولین محصول: {category.prefix}-001",
            components=back_to_main_keyboard()
        )
        return True

    elif step == "edit_name":
        category_id = state["data"]["category_id"]
        category = await get_category_by_id(category_id)

        if text.strip() == "-":
            new_name = category.name
        else:
            if len(text) < 2:
                await message.reply("⚠️ نام باید حداقل ۲ کاراکتر باشد.")
                return True
            new_name = text

        state["data"]["name"] = new_name
        state["step"] = "edit_attributes"
        _cat_states[chat_id] = state

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        cancel_kb = build_kb([[
            InlineKeyboardButton("❌ لغو", callback_data=f"cat:view:{category_id}")
        ]])
        
        old_attrs = "، ".join(category.attributes) if category.attributes else "ندارد"
        await message.reply(
            f"✅ نام: {new_name}\n\n"
            f"ویژگی‌های فعلی: {old_attrs}\n\n"
            "ویژگی‌های جدید را با کاما (,) جدا کرده و وارد کنید:\n"
            "(برای تغییر ندادن، علامت - را بفرستید. برای حذف همه ویژگی‌ها کلمه 'ندارد' را بفرستید)",
            components=cancel_kb
        )
        return True

    elif step == "edit_attributes":
        category_id = state["data"]["category_id"]
        category = await get_category_by_id(category_id)
        
        if text.strip() == "-":
            attributes = category.attributes
        else:
            attributes = []
            if text.strip() and text.strip() != "ندارد":
                attributes = [attr.strip() for attr in text.split(",") if attr.strip()]
            
        name = state["data"]["name"]
        await update_category(category_id, name=name, attributes=attributes)
        del _cat_states[chat_id]

        from bale import InlineKeyboardButton
        from app.bot.keyboards.inline import build_kb
        back_kb = build_kb([[
            InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat:view:{category_id}")
        ]])
        
        attr_str = "، ".join(attributes) if attributes else "ندارد"
        await message.reply(
            f"✅ دسته‌بندی با موفقیت ویرایش شد.\n\n"
            f"نام: {name}\n"
            f"ویژگی‌ها: {attr_str}",
            components=back_kb
        )
        return True

    return False


def get_category_state(chat_id: int) -> dict | None:
    return _cat_states.get(chat_id)


def clear_category_state(chat_id: int):
    _cat_states.pop(chat_id, None)
