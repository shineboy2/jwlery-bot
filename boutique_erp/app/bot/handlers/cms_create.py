"""
CMS Create Content Handler — FSM for creating new content posts.
States: select_category → (sku_input) → upload_image → write_caption → preview
"""
import logging
from datetime import datetime
from bale import Message, CallbackQuery, InlineKeyboardButton

from app.database.crud import (
    get_admin_by_chat_id, get_all_content_categories,
    get_product_by_sku, create_content_post,
    is_product_category, SYSTEM_CATEGORIES,
)
from app.bot.keyboards.inline import (
    build_kb, cms_menu_keyboard, cms_create_category_keyboard,
    cms_create_skip_image_keyboard, cms_create_preview_keyboard,
    cms_creation_mode_keyboard
)
from app.services.cms_service import publish_post_to_channel

logger = logging.getLogger(__name__)

_cms_create_states = {}  # {chat_id: {"step": "...", "data": {...}}}


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────

async def callback_cms_create_mode(callback: CallbackQuery):
    """Show mode selection for CMS creation."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return
        
    await callback.message.edit(
        "✍️ **تولید محتوای جدید**\n\nنحوه ارسال محتوا را انتخاب کنید:",
        components=cms_creation_mode_keyboard()
    )


async def callback_cms_create_forward(callback: CallbackQuery):
    """Start forward mode creation."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _cms_create_states[chat_id] = {"step": "awaiting_forward", "data": {}}
    from bale import InlineKeyboardButton
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
    await callback.message.edit(
        "📥 **ارسال یکجا**\n\nلطفاً پست مورد نظر خود (عکس با کپشن، یا فقط متن) را به اینجا فوروارد کنید یا بفرستید:",
        components=cancel_kb
    )


async def callback_cms_create(callback: CallbackQuery):
    """Start content creation flow — show category selection."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    _cms_create_states[chat_id] = {"step": "select_category", "data": {}}
    custom_cats = await get_all_content_categories()
    await callback.message.edit(
        "✨ **ساخت مرحله به مرحله**\n\nلطفاً دسته‌بندی محتوا را انتخاب کنید:",
        components=cms_create_category_keyboard(custom_cats)
    )


async def callback_cms_select_category(callback: CallbackQuery, cat_code: str):
    """Handle category selection."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    is_forward = cat_code.endswith(":fwd")
    if is_forward:
        cat_code = cat_code.replace(":fwd", "")
        
    state = _cms_create_states.get(chat_id)
    if not state or state["step"] not in ("select_category", "select_category_forward"):
        return

    state["data"]["category"] = cat_code

    if is_forward:
        # Proceed directly to preview
        state["step"] = "preview"
        await _show_preview(callback.message, state)
        return

    if is_product_category(cat_code):
        # Need SKU first
        state["step"] = "sku_input"
        _cms_create_states[chat_id] = state
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
        await callback.message.edit(
            "🔍 لطفاً کد محصول (SKU) را وارد کنید:\n(مثال: NEC-1045)",
            components=cancel_kb
        )
    else:
        _cms_create_states[chat_id] = state
        await callback.message.edit(
            "🖼 لطفاً عکس پست را ارسال کنید:",
            components=cms_create_skip_image_keyboard()
        )


async def callback_cms_skip_image(callback: CallbackQuery):
    """Admin chose to skip image upload."""
    chat_id = callback.message.chat.id
    state = _cms_create_states.get(chat_id)
    if not state:
        return

    state["data"]["image_file_id"] = None
    state["step"] = "write_caption"
    _cms_create_states[chat_id] = state

    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
    await callback.message.edit(
        "✏️ کپشن پست را بنویسید:",
        components=cancel_kb
    )


# ─────────────────────────────────────────
# Message FSM handler
# ─────────────────────────────────────────

