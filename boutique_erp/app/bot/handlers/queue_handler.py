"""
Queue management handler — view and manage queued posts per category.
"""
import logging
from bale import CallbackQuery, Message, InlineKeyboardButton

from app.database.crud import (
    get_admin_by_chat_id, get_all_content_categories,
    get_queue_by_category, get_post_by_id,
    move_post_to_top, move_post_order_up,
    move_post_to_buffer, delete_content_post,
    count_queued_by_category, update_post_content,
    SYSTEM_CATEGORIES,
)
from app.bot.keyboards.inline import (
    build_kb, cms_queue_menu_keyboard, cms_queue_list_keyboard,
    cms_queue_post_keyboard,
)
from app.services.cms_service import publish_post_to_channel

logger = logging.getLogger(__name__)

# FSM states for inline editing in queue
_queue_edit_states = {}  # {chat_id: {"post_id": int, "action": "edit_cap"|"edit_img", "cat_code": str}}


async def callback_cms_queue_menu(callback: CallbackQuery):
    """Show queue menu with counts per category."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    custom_cats = await get_all_content_categories()
    counts = {}
    for code in SYSTEM_CATEGORIES:
        counts[code] = await count_queued_by_category(code)
    for cat in custom_cats:
        counts[cat.code] = await count_queued_by_category(cat.code)

    total = sum(counts.values())
    await callback.message.edit(
        f"📋 **مدیریت صف‌های انتشار**\n\nجمع کل: {total} پست در انتظار",
        components=cms_queue_menu_keyboard(counts, custom_cats)
    )


async def callback_cms_queue_category(callback: CallbackQuery, cat_code: str):
    """Show list of queued posts in a category."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    posts = await get_queue_by_category(cat_code)
    cat_info = SYSTEM_CATEGORIES.get(cat_code, {})
    cat_label = cat_info.get("label", cat_code)

    if not posts:
        await callback.message.edit(
            f"📋 صف «{cat_label}» خالی است.\n\nهنوز پستی در این صف نیست.",
            components=build_kb([[
                InlineKeyboardButton("🔙 بازگشت", callback_data="cms:queue")
            ]])
        )
        return

    text = f"📋 **صف «{cat_label}»** — {len(posts)} پست\n\n"
    for i, p in enumerate(posts, start=1):
        icon = "🖼" if p.image_file_id else "📝"
        sku_part = ""
        if p.product_id:
            sku_part = f" | SKU"
        preview = p.content_text[:35].replace("\n", " ")
        text += f"{i}. {icon}{sku_part} {preview}...\n"

    await callback.message.edit(
        text,
        components=cms_queue_list_keyboard(posts, cat_code)
    )


