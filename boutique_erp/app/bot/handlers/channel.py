"""
Channel publishing handlers: publish, update, remove product posts.
"""
import logging

from bale import CallbackQuery

from app.database.crud import get_admin_by_chat_id, get_product_by_id
from app.services.channel_service import publish_to_channel, update_channel_post, remove_channel_post
from app.bot.keyboards.inline import product_detail_keyboard, back_to_main_keyboard, build_kb
from app.bot.loader import bot
from bale import InlineKeyboardButton

logger = logging.getLogger(__name__)


async def callback_channel_publish(callback: CallbackQuery, product_id: int):
    """Ask admin what type of publication this is before publishing."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    kb = build_kb([
        [InlineKeyboardButton("📢 انتشار مستقیم در کانال", callback_data=f"ch:pub_direct:{product_id}")],
        [InlineKeyboardButton("✨ کالکشن جدید (NEW_ARRIVAL)", callback_data=f"ch:pub_type:{product_id}:NEW_ARRIVAL")],
        [InlineKeyboardButton("🔄 شارژ مجدد (RESTOCK)", callback_data=f"ch:pub_type:{product_id}:RESTOCK")],
        [InlineKeyboardButton("❌ لغو", callback_data=f"prod:view:{product_id}")],
    ])
    product = await get_product_by_id(product_id)
    sku = product.sku if product else str(product_id)
    await callback.message.edit(
        f"📦 انتشار محصول [{sku}]\n\n"
        "چه نوع انتشاری می‌خواهید انجام دهید?",
        components=kb
    )


async def callback_channel_publish_direct(callback: CallbackQuery, product_id: int):
    """Publish product directly to channel immediately."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    await callback.message.edit("⏳ در حال انتشار...")

    message_id = await publish_to_channel(bot, product_id)

    product = await get_product_by_id(product_id)
    is_active = product.status == "ACTIVE" if product else True

    if message_id:
        await callback.message.edit(
            "✅ محصول با موفقیت در کانال منتشر شد!",
            components=product_detail_keyboard(product_id, is_active=is_active, has_channel_post=True)
        )
    else:
        back_kb = build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"prod:view:{product_id}")]])
        await callback.message.edit(
            "❌ خطا در انتشار. لطفاً مطمئن شوید ربات در کانال ادمین است.",
            components=back_kb
        )


async def callback_channel_publish_type(callback: CallbackQuery, product_id: int, pub_type: str):
    """Add product to NEW_ARRIVAL or RESTOCK queue."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    product = await get_product_by_id(product_id)
    if not product:
        await callback.message.reply("❌ محصول یافت نشد.")
        return

    from app.database.crud import async_session, get_product_images
    from app.database.models import ScheduledPost
    from app.utils.formatters import format_channel_post

    images = await get_product_images(product_id)
    caption = format_channel_post(product, product.category, images)
    images_str = ",".join(img.file_id for img in images) if images else None
    post_type = "MEDIA_GROUP" if images_str and "," in images_str else "IMAGE" if images_str else "TEXT"

    label_map = {"NEW_ARRIVAL": "کالکشن جدید", "RESTOCK": "شارژ مجدد"}
    label = label_map.get(pub_type, pub_type)

    async with async_session() as session:
        post = ScheduledPost(
            product_id=product_id,
            post_type=post_type,
            category=pub_type,
            content_text=caption,
            file_id=images_str,
            status="QUEUED"
        )
        session.add(post)
        await session.commit()

    is_active = product.status == "ACTIVE"
    has_channel_post = product.channel_message_id is not None
    await callback.message.edit(
        f"✅ محصول [{product.sku}] با موفقیت به صف '{label}' اضافه شد.\n"
        "هنگام رسیدن نوبت طبق زمان‌بندی منتشر خواهد شد.",
        components=product_detail_keyboard(product_id, is_active, has_channel_post)
    )


async def callback_channel_update(callback: CallbackQuery, product_id: int):
    """Update existing channel post."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    success = await update_channel_post(bot, product_id)

    product = await get_product_by_id(product_id)
    result_text = "✅ پست کانال بروزرسانی شد!" if success else "❌ خطا در بروزرسانی پست."

    await callback.message.edit(
        result_text,
        components=product_detail_keyboard(
            product_id,
            is_active=product.status == "ACTIVE" if product else True,
            has_channel_post=product.channel_message_id is not None if product else False
        )
    )


async def callback_channel_remove(callback: CallbackQuery, product_id: int):
    """Remove product from channel."""
    chat_id = callback.message.chat.id
    admin = await get_admin_by_chat_id(chat_id)
    if not admin or not admin.is_active:
        return

    success = await remove_channel_post(bot, product_id)

    product = await get_product_by_id(product_id)
    result_text = "✅ پست از کانال حذف شد!" if success else "❌ خطا در حذف پست."

    await callback.message.edit(
        result_text,
        components=product_detail_keyboard(
            product_id,
            is_active=product.status == "ACTIVE" if product else True,
            has_channel_post=False
        )
    )


