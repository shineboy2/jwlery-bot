import logging
from bale import Message, CallbackQuery, InlineKeyboardButton, InputFile
from app.bot.handlers.base import BaseHandler
from app.bot.router import CallbackRouter, MessageRouter
from app.database.repositories import product_repo, cms_repo, config_repo
from app.database.repositories.cms_repo import SYSTEM_CATEGORIES
from app.bot.handlers.cms.keyboards import (
    cms_queue_menu_keyboard, cms_queue_list_keyboard, cms_queue_post_keyboard,
    cms_buffer_menu_keyboard, cms_buffer_list_keyboard, cms_buffer_post_keyboard, build_kb
)
from app.services.cms_service import publish_post_to_channel

logger = logging.getLogger(__name__)

def extract_post_title(caption: str) -> str:
    if not caption:
        return "بدون کپشن"
    lines = caption.strip().split('\n')
    for line in lines:
        if '#' in line and 'کد' in line:
            return line.strip()
    for line in lines:
        if line.strip():
            return line.strip()[:35] + "..." if len(line.strip()) > 35 else line.strip()
    return "بدون کپشن"


class CmsQueueHandler(BaseHandler):
    HANDLER_NAME = "cms_queue"

    def register(self, router: CallbackRouter, message_router: MessageRouter) -> None:
        # Queue Routes
        router.register_exact("cms:queue", self.queue_menu)
        router.register_pattern(r"^cms:queue:cat:([a-zA-Z0-9_]+)$", self.queue_category)
        router.register_pattern(r"^cms:queue:post:(\d+)$", self.queue_post_detail)
        router.register_pattern(r"^cms:queue:top:(\d+)$", self.queue_move_top)
        router.register_pattern(r"^cms:queue:up:(\d+)$", self.queue_move_up)
        router.register_pattern(r"^cms:queue:to_buf:(\d+)$", self.queue_to_buffer)
        router.register_pattern(r"^cms:queue:del:(\d+)$", self.queue_delete)
        router.register_pattern(r"^cms:queue:publish_now:(\d+)$", self.queue_publish_now)
        router.register_pattern(r"^cms:queue:edit_cap:(\d+)$", self.queue_edit_cap)
        router.register_pattern(r"^cms:queue:edit_img:(\d+)$", self.queue_edit_img)

        # Buffer Routes
        router.register_exact("cms:buf", self.buffer_menu)
        router.register_pattern(r"^cms:buf:cat:([a-zA-Z0-9_]+)$", self.buffer_category)
        router.register_pattern(r"^cms:buf:post:(\d+)$", self.buffer_post_detail)
        router.register_pattern(r"^cms:buf:to_queue:(\d+)$", self.buffer_to_queue)
        router.register_pattern(r"^cms:buf:del:(\d+)$", self.buffer_delete)
        router.register_pattern(r"^cms:buf:publish_now:(\d+)$", self.buffer_publish_now)
        router.register_pattern(r"^cms:buf:edit_cap:(\d+)$", self.buffer_edit_cap)
        router.register_pattern(r"^cms:buf:edit_img:(\d+)$", self.buffer_edit_img)

    async def handle_message(self, message: Message) -> bool:
        chat_id = message.chat.id
        state = self.conversations.get_active(chat_id)
        if not state or state.handler_name != self.HANDLER_NAME:
            return False

        step = state.step
        post_id = state.data["post_id"]
        source = state.data["source"]  # 'queue' or 'buf'

        if step == "awaiting_caption_edit":
            caption = (message.content or message.caption or "").strip()
            if not caption:
                await message.reply("⚠️ کپشن نمی‌تواند خالی باشد:")
                return True
            
            async with self.session_factory() as session:
                await cms_repo.update_post_content(session, post_id, caption=caption)
            self.conversations.end(chat_id, self.HANDLER_NAME)
            
            preview_kb = build_kb([[InlineKeyboardButton("📌 نمایش پست", callback_data=f"cms:{source}:post:{post_id}")]])
            await message.reply(f"✅ کپشن پست #{post_id} بروزرسانی شد.", components=preview_kb)
            return True

        if step == "awaiting_image_edit":
            file_id = None
            if getattr(message, 'photo', None):
                file_id = message.photo[-1].file_id if isinstance(message.photo, list) else message.photo.file_id
            
            if not file_id:
                await message.reply("⚠️ لطفاً یک عکس ارسال کنید:")
                return True
                
            async with self.session_factory() as session:
                await cms_repo.update_post_content(session, post_id, image_file_id=file_id)
            self.conversations.end(chat_id, self.HANDLER_NAME)
            
            preview_kb = build_kb([[InlineKeyboardButton("📌 نمایش پست", callback_data=f"cms:{source}:post:{post_id}")]])
            await message.reply(f"✅ عکس پست #{post_id} بروزرسانی شد.", components=preview_kb)
            return True

        return False

    # ─────────────────────────────────────────
    # Queue Handlers
    # ─────────────────────────────────────────
    async def queue_menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        async with ctx.session_factory() as session:
            custom_cats = await config_repo.get_all_content_categories(session)
            counts = {}
            for code in SYSTEM_CATEGORIES:
                counts[code] = await cms_repo.count_queued_by_category(session, code)
            for cat in custom_cats:
                counts[cat.code] = await cms_repo.count_queued_by_category(session, cat.code)

        total = sum(counts.values())
        await callback.message.edit(
            f"📋 **مدیریت صف‌های انتشار**\n\nجمع کل: {total} پست در انتظار",
            components=cms_queue_menu_keyboard(counts, custom_cats)
        )

    async def queue_category(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        cat_code = match.group(1)

        async with ctx.session_factory() as session:
            posts = await cms_repo.get_queue_by_category(session, cat_code)
        cat_info = SYSTEM_CATEGORIES.get(cat_code, {})
        cat_label = cat_info.get("label", cat_code)

        if not posts:
            await callback.message.edit(
                f"📋 صف «{cat_label}» خالی است.\n\nهنوز پستی در این صف نیست.",
                components=build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="cms:queue")]])
            )
            return

        text = f"📋 **صف «{cat_label}»** — {len(posts)} پست\n\n"
        for i, p in enumerate(posts, start=1):
            icon = "🖼" if p.image_file_id else "📝"
            sku_part = " [محصول]" if p.product_id else ""
            preview = extract_post_title(p.content_text)
            text += f"{i}. {icon}{sku_part} {preview}\n"

        await callback.message.edit(text, components=cms_queue_list_keyboard(posts, cat_code))

    async def queue_post_detail(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        post_id = int(match.group(1))

        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
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
        kb = cms_queue_post_keyboard(post_id, post.category, is_first=is_first)
        if post.image_file_id:
            try: await callback.message.delete()
            except: pass
            await callback.message.chat.send_photo(photo=InputFile(post.image_file_id), caption=text, components=kb)
        else:
            await callback.message.edit(text, components=kb)

    async def queue_move_top(self, callback: CallbackQuery, ctx, match) -> None:
        if not await self.require_admin(callback.message.chat.id): return
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            await cms_repo.move_post_to_top(session, post_id)
            post = await cms_repo.get_post_by_id(session, post_id)
        if post: await self.queue_post_detail(callback, ctx, match)

    async def queue_move_up(self, callback: CallbackQuery, ctx, match) -> None:
        if not await self.require_admin(callback.message.chat.id): return
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            await cms_repo.move_post_order_up(session, post_id)
        await self.queue_post_detail(callback, ctx, match)

    async def queue_to_buffer(self, callback: CallbackQuery, ctx, match) -> None:
        if not await self.require_admin(callback.message.chat.id): return
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
            if not post: return
            cat_code = post.category
            await cms_repo.move_post_to_buffer(session, post_id)
        await callback.message.edit(
            "✅ پست به بافر منتقل شد.",
            components=build_kb([[InlineKeyboardButton("🔙 بازگشت به صف", callback_data=f"cms:queue:cat:{cat_code}")]])
        )

    async def queue_delete(self, callback: CallbackQuery, ctx, match) -> None:
        if not await self.require_admin(callback.message.chat.id): return
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
            if not post: return
            cat_code = post.category
            await cms_repo.delete_content_post(session, post_id)
        await callback.message.edit(
            "🗑 پست حذف شد.",
            components=build_kb([[InlineKeyboardButton("🔙 بازگشت به صف", callback_data=f"cms:queue:cat:{cat_code}")]])
        )

    async def queue_publish_now(self, callback: CallbackQuery, ctx, match) -> None:
        if not await self.require_admin(callback.message.chat.id): return
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
            if not post: return
            cat_code = post.category
            await callback.message.edit("⏳ در حال انتشار در کانال...")
            success = await publish_post_to_channel(session, self.bot, post)
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

    async def queue_edit_cap(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        post_id = int(match.group(1))
        
        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_caption_edit", {"post_id": post_id, "source": "queue"})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cms:queue:post:{post_id}")]])
        await callback.message.edit("✏️ کپشن جدید را بفرستید:", components=cancel_kb)

    async def queue_edit_img(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        post_id = int(match.group(1))
        
        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_image_edit", {"post_id": post_id, "source": "queue"})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cms:queue:post:{post_id}")]])
        await callback.message.edit("🖼 عکس جدید را بفرستید:", components=cancel_kb)

    # ─────────────────────────────────────────
    # Buffer Handlers
    # ─────────────────────────────────────────
    async def buffer_menu(self, callback: CallbackQuery, ctx) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return

        async with ctx.session_factory() as session:
            custom_cats = await config_repo.get_all_content_categories(session)
            counts = {}
            for code in SYSTEM_CATEGORIES:
                counts[code] = await cms_repo.count_buffered_by_category(session, code)
            for cat in custom_cats:
                counts[cat.code] = await cms_repo.count_buffered_by_category(session, cat.code)

        total = sum(counts.values())
        await callback.message.edit(
            f"🗂 **مدیریت بافرها**\n\nجمع کل: {total} پست در بافر",
            components=cms_buffer_menu_keyboard(counts, custom_cats)
        )

    async def buffer_category(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        cat_code = match.group(1)

        async with ctx.session_factory() as session:
            posts = await cms_repo.get_buffer_by_category(session, cat_code)
        cat_info = SYSTEM_CATEGORIES.get(cat_code, {})
        cat_label = cat_info.get("label", cat_code)

        if not posts:
            await callback.message.edit(
                f"🗂 بافر «{cat_label}» خالی است.\n\nهنوز پستی در این بافر نیست.",
                components=build_kb([[InlineKeyboardButton("🔙 بازگشت", callback_data="cms:buf")]])
            )
            return

        text = f"🗂 **بافر «{cat_label}»** — {len(posts)} پست\n\n"
        for i, p in enumerate(posts, start=1):
            icon = "🖼" if p.image_file_id else "📝"
            product_tag = " [محصول]" if p.product_id else ""
            preview = extract_post_title(p.content_text)
            text += f"{i}. {icon}{product_tag} {preview}\n"

        await callback.message.edit(text, components=cms_buffer_list_keyboard(posts, cat_code))

    async def buffer_post_detail(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        post_id = int(match.group(1))

        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
        if not post or post.status != "buffered":
            await callback.message.edit("❌ این پست در بافر یافت نشد.")
            return

        cat_label = SYSTEM_CATEGORIES.get(post.category, {}).get("label", post.category)
        icon = "🖼 با عکس" if post.image_file_id else "📝 بدون عکس"
        text = (
            f"📌 **پست #{post.id}** | دسته: {cat_label}\n"
            f"وضعیت: بافر | {icon}\n\n"
            f"📝 کپشن:\n{post.content_text}"
        )
        kb = cms_buffer_post_keyboard(post_id, post.category)
        if post.image_file_id:
            try: await callback.message.delete()
            except: pass
            await callback.message.chat.send_photo(photo=InputFile(post.image_file_id), caption=text, components=kb)
        else:
            await callback.message.edit(text, components=kb)

    async def buffer_to_queue(self, callback: CallbackQuery, ctx, match) -> None:
        if not await self.require_admin(callback.message.chat.id): return
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
            if not post: return
            cat_code = post.category
            result = await cms_repo.move_post_to_queue(session, post_id)
        if result:
            await callback.message.edit(
                f"✅ پست به انتهای صف «{SYSTEM_CATEGORIES.get(cat_code, {}).get('label', cat_code)}» منتقل شد. (ترتیب: {result.queue_order})",
                components=build_kb([[InlineKeyboardButton("🔙 بازگشت به بافر", callback_data=f"cms:buf:cat:{cat_code}")]])
            )
        else:
            await callback.message.edit("❌ خطا در انتقال به صف.")

    async def buffer_delete(self, callback: CallbackQuery, ctx, match) -> None:
        if not await self.require_admin(callback.message.chat.id): return
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
            if not post: return
            cat_code = post.category
            await cms_repo.delete_content_post(session, post_id)
        await callback.message.edit(
            "🗑 پست حذف شد.",
            components=build_kb([[InlineKeyboardButton("🔙 بازگشت به بافر", callback_data=f"cms:buf:cat:{cat_code}")]])
        )

    async def buffer_publish_now(self, callback: CallbackQuery, ctx, match) -> None:
        if not await self.require_admin(callback.message.chat.id): return
        post_id = int(match.group(1))
        async with ctx.session_factory() as session:
            post = await cms_repo.get_post_by_id(session, post_id)
            if not post: return
            cat_code = post.category
            await callback.message.edit("⏳ در حال انتشار در کانال...")
            success = await publish_post_to_channel(session, self.bot, post)
        if success:
            await callback.message.edit(
                "✅ پست با موفقیت در کانال منتشر شد!",
                components=build_kb([[InlineKeyboardButton("🔙 بازگشت به بافر", callback_data=f"cms:buf:cat:{cat_code}")]])
            )
        else:
            await callback.message.edit(
                "❌ خطا در انتشار. پست همچنان در بافر است.",
                components=cms_buffer_post_keyboard(post_id, cat_code)
            )

    async def buffer_edit_cap(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        post_id = int(match.group(1))
        
        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_caption_edit", {"post_id": post_id, "source": "buf"})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cms:buf:post:{post_id}")]])
        await callback.message.edit("✏️ کپشن جدید را بفرستید:", components=cancel_kb)

    async def buffer_edit_img(self, callback: CallbackQuery, ctx, match) -> None:
        chat_id = callback.message.chat.id
        if not await self.require_admin(chat_id): return
        post_id = int(match.group(1))
        
        self.conversations.start(chat_id, self.HANDLER_NAME, "awaiting_image_edit", {"post_id": post_id, "source": "buf"})
        cancel_kb = build_kb([[InlineKeyboardButton("❌ لغو", callback_data=f"cms:buf:post:{post_id}")]])
        await callback.message.edit("🖼 عکس جدید را بفرستید:", components=cancel_kb)