async def handle_cms_create_message(message: Message) -> bool:
    """Handle text and images during CMS creation flow."""
    chat_id = message.chat.id
    state = _cms_create_states.get(chat_id)
    if not state:
        return False

    step = state["step"]
    
    if step == "awaiting_forward":
        # Extract photo and caption/text
        text = message.caption or message.text or ""
        photo_id = None
        if message.photo:
            photo_id = message.photo[-1].file_id
            
        if not text and not photo_id:
            await message.reply("⚠️ محتوای قابل قبولی یافت نشد. لطفاً عکس یا متن ارسال کنید.")
            return True
            
        state["data"]["image_file_id"] = photo_id
        state["data"]["content_text"] = text
        state["step"] = "select_category_forward"
        
        custom_cats = await get_all_content_categories()
        await message.reply(
            "✅ محتوا دریافت شد.\n\nلطفاً دسته‌بندی این پست را انتخاب کنید:",
            components=cms_create_category_keyboard(custom_cats, for_forward=True)
        )
        return True

    if step == "sku_input":
        return await _handle_sku_input(message, state)

    if step == "upload_image":
        return await _handle_image_upload(message, state)

    if step == "write_caption":
        return await _handle_caption_input(message, state)

    if step == "edit_caption":
        return await _handle_edit_caption(message, state)

    if step == "edit_image":
        return await _handle_edit_image(message, state)

    return False


async def _handle_sku_input(message: Message, state: dict) -> bool:
    chat_id = message.chat.id
    sku = (message.content or "").strip().upper()
    if not sku:
        return True

    product = await get_product_by_sku(sku)
    if not product:
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
        await message.reply(
            f"❌ محصولی با کد «{sku}» یافت نشد.\nدوباره وارد کنید:",
            components=cancel_kb
        )
        return True

    state["data"]["product_id"] = product.id
    state["data"]["product_sku"] = product.sku
    state["data"]["product_name"] = product.description[:40]
    state["step"] = "upload_image"
    _cms_create_states[chat_id] = state

    await message.reply(
        f"✅ محصول یافت شد: **{product.description[:40]}** | کد: {product.sku}\n\n"
        "🖼 لطفاً عکس پست را ارسال کنید:",
        components=cms_create_skip_image_keyboard()
    )
    return True


async def _handle_image_upload(message: Message, state: dict) -> bool:
    chat_id = message.chat.id

    # Get file_id from photo
    file_id = None
    if getattr(message, 'photo', None):
        file_id = message.photo[-1].file_id if isinstance(message.photo, list) else message.photo.file_id
    elif getattr(message, 'document', None):
        file_id = message.document.file_id

    if not file_id:
        cancel_kb = build_kb([
            [InlineKeyboardButton("⏭ بدون عکس ادامه بده", callback_data="cms:create:skip_img")],
            [InlineKeyboardButton("❌ لغو", callback_data="menu:cms")],
        ])
        await message.reply("⚠️ لطفاً یک عکس ارسال کنید یا «بدون عکس» را انتخاب کنید:", components=cancel_kb)
        return True

    state["data"]["image_file_id"] = file_id
    state["step"] = "write_caption"
    _cms_create_states[chat_id] = state

    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
    await message.reply("✅ عکس دریافت شد.\n\n✏️ کپشن پست را بنویسید:", components=cancel_kb)
    return True


async def _handle_caption_input(message: Message, state: dict) -> bool:
    chat_id = message.chat.id
    caption = (message.content or message.caption or "").strip()
    if not caption:
        await message.reply("⚠️ کپشن نمی‌تواند خالی باشد. لطفاً متن بنویسید:")
        return True

    state["data"]["caption"] = caption
    state["step"] = "preview"
    _cms_create_states[chat_id] = state

    await _show_preview(message, state)
    return True


async def _handle_edit_caption(message: Message, state: dict) -> bool:
    chat_id = message.chat.id
    caption = (message.content or message.caption or "").strip()
    if not caption:
        await message.reply("⚠️ کپشن نمی‌تواند خالی باشد:")
        return True

    state["data"]["caption"] = caption
    state["step"] = "preview"
    _cms_create_states[chat_id] = state

    await _show_preview(message, state)
    return True


async def _handle_edit_image(message: Message, state: dict) -> bool:
    chat_id = message.chat.id

    file_id = None
    if getattr(message, 'photo', None):
        file_id = message.photo[-1].file_id if isinstance(message.photo, list) else message.photo.file_id

    if not file_id:
        await message.reply("⚠️ لطفاً یک عکس ارسال کنید:")
        return True

    state["data"]["image_file_id"] = file_id
    state["step"] = "preview"
    _cms_create_states[chat_id] = state

    await _show_preview(message, state)
    return True


