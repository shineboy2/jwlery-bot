import logging
from bale import CallbackQuery, InlineKeyboardButton
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import product_repo
from app.database.models import ScheduledPost
from app.services.channel_service import publish_to_channel, update_channel_post, remove_channel_post
from app.bot.handlers.product.keyboards import build_kb, product_detail_keyboard
from app.bot.handlers.product.renderers import format_channel_post

logger = logging.getLogger(__name__)

class ProductChannelHandler(BaseHandler):
    HANDLER_NAME = "product_channel"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        router.register_pattern(r"^ch:pub:(\d+)$", self.channel_publish)
        router.register_pattern(r"^ch:pub_direct:(\d+)$", self.channel_publish_direct)
        router.register_pattern(r"^ch:pub_type:(\d+):([A-Z_]+)$", self.channel_publish_type)
        router.register_pattern(r"^ch:update:(\d+)$", self.channel_update)
        router.register_pattern(r"^ch:remove:(\d+)$", self.channel_remove)

    async def channel_publish(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))

        kb = build_kb([
            [InlineKeyboardButton("📢 انتشار مستقیم در کانال", callback_data=f"ch:pub_direct:{product_id}")],
            [InlineKeyboardButton("✨ کالکشن جدید (NEW_ARRIVAL)", callback_data=f"ch:pub_type:{product_id}:NEW_ARRIVAL")],
            [InlineKeyboardButton("🔄 شارژ مجدد (RESTOCK)", callback_data=f"ch:pub_type:{product_id}:RESTOCK")],
            [InlineKeyboardButton("❌ لغو", callback_data=f"prod:view:{product_id}")],
        ])
        async with ctx.session_factory() as session:
            product = await product_repo.get_product_by_id(session, product_id)
        sku = product.sku if product else str(product_id)
        await callback.message.edit(
            f"📦 انتشار محصول [{sku}]\n\n"
            "چه نوع انتشاری می‌خواهید انجام دهید?",
            components=kb
        )

    async def channel_publish_direct(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))

        await callback.message.edit("⏳ در حال انتشار...")
        async with ctx.session_factory() as session:
            message_id = await publish_to_channel(session, self.bot, product_id)
            product = await product_repo.get_product_by_id(session, product_id)
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

    async def channel_publish_type(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))
        pub_type = match.group(2)

        async with ctx.session_factory() as session:
            product = await product_repo.get_product_by_id(session, product_id)
            if not product:
                await callback.message.reply("❌ محصول یافت نشد.")
                return

            images = await product_repo.get_product_images(session, product_id)
        caption = format_channel_post(product, product.category, images)
        images_str = ",".join(img.file_id for img in images) if images else None
        post_type = "MEDIA_GROUP" if images_str and "," in images_str else "IMAGE" if images_str else "TEXT"

        label_map = {"NEW_ARRIVAL": "کالکشن جدید", "RESTOCK": "شارژ مجدد"}
        label = label_map.get(pub_type, pub_type)

        async with ctx.session_factory() as session:
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

    async def channel_update(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))

        async with ctx.session_factory() as session:
            success = await update_channel_post(session, self.bot, product_id)
            product = await product_repo.get_product_by_id(session, product_id)
        result_text = "✅ پست کانال بروزرسانی شد!" if success else "❌ خطا در بروزرسانی پست."

        await callback.message.edit(
            result_text,
            components=product_detail_keyboard(
                product_id,
                is_active=product.status == "ACTIVE" if product else True,
                has_channel_post=product.channel_message_id is not None if product else False
            )
        )

    async def channel_remove(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        product_id = int(match.group(1))

        async with ctx.session_factory() as session:
            success = await remove_channel_post(session, self.bot, product_id)
            product = await product_repo.get_product_by_id(session, product_id)
        result_text = "✅ پست از کانال حذف شد!" if success else "❌ خطا در حذف پست."

        await callback.message.edit(
            result_text,
            components=product_detail_keyboard(
                product_id,
                is_active=product.status == "ACTIVE" if product else True,
                has_channel_post=False
            )
        )