async def callback_cms_queue_post_detail(callback: CallbackQuery, post_id: int):
    """Show detail and actions for a single queued post."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    post = await get_post_by_id(post_id)
    if not post or post.status != "queued":
        await callback.message.edit("❌ این پست در صف یافت نشد.")
        return

    cat_label = SYSTEM_CATEGORIES.get(post.category, {}).get("label", post.category)
    icon = "🖼 با عکس" if post.image_file_id else "📝 بدون عکس"
    text = (
        f"📌 **پست #{post.id}** | دسته: {cat_label}\n"
        f"ترتیب صف: {post.queue_order} | {icon}\n\n"
        f"📝 کپشن:\n{post.content_text}"
    )
    is_first = (post.queue_order == 1)
    await callback.message.edit(
        text,
        components=cms_queue_post_keyboard(post_id, post.category, is_first=is_first)
    )


async def callback_cms_queue_move_top(callback: CallbackQuery, post_id: int):
    await get_admin_by_chat_id(callback.message.chat.id)  # auth check
    await move_post_to_top(post_id)
    post = await get_post_by_id(post_id)
    if post:
        await callback_cms_queue_post_detail(callback, post_id)


async def callback_cms_queue_move_up(callback: CallbackQuery, post_id: int):
    await move_post_order_up(post_id)
    await callback_cms_queue_post_detail(callback, post_id)


async def callback_cms_queue_to_buffer(callback: CallbackQuery, post_id: int):
    post = await get_post_by_id(post_id)
    if not post:
        return
    cat_code = post.category
    await move_post_to_buffer(post_id)
    await callback.message.edit(
        "✅ پست به بافر منتقل شد.",
        components=build_kb([[InlineKeyboardButton("🔙 بازگشت به صف", callback_data=f"cms:queue:cat:{cat_code}")]])
    )


async def callback_cms_queue_delete(callback: CallbackQuery, post_id: int):
    post = await get_post_by_id(post_id)
    if not post:
        return
    cat_code = post.category
    await delete_content_post(post_id)
    await callback.message.edit(
        "🗑 پست حذف شد.",
        components=build_kb([[InlineKeyboardButton("🔙 بازگشت به صف", callback_data=f"cms:queue:cat:{cat_code}")]])
    )


async def callback_cms_queue_publish_now(callback: CallbackQuery, post_id: int):
    """Publish a queued post immediately to channel."""
    from app.bot.loader import bot
    post = await get_post_by_id(post_id)
    if not post:
        return
    cat_code = post.category
    await callback.message.edit("⏳ در حال انتشار در کانال...")
    success = await publish_post_to_channel(bot, post)
    if success:
        await callback.message.edit(
            "✅ پست با موفقیت در کانال منتشر شد!",
            components=build_kb([[InlineKeyboardButton("🔙 بازگشت به صف", callback_data=f"cms:queue:cat:{cat_code}")]])
        )
    else:
        await callback.message.edit(
            "❌ خطا در انتشار. پست همچنان در صف است.",
            components=cms_queue_post_keyboard(post_id, cat_code)
        )


async def callback_cms_queue_edit_cap(callback: CallbackQuery, post_id: int):
    """Start inline caption editing for a queued post."""
    chat_id = callback.message.chat.id
    post = await get_post_by_id(post_id)
    if not post:
        return
    _queue_edit_states[chat_id] = {"post_id": post_id, "action": "edit_cap", "cat_code": post.category}
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cms:queue:post:{post_id}")]])
    await callback.message.reply("✏️ کپشن جدید را بفرستید:", components=cancel_kb)


async def callback_cms_queue_edit_img(callback: CallbackQuery, post_id: int):
    """Start inline image editing for a queued post."""
    chat_id = callback.message.chat.id
    post = await get_post_by_id(post_id)
    if not post:
        return
    _queue_edit_states[chat_id] = {"post_id": post_id, "action": "edit_img", "cat_code": post.category}
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cms:queue:post:{post_id}")]])
    await callback.message.reply("🖼 عکس جدید را بفرستید:", components=cancel_kb)


async def handle_queue_edit_message(message: Message) -> bool:
    """Handle FSM editing for queued posts. Returns True if consumed."""
    chat_id = message.chat.id
    state = _queue_edit_states.get(chat_id)
    if not state:
        return False

    post_id = state["post_id"]
    action = state["action"]
    cat_code = state["cat_code"]

    if action == "edit_cap":
        caption = (message.content or message.caption or "").strip()
        if not caption:
            await message.reply("⚠️ کپشن نمی‌تواند خالی باشد:")
            return True
        post = await update_post_content(post_id, caption=caption)
        _queue_edit_states.pop(chat_id, None)
        cat_label = SYSTEM_CATEGORIES.get(cat_code, {}).get("label", cat_code)
        preview_kb = build_kb([[
            InlineKeyboardButton("📌 نمایش پست", callback_data=f"cms:queue:post:{post_id}")
        ]])
        await message.reply(
            f"✅ کپشن پست #{post_id} بروزرسانی شد.",
            components=preview_kb
        )
        return True

    if action == "edit_img":
        file_id = None
        if getattr(message, 'photo', None):
            file_id = message.photo[-1].file_id if isinstance(message.photo, list) else message.photo.file_id
        if not file_id:
            await message.reply("⚠️ لطفاً یک عکس ارسال کنید:")
            return True
        await update_post_content(post_id, image_file_id=file_id)
        _queue_edit_states.pop(chat_id, None)
        preview_kb = build_kb([[
            InlineKeyboardButton("📌 نمایش پست", callback_data=f"cms:queue:post:{post_id}")
        ]])
        await message.reply(f"✅ عکس پست #{post_id} بروزرسانی شد.", components=preview_kb)
        return True

    return False