async def _show_preview(message: Message, state: dict):
    """Send preview of the post (actual photo + caption if available)."""
    data = state["data"]
    caption = data.get("caption", "")
    image_file_id = data.get("image_file_id")
    category = data.get("category", "")
    product_sku = data.get("product_sku", "")

    cat_label = SYSTEM_CATEGORIES.get(category, {}).get("label", category)
    header = f"📋 پیش‌نمایش پست | دسته: {cat_label}"
    if product_sku:
        header += f" | کد: {product_sku}"

    from bale import InputFile
    kb = cms_create_preview_keyboard()

    try:
        if image_file_id:
            await message.reply_photo(
                photo=InputFile(image_file_id),
                caption=f"{header}\n\n{caption}",
                components=kb
            )
        else:
            await message.reply(
                f"{header}\n\n📝 کپشن:\n{caption}",
                components=kb
            )
    except Exception as e:
        logger.error(f"Error showing preview: {e}")
        await message.reply(
            f"{header}\n\n📝 کپشن:\n{caption}\n\n⚠️ نمایش عکس ممکن نبود.",
            components=kb
        )


# ─────────────────────────────────────────
# Preview action callbacks
# ─────────────────────────────────────────

async def callback_cms_create_queue(callback: CallbackQuery):
    """Save post to queue."""
    chat_id = callback.message.chat.id
    state = _cms_create_states.get(chat_id)
    if not state:
        return

    data = state["data"]
    post = await create_content_post(
        category=data["category"],
        caption=data["caption"],
        image_file_id=data.get("image_file_id"),
        product_id=data.get("product_id"),
        status="queued",
    )
    _cms_create_states.pop(chat_id, None)
    await callback.message.edit(
        f"✅ پست با موفقیت به صف اضافه شد. (شماره {post.queue_order})",
        components=cms_menu_keyboard()
    )


async def callback_cms_create_buffer(callback: CallbackQuery):
    """Save post to buffer."""
    chat_id = callback.message.chat.id
    state = _cms_create_states.get(chat_id)
    if not state:
        return

    data = state["data"]
    await create_content_post(
        category=data["category"],
        caption=data["caption"],
        image_file_id=data.get("image_file_id"),
        product_id=data.get("product_id"),
        status="buffered",
    )
    _cms_create_states.pop(chat_id, None)
    await callback.message.edit(
        "✅ پست در بافر ذخیره شد.",
        components=cms_menu_keyboard()
    )


async def callback_cms_create_publish_now(callback: CallbackQuery):
    """Publish post immediately to channel."""
    from app.bot.loader import bot
    chat_id = callback.message.chat.id
    state = _cms_create_states.get(chat_id)
    if not state:
        return

    data = state["data"]
    await callback.message.edit("⏳ در حال انتشار در کانال...")

    # Create post first
    post = await create_content_post(
        category=data["category"],
        caption=data["caption"],
        image_file_id=data.get("image_file_id"),
        product_id=data.get("product_id"),
        status="buffered",
    )

    success = await publish_post_to_channel(bot, post)
    _cms_create_states.pop(chat_id, None)

    if success:
        await callback.message.edit("✅ پست با موفقیت در کانال منتشر شد!", components=cms_menu_keyboard())
    else:
        await callback.message.edit(
            "❌ خطا در انتشار. پست در بافر ذخیره شد.",
            components=cms_menu_keyboard()
        )


async def callback_cms_create_edit_cap(callback: CallbackQuery):
    """Start editing caption."""
    chat_id = callback.message.chat.id
    state = _cms_create_states.get(chat_id)
    if not state:
        return

    state["step"] = "edit_caption"
    _cms_create_states[chat_id] = state
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
    await callback.message.reply("✏️ کپشن جدید را بفرستید:", components=cancel_kb)


async def callback_cms_create_edit_img(callback: CallbackQuery):
    """Start editing image."""
    chat_id = callback.message.chat.id
    state = _cms_create_states.get(chat_id)
    if not state:
        return

    state["step"] = "edit_image"
    _cms_create_states[chat_id] = state
    cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data="menu:cms")]])
    await callback.message.reply("🖼 عکس جدید را بفرستید:", components=cancel_kb)
